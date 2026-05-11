from __future__ import annotations

import json
import math
import os
import random
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import clip
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import AdamW
from torch.utils.data import DataLoader

from dataset import BenchmarkDataset, CLIPDataset

DEFAULT_SEED = 42
AUTO_HOLDOUT_RATIO = 0.15
MIN_HOLDOUT_POSITIVES = 48
MIN_BENCHMARK_ROWS = 128
MAX_BENCHMARK_NEGATIVES_PER_POSITIVE = 2
MIN_TRAIN_ROWS = 64
MIN_FREE_CUDA_GIB = 2.0


def _format_gib(num_bytes: int) -> str:
    return f"{num_bytes / (1024 ** 3):.2f} GiB"


def _get_cuda_memory_snapshot() -> tuple[int, int] | None:
    if not torch.cuda.is_available():
        return None
    try:
        torch.cuda.empty_cache()
        free_bytes, total_bytes = torch.cuda.mem_get_info()
        return int(free_bytes), int(total_bytes)
    except Exception:
        return None


def _resolve_runtime_device(
    preferred_device: Optional[str],
    allow_cpu_fallback: bool,
    min_free_cuda_gib: float,
) -> str:
    normalized_preference = (preferred_device or "auto").strip().lower()
    requested_device = "cuda" if normalized_preference in {"auto", "cuda", "gpu"} else "cpu"

    if requested_device == "cpu":
        print("Using device: cpu")
        return "cpu"

    if not torch.cuda.is_available():
        if allow_cpu_fallback:
            print("CUDA 不可用，自动回退到 CPU。")
            return "cpu"
        raise RuntimeError("当前环境没有可用 CUDA，但配置中禁止回退到 CPU。")

    snapshot = _get_cuda_memory_snapshot()
    if snapshot is not None:
        free_bytes, total_bytes = snapshot
        print(f"CUDA memory snapshot => free: {_format_gib(free_bytes)} / total: {_format_gib(total_bytes)}")
        minimum_required_bytes = int(min_free_cuda_gib * (1024 ** 3))
        if free_bytes < minimum_required_bytes:
            message = f"当前空闲显存仅 {_format_gib(free_bytes)}，低于安全阈值 {min_free_cuda_gib:.2f} GiB。"
            if allow_cpu_fallback:
                print(f"⚠️ {message} 自动回退到 CPU 训练。")
                return "cpu"
            raise RuntimeError(message)

    print("Using device: cuda")
    return "cuda"


def _load_clip_with_fallback(
    model_name: str,
    device: str,
    allow_cpu_fallback: bool,
) -> tuple[torch.nn.Module, Any, str]:
    try:
        model, preprocess = clip.load(model_name, device=device, jit=False)
        return model, preprocess, device
    except torch.OutOfMemoryError as exc:
        if device != "cuda" or not allow_cpu_fallback:
            raise

        print("⚠️ 加载 CLIP 到 CUDA 时显存不足，自动回退到 CPU。若想继续使用 GPU，请先释放其它进程显存。")
        __import__("gc").collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        model, preprocess = clip.load(model_name, device="cpu", jit=False)
        return model, preprocess, "cpu"


def _set_seed(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _safe_strip(value: Any) -> str:
    return str(value or "").strip()


def _read_jsonl_rows(path: str | Path) -> list[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return []

    rows: list[dict[str, Any]] = []
    with file_path.open("r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _write_jsonl_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def _deduplicate_positive_rows(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    unique_rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in rows:
        image = _safe_strip(item.get("image"))
        text = _safe_strip(item.get("text"))
        if not image or not text:
            continue
        key = (image, text)
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append({"image": image, "text": text})
    return unique_rows


def _load_positive_rows(path: str | Path | None) -> list[dict[str, str]]:
    if path is None:
        return []
    return _deduplicate_positive_rows(_read_jsonl_rows(path))


def _load_benchmark_rows(path: str | Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []

    rows: list[dict[str, Any]] = []
    for item in _read_jsonl_rows(path):
        image = _safe_strip(item.get("image"))
        text = _safe_strip(item.get("text"))
        label = _safe_strip(item.get("label")).lower()
        if not image or not text or label not in {"positive", "negative"}:
            continue
        rows.append(
            {
                "image": image,
                "text": text,
                "label": label,
                "error_type": _safe_strip(item.get("error_type")) or ("无" if label == "positive" else "自动错配"),
                "rationale": _safe_strip(item.get("rationale")),
            }
        )
    return rows


def _build_random_negative_texts(
    positive_text: str,
    text_pool: list[str],
    rng: random.Random,
    limit: int,
    used_texts: set[str],
) -> list[str]:
    candidates = [text for text in text_pool if text and text != positive_text and text not in used_texts]
    rng.shuffle(candidates)
    return candidates[:limit]


def _prepare_data_files(
    jsonl_path: str,
    val_jsonl_path: Optional[str],
    benchmark_jsonl_path: Optional[str],
    save_path_obj: Path,
    seed: int,
) -> tuple[str, Optional[str], Optional[str], dict[str, Any]]:
    train_path_obj = Path(jsonl_path)
    dataset_dir = train_path_obj.parent
    all_jsonl_path = dataset_dir / "all.jsonl"

    source_rows = _load_positive_rows(all_jsonl_path if all_jsonl_path.exists() else train_path_obj)
    if not source_rows:
        source_rows = _deduplicate_positive_rows(
            _read_jsonl_rows(train_path_obj) + _read_jsonl_rows(val_jsonl_path or "")
        )
    if not source_rows:
        raise RuntimeError("无法构建训练集：未找到有效的正样本数据。")

    existing_val_rows = _load_positive_rows(val_jsonl_path)
    existing_benchmark_rows = _load_benchmark_rows(benchmark_jsonl_path)
    benchmark_positive_count = sum(1 for row in existing_benchmark_rows if row["label"] == "positive")
    benchmark_negative_count = sum(1 for row in existing_benchmark_rows if row["label"] == "negative")

    needs_auto_split = (
        len(existing_val_rows) < MIN_HOLDOUT_POSITIVES
        or len(existing_benchmark_rows) < MIN_BENCHMARK_ROWS
        or benchmark_positive_count < MIN_HOLDOUT_POSITIVES
        or benchmark_negative_count < MIN_HOLDOUT_POSITIVES
    )

    if not needs_auto_split:
        return jsonl_path, val_jsonl_path, benchmark_jsonl_path, {
            "used_auto_split": False,
            "train_rows": len(_load_positive_rows(jsonl_path)),
            "val_rows": len(existing_val_rows),
            "benchmark_rows": len(existing_benchmark_rows),
            "benchmark_positive_rows": benchmark_positive_count,
            "benchmark_negative_rows": benchmark_negative_count,
            "source": "original_files",
        }

    if len(source_rows) < MIN_TRAIN_ROWS + MIN_HOLDOUT_POSITIVES:
        raise RuntimeError(
            f"数据总量仅 {len(source_rows)} 条，无法自动切出稳定的 holdout 集。"
        )

    rng = random.Random(seed)
    shuffled_rows = list(source_rows)
    rng.shuffle(shuffled_rows)

    holdout_count = max(MIN_HOLDOUT_POSITIVES, int(len(shuffled_rows) * AUTO_HOLDOUT_RATIO))
    holdout_count = min(holdout_count, len(shuffled_rows) - MIN_TRAIN_ROWS)
    if holdout_count < MIN_HOLDOUT_POSITIVES:
        raise RuntimeError("自动切分 holdout 集失败：可用于训练的样本太少。")

    holdout_rows = shuffled_rows[:holdout_count]
    train_rows = shuffled_rows[holdout_count:]

    explicit_negative_map: dict[str, list[str]] = {}
    for item in existing_benchmark_rows:
        if item["label"] == "negative":
            explicit_negative_map.setdefault(item["image"], []).append(item["text"])

    benchmark_rows: list[dict[str, Any]] = []
    text_pool = [row["text"] for row in shuffled_rows]
    next_id = 1
    for row in holdout_rows:
        benchmark_rows.append(
            {
                "id": next_id,
                "image": row["image"],
                "text": row["text"],
                "label": "positive",
                "error_type": "无",
            }
        )
        next_id += 1

        used_texts = {row["text"]}
        negative_count = 0
        for candidate in explicit_negative_map.get(row["image"], []):
            candidate = _safe_strip(candidate)
            if not candidate or candidate in used_texts:
                continue
            benchmark_rows.append(
                {
                    "id": next_id,
                    "image": row["image"],
                    "text": candidate,
                    "label": "negative",
                    "error_type": "显式负样本",
                    "rationale": "来自已有人工标注的错误描述",
                }
            )
            next_id += 1
            used_texts.add(candidate)
            negative_count += 1
            if negative_count >= MAX_BENCHMARK_NEGATIVES_PER_POSITIVE:
                break

        needed = MAX_BENCHMARK_NEGATIVES_PER_POSITIVE - negative_count
        for candidate in _build_random_negative_texts(
            positive_text=row["text"],
            text_pool=text_pool,
            rng=rng,
            limit=needed,
            used_texts=used_texts,
        ):
            benchmark_rows.append(
                {
                    "id": next_id,
                    "image": row["image"],
                    "text": candidate,
                    "label": "negative",
                    "error_type": "自动错配",
                    "rationale": "自动从其它图片的描述中采样得到的错配文本",
                }
            )
            next_id += 1
            used_texts.add(candidate)

    auto_dir = save_path_obj.parent / "auto_eval"
    auto_train_path = auto_dir / "train.auto.jsonl"
    auto_val_path = auto_dir / "val.auto.jsonl"
    auto_benchmark_path = auto_dir / "benchmark.auto.jsonl"
    _write_jsonl_rows(auto_train_path, train_rows)
    _write_jsonl_rows(auto_val_path, holdout_rows)
    _write_jsonl_rows(auto_benchmark_path, benchmark_rows)

    benchmark_positive_count = sum(1 for row in benchmark_rows if row["label"] == "positive")
    benchmark_negative_count = sum(1 for row in benchmark_rows if row["label"] == "negative")
    return str(auto_train_path), str(auto_val_path), str(auto_benchmark_path), {
        "used_auto_split": True,
        "train_rows": len(train_rows),
        "val_rows": len(holdout_rows),
        "benchmark_rows": len(benchmark_rows),
        "benchmark_positive_rows": benchmark_positive_count,
        "benchmark_negative_rows": benchmark_negative_count,
        "source": str(all_jsonl_path if all_jsonl_path.exists() else train_path_obj),
    }


def _normalize_embeddings(features: torch.Tensor) -> torch.Tensor:
    return features / features.norm(dim=-1, keepdim=True).clamp(min=1e-12)


def _batch_contrastive_loss_and_acc(
    logits_per_image: torch.Tensor,
    logits_per_text: torch.Tensor,
    loss_img: nn.Module,
    loss_txt: nn.Module,
) -> Tuple[torch.Tensor, float, float]:
    batch_size = logits_per_image.shape[0]
    ground_truth = torch.arange(batch_size, dtype=torch.long, device=logits_per_image.device)
    loss = (loss_img(logits_per_image, ground_truth) + loss_txt(logits_per_text, ground_truth)) / 2

    acc_image = (logits_per_image.argmax(dim=-1) == ground_truth).float().mean().item()
    acc_text = (logits_per_text.argmax(dim=-1) == ground_truth).float().mean().item()
    return loss, acc_image, acc_text


def _pairwise_margin_loss(
    model: torch.nn.Module,
    images: torch.Tensor,
    positive_texts: torch.Tensor,
    negative_texts: torch.Tensor,
    margin: float,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    image_features = _normalize_embeddings(model.encode_image(images))
    positive_text_features = _normalize_embeddings(model.encode_text(positive_texts))
    sampled_negative_features = _normalize_embeddings(model.encode_text(negative_texts))

    positive_similarity = (image_features * positive_text_features).sum(dim=-1)
    sampled_negative_similarity = (image_features * sampled_negative_features).sum(dim=-1)

    if images.shape[0] > 1:
        batch_similarity_matrix = image_features @ positive_text_features.T
        mask = torch.eye(images.shape[0], dtype=torch.bool, device=images.device)
        hardest_batch_negative_similarity = batch_similarity_matrix.masked_fill(mask, -1e4).max(dim=-1).values
        strongest_negative_similarity = torch.maximum(sampled_negative_similarity, hardest_batch_negative_similarity)
    else:
        strongest_negative_similarity = sampled_negative_similarity

    target = torch.ones_like(positive_similarity)
    loss = F.margin_ranking_loss(positive_similarity, strongest_negative_similarity, target, margin=margin)
    return loss, positive_similarity, strongest_negative_similarity


def _separation_gap_loss(
    positive_similarity: torch.Tensor,
    negative_similarity: torch.Tensor,
    target_gap: float,
) -> Tuple[torch.Tensor, float]:
    gap = positive_similarity - negative_similarity
    loss = F.relu(target_gap - gap).mean()
    return loss, float(gap.mean().item())


def _extract_resblock_index(name: str, prefix: str) -> int | None:
    if not name.startswith(prefix):
        return None
    remainder = name[len(prefix):]
    block_token = remainder.split(".", 1)[0]
    if not block_token.isdigit():
        return None
    return int(block_token)


def _configure_trainable_parameters(
    model: torch.nn.Module,
    last_text_blocks: int = 1,
    last_visual_blocks: int = 1,
) -> list[str]:
    for parameter in model.parameters():
        parameter.requires_grad = False

    trainable_keywords = (
        "logit_scale",
        "text_projection",
        "ln_final",
        "visual.ln_post",
        "visual.proj",
    )
    text_prefix = "transformer.resblocks."
    visual_prefix = "visual.transformer.resblocks."
    text_block_indices = sorted(
        {
            index
            for name, _ in model.named_parameters()
            if (index := _extract_resblock_index(name, text_prefix)) is not None
        }
    )
    visual_block_indices = sorted(
        {
            index
            for name, _ in model.named_parameters()
            if (index := _extract_resblock_index(name, visual_prefix)) is not None
        }
    )
    text_train_from = (
        max(text_block_indices) - max(last_text_blocks, 0) + 1
        if text_block_indices and last_text_blocks > 0
        else None
    )
    visual_train_from = (
        max(visual_block_indices) - max(last_visual_blocks, 0) + 1
        if visual_block_indices and last_visual_blocks > 0
        else None
    )

    trainable_names: list[str] = []
    for name, parameter in model.named_parameters():
        should_train = any(keyword in name for keyword in trainable_keywords)

        text_block_index = _extract_resblock_index(name, text_prefix)
        if text_train_from is not None and text_block_index is not None and text_block_index >= text_train_from:
            should_train = True

        visual_block_index = _extract_resblock_index(name, visual_prefix)
        if visual_train_from is not None and visual_block_index is not None and visual_block_index >= visual_train_from:
            should_train = True

        if should_train:
            parameter.requires_grad = True
            trainable_names.append(name)

    if not trainable_names:
        raise RuntimeError("未找到可训练参数，请检查当前 CLIP 模型结构。")
    return trainable_names


def _iter_trainable_parameters(model: torch.nn.Module) -> Iterable[torch.nn.Parameter]:
    for parameter in model.parameters():
        if parameter.requires_grad:
            yield parameter


@torch.no_grad()
def evaluate(
    model: torch.nn.Module,
    dataloader: DataLoader,
    device: str,
    loss_img: nn.Module,
    loss_txt: nn.Module,
    contrastive_weight: float,
    margin_weight: float,
    margin: float,
    separation_weight: float,
    separation_target_gap: float,
) -> Dict[str, float]:
    model.eval()
    total_loss = 0.0
    total_contrastive_loss = 0.0
    total_margin_loss = 0.0
    total_separation_loss = 0.0
    total_acc_image = 0.0
    total_acc_text = 0.0
    total_positive_similarity = 0.0
    total_negative_similarity = 0.0
    total_gap = 0.0
    total_samples = 0

    for images, positive_texts, negative_texts in dataloader:
        images = images.to(device)
        positive_texts = positive_texts.to(device)
        negative_texts = negative_texts.to(device)

        logits_per_image, logits_per_text = model(images, positive_texts)
        contrastive_loss, acc_image, acc_text = _batch_contrastive_loss_and_acc(
            logits_per_image=logits_per_image,
            logits_per_text=logits_per_text,
            loss_img=loss_img,
            loss_txt=loss_txt,
        )
        margin_loss, positive_similarity_vec, negative_similarity_vec = _pairwise_margin_loss(
            model=model,
            images=images,
            positive_texts=positive_texts,
            negative_texts=negative_texts,
            margin=margin,
        )
        separation_loss, gap_value = _separation_gap_loss(
            positive_similarity=positive_similarity_vec,
            negative_similarity=negative_similarity_vec,
            target_gap=separation_target_gap,
        )
        total_batch_loss = (
            contrastive_weight * contrastive_loss
            + margin_weight * margin_loss
            + separation_weight * separation_loss
        )

        positive_similarity = float(positive_similarity_vec.mean().item())
        negative_similarity = float(negative_similarity_vec.mean().item())

        batch_size = images.shape[0]
        total_samples += batch_size
        total_loss += float(total_batch_loss.item()) * batch_size
        total_contrastive_loss += float(contrastive_loss.item()) * batch_size
        total_margin_loss += float(margin_loss.item()) * batch_size
        total_separation_loss += float(separation_loss.item()) * batch_size
        total_acc_image += acc_image * batch_size
        total_acc_text += acc_text * batch_size
        total_positive_similarity += positive_similarity * batch_size
        total_negative_similarity += negative_similarity * batch_size
        total_gap += gap_value * batch_size

    if total_samples == 0:
        raise RuntimeError("验证集为空或无法加载，无法计算评估指标。")

    return {
        "loss": total_loss / total_samples,
        "contrastive_loss": total_contrastive_loss / total_samples,
        "margin_loss": total_margin_loss / total_samples,
        "separation_loss": total_separation_loss / total_samples,
        "acc_image": total_acc_image / total_samples,
        "acc_text": total_acc_text / total_samples,
        "positive_similarity": total_positive_similarity / total_samples,
        "negative_similarity": total_negative_similarity / total_samples,
        "gap": total_gap / total_samples,
    }


def _find_best_threshold(similarities: list[float], labels: list[int]) -> Tuple[float, float, float, float]:
    unique_scores = sorted(set(similarities))
    if not unique_scores:
        raise RuntimeError("无法从空的 similarity 列表中寻找阈值。")

    positive_total = sum(1 for label in labels if label == 1)
    negative_total = len(labels) - positive_total
    if positive_total == 0 or negative_total == 0:
        raise RuntimeError("benchmark 中必须同时包含 positive 和 negative 样本。")

    candidate_thresholds = [unique_scores[0] - 1e-6]
    candidate_thresholds.extend((left + right) / 2.0 for left, right in zip(unique_scores, unique_scores[1:]))
    candidate_thresholds.append(unique_scores[-1] + 1e-6)

    best_threshold = candidate_thresholds[0]
    best_balanced_accuracy = -1.0
    best_positive_accuracy = 0.0
    best_negative_accuracy = 0.0

    for threshold in candidate_thresholds:
        true_positive = 0
        true_negative = 0
        for similarity, label in zip(similarities, labels):
            prediction = 1 if similarity >= threshold else 0
            if label == 1 and prediction == 1:
                true_positive += 1
            elif label == 0 and prediction == 0:
                true_negative += 1

        positive_accuracy = true_positive / positive_total
        negative_accuracy = true_negative / negative_total
        balanced_accuracy = (positive_accuracy + negative_accuracy) / 2.0
        if balanced_accuracy > best_balanced_accuracy or (
            abs(balanced_accuracy - best_balanced_accuracy) < 1e-12 and threshold > best_threshold
        ):
            best_threshold = threshold
            best_balanced_accuracy = balanced_accuracy
            best_positive_accuracy = positive_accuracy
            best_negative_accuracy = negative_accuracy

    return (
        float(best_threshold),
        float(best_balanced_accuracy),
        float(best_positive_accuracy),
        float(best_negative_accuracy),
    )


@torch.no_grad()
def evaluate_benchmark(
    model: torch.nn.Module,
    dataloader: DataLoader,
    device: str,
) -> Dict[str, float]:
    model.eval()
    similarities: list[float] = []
    labels: list[int] = []

    for images, texts, batch_labels in dataloader:
        images = images.to(device)
        texts = texts.to(device)

        image_features = _normalize_embeddings(model.encode_image(images))
        text_features = _normalize_embeddings(model.encode_text(texts))
        batch_similarities = (image_features * text_features).sum(dim=-1)

        similarities.extend([float(value) for value in batch_similarities.detach().cpu().tolist()])
        labels.extend([int(value) for value in batch_labels.detach().cpu().tolist()])

    positive_similarities = [similarity for similarity, label in zip(similarities, labels) if label == 1]
    negative_similarities = [similarity for similarity, label in zip(similarities, labels) if label == 0]
    if not positive_similarities or not negative_similarities:
        raise RuntimeError("benchmark 中必须同时包含 positive 和 negative 样本。")

    threshold, balanced_accuracy, positive_accuracy, negative_accuracy = _find_best_threshold(similarities, labels)
    total_accuracy = sum(
        1 for similarity, label in zip(similarities, labels) if (1 if similarity >= threshold else 0) == label
    ) / len(labels)
    positive_mean = sum(positive_similarities) / len(positive_similarities)
    negative_mean = sum(negative_similarities) / len(negative_similarities)

    return {
        "accuracy": total_accuracy,
        "balanced_accuracy": balanced_accuracy,
        "positive_accuracy": positive_accuracy,
        "negative_accuracy": negative_accuracy,
        "threshold": threshold,
        "positive_mean": positive_mean,
        "negative_mean": negative_mean,
        "gap": positive_mean - negative_mean,
        "positive_min": min(positive_similarities),
        "positive_max": max(positive_similarities),
        "negative_min": min(negative_similarities),
        "negative_max": max(negative_similarities),
        "separation_margin": min(positive_similarities) - max(negative_similarities),
    }


def _save_calibration_file(
    calibration_path: Path,
    model_name: str,
    benchmark_metrics: Dict[str, float],
) -> None:
    decision_threshold = float(benchmark_metrics["threshold"])
    min_similarity = min(float(benchmark_metrics["negative_min"]), decision_threshold)
    max_similarity = max(float(benchmark_metrics["positive_max"]), decision_threshold)

    if max_similarity - min_similarity < 1e-4:
        min_similarity = decision_threshold - 0.05
        max_similarity = decision_threshold + 0.05

    payload = {
        "version": 2,
        "model_name": model_name,
        "decision_threshold": decision_threshold,
        "min_similarity": min_similarity,
        "max_similarity": max_similarity,
        "positive_similarity_mean": float(benchmark_metrics["positive_mean"]),
        "negative_similarity_mean": float(benchmark_metrics["negative_mean"]),
        "positive_similarity_min": float(benchmark_metrics["positive_min"]),
        "positive_similarity_max": float(benchmark_metrics["positive_max"]),
        "negative_similarity_min": float(benchmark_metrics["negative_min"]),
        "negative_similarity_max": float(benchmark_metrics["negative_max"]),
        "benchmark_accuracy": float(benchmark_metrics["accuracy"]),
        "benchmark_balanced_accuracy": float(benchmark_metrics["balanced_accuracy"]),
        "benchmark_gap": float(benchmark_metrics["gap"]),
        "benchmark_separation_margin": float(benchmark_metrics["separation_margin"]),
    }
    calibration_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def train(
    jsonl_path: str = "dataset/train.jsonl",
    val_jsonl_path: Optional[str] = "dataset/val.jsonl",
    benchmark_jsonl_path: Optional[str] = "dataset/benchmark.jsonl",
    img_dir: str = "dataset",
    model_name: str = "ViT-B/32",
    batch_size: int = 8,
    lr: float = 5e-6,
    epochs: int = 8,
    save_path: str = "checkpoints/clip_finetuned.pt",
    num_workers: int = 0,
    margin: float = 0.12,
    contrastive_weight: float = 0.65,
    margin_weight: float = 0.25,
    separation_weight: float = 0.10,
    separation_target_gap: float = 0.03,
    freeze_backbone: bool = True,
    early_stop_patience: int = 3,
    seed: int = DEFAULT_SEED,
    unfreeze_text_blocks: int = 1,
    unfreeze_vision_blocks: int = 1,
    preferred_device: Optional[str] = None,
    allow_cpu_fallback: bool = True,
    min_free_cuda_gib: float = MIN_FREE_CUDA_GIB,
    grad_accum_steps: int = 1,
    use_amp: bool = True,
) -> None:
    """
    更稳健的 CLIP 微调流程。

    关键改动：
    - 当原始 val / benchmark 太小，会自动从 `all.jsonl` 切出更大的 holdout 集；
    - 默认只解冻最后的 text / vision block 与投影归一化层，兼顾收敛能力和稳定性；
    - margin loss 同时对抗显式负样本和 batch 内最难负样本；
    - 使用 benchmark 的 balanced accuracy / separation margin 选最佳 checkpoint，并提前停止。
    """
    _set_seed(seed)
    grad_accum_steps = max(1, int(grad_accum_steps))
    device = _resolve_runtime_device(
        preferred_device=preferred_device,
        allow_cpu_fallback=allow_cpu_fallback,
        min_free_cuda_gib=min_free_cuda_gib,
    )

    save_path_obj = Path(save_path)
    save_path_obj.parent.mkdir(parents=True, exist_ok=True)
    calibration_path = save_path_obj.with_suffix(".calibration.json")

    jsonl_path, val_jsonl_path, benchmark_jsonl_path, data_summary = _prepare_data_files(
        jsonl_path=jsonl_path,
        val_jsonl_path=val_jsonl_path,
        benchmark_jsonl_path=benchmark_jsonl_path,
        save_path_obj=save_path_obj,
        seed=seed,
    )
    print(
        "数据划分 => "
        f"train: {data_summary['train_rows']}, val: {data_summary['val_rows']}, "
        f"benchmark: {data_summary['benchmark_rows']} "
        f"(pos: {data_summary['benchmark_positive_rows']}, neg: {data_summary['benchmark_negative_rows']}), "
        f"auto_split: {data_summary['used_auto_split']}"
    )

    model, preprocess, device = _load_clip_with_fallback(
        model_name=model_name,
        device=device,
        allow_cpu_fallback=allow_cpu_fallback,
    )
    amp_enabled = bool(device == "cuda" and use_amp)
    scaler = (
        torch.amp.GradScaler("cuda", enabled=amp_enabled)
        if hasattr(torch, "amp") and hasattr(torch.amp, "GradScaler")
        else torch.cuda.amp.GradScaler(enabled=amp_enabled)
    )
    pin_memory = device == "cuda"
    print(
        f"训练配置 => batch_size: {batch_size}, grad_accum_steps: {grad_accum_steps}, "
        f"effective_batch_size: {batch_size * grad_accum_steps}, lr: {lr:.2e}, amp: {amp_enabled}, device: {device}, "
        f"unfreeze_text_blocks: {unfreeze_text_blocks}, unfreeze_vision_blocks: {unfreeze_vision_blocks}, "
        f"margin: {margin:.3f}, weights(c/m/s): {contrastive_weight:.2f}/{margin_weight:.2f}/{separation_weight:.2f}, "
        f"target_gap: {separation_target_gap:.3f}"
    )

    if freeze_backbone:
        trainable_names = _configure_trainable_parameters(
            model,
            last_text_blocks=unfreeze_text_blocks,
            last_visual_blocks=unfreeze_vision_blocks,
        )
        trainable_params = list(_iter_trainable_parameters(model))
        trainable_count = sum(parameter.numel() for parameter in trainable_params)
        print(
            "冻结大部分骨干，"
            f"仅训练 {len(trainable_names)} 个参数张量，合计 {trainable_count} 个参数；"
            f"解冻 text 后 {unfreeze_text_blocks} 层、vision 后 {unfreeze_vision_blocks} 层。"
        )
    else:
        for parameter in model.parameters():
            parameter.requires_grad = True
        trainable_params = list(model.parameters())
        print("警告: 当前启用了全参数微调，更容易在小数据集上导致分数整体漂移。")

    train_dataset = CLIPDataset(
        jsonl_path=jsonl_path,
        img_dir=img_dir,
        preprocess=preprocess,
        benchmark_jsonl_path=benchmark_jsonl_path,
    )
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=pin_memory,
    )

    if val_jsonl_path is None or not os.path.exists(val_jsonl_path):
        raise RuntimeError("当前训练流程要求存在有效 val 集，用于抑制小样本过拟合。")
    val_dataset = CLIPDataset(
        jsonl_path=val_jsonl_path,
        img_dir=img_dir,
        preprocess=preprocess,
        benchmark_jsonl_path=benchmark_jsonl_path,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=pin_memory,
    )

    if benchmark_jsonl_path is None or not os.path.exists(benchmark_jsonl_path):
        raise RuntimeError("当前训练流程要求存在有效 benchmark 集，用于选优和分数校准。")
    benchmark_dataset = BenchmarkDataset(benchmark_jsonl_path, img_dir, preprocess)
    benchmark_loader = DataLoader(
        benchmark_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=pin_memory,
    )

    optimizer = AdamW(trainable_params, lr=lr, betas=(0.9, 0.98), eps=1e-6, weight_decay=0.1)
    loss_img = nn.CrossEntropyLoss()
    loss_txt = nn.CrossEntropyLoss()

    best_rank_key: Tuple[float, float, float, float] | None = None
    best_epoch = 0
    epochs_without_improvement = 0

    optimizer.zero_grad(set_to_none=True)
    model.train()
    for epoch in range(epochs):
        total_loss = 0.0
        total_contrastive_loss = 0.0
        total_margin_loss = 0.0
        total_acc_image = 0.0
        total_acc_text = 0.0
        total_positive_similarity = 0.0
        total_negative_similarity = 0.0
        total_gap = 0.0
        total_separation_loss = 0.0
        total_samples = 0

        for step, (images, positive_texts, negative_texts) in enumerate(train_loader, start=1):
            try:
                images = images.to(device, non_blocking=pin_memory)
                positive_texts = positive_texts.to(device, non_blocking=pin_memory)
                negative_texts = negative_texts.to(device, non_blocking=pin_memory)

                autocast_context = (
                    torch.autocast(device_type="cuda", dtype=torch.float16)
                    if amp_enabled
                    else nullcontext()
                )
                with autocast_context:
                    logits_per_image, logits_per_text = model(images, positive_texts)
                    contrastive_loss, acc_image, acc_text = _batch_contrastive_loss_and_acc(
                        logits_per_image=logits_per_image,
                        logits_per_text=logits_per_text,
                        loss_img=loss_img,
                        loss_txt=loss_txt,
                    )
                    margin_loss, positive_similarity_vec, negative_similarity_vec = _pairwise_margin_loss(
                        model=model,
                        images=images,
                        positive_texts=positive_texts,
                        negative_texts=negative_texts,
                        margin=margin,
                    )
                    separation_loss, gap_value = _separation_gap_loss(
                        positive_similarity=positive_similarity_vec,
                        negative_similarity=negative_similarity_vec,
                        target_gap=separation_target_gap,
                    )
                    loss = (
                        contrastive_weight * contrastive_loss
                        + margin_weight * margin_loss
                        + separation_weight * separation_loss
                    )

                positive_similarity = float(positive_similarity_vec.mean().item())
                negative_similarity = float(negative_similarity_vec.mean().item())

                scaled_loss = loss / grad_accum_steps
                if amp_enabled:
                    scaler.scale(scaled_loss).backward()
                else:
                    scaled_loss.backward()

                should_step = step % grad_accum_steps == 0 or step == len(train_loader)
                if should_step:
                    if amp_enabled:
                        scaler.unscale_(optimizer)
                    torch.nn.utils.clip_grad_norm_(trainable_params, max_norm=1.0)
                    if amp_enabled:
                        scaler.step(optimizer)
                        scaler.update()
                    else:
                        optimizer.step()
                    optimizer.zero_grad(set_to_none=True)
                    with torch.no_grad():
                        if hasattr(model, "logit_scale"):
                            model.logit_scale.clamp_(0, math.log(100.0))
            except torch.OutOfMemoryError as exc:
                if device == "cuda":
                    optimizer.zero_grad(set_to_none=True)
                    torch.cuda.empty_cache()
                    raise RuntimeError(
                        f"训练阶段 CUDA 显存不足。请先释放其它 GPU 进程，或把 batch_size 从 {batch_size} 继续调小，例如 4。"
                    ) from exc
                raise

            batch_size_actual = images.shape[0]
            total_samples += batch_size_actual
            total_loss += float(loss.item()) * batch_size_actual
            total_contrastive_loss += float(contrastive_loss.item()) * batch_size_actual
            total_margin_loss += float(margin_loss.item()) * batch_size_actual
            total_acc_image += acc_image * batch_size_actual
            total_acc_text += acc_text * batch_size_actual
            total_positive_similarity += positive_similarity * batch_size_actual
            total_negative_similarity += negative_similarity * batch_size_actual
            total_gap += gap_value * batch_size_actual
            total_separation_loss += float(separation_loss.item()) * batch_size_actual

            if step % 10 == 0:
                print(
                    f"Epoch [{epoch + 1}/{epochs}], Step [{step}/{len(train_loader)}], "
                    f"Loss: {loss.item():.4f}, PosSim: {positive_similarity:.4f}, NegSim: {negative_similarity:.4f}"
                )

        if total_samples == 0:
            raise RuntimeError("训练集为空或无法加载，无法继续训练。")

        train_metrics = {
            "loss": total_loss / total_samples,
            "contrastive_loss": total_contrastive_loss / total_samples,
            "margin_loss": total_margin_loss / total_samples,
            "separation_loss": total_separation_loss / total_samples,
            "acc_image": total_acc_image / total_samples,
            "acc_text": total_acc_text / total_samples,
            "positive_similarity": total_positive_similarity / total_samples,
            "negative_similarity": total_negative_similarity / total_samples,
            "gap": total_gap / total_samples,
        }
        print(
            f"Epoch [{epoch + 1}/{epochs}] Train => "
            f"Loss: {train_metrics['loss']:.4f}, Contrastive: {train_metrics['contrastive_loss']:.4f}, "
            f"Margin: {train_metrics['margin_loss']:.4f}, SepLoss: {train_metrics['separation_loss']:.4f}, "
            f"Acc(image->text): {train_metrics['acc_image']:.4f}, Acc(text->image): {train_metrics['acc_text']:.4f}, "
            f"PosSim: {train_metrics['positive_similarity']:.4f}, NegSim: {train_metrics['negative_similarity']:.4f}, "
            f"Gap: {train_metrics['gap']:.4f}"
        )

        val_metrics = evaluate(
            model=model,
            dataloader=val_loader,
            device=device,
            loss_img=loss_img,
            loss_txt=loss_txt,
            contrastive_weight=contrastive_weight,
            margin_weight=margin_weight,
            margin=margin,
            separation_weight=separation_weight,
            separation_target_gap=separation_target_gap,
        )
        print(
            f"Epoch [{epoch + 1}/{epochs}] Val => "
            f"Loss: {val_metrics['loss']:.4f}, Contrastive: {val_metrics['contrastive_loss']:.4f}, "
            f"Margin: {val_metrics['margin_loss']:.4f}, SepLoss: {val_metrics['separation_loss']:.4f}, "
            f"PosSim: {val_metrics['positive_similarity']:.4f}, NegSim: {val_metrics['negative_similarity']:.4f}, "
            f"Gap: {val_metrics['gap']:.4f}"
        )
        model.train()

        benchmark_metrics = evaluate_benchmark(model=model, dataloader=benchmark_loader, device=device)
        print(
            f"Epoch [{epoch + 1}/{epochs}] Benchmark => "
            f"Acc: {benchmark_metrics['accuracy']:.4f}, BalancedAcc: {benchmark_metrics['balanced_accuracy']:.4f}, "
            f"PosAcc: {benchmark_metrics['positive_accuracy']:.4f}, NegAcc: {benchmark_metrics['negative_accuracy']:.4f}, "
            f"Threshold: {benchmark_metrics['threshold']:.4f}, Gap: {benchmark_metrics['gap']:.4f}, "
            f"SepMargin: {benchmark_metrics['separation_margin']:.4f}"
        )
        model.train()

        current_rank_key = (
            float(benchmark_metrics["balanced_accuracy"]),
            float(benchmark_metrics["separation_margin"]),
            float(benchmark_metrics["gap"]),
            -float(val_metrics["loss"]),
        )

        if best_rank_key is None or current_rank_key > best_rank_key:
            best_rank_key = current_rank_key
            best_epoch = epoch + 1
            epochs_without_improvement = 0
            torch.save(model.state_dict(), save_path_obj)
            _save_calibration_file(calibration_path, model_name=model_name, benchmark_metrics=benchmark_metrics)
            print(f"✅ 已更新最佳模型，保存到: {save_path_obj}")
        else:
            epochs_without_improvement += 1
            print(f"⏸️ 本轮未超过最佳模型，连续未提升轮数: {epochs_without_improvement}")

        if early_stop_patience > 0 and epochs_without_improvement >= early_stop_patience:
            print(f"🛑 提前停止训练：连续 {epochs_without_improvement} 轮 benchmark 未提升。")
            break

    print(f"训练完成。最佳 epoch: {best_epoch}")
    if calibration_path.exists():
        print(f"校准文件已保存至: {calibration_path}")


if __name__ == "__main__":
    import sys

    # 简单的命令行参数支持
    # 例如: python train.py cpu
    device_arg = sys.argv[1] if len(sys.argv) > 1 else None

    try:
        train(preferred_device=device_arg)
    except Exception as exc:
        print(f"训练过程中发生致命错误: {exc}")
        import traceback

        traceback.print_exc()

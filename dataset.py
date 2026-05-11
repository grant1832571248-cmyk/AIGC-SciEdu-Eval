from __future__ import annotations

import json
import os
import random
from typing import Any, Dict, List, Tuple

import clip
import torch
from PIL import Image
from torch.utils.data import Dataset


def _safe_strip(value: Any) -> str:
    return str(value or "").strip()


def _read_jsonl(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"标注文件未找到: {path}")

    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as file:
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


class CLIPDataset(Dataset):
    """
    CLIP 微调数据集。

    相比旧版本，除了返回正样本文本，还会为每张图片动态提供一个负样本文本：
    - 优先使用 `benchmark.jsonl` 中同图像的显式负样本；
    - 若没有，则优先从词面更接近的文本里采样“半难负样本”；
    - 再退回到全局随机错配，避免训练一直看到过于简单的负例。
    """

    def __init__(
        self,
        jsonl_path: str,
        img_dir: str,
        preprocess: Any,
        benchmark_jsonl_path: str | None = None,
    ) -> None:
        self.img_dir = img_dir
        self.preprocess = preprocess
        self._fallback_image_tensor = self.preprocess(Image.new("RGB", (224, 224)))
        self._negative_texts_by_image = self._load_negative_texts_by_image(benchmark_jsonl_path)
        self.data = self._load_positive_records(jsonl_path)
        self._text_pool = [item["text"] for item in self.data]
        self._hard_negative_indices = self._build_hard_negative_indices(top_k=8)

        if len(self._text_pool) < 2:
            raise RuntimeError("训练数据至少需要两条不同文本，才能构造负样本。")

    def _load_negative_texts_by_image(self, path: str | None) -> Dict[str, List[str]]:
        if not path or not os.path.exists(path):
            return {}

        negative_map: Dict[str, List[str]] = {}
        for item in _read_jsonl(path):
            label = _safe_strip(item.get("label")).lower()
            image = _safe_strip(item.get("image"))
            text = _safe_strip(item.get("text"))
            if label != "negative" or not image or not text:
                continue
            negative_map.setdefault(image, []).append(text)
        return negative_map

    def _load_positive_records(self, path: str) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for item in _read_jsonl(path):
            image = _safe_strip(item.get("image"))
            text = _safe_strip(item.get("text"))
            if not image or not text:
                continue
            negative_candidates = [
                candidate
                for candidate in self._negative_texts_by_image.get(image, [])
                if _safe_strip(candidate) and _safe_strip(candidate) != text
            ]
            rows.append(
                {
                    "image": image,
                    "text": text,
                    "negative_candidates": negative_candidates,
                }
            )

        if not rows:
            raise RuntimeError(f"未从 {path} 读取到有效训练样本。")
        return rows

    def _build_hard_negative_indices(self, top_k: int) -> List[List[int]]:
        def text_signature(text: str) -> set[str]:
            return {char for char in text if not char.isspace()}

        signatures = [text_signature(text) for text in self._text_pool]
        hard_pools: List[List[int]] = []
        for idx, positive_text in enumerate(self._text_pool):
            current_signature = signatures[idx]
            scored: List[Tuple[float, int]] = []
            for candidate_idx, candidate_text in enumerate(self._text_pool):
                if candidate_idx == idx or candidate_text == positive_text:
                    continue
                candidate_signature = signatures[candidate_idx]
                if not current_signature or not candidate_signature:
                    continue
                overlap = len(current_signature & candidate_signature)
                if overlap == 0:
                    continue
                union = len(current_signature | candidate_signature)
                score = overlap / max(union, 1)
                scored.append((score, candidate_idx))
            scored.sort(key=lambda item: item[0], reverse=True)
            hard_pools.append([candidate_idx for _, candidate_idx in scored[:top_k]])
        return hard_pools

    def __len__(self) -> int:
        return len(self.data)

    def _load_image(self, image_rel_path: str) -> torch.Tensor:
        image_path = os.path.join(self.img_dir, image_rel_path)
        try:
            image = Image.open(image_path).convert("RGB")
            return self.preprocess(image)
        except Exception as exc:
            print(f"警告: 无法读取图片 {image_path}, 错误: {exc}")
            return self._fallback_image_tensor.clone()

    def _sample_negative_text(self, idx: int) -> str:
        item = self.data[idx]
        positive_text = item["text"]
        negative_candidates: List[str] = item["negative_candidates"]

        if negative_candidates:
            return random.choice(negative_candidates)

        hard_pool = self._hard_negative_indices[idx]
        if hard_pool:
            chosen_idx = random.choice(hard_pool)
            candidate = self._text_pool[chosen_idx]
            if candidate != positive_text:
                return candidate

        pool_size = len(self._text_pool)
        start = random.randrange(pool_size)
        for offset in range(pool_size):
            candidate = self._text_pool[(start + offset) % pool_size]
            if candidate != positive_text:
                return candidate

        return positive_text

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        item = self.data[idx]
        image_tensor = self._load_image(item["image"])
        positive_tokens = clip.tokenize([item["text"]], truncate=True).squeeze(0)
        negative_tokens = clip.tokenize([self._sample_negative_text(idx)], truncate=True).squeeze(0)
        return image_tensor, positive_tokens, negative_tokens


class BenchmarkDataset(Dataset):
    """用于评估图文匹配分离效果的基准集。"""

    def __init__(self, jsonl_path: str, img_dir: str, preprocess: Any) -> None:
        self.img_dir = img_dir
        self.preprocess = preprocess
        self._fallback_image_tensor = self.preprocess(Image.new("RGB", (224, 224)))
        self.data = self._load_records(jsonl_path)

    def _load_records(self, path: str) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for item in _read_jsonl(path):
            image = _safe_strip(item.get("image"))
            text = _safe_strip(item.get("text"))
            label = _safe_strip(item.get("label")).lower()
            if not image or not text or label not in {"positive", "negative"}:
                continue
            rows.append({"image": image, "text": text, "label": 1 if label == "positive" else 0})

        if not rows:
            raise RuntimeError(f"未从 {path} 读取到有效 benchmark 样本。")
        return rows

    def __len__(self) -> int:
        return len(self.data)

    def _load_image(self, image_rel_path: str) -> torch.Tensor:
        image_path = os.path.join(self.img_dir, image_rel_path)
        try:
            image = Image.open(image_path).convert("RGB")
            return self.preprocess(image)
        except Exception as exc:
            print(f"警告: 无法读取 benchmark 图片 {image_path}, 错误: {exc}")
            return self._fallback_image_tensor.clone()

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        item = self.data[idx]
        image_tensor = self._load_image(item["image"])
        text_tokens = clip.tokenize([item["text"]], truncate=True).squeeze(0)
        label_tensor = torch.tensor(item["label"], dtype=torch.long)
        return image_tensor, text_tokens, label_tensor

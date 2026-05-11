from __future__ import annotations

"""
用法说明:
前提：需要有一个有图片的文件夹，文件夹中图片的命名是对图片的描述
1) 默认导入（只写入 train，不写入 val）:
python add_dataset_from_folder.py --input-dir "D:/new_images"

2) 规则 C: 按比例拆分到 train / val（例如 10% 写入 val）:
python add_dataset_from_folder.py --input-dir "D:/new_images" --split-mode split --val-ratio 0.1 --seed 42

3) 全部写入 val（不写入 train）:
python add_dataset_from_folder.py --input-dir "D:/new_images" --split-mode val_only

4) 递归扫描子目录:
python add_dataset_from_folder.py --input-dir "D:/new_images" --recursive

5) 仅预览，不真正写文件(只统计“预计新增/跳过多少”，不会复制图片，也不会改):
python add_dataset_from_folder.py --input-dir "D:/new_images" --dry-run

6) 导入后移动源文件（默认是复制）:
python add_dataset_from_folder.py --input-dir "D:/new_images" --move

说明:
- 图片会复制/移动到 dataset/images，并自动命名为 6 位递增编号（如 000417.png）。
- 文件名（不含后缀）会作为 text 写入。
- 会增量写入 mapping/all/train/val（由 split-mode 决定 train 与 val 的去向）。
- 按 source_name 去重，重复导入会跳过（或通过 --on-conflict error 改为报错）。
"""

import argparse
import csv
import json
import random
import re
import shutil
from pathlib import Path
from typing import Any


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
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


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return [dict(item) for item in reader if item]


def write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def collect_images(input_dir: Path, recursive: bool) -> list[Path]:
    pattern = "**/*" if recursive else "*"
    files = [p for p in input_dir.glob(pattern) if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES]
    return sorted(files, key=lambda p: p.name.lower())


def get_max_mapping_id(mapping_rows: list[dict[str, Any]]) -> int:
    max_id = 0
    for row in mapping_rows:
        try:
            current_id = int(str(row.get("id", "")).strip())
        except ValueError:
            continue
        if current_id > max_id:
            max_id = current_id
    return max_id


def get_next_image_index(images_dir: Path) -> int:
    max_index = 0
    for file in images_dir.iterdir():
        if not file.is_file():
            continue
        match = re.fullmatch(r"(\d+)\.[^.]+", file.name)
        if not match:
            continue
        value = int(match.group(1))
        if value > max_index:
            max_index = value
    return max_index + 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="把“文件名即描述”的图片目录增量追加到 dataset。",
    )
    parser.add_argument("--input-dir", required=True, help="待导入图片目录")
    parser.add_argument("--dataset-dir", default="dataset", help="数据目录（默认: dataset）")
    parser.add_argument("--recursive", action="store_true", help="是否递归扫描子目录")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不写文件")
    parser.add_argument(
        "--on-conflict",
        choices=["skip", "error"],
        default="skip",
        help="当 source_name 已存在时的处理方式（默认: skip）",
    )
    parser.add_argument(
        "--move",
        action="store_true",
        help="导入后移动原文件（默认复制）",
    )
    parser.add_argument(
        "--split-mode",
        choices=["train_only", "val_only", "split"],
        default="train_only",
        help="写入 train/val 的策略（默认: train_only）",
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.1,
        help="当 split-mode=split 时，写入 val 的比例（默认: 0.1）",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="当 split-mode=split 时，拆分随机种子（默认: 42）",
    )
    return parser


def split_pairs(
    rows: list[dict[str, str]],
    split_mode: str,
    val_ratio: float,
    seed: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    if split_mode == "train_only":
        return rows, []
    if split_mode == "val_only":
        return [], rows

    if not (0.0 <= val_ratio <= 1.0):
        raise ValueError("--val-ratio 必须在 [0, 1] 范围内。")

    shuffled = list(rows)
    rng = random.Random(seed)
    rng.shuffle(shuffled)

    total = len(shuffled)
    val_count = int(total * val_ratio)
    if total > 0 and val_ratio > 0 and val_count == 0:
        val_count = 1
    if total > 1 and val_ratio < 1 and val_count >= total:
        val_count = total - 1

    val_rows = shuffled[:val_count]
    train_rows = shuffled[val_count:]
    return train_rows, val_rows


def main() -> None:
    args = build_parser().parse_args()

    input_dir = Path(args.input_dir).resolve()
    dataset_dir = Path(args.dataset_dir).resolve()
    images_dir = dataset_dir / "images"
    mapping_jsonl = dataset_dir / "mapping.jsonl"
    mapping_csv = dataset_dir / "mapping.csv"
    all_jsonl = dataset_dir / "all.jsonl"
    train_jsonl = dataset_dir / "train.jsonl"
    train_csv = dataset_dir / "train.csv"
    val_jsonl = dataset_dir / "val.jsonl"
    val_csv = dataset_dir / "val.csv"

    if not input_dir.exists() or not input_dir.is_dir():
        raise FileNotFoundError(f"输入目录不存在: {input_dir}")
    if not dataset_dir.exists() or not dataset_dir.is_dir():
        raise FileNotFoundError(f"dataset 目录不存在: {dataset_dir}")
    images_dir.mkdir(parents=True, exist_ok=True)

    source_files = collect_images(input_dir, recursive=args.recursive)
    if not source_files:
        print("未找到可导入图片。")
        return

    mapping_rows = read_jsonl(mapping_jsonl)
    existing_source_names = {str(row.get("source_name", "")).strip() for row in mapping_rows}
    next_mapping_id = get_max_mapping_id(mapping_rows) + 1
    next_image_index = get_next_image_index(images_dir)

    new_mapping_rows: list[dict[str, Any]] = []
    new_pair_rows: list[dict[str, str]] = []
    copied_count = 0
    skipped_count = 0

    for src in source_files:
        source_name = src.name
        text = src.stem.strip()
        if not text:
            skipped_count += 1
            print(f"[SKIP] 文件名为空，无法提取描述: {src}")
            continue

        if source_name in existing_source_names:
            if args.on_conflict == "error":
                raise RuntimeError(f"source_name 已存在: {source_name}")
            skipped_count += 1
            print(f"[SKIP] source_name 已存在: {source_name}")
            continue

        image_name = f"{next_image_index:06d}{src.suffix.lower()}"
        image_rel = f"images/{image_name}"
        dst = images_dir / image_name

        if not args.dry_run:
            if args.move:
                shutil.move(str(src), str(dst))
            else:
                shutil.copy2(src, dst)

        row_mapping = {
            "id": next_mapping_id,
            "image": image_rel,
            "text": text,
            "source_name": source_name,
        }
        row_pair = {"image": image_rel, "text": text}

        new_mapping_rows.append(row_mapping)
        new_pair_rows.append(row_pair)
        existing_source_names.add(source_name)
        next_mapping_id += 1
        next_image_index += 1
        copied_count += 1

    if args.dry_run:
        train_new_rows, val_new_rows = split_pairs(
            rows=new_pair_rows,
            split_mode=args.split_mode,
            val_ratio=args.val_ratio,
            seed=args.seed,
        )
        print(f"[DRY RUN] 预计新增: {copied_count}，跳过: {skipped_count}")
        print(f"[DRY RUN] train 新增: {len(train_new_rows)}")
        print(f"[DRY RUN] val 新增: {len(val_new_rows)}")
        return

    train_new_rows, val_new_rows = split_pairs(
        rows=new_pair_rows,
        split_mode=args.split_mode,
        val_ratio=args.val_ratio,
        seed=args.seed,
    )

    append_jsonl(mapping_jsonl, new_mapping_rows)
    append_jsonl(all_jsonl, new_pair_rows)
    append_jsonl(train_jsonl, train_new_rows)
    append_jsonl(val_jsonl, val_new_rows)

    mapping_csv_rows = read_csv_rows(mapping_csv)
    mapping_csv_rows.extend(new_mapping_rows)
    write_csv_rows(mapping_csv, ["id", "image", "text", "source_name"], mapping_csv_rows)

    train_csv_rows = read_csv_rows(train_csv)
    train_csv_rows.extend(train_new_rows)
    write_csv_rows(train_csv, ["image", "text"], train_csv_rows)

    val_csv_rows = read_csv_rows(val_csv)
    val_csv_rows.extend(val_new_rows)
    write_csv_rows(val_csv, ["image", "text"], val_csv_rows)

    print("导入完成")
    print(f"- 新增样本: {copied_count}")
    print(f"- 跳过样本: {skipped_count}")
    print(f"- mapping.jsonl 新增: {len(new_mapping_rows)}")
    print(f"- all.jsonl 新增: {len(new_pair_rows)}")
    print(f"- train.jsonl 新增: {len(train_new_rows)}")
    print(f"- val.jsonl 新增: {len(val_new_rows)}")


if __name__ == "__main__":
    main()

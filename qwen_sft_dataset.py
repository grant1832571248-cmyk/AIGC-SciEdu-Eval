import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import torch
from torch.utils.data import Dataset


def _safe_read_jsonl(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"未找到数据文件: {path}")

    items: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as e:
                raise ValueError(f"JSONL 解析失败: {path}:{line_no}: {e}") from e
            if not isinstance(obj, dict):
                raise ValueError(f"JSONL 每行必须是 object: {path}:{line_no}")
            items.append(obj)
    if not items:
        raise ValueError(f"数据文件为空: {path}")
    return items


@dataclass(frozen=True)
class AlpacaSample:
    instruction: str
    input: str
    output: str
    system: str = "You are a helpful assistant."

    @staticmethod
    def from_dict(obj: Dict[str, Any]) -> "AlpacaSample":
        instruction = str(obj.get("instruction", "")).strip()
        input_text = str(obj.get("input", "")).strip()
        output = str(obj.get("output", "")).strip()
        system = str(obj.get("system", "You are a helpful assistant.")).strip()

        if not instruction:
            raise ValueError("缺少 instruction")
        if not output:
            raise ValueError("缺少 output")
        return AlpacaSample(instruction=instruction, input=input_text, output=output, system=system)


def _build_user_content(sample: AlpacaSample) -> str:
    if sample.input:
        return f"{sample.instruction}\n\n{sample.input}"
    return sample.instruction


def _has_chat_template(tokenizer: Any) -> bool:
    return callable(getattr(tokenizer, "apply_chat_template", None))


def _tokenize_chat(
    tokenizer: Any,
    messages: Sequence[Dict[str, str]],
    add_generation_prompt: bool,
) -> List[int]:
    if _has_chat_template(tokenizer):
        input_ids = tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=add_generation_prompt,
            tokenize=True,
        )
        if not isinstance(input_ids, list) or not all(isinstance(x, int) for x in input_ids):
            raise TypeError("tokenizer.apply_chat_template(..., tokenize=True) 必须返回 List[int]")
        return input_ids

    text_parts: List[str] = []
    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "")
        text_parts.append(f"<|{role}|>\n{content}\n")
    if add_generation_prompt:
        text_parts.append("<|assistant|>\n")
    text = "".join(text_parts)
    enc = tokenizer(text, add_special_tokens=True, return_attention_mask=False, return_token_type_ids=False)
    input_ids = enc.get("input_ids")
    if not isinstance(input_ids, list):
        raise TypeError("tokenizer(...) 必须返回 input_ids: List[int]")
    return [int(x) for x in input_ids]


class QwenSFTDataset(Dataset):
    def __init__(
        self,
        jsonl_path: str,
        tokenizer: Any,
        max_length: int = 2048,
    ) -> None:
        self._tokenizer = tokenizer
        self._max_length = int(max_length)
        raw_items = _safe_read_jsonl(jsonl_path)

        samples: List[AlpacaSample] = []
        for idx, obj in enumerate(raw_items):
            try:
                samples.append(AlpacaSample.from_dict(obj))
            except Exception as e:
                raise ValueError(f"样本解析失败: {jsonl_path} 第 {idx + 1} 条: {e}") from e
        self._samples = samples

    def __len__(self) -> int:
        return len(self._samples)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        sample = self._samples[idx]

        prompt_messages = [
            {"role": "system", "content": sample.system},
            {"role": "user", "content": _build_user_content(sample)},
        ]
        full_messages = [
            {"role": "system", "content": sample.system},
            {"role": "user", "content": _build_user_content(sample)},
            {"role": "assistant", "content": sample.output},
        ]

        prompt_ids = _tokenize_chat(self._tokenizer, prompt_messages, add_generation_prompt=True)
        full_ids = _tokenize_chat(self._tokenizer, full_messages, add_generation_prompt=False)

        if len(full_ids) > self._max_length:
            full_ids = full_ids[-self._max_length :]
        if len(prompt_ids) > len(full_ids):
            prompt_ids = prompt_ids[: len(full_ids)]

        labels = [-100] * len(full_ids)
        for i in range(len(prompt_ids), len(full_ids)):
            labels[i] = full_ids[i]

        input_ids = torch.tensor(full_ids, dtype=torch.long)
        labels_t = torch.tensor(labels, dtype=torch.long)
        attention_mask = torch.ones_like(input_ids, dtype=torch.long)

        return {"input_ids": input_ids, "attention_mask": attention_mask, "labels": labels_t}


@dataclass(frozen=True)
class CausalLMCollator:
    pad_token_id: int

    def __call__(self, features: List[Dict[str, torch.Tensor]]) -> Dict[str, torch.Tensor]:
        if not features:
            raise ValueError("空 batch")

        input_ids_list = [f["input_ids"] for f in features]
        attn_list = [f["attention_mask"] for f in features]
        labels_list = [f["labels"] for f in features]

        input_ids = torch.nn.utils.rnn.pad_sequence(
            input_ids_list, batch_first=True, padding_value=int(self.pad_token_id)
        )
        attention_mask = torch.nn.utils.rnn.pad_sequence(attn_list, batch_first=True, padding_value=0)
        labels = torch.nn.utils.rnn.pad_sequence(labels_list, batch_first=True, padding_value=-100)

        return {"input_ids": input_ids, "attention_mask": attention_mask, "labels": labels}


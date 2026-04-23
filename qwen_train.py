import argparse
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import torch

from qwen_sft_dataset import CausalLMCollator, QwenSFTDataset


def _require_pkg(name: str) -> None:
    try:
        __import__(name)
    except Exception as e:
        raise RuntimeError(
            f"缺少依赖 {name}，请先安装对应包后再运行。"
        ) from e


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--model_name_or_path", type=str, default="Qwen/Qwen2.5-7B-Instruct")
    p.add_argument("--train_jsonl", type=str, default="data/alpaca_train.jsonl")
    p.add_argument("--val_jsonl", type=str, default="data/alpaca_val.jsonl")
    p.add_argument("--output_dir", type=str, default="checkpoints/qwen2p5_7b_lora")

    p.add_argument("--max_length", type=int, default=2048)
    p.add_argument("--per_device_train_batch_size", type=int, default=1)
    p.add_argument("--per_device_eval_batch_size", type=int, default=1)
    p.add_argument("--gradient_accumulation_steps", type=int, default=8)
    p.add_argument("--learning_rate", type=float, default=2e-4)
    p.add_argument("--num_train_epochs", type=float, default=1.0)
    p.add_argument("--warmup_ratio", type=float, default=0.03)
    p.add_argument("--weight_decay", type=float, default=0.0)
    p.add_argument("--logging_steps", type=int, default=10)
    p.add_argument("--eval_strategy", type=str, default="steps", choices=["no", "steps", "epoch"])
    p.add_argument("--eval_steps", type=int, default=200)
    p.add_argument("--save_strategy", type=str, default="steps", choices=["steps", "epoch"])
    p.add_argument("--save_steps", type=int, default=200)
    p.add_argument("--save_total_limit", type=int, default=2)

    p.add_argument("--lora_r", type=int, default=16)
    p.add_argument("--lora_alpha", type=int, default=32)
    p.add_argument("--lora_dropout", type=float, default=0.05)

    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--bf16", action="store_true")
    p.add_argument("--fp16", action="store_true")
    p.add_argument("--gradient_checkpointing", action="store_true")
    p.add_argument("--num_workers", type=int, default=0)
    return p.parse_args()


def _default_lora_target_modules(model: Any) -> Any:
    for name in ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]:
        if any(name in n for n, _ in model.named_modules()):
            return ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
    return ["q_proj", "k_proj", "v_proj", "o_proj"]


def main() -> None:
    _require_pkg("transformers")
    _require_pkg("accelerate")
    _require_pkg("peft")

    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
        set_seed,
    )
    from peft import LoraConfig, TaskType, get_peft_model

    args = _parse_args()
    set_seed(int(args.seed))

    if args.bf16 and args.fp16:
        raise ValueError("--bf16 和 --fp16 不能同时启用")

    os.makedirs(args.output_dir, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(args.model_name_or_path, use_fast=True, trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        if tokenizer.eos_token_id is None:
            raise ValueError("Tokenizer 缺少 pad_token_id 且 eos_token_id 为空，无法进行 padding")
        tokenizer.pad_token = tokenizer.eos_token

    torch_dtype: Optional[torch.dtype] = None
    if args.bf16:
        torch_dtype = torch.bfloat16
    if args.fp16:
        torch_dtype = torch.float16

    model = AutoModelForCausalLM.from_pretrained(
        args.model_name_or_path,
        torch_dtype=torch_dtype,
        device_map=None,
        trust_remote_code=True,
    )

    if args.gradient_checkpointing and hasattr(model, "gradient_checkpointing_enable"):
        model.gradient_checkpointing_enable()
        try:
            model.enable_input_require_grads()
        except Exception:
            pass

    lora_config = LoraConfig(
        r=int(args.lora_r),
        lora_alpha=int(args.lora_alpha),
        lora_dropout=float(args.lora_dropout),
        target_modules=_default_lora_target_modules(model),
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_config)

    train_dataset = QwenSFTDataset(jsonl_path=args.train_jsonl, tokenizer=tokenizer, max_length=int(args.max_length))
    eval_dataset = None
    if args.val_jsonl and os.path.exists(args.val_jsonl):
        eval_dataset = QwenSFTDataset(jsonl_path=args.val_jsonl, tokenizer=tokenizer, max_length=int(args.max_length))

    data_collator = CausalLMCollator(pad_token_id=int(tokenizer.pad_token_id))

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=int(args.per_device_train_batch_size),
        per_device_eval_batch_size=int(args.per_device_eval_batch_size),
        gradient_accumulation_steps=int(args.gradient_accumulation_steps),
        learning_rate=float(args.learning_rate),
        num_train_epochs=float(args.num_train_epochs),
        warmup_ratio=float(args.warmup_ratio),
        weight_decay=float(args.weight_decay),
        logging_steps=int(args.logging_steps),
        evaluation_strategy=args.eval_strategy,
        eval_steps=int(args.eval_steps) if args.eval_strategy == "steps" else None,
        save_strategy=args.save_strategy,
        save_steps=int(args.save_steps) if args.save_strategy == "steps" else None,
        save_total_limit=int(args.save_total_limit),
        bf16=bool(args.bf16),
        fp16=bool(args.fp16),
        dataloader_num_workers=int(args.num_workers),
        report_to=[],
        ddp_find_unused_parameters=False,
        remove_unused_columns=False,
    )

    def compute_metrics(eval_pred: Any) -> Dict[str, float]:
        return {}

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )

    trainer.train()
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback

        print(f"❌ Qwen LoRA SFT 训练失败: {e}")
        traceback.print_exc()

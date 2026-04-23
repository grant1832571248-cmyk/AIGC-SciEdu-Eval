import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torch.optim import AdamW
import clip
import os
from dataset import CLIPDataset
from typing import Dict, Optional, Tuple

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


@torch.no_grad()
def evaluate(
    model: torch.nn.Module,
    dataloader: DataLoader,
    device: str,
    loss_img: nn.Module,
    loss_txt: nn.Module,
) -> Dict[str, float]:
    model.eval()
    total_loss = 0.0
    total_acc_image = 0.0
    total_acc_text = 0.0
    total_samples = 0

    for images, texts in dataloader:
        images = images.to(device)
        texts = texts.to(device)

        logits_per_image, logits_per_text = model(images, texts)
        loss, acc_image, acc_text = _batch_contrastive_loss_and_acc(
            logits_per_image=logits_per_image,
            logits_per_text=logits_per_text,
            loss_img=loss_img,
            loss_txt=loss_txt,
        )

        batch_size = images.shape[0]
        total_samples += batch_size
        total_loss += float(loss.item()) * batch_size
        total_acc_image += acc_image * batch_size
        total_acc_text += acc_text * batch_size

    if total_samples == 0:
        raise RuntimeError("验证集为空或无法加载，无法计算评估指标。")

    return {
        "loss": total_loss / total_samples,
        "acc_image": total_acc_image / total_samples,
        "acc_text": total_acc_text / total_samples,
    }


def train(
    jsonl_path: str = "dataset/train.jsonl",
    val_jsonl_path: Optional[str] = "dataset/val.jsonl",
    img_dir: str = "dataset",
    model_name: str = "ViT-B/32",
    batch_size: int = 16,
    lr: float = 5e-6,
    epochs: int = 5,
    save_path: str = "checkpoints/clip_finetuned.pt",
    num_workers: int = 0,
):
    """
    CLIP 微调主程序。
    
    Why: 
    - 使用 AdamW 优化器，因为它在 Transformer 架构上表现更好。
    - 学习率设为 5e-6 (极小)，防止破坏预训练权重。
    - 采用对比损失 (Contrastive Loss) 来对齐图像和文本特征。
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    # 加载模型
    model, preprocess = clip.load(model_name, device=device, jit=False)
    
    # 准备数据
    train_dataset = CLIPDataset(jsonl_path, img_dir, preprocess)
    train_loader = DataLoader(
        train_dataset, 
        batch_size=batch_size, 
        shuffle=True, 
        num_workers=num_workers,
    )

    val_loader: Optional[DataLoader] = None
    if val_jsonl_path is not None and os.path.exists(val_jsonl_path):
        val_dataset = CLIPDataset(val_jsonl_path, img_dir, preprocess)
        val_loader = DataLoader(
            val_dataset,
            batch_size=batch_size,
            shuffle=False,
            num_workers=num_workers,
        )

    # 准备优化器 (仅更新可学习参数)
    optimizer = AdamW(model.parameters(), lr=lr, betas=(0.9, 0.98), eps=1e-6, weight_decay=0.2)
    
    # 损失函数 (CrossEntropy 用于对比学习)
    loss_img = nn.CrossEntropyLoss()
    loss_txt = nn.CrossEntropyLoss()

    model.train()
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    for epoch in range(epochs):
        total_loss = 0.0
        total_acc_image = 0.0
        total_acc_text = 0.0
        total_samples = 0
        for i, (images, texts) in enumerate(train_loader):
            images = images.to(device)
            texts = texts.to(device)

            # 前向传播
            logits_per_image, logits_per_text = model(images, texts)
            
            # 计算对比损失与 batch 内 top-1 精度
            loss, acc_image, acc_text = _batch_contrastive_loss_and_acc(
                logits_per_image=logits_per_image,
                logits_per_text=logits_per_text,
                loss_img=loss_img,
                loss_txt=loss_txt,
            )
            
            # 反向传播
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            batch_size_actual = images.shape[0]
            total_samples += batch_size_actual
            total_loss += float(loss.item()) * batch_size_actual
            total_acc_image += acc_image * batch_size_actual
            total_acc_text += acc_text * batch_size_actual

            if (i + 1) % 10 == 0:
                print(f"Epoch [{epoch+1}/{epochs}], Step [{i+1}/{len(train_loader)}], Loss: {loss.item():.4f}")

        if total_samples == 0:
            raise RuntimeError("训练集为空或无法加载，无法继续训练。")

        avg_loss = total_loss / total_samples
        avg_acc_image = total_acc_image / total_samples
        avg_acc_text = total_acc_text / total_samples
        print(
            f"Epoch [{epoch+1}/{epochs}] 完成, 平均 Loss: {avg_loss:.4f}, "
            f"Acc(image->text): {avg_acc_image:.4f}, Acc(text->image): {avg_acc_text:.4f}"
        )

        if val_loader is not None:
            metrics = evaluate(model=model, dataloader=val_loader, device=device, loss_img=loss_img, loss_txt=loss_txt)
            print(
                f"Val: Loss: {metrics['loss']:.4f}, "
                f"Acc(image->text): {metrics['acc_image']:.4f}, Acc(text->image): {metrics['acc_text']:.4f}"
            )
            model.train()

        # 保存模型
        torch.save(model.state_dict(), save_path)
        print(f"模型权重已保存至: {save_path}")

if __name__ == "__main__":
    try:
        train()
    except Exception as e:
        print(f"训练过程中发生致命错误: {e}")
        # 记录错误原因 (Root Cause Analysis 基础)
        import traceback
        traceback.print_exc()

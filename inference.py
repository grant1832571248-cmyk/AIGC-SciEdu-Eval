import torch
import clip
from PIL import Image
import os
from typing import List, Optional

# 设置模型缓存目录
os.environ['XDG_CACHE_HOME'] = os.path.expanduser('~/models/openai')

def run_inference(
    image_path: str = "test.jpg", 
    labels: List[str] = ["a dog", "a cat", "a robot"],
    model_weight_path: Optional[str] = "checkpoints/clip_finetuned.pt",
    model_name: str = "ViT-B/32"
):
    """
    运行 CLIP 推理，支持加载微调权重。
    
    Why: 
    - 统一推理接口，方便在原始模型和微调模型间切换。
    - 增加防御性编程逻辑，处理权重加载失败的情况。
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    # 1. 加载模型结构和预处理
    model, preprocess = clip.load(model_name, device=device)

    # 2. 尝试加载微调权重
    if model_weight_path and os.path.exists(model_weight_path):
        try:
            model.load_state_dict(torch.load(model_weight_path, map_location=device))
            print(f"✅ 成功加载微调权重: {model_weight_path}")
        except Exception as e:
            print(f"⚠️ 加载微调权重失败，将使用原始权重: {e}")

    # 3. 推理逻辑
    try:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"未找到测试图片: {image_path}")
            
        image = preprocess(Image.open(image_path)).unsqueeze(0).to(device)
        text = clip.tokenize(labels).to(device)

        with torch.no_grad():
            logits_per_image, _ = model(image, text)
            probs = logits_per_image.softmax(dim=-1).cpu().numpy()

        print(f"推理结果 (Label probs): {probs}")
        for label, prob in zip(labels, probs[0]):
            print(f"- {label}: {prob:.4f}")
            
    except Exception as e:
        print(f"❌ 推理失败: {e}")

if __name__ == "__main__":
    run_inference()

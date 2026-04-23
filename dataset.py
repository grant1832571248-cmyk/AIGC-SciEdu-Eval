import os
import json
import torch
from torch.utils.data import Dataset
from PIL import Image
import clip
from typing import List, Tuple, Dict, Any

class CLIPDataset(Dataset):
    """
    CLIP 微调数据集类。
    负责从 JSONL 文件读取图片路径和文本，并进行预处理。
    """
    def __init__(self, jsonl_path: str, img_dir: str, preprocess: Any):
        """
        Args:
            jsonl_path (str): JSONL 标注文件路径。
            img_dir (str): 图片根目录。
            preprocess (Any): CLIP 模型的图像预处理函数。
        """
        self.img_dir = img_dir
        self.preprocess = preprocess
        self.data = self._load_data(jsonl_path)

    def _load_data(self, path: str) -> List[Dict[str, str]]:
        """读取 JSONL 文件"""
        data = []
        if not os.path.exists(path):
            raise FileNotFoundError(f"标注文件未找到: {path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        return data

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        返回:
            image_tensor (torch.Tensor): 预处理后的图像。
            text_tokens (torch.Tensor): 编码后的文本。
        """
        item = self.data[idx]
        img_path = os.path.join(self.img_dir, item['image'])
        text = item['text']

        try:
            image = Image.open(img_path).convert("RGB")
            image_tensor = self.preprocess(image)
        except Exception as e:
            # 防御性编程：处理损坏图片或路径错误
            print(f"警告: 无法读取图片 {img_path}, 错误: {e}")
            # 返回一个零张量作为占位符（实际训练中应过滤掉或重试）
            image_tensor = torch.zeros(3, 224, 224)

        # 限制文本长度并进行 tokenization
        # 注意：CLIP 的默认文本最大长度是 77
        text_tokens = clip.tokenize([text], truncate=True).squeeze(0)

        return image_tensor, text_tokens

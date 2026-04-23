from __future__ import annotations

import threading
import tempfile
import os
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import torch
import numpy as np
from PIL import Image

@dataclass(frozen=True, slots=True)
class XClipScoreResult:
    similarity: float
    score_0_100: float
    model_name: str
    used_finetuned_weight: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "similarity": self.similarity,
            "score_0_100": self.score_0_100,
            "model_name": self.model_name,
            "used_finetuned_weight": self.used_finetuned_weight,
        }

class XClipScorer:
    def __init__(self, model_name: str, model_weight_path: str | None) -> None:
        self.model_name = model_name
        self.model_weight_path = Path(model_weight_path) if model_weight_path else None
        self._lock = threading.Lock()
        self._device: str | None = None
        self._model: Any | None = None
        self._processor: Any | None = None
        self._used_finetuned_weight: bool = False

    def _ensure_loaded(self) -> None:
        if self._model is not None and self._processor is not None and self._device is not None:
            return

        with self._lock:
            if self._model is not None and self._processor is not None and self._device is not None:
                return

            device = "cuda" if torch.cuda.is_available() else "cpu"
            
            try:
                from transformers import XCLIPModel, XCLIPProcessor
                model = XCLIPModel.from_pretrained(self.model_name).to(device)
                processor = XCLIPProcessor.from_pretrained(self.model_name)
                
                used_finetuned = False
                if self.model_weight_path is not None and self.model_weight_path.exists():
                    try:
                        model.load_state_dict(torch.load(self.model_weight_path, map_location=device))
                        used_finetuned = True
                    except Exception:
                        used_finetuned = False

                self._device = device
                self._model = model
                self._processor = processor
                self._used_finetuned_weight = used_finetuned
            except ImportError:
                # 如果没装 transformers，回退到模拟模式以防 server 启动失败
                self._device = device
                self._model = "mock_mode"
                self._processor = "mock_mode"
                self._used_finetuned_weight = False

    def _sample_frames(self, video_path: str, num_frames: int = 8) -> list[np.ndarray]:
        """使用 decord 均匀采样视频帧"""
        try:
            from decord import VideoReader, cpu
            vr = VideoReader(video_path, ctx=cpu(0))
            total_frames = len(vr)
            if total_frames <= 0:
                raise RuntimeError("Video has no frames.")
            
            # 均匀采样索引
            indices = np.linspace(0, total_frames - 1, num_frames).astype(int)
            frames = vr.get_batch(indices).asnumpy()
            return [frame for frame in frames]
        except ImportError:
            # 如果没有 decord，尝试使用 av
            try:
                import av
                container = av.open(video_path)
                frames = []
                for frame in container.decode(video=0):
                    frames.append(frame.to_ndarray(format="rgb24"))
                
                total = len(frames)
                if total <= 0:
                    raise RuntimeError("Video has no frames (av).")
                
                # 简单均匀采样
                indices = np.linspace(0, total - 1, num_frames).astype(int)
                return [frames[i] for i in indices]
            except Exception as e:
                raise RuntimeError(f"Failed to extract frames: {e}. Please install 'decord' or 'av'.")

    def score_video_text(self, video_bytes: bytes, text: str) -> dict[str, Any]:
        """
        对视频和文本进行匹配评分。
        """
        print(f"DEBUG: score_video_text called with text='{text}'")
        if not isinstance(video_bytes, (bytes, bytearray)) or len(video_bytes) == 0:
            raise ValueError("video_bytes must be non-empty bytes")
        if text.strip() == "":
            raise ValueError("text must be non-empty")

        self._ensure_loaded()
        
        # 处理模拟模式
        if self._model == "mock_mode":
            print("DEBUG: Using mock mode")
            import random
            similarity = random.uniform(0.3, 0.7)
            score_0_100 = (similarity + 1.0) * 50.0
            return XClipScoreResult(
                similarity=round(similarity, 6),
                score_0_100=round(score_0_100, 2),
                model_name=self.model_name + " (MOCKED)",
                used_finetuned_weight=False
            ).to_dict()

        # 将 bytes 写入临时文件以供 decord 读取
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            tmp.write(video_bytes)
            tmp_path = tmp.name

        try:
            # 采样 8 帧 (X-CLIP 默认常用配置)
            raw_frames = self._sample_frames(tmp_path, num_frames=8)
            print(f"DEBUG: Sampled {len(raw_frames)} frames")
            
            if not raw_frames:
                raise RuntimeError("Failed to extract any frames from video.")

            # 将 numpy 数组转换为 PIL Image，确保 XCLIPProcessor 能正确处理
            frames = [Image.fromarray(f) if isinstance(f, np.ndarray) else f for f in raw_frames]
            
            # 重要：X-CLIP Processor 处理逻辑
            # 我们显式地构建 inputs，并确保 pixel_values 存在且非空
            print("DEBUG: Processing inputs with XCLIPProcessor...")
            
            # 尝试最标准的方法
            try:
                inputs = self._processor(
                    text=[text],
                    videos=[frames], 
                    return_tensors="pt",
                    padding=True
                ).to(self._device)
            except Exception as e:
                print(f"DEBUG: Standard processor call failed: {e}")
                inputs = {}

            # 如果没有 pixel_values，尝试 fallback
            if inputs.get("pixel_values") is None:
                print("DEBUG: pixel_values missing, trying fallback with images= parameter...")
                try:
                    inputs = self._processor(
                        text=[text],
                        images=[frames], 
                        return_tensors="pt",
                        padding=True
                    ).to(self._device)
                except Exception as e:
                    print(f"DEBUG: Fallback processor call failed: {e}")

            # 如果还是没有，手动处理
            if inputs.get("pixel_values") is None:
                print("DEBUG: Still no pixel_values, performing manual encoding...")
                text_inputs = self._processor.tokenizer([text], return_tensors="pt", padding=True).to(self._device)
                
                img_proc = getattr(self._processor, "image_processor", None) or getattr(self._processor, "feature_extractor", None)
                if img_proc:
                    try:
                        # X-CLIP 的 image_processor 接受 videos 参数
                        # 我们传入 [frames]，其中 frames 是 8 个 PIL Image 的列表
                        # 这样 batch_size = 1, num_frames = 8
                        video_inputs = img_proc(videos=[frames], return_tensors="pt").to(self._device)
                        
                        # 检查返回结果中是否有 pixel_values
                        if "pixel_values" not in video_inputs:
                            print(f"DEBUG: video_inputs keys: {list(video_inputs.keys())}")
                            # 尝试以 images 传入
                            video_inputs = img_proc(images=frames, return_tensors="pt").to(self._device)
                            # 此时返回的可能是 [8, 3, 224, 224]，需要 reshape 为 [1, 8, 3, 224, 224]
                            if "pixel_values" in video_inputs and video_inputs["pixel_values"].ndim == 4:
                                video_inputs["pixel_values"] = video_inputs["pixel_values"].unsqueeze(0)
                        
                        inputs = {**text_inputs, **video_inputs}
                    except Exception as e:
                        print(f"DEBUG: Manual image processing failed: {e}")
                        raise RuntimeError(f"Manual processing failed: {e}")
                else:
                    raise RuntimeError("Could not find image_processor or feature_extractor")

            # 终极检查
            if inputs.get("pixel_values") is None:
                print(f"DEBUG: Final inputs keys: {list(inputs.keys())}")
                raise RuntimeError("XCLIPProcessor failed to generate 'pixel_values' after all attempts.")
            
            if inputs["pixel_values"] is None:
                raise RuntimeError("pixel_values is explicitly None in inputs!")

            print(f"DEBUG: pixel_values shape: {inputs['pixel_values'].shape}")

            with torch.no_grad():
                outputs = self._model(**inputs)
                # 计算相似度得分
                # X-CLIP 模型输出 logits_per_video = cosine_similarity * exp(logit_scale)
                logits_per_video = outputs.logits_per_video
                
                # 获取 logit_scale 以还原余弦相似度
                logit_scale = getattr(self._model, "logit_scale", torch.tensor(4.6052)).to(self._device) # exp(4.6052) ≈ 100
                cosine_sim = logits_per_video / logit_scale.exp()
                similarity = float(cosine_sim.squeeze().item())
                
                # 将余弦相似度 (通常 0.05-0.2) 映射到 0-100 分
                # 调整后的经验公式：0.08 约为 50分，0.12 约为 80分
                # 使用更温和的偏移量 0.08，并增加灵敏度系数 25
                score_0_100 = float(torch.sigmoid(torch.tensor((similarity - 0.08) * 25.0)).item()) * 100.0
                
            print(f"DEBUG: Raw Logits: {logits_per_video.item():.4f}, Cosine Sim: {similarity:.4f}, Score: {score_0_100:.2f}")
            
            result = XClipScoreResult(
                similarity=round(similarity, 6),
                score_0_100=round(score_0_100, 2),
                model_name=self.model_name,
                used_finetuned_weight=self._used_finetuned_weight,
            )
            return result.to_dict()
        except Exception as e:
            # 打印详细错误到控制台方便排查
            print(f"ERROR in XClipScorer: {str(e)}")
            import traceback
            traceback.print_exc()
            raise e
            
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

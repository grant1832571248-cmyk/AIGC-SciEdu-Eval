from __future__ import annotations

import threading
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import clip
import torch
from PIL import Image


@dataclass(frozen=True, slots=True)
class ClipScoreResult:
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


class ClipScorer:
    def __init__(self, model_name: str, model_weight_path: str | None) -> None:
        self.model_name = model_name
        self.model_weight_path = Path(model_weight_path) if model_weight_path else None
        self._lock = threading.Lock()
        self._device: str | None = None
        self._model: Any | None = None
        self._preprocess: Any | None = None
        self._used_finetuned_weight: bool = False

    def _ensure_loaded(self) -> None:
        if self._model is not None and self._preprocess is not None and self._device is not None:
            return

        with self._lock:
            if self._model is not None and self._preprocess is not None and self._device is not None:
                return

            device = "cuda" if torch.cuda.is_available() else "cpu"
            model, preprocess = clip.load(self.model_name, device=device)

            used_finetuned = False
            if self.model_weight_path is not None and self.model_weight_path.exists():
                try:
                    model.load_state_dict(torch.load(self.model_weight_path, map_location=device))
                    used_finetuned = True
                except Exception:
                    used_finetuned = False

            self._device = device
            self._model = model
            self._preprocess = preprocess
            self._used_finetuned_weight = used_finetuned

    def score_image_text(self, image_bytes: bytes, text: str) -> dict[str, Any]:
        if not isinstance(image_bytes, (bytes, bytearray)) or len(image_bytes) == 0:
            raise ValueError("image_bytes must be non-empty bytes")
        if text.strip() == "":
            raise ValueError("text must be non-empty")

        self._ensure_loaded()
        assert self._model is not None
        assert self._preprocess is not None
        assert self._device is not None

        try:
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
        except Exception as e:
            raise ValueError(f"Invalid image bytes: {e}") from e

        image_input = self._preprocess(image).unsqueeze(0).to(self._device)
        text_input = clip.tokenize([text]).to(self._device)

        with torch.no_grad():
            image_features = self._model.encode_image(image_input)
            text_features = self._model.encode_text(text_input)

            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            similarity = float((image_features @ text_features.T).squeeze().item())

        score_0_100 = max(0.0, min(100.0, (similarity + 1.0) * 50.0))
        result = ClipScoreResult(
            similarity=round(similarity, 6),
            score_0_100=round(score_0_100, 2),
            model_name=self.model_name,
            used_finetuned_weight=self._used_finetuned_weight,
        )
        return result.to_dict()


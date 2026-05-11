from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import clip
import torch
from PIL import Image


@dataclass(frozen=True, slots=True)
class ClipCalibration:
    min_similarity: float
    max_similarity: float
    decision_threshold: float
    positive_similarity_mean: float
    negative_similarity_mean: float
    positive_similarity_min: float
    negative_similarity_max: float

    @classmethod
    def conservative_default(cls) -> "ClipCalibration":
        return cls(
            min_similarity=0.05,
            max_similarity=0.30,
            decision_threshold=0.18,
            positive_similarity_mean=0.24,
            negative_similarity_mean=0.10,
            positive_similarity_min=0.22,
            negative_similarity_max=0.14,
        )

    @classmethod
    def from_file(cls, file_path: Path | None) -> "ClipCalibration":
        if file_path is None or not file_path.exists():
            return cls.conservative_default()

        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            return cls.conservative_default()

        min_similarity = float(payload.get("min_similarity", 0.05))
        max_similarity = float(payload.get("max_similarity", 0.30))
        decision_threshold = float(payload.get("decision_threshold", (min_similarity + max_similarity) / 2.0))
        positive_similarity_min = float(payload.get("positive_similarity_min", payload.get("positive_similarity_mean", max_similarity)))
        negative_similarity_max = float(payload.get("negative_similarity_max", payload.get("negative_similarity_mean", min_similarity)))

        if max_similarity - min_similarity < 1e-4:
            return cls.conservative_default()

        return cls(
            min_similarity=min_similarity,
            max_similarity=max_similarity,
            decision_threshold=decision_threshold,
            positive_similarity_mean=float(payload.get("positive_similarity_mean", max_similarity)),
            negative_similarity_mean=float(payload.get("negative_similarity_mean", min_similarity)),
            positive_similarity_min=positive_similarity_min,
            negative_similarity_max=negative_similarity_max,
        )


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _similarity_to_score(similarity: float, calibration: ClipCalibration) -> float:
    min_similarity = calibration.min_similarity
    max_similarity = calibration.max_similarity
    decision_threshold = _clamp(calibration.decision_threshold, min_similarity, max_similarity)
    lower_anchor = _clamp(calibration.negative_similarity_max, min_similarity, decision_threshold)
    upper_anchor = _clamp(calibration.positive_similarity_min, decision_threshold, max_similarity)

    if max_similarity - min_similarity <= 1e-6:
        calibration = ClipCalibration.conservative_default()
        min_similarity = calibration.min_similarity
        max_similarity = calibration.max_similarity
        decision_threshold = calibration.decision_threshold
        lower_anchor = calibration.negative_similarity_max
        upper_anchor = calibration.positive_similarity_min

    global_span = max(max_similarity - min_similarity, 1e-6)
    anchor_span = max(upper_anchor - lower_anchor, 1e-4)

    linear_component = _clamp((similarity - min_similarity) / global_span, 0.0, 1.0)

    temperature = max(anchor_span / 6.0, 1e-4)
    z = _clamp((similarity - decision_threshold) / temperature, -50.0, 50.0)
    sigmoid_component = 1.0 / (1.0 + __import__("math").exp(-z))

    normalized = 0.25 * linear_component + 0.75 * sigmoid_component

    if similarity < lower_anchor:
        normalized *= 0.85
    elif similarity > upper_anchor:
        normalized = 0.85 + 0.15 * _clamp((normalized - 0.85) / 0.15, 0.0, 1.0)

    return _clamp(normalized * 100.0, 0.0, 100.0)


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
        self._calibration_path = self.model_weight_path.with_suffix(".calibration.json") if self.model_weight_path else None
        self._lock = threading.Lock()
        self._device: str | None = None
        self._model: Any | None = None
        self._preprocess: Any | None = None
        self._used_finetuned_weight: bool = False
        self._calibration = ClipCalibration.conservative_default()

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
            self._calibration = ClipCalibration.from_file(self._calibration_path if used_finetuned else None)

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
        except Exception as exc:
            raise ValueError(f"Invalid image bytes: {exc}") from exc

        image_input = self._preprocess(image).unsqueeze(0).to(self._device)
        text_input = clip.tokenize([text], truncate=True).to(self._device)

        with torch.no_grad():
            image_features = self._model.encode_image(image_input)
            text_features = self._model.encode_text(text_input)

            image_features = image_features / image_features.norm(dim=-1, keepdim=True).clamp(min=1e-12)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True).clamp(min=1e-12)
            similarity = float((image_features @ text_features.T).squeeze().item())

        score_0_100 = _similarity_to_score(similarity, self._calibration)
        result = ClipScoreResult(
            similarity=round(similarity, 6),
            score_0_100=round(score_0_100, 2),
            model_name=self.model_name,
            used_finetuned_weight=self._used_finetuned_weight,
        )
        return result.to_dict()

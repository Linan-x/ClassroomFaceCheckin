"""Model-backed, file-local recognition primitives.

This module deliberately owns no business database or attendance state.  It
only creates and reads local facebank artifacts supplied through the internal
API.
"""

from __future__ import annotations

import io
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, UnidentifiedImageError

from checkin_web.recognition import RecognitionService


class RecognitionInputError(ValueError):
    """Raised when a valid HTTP request cannot be used for inference."""


@dataclass(frozen=True)
class RecognitionMatch:
    student_id: int | None
    confidence: float | None


class MtcnnMobileFaceNetEngine:
    """Adapt the existing lazy MTCNN/MobileFaceNet lifecycle for HTTP use."""

    def __init__(self, models: RecognitionService | None = None) -> None:
        self._models = models or RecognitionService()

    @property
    def models_loaded(self) -> bool:
        return self._models.models_loaded

    def build_embeddings(self, images: Iterable[Image.Image]):
        import torch

        mtcnn, learner = self._models.load_models()
        conf = self._models.get_config()
        embeddings = []
        for image in images:
            _, faces = mtcnn.align_multi(image, conf.face_limit, conf.min_face_size)
            if faces is None or len(faces) != 1:
                raise RecognitionInputError("Each facebank reference image must contain exactly one face.")
            face = faces[0]
            with torch.no_grad():
                embedding = learner.model(conf.test_transform(face).to(conf.device).unsqueeze(0)).cpu()
            embeddings.append(embedding)
        if not embeddings:
            raise RecognitionInputError("At least one facebank entry is required.")
        return torch.cat(embeddings)

    def recognize(self, image: Image.Image, student_ids: list[int], embeddings) -> RecognitionMatch:
        mtcnn, learner = self._models.load_models()
        conf = self._models.get_config()
        _, faces = mtcnn.align_multi(image, conf.face_limit, conf.min_face_size)
        if faces is None or len(faces) != 1:
            raise RecognitionInputError("Recognition images must contain exactly one face.")
        results, scores = learner.infer(conf, faces, embeddings, tta=True)
        index = int(results[0])
        if index < 0:
            return RecognitionMatch(None, None)
        return RecognitionMatch(student_ids[index], float(scores[0]))


class FacebankStore:
    """Safely persist service-owned artifacts beneath one configured directory."""

    def __init__(self, root: Path, engine: MtcnnMobileFaceNetEngine) -> None:
        self._root = root.resolve()
        self._engine = engine
        self._lock = threading.Lock()

    @property
    def model_loaded(self) -> bool:
        return self._engine.models_loaded

    def build(self, facebank_id: str, entries: list[tuple[int, Image.Image]]) -> int:
        import torch

        embeddings = self._engine.build_embeddings(image for _, image in entries)
        destination = self._path(facebank_id)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".tmp")
        with self._lock:
            torch.save(
                {"student_ids": [student_id for student_id, _ in entries], "embeddings": embeddings.cpu()},
                temporary,
            )
            temporary.replace(destination)
        return len(entries)

    def status(self, facebank_id: str) -> dict[str, int | str]:
        path = self._path(facebank_id)
        if not path.exists():
            return {"status": "MISSING", "entry_count": 0}
        data = self._load(path)
        return {"status": "READY", "entry_count": len(data["student_ids"])}

    def recognize(self, facebank_id: str, image: Image.Image) -> RecognitionMatch:
        path = self._path(facebank_id)
        if not path.exists():
            raise RecognitionInputError("The requested facebank does not exist.")
        data = self._load(path)
        return self._engine.recognize(image, data["student_ids"], data["embeddings"])

    def _path(self, facebank_id: str) -> Path:
        if not facebank_id or len(facebank_id) > 64 or not facebank_id.replace("-", "").replace("_", "").isalnum():
            raise RecognitionInputError("facebank_id must contain only letters, digits, hyphens, or underscores.")
        return self._root / f"{facebank_id}.pt"

    @staticmethod
    def _load(path: Path):
        import torch

        try:
            data = torch.load(path, map_location="cpu", weights_only=True)
        except (OSError, RuntimeError, ValueError) as exc:
            raise RecognitionInputError("The facebank artifact is unreadable.") from exc
        if not isinstance(data, dict) or not isinstance(data.get("student_ids"), list) or "embeddings" not in data:
            raise RecognitionInputError("The facebank artifact has an invalid format.")
        return data


def decode_image(encoded: str, max_bytes: int, max_pixels: int) -> Image.Image:
    """Decode an untrusted base64 image without permitting decompression bombs."""

    import base64
    import binascii

    if not isinstance(encoded, str) or not encoded or len(encoded) > (max_bytes * 4 // 3) + 8:
        raise RecognitionInputError("image_base64 is missing or exceeds the configured limit.")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise RecognitionInputError("image_base64 must be valid base64.") from exc
    if not raw or len(raw) > max_bytes:
        raise RecognitionInputError("The decoded image exceeds the configured limit.")
    try:
        with Image.open(io.BytesIO(raw)) as decoded:
            decoded.verify()
        with Image.open(io.BytesIO(raw)) as decoded:
            if decoded.width * decoded.height > max_pixels:
                raise RecognitionInputError("The image exceeds the configured pixel limit.")
            return decoded.convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise RecognitionInputError("The supplied data is not a supported image.") from exc

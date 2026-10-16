import base64
import io

from PIL import Image
import torch

from recognition_service.app import ServiceConfig, create_app
from recognition_service.service import FacebankStore, RecognitionMatch


class StubEngine:
    models_loaded = False

    def build_embeddings(self, images):
        images = list(images)
        return torch.arange(len(images), dtype=torch.float32).reshape(len(images), 1)

    def recognize(self, image, student_ids, embeddings):
        return RecognitionMatch(student_ids[0], 0.12)


def image_base64():
    raw = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(raw, format="PNG")
    return base64.b64encode(raw.getvalue()).decode()


def app(tmp_path):
    config = ServiceConfig("test-token", False, tmp_path, max_image_bytes=1024 * 1024)
    return create_app(config, FacebankStore(tmp_path, StubEngine()))


def auth():
    return {"Authorization": "Bearer test-token"}


def test_internal_endpoints_require_shared_token(tmp_path):
    client = app(tmp_path).test_client()
    response = client.post("/internal/v1/recognitions", json={})
    assert response.status_code == 401
    assert response.json["error"]["code"] == "UNAUTHORIZED"
    assert response.headers["X-Request-ID"]


def test_missing_token_fails_closed_outside_development_mode(tmp_path):
    client = create_app(ServiceConfig("", False, tmp_path), FacebankStore(tmp_path, StubEngine())).test_client()
    health = client.get("/health")
    assert health.status_code == 503
    assert health.json["status"] == "misconfigured"
    rejected = client.get("/internal/v1/facebanks/course-1")
    assert rejected.status_code == 503


def test_facebank_build_and_recognition_are_model_stubbed(tmp_path):
    client = app(tmp_path).test_client()
    image = image_base64()
    build = client.post("/internal/v1/facebanks/course-1/build", headers=auth(), json={
        "entries": [{"student_id": 17, "image_base64": image}]
    })
    assert build.status_code == 201
    assert build.json["entry_count"] == 1
    recognized = client.post("/internal/v1/recognitions", headers=auth(), json={
        "facebank_id": "course-1", "image_base64": image
    })
    assert recognized.status_code == 200
    assert recognized.json["result"] == {
        "status": "MATCHED", "recognized_student_id": 17, "confidence": 0.12
    }


def test_image_and_request_validation_returns_structured_error(tmp_path):
    client = app(tmp_path).test_client()
    response = client.post("/internal/v1/recognitions", headers=auth(), json={
        "facebank_id": "../unsafe", "image_base64": "not-base64"
    })
    assert response.status_code == 422
    assert response.json["error"]["code"] == "INVALID_RECOGNITION_INPUT"

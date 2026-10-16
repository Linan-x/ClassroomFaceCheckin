"""Authenticated internal HTTP service for MTCNN/MobileFaceNet inference."""

from __future__ import annotations

import os
import secrets
import uuid
from dataclasses import dataclass
from pathlib import Path

from flask import Flask, Response, g, jsonify, request
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from checkin_web.runtime import configure_runtime

configure_runtime()
from recognition_service.service import FacebankStore, MtcnnMobileFaceNetEngine, RecognitionInputError, decode_image


@dataclass(frozen=True)
class ServiceConfig:
    shared_token: str
    development_mode: bool
    facebank_root: Path
    max_request_bytes: int = 20 * 1024 * 1024
    max_image_bytes: int = 5 * 1024 * 1024
    max_image_pixels: int = 16_000_000
    max_facebank_entries: int = 200

    @classmethod
    def from_environment(cls) -> "ServiceConfig":
        development_mode = os.environ.get("RECOGNITION_DEVELOPMENT_MODE", "").lower() == "true"
        token = os.environ.get("RECOGNITION_SHARED_TOKEN", "")
        if not token and not development_mode:
            token = ""
        root = Path(os.environ.get("RECOGNITION_FACEBANK_ROOT", "data/recognition-facebanks"))
        return cls(shared_token=token, development_mode=development_mode, facebank_root=root)

    @property
    def configured(self) -> bool:
        return self.development_mode or bool(self.shared_token)


def create_app(config: ServiceConfig | None = None, store: FacebankStore | None = None) -> Flask:
    config = config or ServiceConfig.from_environment()
    app = Flask(__name__)
    app.logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())
    app.config["MAX_CONTENT_LENGTH"] = config.max_request_bytes
    store = store or FacebankStore(config.facebank_root, MtcnnMobileFaceNetEngine())

    def response(payload: dict, status: int = 200):
        payload["request_id"] = g.request_id
        return jsonify(payload), status

    @app.before_request
    def request_context():
        supplied = request.headers.get("X-Request-ID", "")
        g.request_id = supplied if supplied and len(supplied) <= 128 and supplied.isascii() else str(uuid.uuid4())
        if request.path != "/health" and not config.configured:
            return response({"error": {"code": "SERVICE_MISCONFIGURED", "message": "Recognition authentication is not configured."}}, 503)
        if request.path.startswith("/internal/") and not config.development_mode:
            bearer = request.headers.get("Authorization", "")
            if not bearer.startswith("Bearer ") or not secrets.compare_digest(bearer[7:], config.shared_token):
                return response({"error": {"code": "UNAUTHORIZED", "message": "Authentication is required."}}, 401)
        if request.path.startswith("/internal/") and request.method in {"POST", "PUT"}:
            if not request.is_json or not isinstance(request.get_json(silent=True), dict):
                return response({"error": {"code": "INVALID_REQUEST", "message": "A JSON object request body is required."}}, 400)

    @app.after_request
    def add_request_id(http_response: Response):
        request_id = g.get("request_id", str(uuid.uuid4()))
        http_response.headers["X-Request-ID"] = request_id
        app.logger.info(
            "request_completed request_id=%s method=%s path=%s status=%s",
            request_id,
            request.method,
            request.path,
            http_response.status_code,
        )
        return http_response

    @app.errorhandler(RecognitionInputError)
    def invalid_recognition_input(error: RecognitionInputError):
        return response({"error": {"code": "INVALID_RECOGNITION_INPUT", "message": str(error)}}, 422)

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(_: RequestEntityTooLarge):
        return response({"error": {"code": "REQUEST_TOO_LARGE", "message": "Request exceeds the configured size limit."}}, 413)

    @app.errorhandler(HTTPException)
    def http_error(error: HTTPException):
        return response({"error": {"code": "HTTP_ERROR", "message": "The request cannot be processed."}}, error.code)

    @app.errorhandler(Exception)
    def unexpected_error(error: Exception):
        app.logger.exception("Recognition service request failed", exc_info=error)
        return response({"error": {"code": "INTERNAL_ERROR", "message": "Recognition processing failed."}}, 500)

    @app.get("/health")
    def health():
        return response(
            {
                "status": "ok" if config.configured else "misconfigured",
                "service": "recognition-service",
                "models_loaded": store.model_loaded,
            },
            200 if config.configured else 503,
        )

    @app.get("/internal/v1/facebanks/<facebank_id>")
    def facebank_status(facebank_id: str):
        return response({"facebank_id": facebank_id, **store.status(facebank_id)})

    @app.post("/internal/v1/facebanks/<facebank_id>/build")
    def build_facebank(facebank_id: str):
        entries = request.get_json()["entries"]
        if not isinstance(entries, list) or not entries or len(entries) > config.max_facebank_entries:
            raise RecognitionInputError(f"entries must contain between 1 and {config.max_facebank_entries} items.")
        parsed = []
        student_ids = set()
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("student_id"), int) or entry["student_id"] <= 0:
                raise RecognitionInputError("Each entry must include a positive integer student_id.")
            if entry["student_id"] in student_ids:
                raise RecognitionInputError("Each facebank student_id must be unique.")
            student_ids.add(entry["student_id"])
            parsed.append((entry["student_id"], decode_image(entry.get("image_base64"), config.max_image_bytes, config.max_image_pixels)))
        return response({"facebank_id": facebank_id, "status": "READY", "entry_count": store.build(facebank_id, parsed)}, 201)

    @app.post("/internal/v1/recognitions")
    def recognize():
        payload = request.get_json()
        facebank_id = payload.get("facebank_id")
        if not isinstance(facebank_id, str):
            raise RecognitionInputError("facebank_id is required.")
        image = decode_image(payload.get("image_base64"), config.max_image_bytes, config.max_image_pixels)
        match = store.recognize(facebank_id, image)
        return response(
            {
                "result": {
                    "status": "MATCHED" if match.student_id is not None else "NO_MATCH",
                    "recognized_student_id": match.student_id,
                    "confidence": match.confidence,
                }
            }
        )

    return app


app = create_app()

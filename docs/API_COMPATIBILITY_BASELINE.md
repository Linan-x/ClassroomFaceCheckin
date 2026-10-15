# Flask API Compatibility Baseline

This document records the public Flask behavior preserved during phase one of
the Java business-service migration. The Python/Flask application remains the
system of record; no Java service is introduced by this phase.

## Runtime contract

- Start the unified web service with `python start_all.py`; it listens on port
  `8090` by default.
- Runtime data remains under `data/`; model files remain under
  `work_space/`. Neither location is deleted or recreated during startup.
- `GET /health` returns `200` with `status: "ok"` and does not initialize face
  recognition models. `models_loaded` reports whether a recognition endpoint
  has initialized them in the current process.
- JSON API failures use `{"error": "..."}`. Malformed JSON returns `400`
  without a traceback; unexpected API failures return the generic
  `服务器内部错误` message.

## Existing endpoint families

| Area | Public route prefix | Compatibility behavior |
| --- | --- | --- |
| Meeting management | `/api/meetings`, `/api/meeting/<name>` | Existing CRUD payloads, status codes, and Chinese validation messages are retained. |
| Participants and metadata | `/api/meeting/<name>/participants` | Existing multipart photo upload, batch, metadata, search, and export workflows remain available. |
| Attendance and reports | `/api/meeting/<name>/checkin*`, `/api/meeting/<name>/report` | Session-scoped records, check-in codes, CSV, and HTML exports are unchanged. |
| Classes and students | `/api/classes`, `/api/global-*`, `/api/class/*` | Global class/student indices and class facebanks retain their existing JSON/file layout. |
| Mobile client | `/api/mobile/*` | WeChat multipart/base64 recognition request formats and response fields are unchanged. |
| Browser pages | `/`, `/kiosk/*`, `/register/*`, `/dashboard/*` | Existing template routes and page URLs are unchanged. |

## Phase-one boundaries

- The legacy `core/` business modules still provide persistence and business
  operations, including JSON, NumPy, and PyTorch file access.
- Recognition initialization is now isolated in
  `checkin_web.recognition.RecognitionService`; routes use the same lazy,
  process-local model instances as before.
- This is a compatibility baseline, not an authentication, authorization, or
  database migration. Those concerns remain for later phases.

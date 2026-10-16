# Flask API Compatibility Baseline

This document records the public Flask behavior preserved during the staged
Java business-service migration. The Python/Flask application remains the
system of record for its existing routes; no Flask endpoint is replaced in
this phase.

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

## Phase-three additive Java mapping

The Spring service adds a separate, versioned API on port `8081`; it does not
proxy or alter any Flask route. Legacy concepts map as follows:

| Legacy JSON/file concept | Additive Java API/database concept | Limitation |
| --- | --- | --- |
| `data/classes.json` | `classrooms` / `/api/v1/classrooms` | Names become stable imported keys and generated codes. |
| `data/students_index.json` | `students` / `/api/v1/students` | Name-based legacy identities are ambiguous where duplicate names existed. |
| `data/courses/*/meeting_info.json` | `courses` / `/api/v1/courses` and course/class links | Legacy directory names become import keys. |
| Student `courses` lists | `enrollments` | Only students present in the global index can be enrolled. |
| `sessions.json` | `checkin_sessions` | The active session is `ACTIVE`; older sessions import as `ENDED`. |
| Local image paths | `student_photos.storage_uri` metadata | References are non-public; no files or biometric data are copied or served. |

Legacy attendance JSON, facebanks, vector embeddings, Flask attendance
execution, and mobile recognition payloads remain exclusively in the Python
runtime for the next phase.

# Recognition service boundary

Phase 4 keeps the legacy Flask web routes intact and adds a separate, internal-only
Python service for MTCNN/MobileFaceNet inference. It has no MySQL credentials and
never writes attendance records. The Spring Boot business service is the only
component that turns a recognition result into an attendance write.

## Services and boundaries

| Service | URL | Responsibility |
|---|---|---|
| Legacy Flask UI | `http://localhost:5000` | Existing browser-facing routes; unchanged |
| Spring business service | `http://localhost:8081` | Course/session authorization, enrollment check, transactional attendance |
| Python recognition service | `http://recognition-service:8090` inside Compose | Internal facebank build/status and inference only |
| MySQL | `mysql:3306` inside Compose | Authoritative course, enrollment, and attendance state |
| Redis | `redis:6379` inside Compose | Optional short-lived assistance only; never attendance authority |

Do not expose port 8090 publicly. MySQL, Redis, and the recognition service are
all Compose-internal services; the Compose file does not bind their ports to the
host. This avoids collisions with a locally installed MySQL or Redis instance.

## Authentication and configuration

Every `/internal/v1/*` Python endpoint requires
`Authorization: Bearer $RECOGNITION_SHARED_TOKEN`. Set a high-entropy value before
starting the stack:

```powershell
$env:RECOGNITION_SHARED_TOKEN = [guid]::NewGuid().Guid + [guid]::NewGuid().Guid
docker compose -f business-service/compose.yaml up --build
```

The service fails closed outside development mode: without
`RECOGNITION_SHARED_TOKEN`, `/health` reports `503` and internal requests are
rejected. `RECOGNITION_DEVELOPMENT_MODE=true` is an explicit local-development
exception and must never be used in deployment.

Spring integration is disabled by default (`RECOGNITION_ENABLED=false`). Enabling
it requires `RECOGNITION_BASE_URL` and `RECOGNITION_SHARED_TOKEN`; it uses a 1s
connection timeout and a 5s read timeout by default. A remote failure produces a
safe `RECOGNITION_UNAVAILABLE` response—there is no local or database fallback.

## Internal API contract

All bodies are JSON, image values are base64 (not data URLs), and each response
contains `request_id` and sends it in `X-Request-ID`. Requests are bounded to 20
MiB, individual images to 5 MiB/16 megapixels, and a facebank build to 200 entries.

* `GET /health` reports configuration and whether models are loaded. It does not
  load models.
* `POST /internal/v1/facebanks/{facebankId}/build` builds a local artifact from
  `{ "entries": [{ "student_id": 1, "image_base64": "..." }] }`.
* `GET /internal/v1/facebanks/{facebankId}` reports `MISSING` or `READY`.
* `POST /internal/v1/recognitions` receives
  `{ "facebank_id": "...", "image_base64": "..." }` and returns either a matched
  student ID and distance confidence or `NO_MATCH`.

Only trusted administrative backend work should build a facebank. The recognition
service does not accept storage paths, course IDs, MySQL connection values, or
attendance metadata.

## Attendance API

`POST /api/v1/checkin-sessions/{sessionId}/attendance/recognize` calls the internal
service and accepts:

```json
{ "facebankId": "course-42-v1", "imageBase64": "..." }
```

The business service resolves the session and course itself, rejects closed
sessions, verifies that the recognized student exists and is enrolled, and then
writes an `attendance_records` row. The database constraint on
`(checkin_session_id, student_id)` makes retries idempotent; a duplicate returns
the existing record with `alreadyRecorded: true`. Existing frontend clients should
continue using legacy Flask APIs until a later integration phase.

## Test setup

Python contract tests stub the model engine:

```powershell
python -m pytest tests/test_recognition_service.py
```

Java tests use H2 and mock the remote recognition client:

```powershell
Set-Location business-service
mvn test
```

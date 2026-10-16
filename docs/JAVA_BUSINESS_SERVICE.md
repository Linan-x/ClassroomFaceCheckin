# Java Business Service Foundation

`business-service/` is an independent Java 21 / Spring Boot 3 service. It is
the foundation for the future transactional business API; it does **not**
replace, proxy, or change the legacy Flask service in this phase.

The Flask service remains available at `http://localhost:8090` when started
with `python start_all.py`. Its JSON files, photos, facebanks, model assets,
and routes are not read or modified by the Java service.

## Phase 5 compatibility and realtime rollout

The Java adapter is **additive and disabled by default**. It preserves Flask
routes and is intended only for a controlled, per-client migration after the
legacy `data/` import has completed. When enabled, it exposes the active
mini-program surfaces beneath `/api/compat`:

| Legacy shape | Compatibility route | Notes |
| --- | --- | --- |
| `GET /api/mobile/courses` | `GET /api/compat/mobile/courses` | Keeps `name`, progress counts, and rate fields. |
| `/api/course/{name}/sessions` | `/api/compat/course/{name}/sessions` | Course names are resolved once at the boundary through imported legacy keys; business logic uses numeric IDs. |
| `POST /api/mobile/checkin` | `POST /api/compat/mobile/checkin` | Multipart `course`, optional `session`, and `image`; delegates to the transactional Java attendance service and the isolated recognition service. |
| `GET /api/mobile/checkin/result` | `GET /api/compat/mobile/checkin/result` | Keeps the legacy result envelope. Newer Java-only session IDs are returned as `java-{id}`. |

Enable it only after setting all of the following environment variables:

```powershell
$env:COMPATIBILITY_ENABLED = "true"
$env:COMPAT_FACEBANK_ID_TEMPLATE = "course-%d-v1"
$env:COMPAT_MAX_IMAGE_BYTES = "5000000"
$env:COMPAT_CHECKINS_PER_MINUTE = "30"
$env:REALTIME_ENABLED = "true"
$env:REALTIME_MAX_EVENTS_PER_SESSION = "200"
$env:DASHBOARD_TOKEN = "replace-with-a-long-random-secret"
```

`COMPAT_FACEBANK_ID_TEMPLATE` must name facebanks that resolve to Java student
IDs in the recognition service. The adapter accepts JPEG/PNG uploads only,
rejects bodies above `COMPAT_MAX_IMAGE_BYTES`, and uses Redis to rate-limit
check-ins per client address. Redis failure is surfaced rather than bypassed.

Successful, newly-created attendance rows publish an `attendance-recorded`
event only after their transaction commits. Redis retains at most
`REALTIME_MAX_EVENTS_PER_SESSION` JSON events per session and fans out live
events through Redis pub/sub, so dashboard SSE connections can be served by
any Java instance. A dashboard can open
`GET /api/v1/checkin-sessions/{id}/events?token=...` as an SSE stream; the
endpoint requires the configured dashboard token and replays that bounded
backlog before streaming live events. Duplicate attendance responses do not
create an event.

To migrate one mini-program build, set `compatibilityMode: true` and
`compatibilityServerUrl` to the Spring service in `weapp/app.js` (or inject
the same values in its build configuration). The committed defaults remain
`false` and empty, so production clients keep their Flask URL. Validate course
list, session creation, recognition, results, and dashboard events for one
course before increasing adoption.

**Rollback:** set `compatibilityMode` back to `false`, or set
`COMPATIBILITY_ENABLED=false` and redeploy Java. Flask endpoints and legacy
data are untouched, so clients immediately resume the existing behavior.

## Development prerequisites

- JDK 21
- Docker Desktop or another Docker-compatible daemon

The Maven wrapper is committed with the module. Start MySQL 8 and Redis:

```powershell
Set-Location business-service
docker compose up -d
```

The compose credentials are intentionally local-only placeholders. Set real,
unique secrets with environment variables before any deployed use:

```powershell
$env:DB_URL = "jdbc:mysql://localhost:3306/classroom_face_checkin?useUnicode=true&characterEncoding=utf8&serverTimezone=UTC"
$env:DB_USERNAME = "classroom"
$env:DB_PASSWORD = "replace-with-a-secret"
$env:REDIS_HOST = "localhost"
$env:REDIS_PORT = "6379"
$env:REDIS_PASSWORD = ""
$env:SPRING_PROFILES_ACTIVE = "dev"
.\mvnw.cmd spring-boot:run
```

The service binds to `8081` by default, avoiding Flask's port `8090`.

## Operational endpoints

- `GET /api/v1/system/info` proves the versioned API and unified response
  envelope.
- `GET /actuator/health/liveness` is the liveness probe.
- `GET /actuator/health/readiness` is the readiness probe and includes
  database and Redis availability.

The schema is managed only by Flyway. JPA validates the migrated schema at
startup and does not generate tables. The migration includes a database-level
unique constraint on `(checkin_session_id, student_id)` so a student cannot
receive duplicate attendance records in a single session.

## Tests

```powershell
Set-Location business-service
.\mvnw.cmd test
```

Tests use an in-memory H2 database in MySQL compatibility mode; they do not
connect to the Docker services.

## Current boundaries

## Core business API (phase 3)

All business endpoints are versioned under `/api/v1` and use the same
`success`, `data`, `error`, and `timestamp` response envelope as the system
endpoint. Validation failures return `400` / `VALIDATION_ERROR`, unknown IDs
return `404` / `NOT_FOUND`, and duplicate or invalid lifecycle changes return
`409`.

| Resource | Endpoints |
| --- | --- |
| Classrooms | `GET`, `POST`, and `PUT /api/v1/classrooms` |
| Students | `GET`, `POST`, and `PUT /api/v1/students`; `POST /{id}/photos` records only a `legacy://` or `storage://` metadata reference. It never serves photo bytes. |
| Courses | `GET`, `POST`, and `PUT /api/v1/courses`; `PUT /{id}/classrooms`; `PUT`/`DELETE /{courseId}/students/{studentId}`; `GET /{id}/enrollments` |
| Check-in sessions | `GET`/`POST /api/v1/courses/{id}/checkin-sessions`; `POST /api/v1/checkin-sessions/{id}/end` transitions an `ACTIVE` session to `ENDED` exactly once. |

The database schema remains Flyway-managed. This phase adds stable nullable
legacy keys for idempotent import without adding biometric embeddings or
recognition runtime behavior.

## Legacy JSON import

The optional import command reads the existing `data/` directory only; it
never changes JSON, photos, facebanks, or Flask state. Run it with the web
server disabled:

```powershell
Set-Location business-service
.\mvnw.cmd spring-boot:run "-Dspring-boot.run.arguments=--spring.main.web-application-type=none --legacy-import.enabled=true --legacy-import.root=../data --legacy-import.dry-run=true"
```

Set `--legacy-import.dry-run=false` to write mapped classes, students,
non-public photo metadata references, courses, enrollments, and sessions to
MySQL. Re-running uses legacy keys and reports existing records, so it is
idempotent. The summary prints created/existing counts and unresolvable
files or records. It intentionally does not import face embeddings,
facebanks, attendance records, or start recognition.

## Current boundaries

Flask continues unchanged at port `8090`. This service neither replaces
legacy routes nor migrates the attendance recognition/runtime flow.
Authentication and the independent Python recognition service remain later
phases.

## Production deployment

The production Compose topology, required environment values, migration
reconciliation, backup/restore, controlled rollout, and Flask rollback
procedures are in [`PRODUCTION_CUTOVER.md`](PRODUCTION_CUTOVER.md). Do not use
the former local Compose defaults for a deployment.

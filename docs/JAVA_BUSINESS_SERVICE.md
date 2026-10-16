# Java Business Service Foundation

`business-service/` is an independent Java 21 / Spring Boot 3 service. It is
the foundation for the future transactional business API; it does **not**
replace, proxy, or change the legacy Flask service in this phase.

The Flask service remains available at `http://localhost:8090` when started
with `python start_all.py`. Its JSON files, photos, facebanks, model assets,
and routes are not read or modified by the Java service.

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

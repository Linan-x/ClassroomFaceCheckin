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

This module contains only database, Redis, API-envelope, health, and
foundational-domain plumbing. Authentication, legacy data import, legacy
endpoint migration, face recognition integration, and write business flows
are intentionally deferred to later phases.

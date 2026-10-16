# Production cutover runbook

This runbook deploys the independent Spring business service, Python recognition
service, MySQL, Redis, and Nginx. It does not remove or modify Flask, its JSON
data, photos, facebanks, or model files. The compatibility adapter remains
disabled by default.

## Operator inputs

Copy `business-service/.env.example` to `business-service/.env` and replace
every placeholder. The required values are:

| Value | Purpose |
| --- | --- |
| `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD` | New MySQL database and distinct credentials. |
| `REDIS_PASSWORD` | Redis authentication; Redis is not published to the host. |
| `RECOGNITION_SHARED_TOKEN`, `DASHBOARD_TOKEN`, `FLASK_SECRET_KEY` | Separate high-entropy secrets for internal inference, dashboard SSE, and the rollback-only Flask container. |
| `SERVER_NAME`, `TLS_CERT_PATH`, `TLS_KEY_PATH` | Public DNS name and existing PEM certificate/key paths. Certificates are not generated or stored by this repository. |
| `COMPATIBILITY_ENABLED`, `REALTIME_ENABLED` | Leave both `false` until the controlled rollout checks pass. |

Only Nginx publishes host ports (HTTP 80 and HTTPS 443 by default). MySQL,
Redis, Java, and recognition ports are internal to the Compose network. Docker
named volumes retain MySQL, Redis AOF, and recognition facebanks across
container recreation. Back up named volumes before destructive Docker
operations.

## Pre-cutover verification and import

1. Take an immutable backup of the complete legacy `data/` directory while
   Flask is stopped or otherwise quiesced. Keep that backup outside the host
   running Compose.
2. Start MySQL and Redis from the production `.env`, then run a dry import.
   The importer never writes legacy JSON, photos, facebanks, attendance JSON,
   or Flask state.

   ```powershell
   Set-Location business-service
   .\mvnw.cmd spring-boot:run "-Dspring-boot.run.arguments=--spring.main.web-application-type=none --legacy-import.enabled=true --legacy-import.root=../data --legacy-import.dry-run=true"
   ```

3. Review the created/existing/unresolved summary. Correct every unresolved
   source record or explicitly retain it as legacy-only. Run again with
   `--legacy-import.dry-run=false`. The legacy keys make repeated writes
   idempotent.
4. Reconcile source and imported data:

   ```powershell
   .\scripts\verify-legacy-migration.ps1 -LegacyDataRoot ..\data
   ```

   The report compares classes, students, course directories, and sessions
   against rows carrying legacy keys. A `MISMATCH` or any
   `unmappable_records` entry blocks cutover until understood. Legacy
   `attendance.json` rows are counted but deliberately reported as
   `NOT_MIGRATED`: historical attendance has no safe stable identity mapping
   in this migration and remains available through Flask.

## Start and acceptance

Run Compose only after the import/reconciliation is accepted:

```powershell
Set-Location business-service
docker compose --env-file .env config
docker compose --env-file .env up --build -d
docker compose --env-file .env ps
```

Check Nginx `/healthz`, Java `/actuator/health/readiness`, and an authenticated
recognition health check from their intended networks. Confirm the Nginx logs
contain `request_id` and that Java returns the same value in `X-Request-ID`.
Keep `COMPATIBILITY_ENABLED=false` while normal Flask users continue to use
the legacy URL. Enable it only for one approved client cohort, then validate
course listing, sessions, recognition, transactional attendance, and SSE
events before widening rollout.

## Backup and restore

Back up the legacy data tree and MySQL independently. A MySQL logical backup
can be taken without exposing MySQL:

```powershell
docker compose --env-file .env exec -T mysql sh -c 'exec mysqldump -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' > classroom-face-checkin.sql
```

To restore into a stopped/quiesced service, verify the target database name,
then run:

```powershell
Get-Content -Raw .\classroom-face-checkin.sql | docker compose --env-file .env exec -T mysql sh -c 'exec mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"'
```

Restore the legacy data backup only with Flask stopped. Do not overwrite
production data volumes until the backup and target have been independently
verified.

## Rollback

Do not delete MySQL or Redis volumes during rollback. Set
`COMPATIBILITY_ENABLED=false`; clients configured for compatibility must set
`compatibilityMode: false` and use their original Flask URL. This restores
normal legacy behavior immediately because Flask data was never changed.

If the public proxy must return to a containerized Flask image, set
`PUBLIC_UPSTREAM=legacy-flask:8090`, provide `FLASK_SECRET_KEY`,
`LEGACY_FLASK_IMAGE`, `LEGACY_DATA_PATH`, and `LEGACY_WORKSPACE_PATH`, then
run:

```powershell
docker compose --env-file .env --profile rollback up -d legacy-flask nginx
```

`LEGACY_FLASK_IMAGE` is an operator-built image containing the existing model
runtime; this repository does not manufacture a certificate or model image.
Validate the Flask `/health` endpoint and the legacy client flows before
declaring rollback complete.

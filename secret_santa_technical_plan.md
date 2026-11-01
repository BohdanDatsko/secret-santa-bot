# Technical Specification: Secret Santa Telegram Bot


## Objective

Implement and deploy the “Secret Santa” Telegram bot on the existing Ubuntu Server `alfred`. The agent must audit the repository and server, implement the application, configure Docker, deploy it, verify operation, configure backups, and provide documentation. When repository/server access is available, perform the work rather than only generating example code.


## Existing environment and assumptions

Previous discussions mentioned Intel Celeron J1800 (2 cores, 2.41 GHz), possibly 4 GB RAM, an approximately 120 GB SSD, Ubuntu Server, hostname `alfred`, and local IP `192.168.0.210`. Jellyfin was configured but is not used continuously. Verify every detail before relying on it. Inspect other services, disks, containers, and actual resource usage. These are historical assumptions, not a current server audit.


## Functional requirements

### Participants
- Register Telegram users through `/start`.
- The organizer manually adds registered users to the game.
- Identify users by Telegram ID, not username.
- Display participants; allow removal before the draw.
- Prevent duplicate participation in the same game.
- Registration with the bot does not automatically mean participation.
- A user must start the bot at least once before it can send them a private message; Telegram bots cannot initiate arbitrary private conversations by username.

### Organizer
- One organizer configured through `ADMIN_TELEGRAM_ID`.
- Enforce authorization server-side for every administrative operation.
- Display registered users eligible to be added.
- Add/remove participants, manage excluded pairs, inspect participant count and draw feasibility, start the draw, and view game status.
- Do not rely only on hiding admin buttons.

### Excluded pairs
- The organizer defines pairs that must not be assigned to each other.
- Restrictions are symmetric: forbid both A → B and B → A.
- Reject duplicate pairs, self-pairs, participants from different games, and edits after the draw.
- Store each pair once using canonical participant ID ordering.

### Draw
- Every active participant gives to exactly one recipient and receives from exactly one giver.
- No self-assignments.
- No assignments in either direction between excluded pairs.
- If no valid complete assignment exists, notify the organizer and persist no partial result.
- A completed draw cannot be run again.
- Persist assignments transactionally before sending notifications.
- Delivery failures must not trigger a new draw.
- Use maximum bipartite matching. Test its properties. Do not claim that shuffling candidate order produces a uniform distribution over all valid assignments.

### Wishlist
- Each participant can create/edit their own plain-text wishlist, including links.
- After the draw, a giver can view only their assigned recipient’s wishlist.
- Other participants must not gain access through commands, callbacks, or direct requests.
- The organizer does not automatically receive access to other wishlists.

### Game statuses
- `SETUP`: participants and exclusions can be edited.
- `DRAWN`: draw completed and assignments fixed.
- `CANCELLED`: game cancelled.
- Do not allow participant or exclusion changes after the draw unless a separate cancellation workflow is explicitly implemented.


## Technology stack

Use Python 3.12 or a compatible stable version, aiogram 3.x, SQLAlchemy 2.x async, PostgreSQL, asyncpg, Alembic, pydantic-settings, Docker Engine/Compose, and pytest. Do not add FastAPI, Redis, Celery, a web UI, or microservices without a justified need. Use Telegram long polling; no webhook, domain, or inbound application port is required.


## Project structure

```text
secret_santa/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── bot.py
│   ├── database/
│   │   ├── base.py
│   │   ├── session.py
│   │   └── models/
│   ├── handlers/
│   │   ├── admin.py
│   │   ├── participants.py
│   │   ├── pairs.py
│   │   ├── draw.py
│   │   └── wishlist.py
│   ├── keyboards/
│   ├── states/
│   ├── services/
│   ├── repositories/
│   └── domain/
│       └── draw_algorithm.py
├── migrations/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── .env.example
├── .gitignore
├── .dockerignore
├── Dockerfile
├── compose.yaml
├── alembic.ini
├── pyproject.toml
└── README.md
```
Adjust only if this improves clarity while keeping Telegram handlers, business logic, and database access separated.


## Data models

Implement:

- `User`: internal ID, unique Telegram ID, nullable username, first name, creation timestamp. Never use username as the primary key.
- `Game`: ID, name, organizer ID, status, creation timestamp, draw completion timestamp. Keep this entity even though only one game is currently required.
- `Participant`: ID, game ID, user ID, display name, wishlist, active status. Enforce unique `(game_id, user_id)`.
- `Exclusion`: ID, game ID, two participant IDs. Enforce different IDs, canonical ordering, pair uniqueness within a game, and both participants belonging to that game.
- `Assignment`: ID, game ID, giver ID, recipient ID. Enforce unique `(game_id, giver_id)` and `(game_id, receiver_id)`, no self-assignment, same-game membership, and compliance with exclusions.

Simple foreign keys cannot enforce all cross-row and same-game invariants. Validate them in services and add database constraints where appropriate.

Import all models into Alembic metadata. Use Alembic for schema changes. Do not call `Base.metadata.create_all()` on every production startup. Test migrations against a test database before production.


## Phase 1 — Ubuntu Server audit

Before installing packages or changing configuration, inspect Ubuntu version, CPU architecture, RAM/swap/load, disk space, systemd, Docker/Compose, containers/networks/volumes, active ports, firewall, internet/DNS, SSH, existing services (including Jellyfin and Samba), media-server resource usage, and Docker data directory size if applicable.

Read-only commands:

```bash
echo "=== OS ==="
cat /etc/os-release
echo "=== CPU and load ==="
lscpu
uptime
echo "=== RAM and swap ==="
free -h
swapon --show
echo "=== Disk space ==="
df -h
echo "=== Docker ==="
systemctl is-enabled docker 2>/dev/null
systemctl is-active docker 2>/dev/null
docker compose version 2>/dev/null
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null
docker stats --no-stream 2>/dev/null
echo "=== Services ==="
systemctl is-active smbd jellyfin docker 2>/dev/null
echo "=== Firewall ==="
sudo ufw status verbose 2>/dev/null
```

Do not make changes until the audit is complete. Then report the findings and proposed changes. Do not remove or restart existing containers without impact analysis. If Docker is missing, use the official installation instructions for the detected Ubuntu version; do not run unverified third-party scripts.


## Phase 2 — application implementation

1. Configure settings with `pydantic-settings`.
2. Configure async SQLAlchemy engine and `async_sessionmaker`.
3. Implement models and Alembic migrations.
4. Implement participant, pair, draw, and wishlist services.
5. Implement Telegram handlers and inline keyboards.
6. Implement FSM flows where data entry requires them.
7. Add logging and error handling.
8. Close database sessions and resources correctly during shutdown.
9. Never log tokens, passwords, wishlists, or full draw results.

Telegram handlers must call application services. Business logic must not depend on the Telegram API and must be independently testable.


## Phase 3 — draw algorithm and transactions

Implement a dedicated `DrawService` and an independent algorithm function.

Within a transaction: lock the game row using `SELECT ... FOR UPDATE`; verify organizer permissions and `SETUP` status; load active participants and exclusions; check feasibility; run maximum bipartite matching; validate invariants; persist all assignments; set status to `DRAWN` and record the timestamp; commit.

Only after commit, send Telegram notifications.

Do not send messages inside the database transaction. Do not leave partial assignments. Prevent concurrent draw attempts. If no complete assignment exists, keep the game in `SETUP`. A repeated request must not create new assignments. Delivery failures must not modify results.

For reliable delivery, implement a `notification_outbox` table or equivalent durable retry mechanism. Retries must use persisted assignments and must never rerun the draw.


## Phase 4 — Docker and Compose

Create a Dockerfile, `compose.yaml`, `bot` and `db` services, persistent PostgreSQL volume, PostgreSQL healthcheck, restart policies, internal Docker network, and secure secret configuration.

Requirements:
- Do not publish PostgreSQL on all host interfaces.
- Do not expose an inbound bot port; use long polling.
- Do not run the Python process as root in the container.
- Pin a stable PostgreSQL version; do not use `latest`.
- Persist database data in a volume.
- Do not copy `.env` into the image.
- Add `.dockerignore` and `.gitignore`.
- Handle `SIGTERM` and graceful shutdown.
- Limit Docker log size.

Use this restart policy for both services:

```yaml
services:
  bot:
    restart: unless-stopped

  db:
    restart: unless-stopped
```

This is a fragment to merge into the complete Compose file. Never delete Docker volumes during normal application updates.


## Phase 5 — secrets and security

Configure `BOT_TOKEN`, `ADMIN_TELEGRAM_ID`, `DATABASE_URL`, and `POSTGRES_PASSWORD`.

- Keep `.env` out of Git and restrict its server-side permissions.
- Never log secrets; do not use real tokens in tests.
- Avoid passing secrets as command-line arguments that may remain in shell history.
- Do not use `privileged: true` or mount the Docker socket into the bot container.
- Restrict network access.
- Do not change SSH authentication or disable password access until key-based authentication and an alternative access path are verified.
- Do not change firewall rules without analyzing effects on Docker and existing services.


## Phase 6 — deployment

1. Prepare the application directory.
2. Transfer code using Git or another controlled method.
3. Create production `.env` outside the repository.
4. Validate Compose configuration.
5. Start PostgreSQL and wait for its healthcheck.
6. Run Alembic migrations.
7. Start the bot.
8. Inspect logs.
9. Test `/start` and organizer authorization.
10. Verify operation after container and server restarts.

Use `docker compose config` for validation, but do not publish output containing secrets. Never run `docker compose down -v`, delete volumes, clean `/var/lib/docker`, or perform destructive operations without explicit approval.


## Phase 7 — automatic startup

Check Docker startup configuration:

```bash
systemctl is-enabled docker
systemctl is-active docker
```

If Docker is installed but not enabled at boot:

```bash
sudo systemctl enable --now docker
```

Do not reinstall Docker without a technical reason.

After Ubuntu boots, systemd starts Docker; Docker restores containers configured with `unless-stopped`; PostgreSQL passes its healthcheck; then the bot starts and connects to PostgreSQL and Telegram. The bot must retry database connections after temporary failures. Temporary internet loss must not require a manual restart.

Perform a controlled reboot and verify Docker, PostgreSQL, bot status, data persistence, `/start`, absence of duplicate assignments, and that the draw is not automatically rerun.


## Phase 8 — prevent automatic sleep

Audit `systemd-logind`, `/etc/systemd/logind.conf`, `/etc/systemd/logind.conf.d/`, automatic suspend/hibernate mechanisms, desktop environment, and third-party power-management services.

If the server can enter sleep automatically, configure the actual mechanism to prevent idle-triggered sleep. For a headless Ubuntu Server, consider this drop-in only after inspecting current settings:

```ini
# /etc/systemd/logind.conf.d/60-always-on.conf

[Login]
IdleAction=ignore
HandlePowerKey=ignore
HandleSuspendKey=ignore
HandleHibernateKey=ignore
```

Do not overwrite the entire `logind.conf`. Do not set `HandleLidSwitch` unless this is a laptop with a lid. If another mechanism controls sleep, configure that mechanism instead. Validate changes and restart the relevant service only at a safe time. Do not trigger suspend/hibernate as a test.

Acceptance: the server does not enter sleep due to idle timeout; Docker and the bot remain active; Jellyfin and other services continue working; normal shutdown and reboot remain possible.


## Phase 9 — recovery after power outages

Check whether BIOS/UEFI supports automatic startup after power is restored. Look for options such as `Restore on AC Power Loss`, `AC Power Recovery`, `After Power Failure`, or `State After G3`.

If available, configure `Power On` or the equivalent. Do not change unrelated BIOS settings. If the agent has no physical BIOS access, provide precise manual instructions.

Before testing, ensure data is saved and a recent backup exists. Do not forcibly power off during database operations. Do not perform a physical power-loss test without user approval. If hardware auto-start is unsupported or unverified, record this limitation. Docker cannot power on a physically switched-off server.


## Phase 10 — monitoring and logs

Provide status commands:

```bash
docker compose ps
docker compose logs --tail=100 bot
docker compose logs --tail=100 db
systemctl status docker
```

Run them from the directory containing production `compose.yaml`, or specify its path. Configure Docker log rotation so logs cannot fill the SSD. Do not delete system logs without inspecting their configuration.

Document service status, log viewing, bot/service restarts, Telegram API connectivity checks, PostgreSQL checks, network troubleshooting, and low-disk-space procedures.


## Phase 11 — backups

Implement daily PostgreSQL backups using `pg_dump`.

Requirements: restorable format; timestamped filenames; restricted permissions; retention/rotation; several recent backups; a copy outside the primary disk or server; success/failure logging; documented restore procedure.

Do not consider backups verified until a test restore into a separate database succeeds. If external storage is not configured, document it as an unmet requirement. A backup on the same disk does not protect against disk failure.


## Phase 12 — testing

### Unit tests
Test successful draws, prevention of self-assignments, both directions of excluded pairs, giver/recipient uniqueness, impossible combinations, duplicate IDs, invalid exclusions, and wishlist access rules.

### Integration tests
Test user creation, participant addition, pair creation/deletion, transaction handling, prevention of repeated draws, database-error behavior, concurrent draw requests, notification retries, and state recovery after restart.

### Manual Telegram tests
Test `/start`, admin menu, adding/removing participants, excluded pairs, draw, result delivery, wishlist access, and handling users who blocked the bot.

Tests must verify assignment properties, not a particular random result.


## Phase 13 — documentation

Create a README covering application purpose, technology stack, project structure, local setup, environment variables, tests, migrations, Ubuntu deployment, automatic startup, sleep configuration, logs, restart/update procedures, backups, database restoration, and troubleshooting.

Include working commands but no real secrets, passwords, or tokens.


## Acceptance criteria

The work is complete only when:
- The application runs on Ubuntu Server and uses Telegram long polling.
- PostgreSQL data survives container and server restarts.
- Migrations and automated tests pass.
- Draws respect all constraints; impossible draws create no partial assignments.
- Repeated draw requests do not change completed assignments.
- Wishlists are accessible only to authorized users.
- Failed notifications can be retried.
- Docker starts automatically after Ubuntu boots and containers recover after reboot.
- Ubuntu does not automatically sleep through the configured mechanisms.
- BIOS power-recovery settings are verified or explicitly marked unverified.
- Docker logs have size limits.
- A controlled reboot test passes.
- Backups are configured and a test restore succeeds.
- README contains maintenance instructions.


## Automation restrictions

Without explicit approval, the agent must not force shutdown/reboot, change BIOS settings, disable unrelated services, delete Docker volumes, clean `/var/lib/docker`, change network interfaces/firewall rules without impact analysis, perform destructive power-loss tests, or change SSH settings in a way that could lock out remote access.

If access is unavailable, provide exact manual instructions and mark checks incomplete.


## Final report

After completion, provide:
1. Server state before changes.
2. Created/modified files.
3. Applied migrations.
4. Test results.
5. Docker Compose validation.
6. Container status.
7. Telegram smoke-test result.
8. Automatic startup verification after reboot.
9. Sleep-mode verification.
10. BIOS power-recovery status.
11. Backup and test-restore results.
12. Commands for logs, restart, and updates.
13. Incomplete requirements and known risks.

Never claim success without actual verification.


## Execution order

1. Audit environment and repository.
2. Propose changes.
3. Implement application.
4. Run automated tests.
5. Validate configuration.
6. Deploy.
7. Verify operation.
8. Verify automatic startup.
9. Configure continuous operation and sleep prevention.
10. Configure backups and test restoration.
11. Document and report.

Start with the server and repository audit. Do not install packages or change system settings before the audit is complete. If required access is unavailable, ask for it. Never invent SSH credentials, IP addresses, tokens, or passwords.

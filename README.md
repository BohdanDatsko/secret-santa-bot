# Secret Santa Telegram Bot

An asynchronous Telegram bot for managing a Secret Santa game: user
registration, organizer-managed participants, symmetric exclusions, draw
generation using a complete bipartite matching algorithm, wishlists, and
reliable result delivery through a persistent notification queue.

The bot uses long polling. It does not need an inbound port, webhook, Redis, or
a web server. Registering with `/start` does not automatically add a user to a
game.

## Technology stack

- Python 3.12
- aiogram 3
- SQLAlchemy 2 async and asyncpg
- PostgreSQL 16
- Alembic
- pytest and SQLite for integration tests
- Docker Compose

## Project structure

```text
app/
  database/models/    ORM models
  domain/             Standalone draw algorithm
  handlers/           Telegram handlers
  services/           Business logic and data access
  states/             Telegram FSM states
migrations/            Alembic migrations
tests/unit/            Algorithm tests
tests/integration/     Service and transaction tests
scripts/               Operational scripts
```

## Local setup

You need Python 3.12, `uv`, Docker Engine with the Compose plugin, and a
Telegram bot token. On Windows, install `uv` with
`winget install --id astral-sh.uv --exact`, then restart the terminal.

1. Copy `.env.example` to `.env`.
2. Set `BOT_TOKEN`, the organizer's numeric `ADMIN_TELEGRAM_ID`, and a strong,
   randomly generated `POSTGRES_PASSWORD`. Use matching PostgreSQL credentials
   in `DATABASE_URL`. Do not commit `.env`.
3. Validate Compose configuration and start the application:

   ```sh
   docker compose config --quiet
   docker compose up --build -d
   docker compose ps
   ```

Compose starts PostgreSQL without publishing its port, waits for its
healthcheck, applies Alembic migrations, and runs the bot as a non-root user.
The `postgres_data` volume persists across container updates.

To run locally without Docker, you need PostgreSQL and `uv`. After installing
`uv`, restart your terminal so the updated `PATH` is available, or run `uv`
using its full installation path. In the project directory, create `.env`
from `.env.example`, then run:

```sh
uv sync --extra dev
uv run alembic upgrade head
uv run python -m app.main
```

`uv sync` creates or updates `.venv` and installs the dependencies pinned in
`uv.lock`.

## Configuration

| Variable | Purpose |
|---|---|
| `BOT_TOKEN` | Token issued by BotFather |
| `ADMIN_TELEGRAM_ID` | Telegram ID of the sole organizer |
| `DATABASE_URL` | SQLAlchemy async URL for PostgreSQL |
| `POSTGRES_DB` | Database name used by Compose |
| `POSTGRES_USER` | PostgreSQL user used by Compose |
| `POSTGRES_PASSWORD` | PostgreSQL password; passed only to the database container |
| `LOG_LEVEL` | Logging level; defaults to `INFO` |

Tests use dummy credentials only. Logs do not include tokens, passwords,
wishlists, or draw results.

## Using the bot

### Participants

- Send `/start` to register your Telegram profile.
- The organizer uses `/admin` to manually add registered users to a game.
- Participants can edit their own wishlist with `/wishlist` and view their
  assigned recipient's wishlist with `/gift` after the draw.
- `/gift` only returns the recipient assigned to the requesting user. Users
  cannot access other participants' wishlists arbitrarily.

### Organizer

- `/admin` — open the current game's menu.
- **Нова гра** in `/admin` — create a game and make it current; the bot asks
  for its name. `/new_game Name` remains available as a shortcut.
- `/cancel_game` — cancel the current game while it is in `SETUP`.
- After a draw, use **Скасувати жеребкування** in `/admin` only before any
  notification attempt; this removes the unsent assignments and returns the
  game to `SETUP`, where a new draw can be run.
- Use the menu to view and manage participants, configure symmetric exclusions,
  check whether a complete assignment is possible, and confirm the draw.
- `/retry_notifications` — make failed notifications eligible for delivery
  again.

All administrative operations validate the Telegram ID and game ownership on
the server. Participants and exclusions cannot be changed after the game
reaches `DRAWN`. Once notification delivery has been attempted, the draw cannot
be cancelled or changed; create a new game with `/new_game Name` instead. A new
game does not copy participants or exclusions automatically.

The draw algorithm finds a complete matching using augmenting paths. Candidate
orders are shuffled for variety, but this **does not guarantee a uniform
distribution** among all valid assignments.

## Migrations and tests

```sh
uv sync --extra dev
uv run pytest
uv run alembic upgrade head
```

Service tests use an in-memory SQLite database. Production schemas are managed
only by Alembic migrations, not by `metadata.create_all()`. Before applying a
migration in production, test it against a copy of the database.

## Docker operations

Check service status and view logs:

```sh
docker compose ps
docker compose logs --tail=100 bot
docker compose logs --tail=100 db
```

Restart or update the application:

```sh
docker compose restart bot
docker compose up --build -d
```

Do not use `docker compose down -v` for routine updates. Both services rotate
their logs at `10m` × `3`. Temporary database connection failures during
startup are retried with exponential backoff; each Telegram update gets a new
database session. Telegram delivery failures are retried with a delay.
Delivery is **at least once**: a crash after Telegram accepts a message but
before the outbox entry is marked `DELIVERED` can result in a duplicate
message.

## Ubuntu Server deployment

This repository is prepared for deployment, but the `alfred` server was not
accessible from this environment. Its OS, resources, Docker installation,
firewall, SSH, existing services/Jellyfin, sleep settings, BIOS, restart
behavior, and Telegram connectivity with a production token have not been
verified. Do not change the server before completing the read-only audit in
the technical plan.

Before deploying:

1. Audit the host and Docker; check disk space and existing services.
2. Install Docker only by following the official instructions for the
   server's actual Ubuntu version.
3. Place the project in a controlled directory, create `.env` with file
   permissions set to `600`, and run `docker compose config --quiet`.
4. Start Compose and verify the migration, logs, and `/start`.
5. Verify Docker auto-start separately. Do not change firewall, SSH, logind,
   or BIOS settings without first assessing the impact and confirming access.

## Backups and recovery

`scripts/backup_postgres.sh` creates a custom-format `pg_dump`, restricts file
permissions, and copies backups with rsync to a **required off-server
destination**. It retains the latest 14 days locally and remotely. Create a
dedicated directory on the remote storage and set `BACKUP_REMOTE` in cron, for
example:

```cron
15 3 * * * BACKUP_REMOTE=backup@nas:/srv/secret-santa bash /opt/secret-santa/scripts/backup_postgres.sh >> /var/log/secret-santa-backup.log 2>&1
```

Verify rsync access to the remote storage separately and restrict the SSH key
permissions. Backup creation or transfer failures return a non-zero exit code.
Without `BACKUP_REMOTE`, the script does not create a local-only backup that
could be mistaken for a complete backup.

Test recovery into a separate database, never over production:

```sh
docker compose exec -T db sh -c 'createdb -U "$POSTGRES_USER" secret_santa_restore'
docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d secret_santa_restore --no-owner < backups/secret-santa-TIMESTAMP.dump
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d secret_santa_restore -c "\dt"'
```

The cron job, remote storage access, and test restore must be verified after
deployment. This local workspace does not prove that these steps have been
performed.

## Troubleshooting

- `docker compose ps` — check the `bot` and `db` service states.
- Container logs — look for database, migration, or Telegram API errors. Do
  not publish configuration output that might contain secrets.
- DNS or Telegram connectivity issues — check the host's network and DNS
  without opening inbound bot ports.
- Low disk space — check `df -h`, Docker logs, and backups. Do not clean
  `/var/lib/docker` or delete volumes without assessing the impact.
- If a participant has blocked the bot, delivery attempts will continue with
  backoff. The organizer can retry pending notifications after the participant
  opens the bot again.

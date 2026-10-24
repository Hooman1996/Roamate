# Design M0.2: infrastructure, conda environment and `.env` settings

| | |
| --- | --- |
| **Status** | draft, revision 2 (updated after review 1); not approved |
| **Date** | 24 October 2026 |
| **Approved by** | not yet (hooman) |
| **Supersedes** | revision 1 of the same day |
| **Plan reference** | [implementation plan](../plan/implementation-plan.md) v3.0, §4, §5, §6 |
| **Gate before approval** | the server facts in §8 are filled into the [compatibility manifest](00-compatibility-manifest.md) |

This design fixes where Roamate's services run, how Roamate stays separate from RagBot on the same server, how a developer sets up the environment, and every setting in `.env`. Nothing here is coded until it is approved.

**Changes in revision 2 (review 1):** two Postgres roles and an honest statement of what they isolate (F06); Qdrant separation stated as a development boundary with a plan for Beta (F07); four buckets everywhere (F08); Compose project and names of its own, profiles, loopback ports, root-relative commands, dependency locks, and a launcher that really uses `APP_PORT` (F09); health split into live, ready and admin diagnostics (F10); no shared service is ever stopped, and a separate lab TEI for embedding experiments (F05); 9Router opt-in (F22); routing provisional on the M0.16 spike (F33, F42).

---

## 1. Services Roamate connects to

Roamate reuses the containers already running for RagBot. Default addresses below come from RagBot's `.env.example`; the real values go in Roamate's `.env` and the real versions in the compatibility manifest.

| Service | Existing container | Default address | What Roamate owns there |
| --- | --- | --- | --- |
| PostgreSQL | `postgres-server` | `localhost:5432` | Database `roamate`, owned by role `roamate_owner`; runtime role `roamate_app` |
| Qdrant | `qdrant-server` (`qdrant/qdrant:v1.16.2`) | `http://localhost:6333` | Collections whose names start with `roamate_`, and the alias `roamate_places` |
| MinIO | `minio-server` | `localhost:9000` (S3 API) | Buckets `roamate-media`, `roamate-tiles`, `roamate-routing`, `roamate-raw` |
| TEI embedding | `tei-embedding` | `http://localhost:7997` | Nothing stored; read-only use, at most 4 parallel requests |
| TEI reranker | `tei-reranker` | `http://localhost:7998` | Nothing stored; read-only use, at most 4 parallel requests |
| vLLM | `gemma4-vllm` | `http://localhost:8000/v1` | Nothing stored; read-only use, at most 2 parallel requests |

Roamate's own services (Compose project `roamate`, §3):

| Service | Container | Address | Notes |
| --- | --- | --- | --- |
| Routing | `roamate-routing` (Valhalla, tag pinned in M1) | `127.0.0.1:8002` | Provisional until the M0.16 spike; data in volume `roamate-routing-data`, one directory per routing version |
| Embedding lab | `roamate-tei-lab` | `127.0.0.1:7999` | Started only for embedding experiments (M8.7), and only when the GPU has room; never replaces RagBot's TEI |
| 9Router | not installed | `127.0.0.1:20128/v1` | Opt-in, M4.3, only after its upstream accounts are checked |

Roamate's own processes:

| Process | Port | How it runs during development (from the repository root) |
| --- | --- | --- |
| Backend (FastAPI) | `APP_PORT`, default `8100` | `python -m app` (in `backend/`), which starts Uvicorn with `APP_HOST` and `APP_PORT` from `.env`; 8000 is taken by vLLM |
| Worker | none | `python -m app.worker` (in `backend/`), runs planning, ingestion and publish jobs |
| Web app (Vite dev server) | `5173` | `npm --prefix web run dev`; it forwards `/api` to the backend, so the browser sees one origin |

In production (M12) the web app is built into static files and served by the backend behind Caddy (TLS), so there is a single origin and port.

---

## 2. Keeping Roamate separate from RagBot

### Rules

1. **Roamate never stops, restarts or reconfigures a RagBot service.** Failure tests use a fake provider or a deliberately wrong Roamate address. This replaces the earlier "stop vLLM" demonstration in M4.
2. **Setup scripts are dry-run first.** Each script prints exactly what it will create and needs `--apply` to do it. It refuses any database, role, collection or bucket name that does not start with `roamate`, and it never drops anything.
3. **Admin logins** for Postgres, MinIO and Qdrant are typed in when a setup script runs. They are never stored in Roamate's `.env`.
4. **Request caps** on shared endpoints (settings in §5) keep Roamate from crowding out RagBot. M12.12 measures RagBot's latency while Roamate is under load.

### What each service separates, honestly

| Service | Separation | What we can claim | Who creates it |
| --- | --- | --- | --- |
| PostgreSQL | Role `roamate_owner` owns database `roamate` and its schema and runs migrations. Role `roamate_app` (in `.env`) can read and write rows but cannot create, alter or drop tables | `roamate_app` has **no rights on any RagBot object**, shown by negative tests (it cannot read or write RagBot's tables). PostgreSQL grants CONNECT on every database to PUBLIC by default, so `roamate_app` can still open a connection to another database; revoking that is optional and only done by the server owner, never by our scripts | `infra/setup/create_database.sql`, run once with the Postgres admin login |
| Qdrant | Code only creates, writes or deletes collections whose names start with `roamate_`, and refuses any other name | **Naming only**, an accepted development boundary: the server's key (if any) reaches every collection. Collection-scoped keys need JWT RBAC switched on in the server's config, which is the server owner's decision. Before Beta (M12.9): scoped keys if enabled, otherwise a dedicated Roamate Qdrant | Roamate's setup script in M1.5 |
| MinIO | Own access key `roamate` with a policy that allows only the four `roamate-*` buckets | The key cannot list, read or write other buckets, shown by negative tests | `infra/setup/create_buckets.sh`, run once with the MinIO admin login |
| GPU services | Shared, read-only, with request caps | Roamate stores nothing there and never changes them | Nobody: they already run |

### 2a. Routing service: Valhalla recommended

Two open-source engines fit:

| | Valhalla | OSRM |
| --- | --- | --- |
| Cities | One service serves every city from one tile set; adding a city means rebuilding the set with the new extract | One data set per process; adding a city means a merged extract or another process |
| Travel modes | Walking, driving, cycling from one service; public transport (GTFS) possible later | One mode (profile) per process, so walking and driving need two |
| Distance/time matrix | `sources_to_targets`; fine for the up to 60 candidates per trip; unreachable pairs come back empty, which we treat as "not connected" | `table`; faster on very large matrices |
| License | MIT | BSD-2 |

**Recommendation: Valhalla**, because "adding a city is easy" matters more to us than raw matrix speed, and one service covers both modes. It stays provisional until the M0.16 spike builds and serves a small area.

How it runs: one container `roamate-routing` (port 8002, image tag pinned in M1, digest in the manifest). Each build writes a new directory `/data/valhalla/<routing_version>/` from the extracts of every active city (each cut with a buffer of about 10 km so routes near the edge work). After a smoke test of known walking and driving routes, a symlink `current` is moved to the new directory and the container is restarted. That container is Roamate's own, so restarting it is allowed. Builds run as jobs with time, memory and disk limits. Archives of each build go to `roamate-routing` for rollback. If the service is down, the planner falls back to distance estimates labeled `Estimated`.

---

## 3. Docker Compose

`infra/docker-compose.yml` uses project name `roamate` (`name: roamate` in the file), so its containers, volumes and network never collide with RagBot's. Every container name starts with `roamate-`, every volume with `roamate-`, and every port is bound to `127.0.0.1`.

| Service | Image | Profiles | Notes |
| --- | --- | --- | --- |
| `roamate-routing` | Valhalla, pinned tag | `shared`, `standalone` | Roamate's own; needed in both modes |
| `roamate-tei-lab` | `ghcr.io/huggingface/text-embeddings-inference:<pinned>` | `lab` | Only for embedding experiments |
| `roamate-postgres` | `postgres:<major version on the server>` | `standalone` | For a fresh machine without RagBot's services |
| `roamate-qdrant` | `qdrant/qdrant:v1.16.2` | `standalone` | Same as the server |
| `roamate-minio` | the server's MinIO image, by digest | `standalone` | Pinned by digest, since MinIO publishes no new images |
| `roamate-tei-embed`, `roamate-tei-rerank` | TEI, pinned | `standalone-gpu` | Only on a machine with a GPU |

On the shared server: `docker compose -f infra/docker-compose.yml --profile shared up -d`. On a fresh laptop: `--profile standalone` (and `standalone-gpu` if it has a GPU, or API models only). The standalone services use different host ports from RagBot's defaults when both could run on one machine (set in `.env`).

Data lives in named volumes, so `docker compose down` keeps it and `docker compose down -v` deletes it (only Roamate's volumes, because of the project name).

---

## 4. Conda environment and dependency locks

`environment.yml` at the repository root:

```yaml
name: roamate
channels:
  - conda-forge
dependencies:
  - python=3.12
  - nodejs=22
  - pip
```

Python packages are listed in `backend/pyproject.toml` and locked with pip-tools in `backend/requirements.lock` (exact versions with hashes). Web packages are in `web/package.json`, locked in `web/package-lock.json`. Setup for a new developer, every command run from the repository root:

```bash
conda env create -f environment.yml
conda activate roamate
pip install -r backend/requirements.lock
pip install -e backend --no-deps
npm --prefix web ci
cp .env.example .env              # then fill in the values
python backend/scripts/check_setup.py   # compatibility smoke check (M1.12)
```

To update after pulling changes: `conda env update -f environment.yml`, then the two `pip` lines and `npm --prefix web ci`. To change a Python dependency: edit `pyproject.toml`, run `pip-compile --generate-hashes -o backend/requirements.lock backend/pyproject.toml`, and commit both files. CI fails if the lock does not match `pyproject.toml`.

Python 3.12 is supported by every library in the plan (OR-Tools, LangGraph, FastAPI, boto3, qdrant-client). Node.js 22 is the current long-term support line. The TravelPlanner research track uses its own environment `roamate-tp` (Python 3.9), never this one.

---

## 5. `.env` settings

`.env` is listed in `.gitignore` and never committed; gitleaks checks every commit. `.env.example` holds every setting below with a comment and no secrets. The backend reads them with Pydantic Settings at start. A missing **required** setting stops the start with a clear message. An optional service that is unset or unreachable only marks a capability as unavailable (§6).

### App

| Setting | Example | Required | Meaning |
| --- | --- | --- | --- |
| `APP_ENV` | `development` | yes | `development`, `test` or `production` |
| `APP_HOST` | `127.0.0.1` | no | Address the backend listens on |
| `APP_PORT` | `8100` | no | Port the backend listens on; read by `python -m app` |
| `APP_BASE_URL` | `http://localhost:5173` | yes | Where users open the app; used for cookie settings and the Origin check |
| `SESSION_DAYS` | `14` | no | How long a sign-in lasts |
| `LOG_LEVEL` | `INFO` | no | Log detail; logs never contain passwords, tokens or full prompts |

There is no `SESSION_SECRET`: session tokens are random values whose SHA-256 hash is stored in Postgres, so there is nothing to sign (design M0.7).

### PostgreSQL

| Setting | Example | Required |
| --- | --- | --- |
| `POSTGRES_HOST` | `localhost` | yes |
| `POSTGRES_PORT` | `5432` | no |
| `POSTGRES_DB` | `roamate` | yes |
| `POSTGRES_USER` | `roamate_app` | yes; the runtime role |
| `POSTGRES_PASSWORD` | secret | yes |
| `POSTGRES_MIGRATION_USER` | `roamate_owner` | no; used only by `alembic upgrade`, which asks for its password when run |

### Qdrant

| Setting | Example | Required |
| --- | --- | --- |
| `QDRANT_URL` | `http://localhost:6333` | yes |
| `QDRANT_API_KEY` | secret or empty | no |
| `QDRANT_COLLECTION_PREFIX` | `roamate_` | no; must start with `roamate` |

### Object storage (MinIO)

| Setting | Example | Required |
| --- | --- | --- |
| `S3_ENDPOINT_URL` | `http://localhost:9000` | yes |
| `S3_ACCESS_KEY` | `roamate` | yes |
| `S3_SECRET_KEY` | secret | yes |
| `S3_REGION` | `us-east-1` | no |
| `S3_BUCKET_MEDIA` | `roamate-media` | no |
| `S3_BUCKET_TILES` | `roamate-tiles` | no |
| `S3_BUCKET_ROUTING` | `roamate-routing` | no |
| `S3_BUCKET_RAW` | `roamate-raw` | no |

The settings are named `S3_*` rather than `MINIO_*` because the code speaks plain S3 through boto3. Every bucket name must start with `roamate-`.

### Embeddings and reranker (TEI)

| Setting | Example | Required |
| --- | --- | --- |
| `TEI_EMBED_URL` | `http://localhost:7997` | yes for search; the form path with fixtures works without it |
| `TEI_RERANK_URL` | `http://localhost:7998` | no; search works without reranking |
| `TEI_LAB_URL` | `http://localhost:7999` | no; only for embedding experiments |
| `TEI_MAX_PARALLEL` | `4` | no; cap per TEI service |
| `EMBEDDING_MODEL_NAME` | `jina-embeddings-v5-text-small-retrieval` | yes for search; part of the collection name and fingerprint |
| `EMBEDDING_DIM` | `1024` | yes for search; checked against TEI's answer |

### Chat models

| Setting | Example | Required |
| --- | --- | --- |
| `LLM_CONFIG` | `config/models.yaml` | no; the launch deployment points at `config/models.launch.yaml` |
| `LLM_CHAIN` | `openrouter-free,gemini-free,local-gemma` | no; overrides the `chain` line in the config file |
| `VLLM_BASE_URL` | `http://localhost:8000/v1` | no |
| `VLLM_MAX_PARALLEL` | `2` | no; cap on requests to the shared vLLM |
| `OPENROUTER_API_KEY` | secret | no |
| `GEMINI_API_KEY` | secret | no |
| `NINEROUTER_BASE_URL`, `NINEROUTER_API_KEY`, `NINEROUTER_MODEL` | | no; only if 9Router is opted in |
| `LLM_TIMEOUT_SECONDS` | `60` | no; per attempt |
| `LLM_COOLDOWN_SECONDS` | `60` | no; how long a provider that returned 429 is skipped |
| `JOB_MAX_LLM_CALLS` | `30` | no; the job-wide budget (plan §8) |
| `JOB_DEADLINE_SECONDS` | `120` | no |

A provider with no key or address is skipped. The provider list format itself is designed in M0.8.

### Solver and routing

| Setting | Example | Required |
| --- | --- | --- |
| `ROUTING_URL` | `http://localhost:8002` | no; without it the planner uses labeled distance estimates |
| `ROUTING_TIMEOUT_SECONDS` | `10` | no |
| `SOLVER_TIME_LIMIT_SECONDS` | `10` | no; per solve, enforced by killing the child process |
| `SOLVER_MAX_PROCESSES` | `4` | no |

Rush-hour factors are city data (`city_traffic_profile`), not a setting.

### External data

| Setting | Example | Required |
| --- | --- | --- |
| `CONTACT_EMAIL` | `you@example.com` | yes for city ingestion; Nominatim and Overpass ask for a contact |
| `HTTP_USER_AGENT` | `Roamate/0.1 (+contact)` | no |
| `OPEN_METEO_URL` | `https://api.open-meteo.com` | no; the free hosted tier is for development only |

---

## 6. Health endpoints

| Endpoint | Who | Answers | Status codes |
| --- | --- | --- | --- |
| `GET /api/health/live` | Anyone | `{"status": "ok"}` if the process runs. Checks nothing else | 200 |
| `GET /api/health/ready` | Anyone | Whether the app can serve its current mode: Postgres reachable and migrated, settings valid. Lists capabilities as on or off, without internal details | 200 ready, 503 not ready |
| `GET /api/admin/diagnostics` | Admins only (from M2) | Every dependency in detail, run in parallel with 2-second timeouts and cached for 30 seconds | 200 |

Example of the admin diagnostics:

```json
{
  "checked_at": "2026-10-24T12:00:00Z",
  "capabilities": {"accounts": true, "search": true, "rerank": true, "routing": true, "llm": true, "ingestion": true},
  "services": {
    "postgres":  {"ok": true, "latency_ms": 3,  "detail": "roamate @ 16.4, migrations at head"},
    "qdrant":    {"ok": true, "latency_ms": 5,  "detail": "v1.16.2, alias roamate_places → 1 collection"},
    "storage":   {"ok": true, "latency_ms": 4,  "detail": "4 of 4 buckets present"},
    "tei_embed": {"ok": true, "latency_ms": 12, "detail": "jina-embeddings-v5-text-small-retrieval, dim 1024"},
    "tei_rerank":{"ok": true, "latency_ms": 10, "detail": "bge-reranker-v2-m3"},
    "routing":   {"ok": true, "latency_ms": 6,  "detail": "valhalla, routing version 3, 1 city"},
    "llm": {"ok": true, "detail": [
      {"provider": "openrouter-free", "state": "reachable"},
      {"provider": "gemini-free", "state": "not configured"},
      {"provider": "local-gemma", "state": "reachable"}
    ]}
  }
}
```

Rules:

- **Ready** fails only for what the app cannot work without (Postgres, valid settings). A missing reranker, routing service, weather or LLM provider turns its capability off; the app starts and says what is unavailable.
- **"Reachable" is not "working".** The LLM check calls each provider's model list endpoint, which costs nothing. It proves the provider answers and the key is accepted, not that it returns valid JSON for our schemas; that is what the Lab test prompt is for.
- Routine checks never call a billed inference endpoint.
- The public status page (M1.8) shows ready and the capability list; the admin page shows the diagnostics.

---

## 7. Repository files created by M1

| File | Contents |
| --- | --- |
| `environment.yml` | §4 |
| `.env.example` | §5 |
| `.gitignore` | `.env`, Python and Node build output, local data |
| `infra/docker-compose.yml` | §3 |
| `infra/setup/create_database.sql` | Creates `roamate_owner`, `roamate_app` and the `roamate` database; grants `roamate_app` data rights only; no change to other databases |
| `infra/setup/create_buckets.sh` | Creates the four buckets, the `roamate` access key and its bucket-limited policy; dry run unless `--apply` |
| `infra/setup/create_collections.py` | Creates the first Qdrant collection and the alias; refuses names without the prefix |
| `backend/pyproject.toml`, `backend/requirements.lock` | Python packages, tool settings (ruff, mypy, pytest) and the lock |
| `backend/app/__main__.py` | Starts Uvicorn with `APP_HOST` and `APP_PORT` |
| `backend/scripts/check_setup.py` | Compatibility smoke check: versions, reachability, the four buckets, roles' rights |
| `web/package.json`, `web/package-lock.json` | Web packages, scripts and the lock |

---

## 8. Server facts needed before approval

These cannot be guessed. Each answer goes into the [compatibility manifest](00-compatibility-manifest.md) with the command that showed it.

1. **Postgres version** on the server (`SELECT version();`). Compose's standalone profile pins that major version.
2. **MinIO image and digest** on the server (`docker inspect minio-server --format '{{.Image}}'`), so the standalone setup matches it.
3. **Qdrant authentication:** does the server use an API key, and is JWT RBAC enabled or allowed to be enabled? This decides between naming-only isolation (development) and scoped keys.
4. **Where Roamate runs during development:** on the same server as the services (addresses stay `localhost`), or on your laptop connecting to the server (addresses become the server's IP, and the ports must be reachable; we would then use an SSH tunnel rather than open ports).
5. **Free ports** on the server: 8100 (backend), 8002 (routing), 7999 (lab TEI).
6. **GPU headroom:** free GPU memory next to vLLM and both TEI services, to know whether the lab TEI can run at all.
7. **Backups:** who owns backups of the shared Postgres and MinIO today, so Roamate's backups (M12.12) fit in.
8. **Routing engine:** OK to go with Valhalla (§2a), subject to the M0.16 spike?

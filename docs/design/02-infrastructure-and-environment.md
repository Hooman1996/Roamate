# Design M0.2: infrastructure, conda environment and `.env` settings

**Status:** draft for approval · 24 October 2026
**Plan reference:** [implementation plan](../plan/implementation-plan.md) §4, §5 and §6

This design fixes where Roamate's services run, how Roamate stays separate from RagBot on the same server, how a developer sets up the environment, and every setting in `.env`. Nothing here is coded until it is approved.

---

## 1. Services Roamate connects to

Roamate reuses the containers already running for RagBot. Default addresses below come from RagBot's `.env.example`; the real values go in Roamate's `.env`.

| Service | Existing container | Default address | What Roamate owns there |
| --- | --- | --- | --- |
| PostgreSQL | `postgres-server` | `localhost:5432` | Database `roamate`, owned by user `roamate_app` |
| Qdrant | `qdrant-server` (`qdrant/qdrant:v1.16.2`) | `http://localhost:6333` | Collections whose names start with `roamate_` |
| MinIO | `minio-server` | `localhost:9000` (S3 API) | Buckets `roamate-media`, `roamate-tiles`, `roamate-raw` |
| TEI embedding | `tei-embedding` | `http://localhost:7997` | Nothing stored; read-only use |
| TEI reranker | `tei-reranker` | `http://localhost:7998` | Nothing stored; read-only use |
| vLLM | `gemma4-vllm` | `http://localhost:8000/v1` | Nothing stored; read-only use |
| 9Router | not running yet | `http://localhost:20128/v1` | Installed in M4.3, only if we decide to use it |
| Routing | new: `roamate-routing` | `http://localhost:8002` | Roamate's own service; its data is built from each published city's OpenStreetMap extract (§2a) |

Roamate's own processes:

| Process | Port | How it runs during development |
| --- | --- | --- |
| Backend (FastAPI) | `8100` | `uvicorn app.main:app --reload --port 8100` (8000 is taken by vLLM) |
| Web app (Vite dev server) | `5173` | `npm run dev`; it forwards `/api` to the backend |

In production (M12) the web app is built into static files and served by the backend, so there is a single port.

---

## 2. Keeping Roamate separate from RagBot

| Service | Separation | Who creates it |
| --- | --- | --- |
| PostgreSQL | Own database `roamate` and own login `roamate_app`. `roamate_app` can only connect to `roamate`; it has no rights on `ragbot` | `infra/setup/create_database.sql`, run once by someone with the Postgres admin login |
| Qdrant | Qdrant has one API key for the whole server, so separation is by name: Roamate code only creates, writes or deletes collections whose names start with `roamate_`, and refuses any other name | Created by Roamate's setup script in M3 |
| MinIO | Own access key `roamate` with a policy that allows only the `roamate-*` buckets | `infra/setup/create_buckets.sh`, run once with the MinIO admin login |
| GPU services | Shared, read-only. Roamate never restarts or reconfigures them | Nobody: they already run |

The admin logins for Postgres and MinIO are used only by the one-time setup scripts, typed in when the script runs. They are never stored in Roamate's `.env`.

### 2a. Routing service: Valhalla recommended

The plan adds a self-hosted routing service for walking and driving times and distances (decided 24 Oct 2026). Two open-source engines fit:

| | Valhalla | OSRM |
| --- | --- | --- |
| Cities | One service serves every city; adding a city adds its extract to the tile build | One data set per process; adding a city means a merged extract or another process |
| Travel modes | Walking, driving, cycling from one service; public transport (GTFS) possible later | One mode (profile) per process, so walking and driving need two |
| Distance/time matrix | `sources_to_targets`; fine for the 30–60 candidates per trip | `table`; faster on very large matrices |
| License | MIT | BSD-2 |

**Recommendation: Valhalla**, because "adding a city is easy" matters more to us than raw matrix speed, and one service covers both modes. It runs as one container (`roamate-routing`, port 8002, image tag pinned in M1) with its data in a Docker volume. When a city is published (M6), its extract is downloaded, the tiles are rebuilt, and the service is reloaded. If the service is down, the planner falls back to distance estimates labeled `Estimated`.

---

## 3. A fresh machine without the RagBot services

`infra/docker-compose.yml` starts the same kind of services with the same names, for a developer laptop or a new server:

| Service | Image | Notes |
| --- | --- | --- |
| `postgres-server` | `postgres:<major version>` | Pinned to the same major version as the server (to confirm, see §8) |
| `qdrant-server` | `qdrant/qdrant:v1.16.2` | Same as the server |
| `minio-server` | the same MinIO image tag as the server | Pinned, since MinIO publishes no new images |
| `tei-embedding`, `tei-reranker` | `ghcr.io/huggingface/text-embeddings-inference:cuda-1.9` | Profile `gpu`, started only with `--profile gpu` |
| `vllm` | `vllm/vllm-openai:<pinned tag>` | Profile `gpu`; not needed if API models are used |
| `roamate-routing` | Valhalla, pinned tag | Always started; also part of the server setup, since the server does not run it yet |

Data lives in named Docker volumes, so `docker compose down` keeps it and `docker compose down -v` deletes it.

---

## 4. Conda environment

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

Python packages are listed in `backend/pyproject.toml` and web packages in `web/package.json`, so each has one source of truth. Setup for a new developer:

```bash
conda env create -f environment.yml
conda activate roamate
pip install -e "backend[dev]"
cd web && npm ci
cp .env.example .env        # then fill in the values
```

To update after pulling changes: `conda env update -f environment.yml`, `pip install -e "backend[dev]"`, `npm ci`.

Python 3.12 is supported by every library in the plan (OR-Tools, LangGraph, FastAPI, boto3, qdrant-client). Node.js 22 is the current long-term support line.

---

## 5. `.env` settings

`.env` is listed in `.gitignore` and never committed. `.env.example` holds every setting below with a comment and no secrets. The backend reads them with Pydantic Settings and refuses to start if a required one is missing.

### App

| Setting | Example | Required | Meaning |
| --- | --- | --- | --- |
| `APP_ENV` | `development` | yes | `development`, `test` or `production` |
| `APP_PORT` | `8100` | no | Backend port |
| `APP_BASE_URL` | `http://localhost:5173` | yes | Where users open the app; used for cookies and CORS |
| `SESSION_SECRET` | random 64 characters | yes | Signs session cookies |
| `SESSION_DAYS` | `14` | no | How long a sign-in lasts |
| `LOG_LEVEL` | `INFO` | no | Log detail |

### PostgreSQL

| Setting | Example | Required |
| --- | --- | --- |
| `POSTGRES_HOST` | `localhost` | yes |
| `POSTGRES_PORT` | `5432` | no |
| `POSTGRES_DB` | `roamate` | yes |
| `POSTGRES_USER` | `roamate_app` | yes |
| `POSTGRES_PASSWORD` | secret | yes |

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
| `S3_BUCKET_RAW` | `roamate-raw` | no |

The settings are named `S3_*` rather than `MINIO_*` because the code speaks plain S3 through boto3.

### Embeddings and reranker (TEI)

| Setting | Example | Required |
| --- | --- | --- |
| `TEI_EMBED_URL` | `http://localhost:7997` | yes |
| `TEI_RERANK_URL` | `http://localhost:7998` | no; search works without reranking |
| `EMBEDDING_MODEL_NAME` | `jina-embeddings-v5-text-small-retrieval` | yes; used in the Qdrant collection name |
| `EMBEDDING_DIM` | `1024` | yes; checked against TEI at startup |

### Chat models

| Setting | Example | Required |
| --- | --- | --- |
| `LLM_CHAIN` | `openrouter-free,gemini-free,local-gemma` | no; overrides the `chain` line in `config/models.yaml` |
| `VLLM_BASE_URL` | `http://localhost:8000/v1` | no |
| `OPENROUTER_API_KEY` | secret | no |
| `GEMINI_API_KEY` | secret | no |
| `NINEROUTER_BASE_URL`, `NINEROUTER_API_KEY`, `NINEROUTER_MODEL` | | no |
| `LLM_TIMEOUT_SECONDS` | `60` | no |
| `LLM_COOLDOWN_SECONDS` | `60` | no; how long a provider that returned 429 is skipped |

At least one provider in the chain must be reachable; the health page shows which ones are. The provider list format itself is designed in M0.8.

### Routing

| Setting | Example | Required |
| --- | --- | --- |
| `ROUTING_URL` | `http://localhost:8002` | no; without it the planner uses labeled distance estimates |
| `ROUTING_TIMEOUT_SECONDS` | `10` | no |
| `TRAFFIC_FACTOR_PEAK` | `1.3` | no; multiplies driving times in rush hours, since the engine has no live traffic |

### External data

| Setting | Example | Required |
| --- | --- | --- |
| `CONTACT_EMAIL` | `you@example.com` | yes for city ingestion; Nominatim and Overpass ask for a contact |
| `HTTP_USER_AGENT` | `Roamate/0.1 (+contact)` | no |
| `OPEN_METEO_URL` | `https://api.open-meteo.com` | no |

---

## 6. Health endpoint

`GET /api/health` checks every service with a short timeout (2 seconds each, run in parallel) and returns:

```json
{
  "status": "degraded",
  "checked_at": "2026-10-24T12:00:00Z",
  "services": {
    "postgres":  {"ok": true,  "latency_ms": 3,  "detail": "roamate @ 16.4"},
    "qdrant":    {"ok": true,  "latency_ms": 5,  "detail": "v1.16.2, 1 roamate collection"},
    "storage":   {"ok": true,  "latency_ms": 4,  "detail": "3 of 3 buckets present"},
    "tei_embed": {"ok": true,  "latency_ms": 12, "detail": "jina-embeddings-v5-text-small-retrieval, dim 1024"},
    "tei_rerank":{"ok": true,  "latency_ms": 10, "detail": "bge-reranker-v2-m3"},
    "routing":   {"ok": true,  "latency_ms": 6,  "detail": "valhalla, 1 city loaded"},
    "llm":       {"ok": false, "latency_ms": 2000, "detail": "local-gemma: timeout; openrouter-free: not configured"}
  }
}
```

`status` is `ok` when everything passes, `degraded` when an optional service fails (reranker, some LLM providers), and `down` when Postgres, Qdrant, storage or embeddings fail. A failing routing service counts as `degraded`, because the planner can fall back to estimates. The LLM check lists each provider in the chain without spending tokens: it calls the provider's model list endpoint. The web health page (M1.8) shows this as a table.

---

## 7. Repository files created by M1

| File | Contents |
| --- | --- |
| `environment.yml` | §4 |
| `.env.example` | §5 |
| `.gitignore` | `.env`, Python and Node build output, local data |
| `infra/docker-compose.yml` | §3 |
| `infra/setup/create_database.sql` | Creates `roamate_app` and the `roamate` database, with no rights on others |
| `infra/setup/create_buckets.sh` | Creates the three buckets, the `roamate` access key and its bucket-limited policy |
| `backend/pyproject.toml` | Python packages and tool settings (ruff, pytest) |
| `web/package.json` | Web packages and scripts |

---

## 8. Questions for you

1. **Postgres version on the server.** RagBot's notes show `postgres:latest`. Which major version is it (`SELECT version();`)? `infra/docker-compose.yml` will pin that major version.
2. **MinIO image tag on the server** (`docker ps --format '{{.Image}}'`), so the fresh-machine setup matches it.
3. **Where Roamate runs during development:** on the same server as the services (addresses stay `localhost`), or on your laptop connecting to the server (addresses become the server's IP, and the ports must be reachable)?
4. **Qdrant API key:** does the server's Qdrant use one? If yes, Roamate gets the same key and stays separate by collection names, as in §2.
5. **Ports 8100** (backend) **and 8002** (routing): free on the server?
6. **Routing engine:** OK to go with Valhalla (§2a)?

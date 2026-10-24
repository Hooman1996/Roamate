# Compatibility manifest

| | |
| --- | --- |
| **Status** | template; filled in during M0.2 (server facts) and M1.12 (pinned versions) |
| **Date** | 24 October 2026 |
| **Plan reference** | [implementation plan](../plan/implementation-plan.md) v3.0, §0 and §4 |

This file records what is actually installed and tested, so nobody has to guess a version or a capability. Every row names the command that showed the value and the date it was checked. A value that has not been checked stays empty. When a check fails, the affected design or ADR is reopened instead of quietly working around it.

## Shared server (RagBot services, read by Roamate)

| Component | Needed by Roamate | Found on the server | Image digest | Checked with | Date |
| --- | --- | --- | --- | --- | --- |
| PostgreSQL | 15 or newer | | | `SELECT version();` | |
| Qdrant | 1.16.x, query API with RRF fusion | | | `GET /` on port 6333 | |
| Qdrant authentication | API key? JWT RBAC enabled or allowed? | | | server config, asked of the server owner | |
| MinIO | S3 API with range reads and bucket policies | | | `docker inspect minio-server` | |
| TEI embedding | model, revision, dimension, dtype | | | `GET /info` on port 7997 | |
| TEI reranker | model, revision | | | `GET /info` on port 7998 | |
| vLLM | served model, max context | | | `GET /v1/models` on port 8000 | |
| GPU | free memory next to vLLM and TEI | | | `nvidia-smi` | |
| Free ports | 8100, 8002, 7999 | | | `ss -ltn` | |
| Backups | owner of Postgres and MinIO backups | | | asked of the server owner | |

## Roamate's own pinned components

| Component | Pinned version | Image digest or lock | Smoke test | Date |
| --- | --- | --- | --- | --- |
| Python / Node.js | 3.12.x / 22.x | `environment.yml` | `python --version`, `node --version` | |
| Python packages | | `backend/requirements.lock` | `python backend/scripts/check_setup.py` | |
| Web packages | | `web/package-lock.json` | `npm --prefix web ci` | |
| Valhalla | | | M0.16 spike: walking and driving matrix on a small area | |
| Protomaps basemap build and `pmtiles` CLI | | | M0.16 spike: extract, serve with range requests, render in MapLibre | |
| OR-Tools | | `backend/requirements.lock` | M0.15 spike cases | |
| LangGraph and its Postgres checkpointer | | `backend/requirements.lock` | M9.2 resume test | |
| Caddy (production) | | | M12.9 TLS check | |

## Providers and data sources

Rights, limits, cost and data policy for each provider and source are recorded in step M0.17, in its own design file. This manifest only records which version or endpoint was tested.

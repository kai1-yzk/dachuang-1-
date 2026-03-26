# Project Guidelines

## Code Style
- Keep changes minimal and scoped to the requested task; do not refactor unrelated files.
- Backend uses Flask blueprints under `backend/routes/`; shared utilities stay in `backend/utils/`.
- Frontend uses Vue 3 + Vite + Element Plus in `frontend/src/`; keep view logic in `views/` and HTTP logic in `utils/request.js`.
- Preserve existing API response style (JSON with `code`, `message`, optional `data`) unless endpoint conventions require otherwise.

## Architecture
- Frontend: `frontend/` (Vue 3 dashboard, auth, terminal UI).
- Backend API: `backend/app.py` with blueprints in `backend/routes/` (`auth`, `metrics`, `ai_analysis`, `data_ingestion`).
- Async pipeline: Celery worker in `backend/tasks.py`, Redis as broker/cache, MySQL as persistent store.
- AI module: model training and artifacts in `ai_engine/`; backend inference entry is in `backend/routes/ai_analysis.py`.
- Collector: data collection and preprocessing in `data_collector/collector.py`.

## Build And Test
- Frontend install: `cd frontend && npm install`
- Frontend dev: `cd frontend && npm run dev`
- Frontend build: `cd frontend && npm run build`
- Backend install: `cd backend && pip install -r requirements.txt`
- Backend run (dev): `cd backend && python app.py`
- Backend run (prod): `cd backend && gunicorn -c gunicorn.conf.py app:app`
- Worker run: `cd backend && celery -A tasks worker --loglevel=info`
- Backend tests: `cd backend && pytest`
- Full stack with containers: `docker-compose up -d`

## Conventions
- Auth and security are enforced by middleware in `backend/app.py` and `backend/utils/security.py`; keep new protected routes compatible with JWT flow.
- For high-throughput ingestion, API endpoints should enqueue heavy work to Celery instead of blocking request threads.
- Prefer environment variables for secrets and connection settings; do not introduce hardcoded credentials.
- Keep audit/security-sensitive behavior explicit and traceable in logs and database records.

## Documentation Links
- System overview: `README.md`
- Functional spec and API details: `Project_Functional_Specification.md`
- Multi-server expansion plan: `docs/multi_server_management_plan.md`
- 8-layer architecture diagram: `docs/architecture_8_layers.mmd`

## Known Pitfalls
- `backend/routes/ai_analysis.py` may fall back to mock behavior when model artifacts are missing; verify model files in deployment.
- Default local DB settings may exist in utility modules; prefer explicit `.env`/deployment config.
- In-memory rate-limit storage is not suitable for multi-instance production; use Redis-backed storage when scaling.

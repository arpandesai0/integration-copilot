.PHONY: setup backend frontend check

setup:
	uv venv backend/.venv --python python3
	uv pip install --python backend/.venv/bin/python -r backend/requirements.lock
	cd frontend && npm ci

backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

frontend:
	cd frontend && npm run dev

check:
	cd backend && .venv/bin/python -m pytest -q
	cd frontend && npm run lint && npm run typecheck && npm run build

# Makefile — SiteGuard convenience targets
# Requires: docker, python3.11, node 18+
#
# Quick start:
#   make up        # start Mosquitto broker
#   make backend   # activate venv and start FastAPI
#   make frontend  # start React dev server (in another terminal)
#   make demo      # start everything (needs tmux or 3 separate terminals)

.PHONY: up down backend frontend test replay demo

# Start Mosquitto
up:
	docker compose up -d mosquitto
	@echo "Mosquitto running on :1883"

# Stop services
down:
	docker compose down

# Backend: create venv if needed, install deps, start Uvicorn
backend:
	@cd backend && \
	  python3 -m venv .venv 2>/dev/null || true && \
	  . .venv/bin/activate && \
	  pip install -q -r requirements.txt && \
	  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend
frontend:
	@cd frontend && npm install && npm run dev

# Run tests
test:
	@cd backend && \
	  . .venv/bin/activate && \
	  pytest -v

# DEV ONLY replay — never use for demo/evidence
replay:
	@echo "⚠️  REPLAY MODE — not live PipeGen output. Do not use as evidence."
	@cd backend && \
	  . .venv/bin/activate && \
	  python scripts/replay.py $(FILE) --speed $(or $(SPEED),1.0)

# Start broker + backend in sequence (for demo machine — backend in foreground)
demo: up backend

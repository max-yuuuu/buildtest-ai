.PHONY: help infra dev prod backend worker frontend up full doctor logs print-env validate-compose

help:
	@echo "BuildTest AI dev commands"
	@echo ""
	@echo "  make infra       Start postgres/redis/qdrant (docker)"
	@echo "  make dev         Start full development stack (compose base+dev)"
	@echo "  make prod        Start full production stack (compose base+prod)"
	@echo "  make backend     Start backend on host"
	@echo "  make worker      Start celery worker on host"
	@echo "  make frontend    Start frontend on host"
	@echo "  make up          Start infra + backend(host) + worker(host) + frontend(host)"
	@echo "  make full        Alias of make dev"
	@echo "  make doctor      Verify infra connectivity"
	@echo "  make validate-compose Validate compose files for infra/dev/prod"
	@echo "  make logs S=svc  Tail full compose logs (optional service)"
	@echo "  make print-env   Print resolved env values"

infra:
	@bash scripts/dev infra

dev:
	@bash scripts/dev dev

prod:
	@bash scripts/dev prod

backend:
	@bash scripts/dev backend

worker:
	@bash scripts/dev worker

frontend:
	@bash scripts/dev frontend

up:
	@bash scripts/dev up

full:
	@bash scripts/dev full

doctor:
	@bash scripts/dev doctor

logs:
	@bash scripts/dev logs $(S)

print-env:
	@bash scripts/dev print-env

validate-compose:
	@bash scripts/dev validate-compose


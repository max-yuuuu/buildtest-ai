.PHONY: help infra backend frontend up full doctor logs print-env

help:
	@echo "BuildTest AI dev commands"
	@echo ""
	@echo "  make infra       Start postgres/redis/qdrant (docker)"
	@echo "  make backend     Start backend on host"
	@echo "  make frontend    Start frontend on host"
	@echo "  make up          Start infra + backend(host) + frontend(host)"
	@echo "  make full        Start full stack (docker compose up --build)"
	@echo "  make doctor      Verify infra connectivity"
	@echo "  make logs S=svc  Tail full compose logs (optional service)"
	@echo "  make print-env   Print resolved env values"

infra:
	@bash scripts/dev infra

backend:
	@bash scripts/dev backend

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


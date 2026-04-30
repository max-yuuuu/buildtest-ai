# 在 frontend/ 下执行 `make frontend` 时转发到仓库根目录（根 Makefile 才有 frontend 目标）
ROOT_DIR := $(shell cd "$(dir $(lastword $(MAKEFILE_LIST)))"/.. && pwd)

.PHONY: frontend
frontend:
	@$(MAKE) -C "$(ROOT_DIR)" frontend

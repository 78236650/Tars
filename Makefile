# TARS Makefile
# 便捷命令集合

.PHONY: help install backend-install frontend-install backend-dev frontend-dev dev format lint test clean

help:
	@echo "TARS 项目命令"
	@echo "  make install              - 安装所有依赖"
	@echo "  make backend-install      - 安装后端依赖"
	@echo "  make frontend-install     - 安装前端依赖"
	@echo "  make backend-dev          - 启动后端开发服务器"
	@echo "  make frontend-dev         - 启动前端开发服务器"
	@echo "  make dev                  - 同时启动前端和后端 (需要 tmux 或另一个终端)"
	@echo "  make format               - 格式化代码"
	@echo "  make lint                 - 代码检查"
	@echo "  make test                 - 运行测试"
	@echo "  make clean                - 清理构建产物"

install: backend-install frontend-install

backend-install:
	@echo "Installing backend dependencies..."
	cd backend && python3 -m venv venv
	@echo "Backend virtual environment created at backend/venv"
	@echo "Run 'source backend/venv/bin/activate' to activate"
	@echo "Then run 'pip install -r requirements.txt' to install dependencies"

frontend-install:
	@echo "Installing frontend dependencies..."
	cd frontend && npm install

backend-dev:
	@echo "Starting backend development server..."
	cd backend && source venv/bin/activate && python -m tars.main

frontend-dev:
	@echo "Starting frontend development server..."
	cd frontend && npm run dev

format:
	@echo "Formatting backend code..."
	cd backend && black . && isort .
	@echo "Formatting frontend code..."
	cd frontend && npm run format

lint:
	@echo "Linting backend code..."
	cd backend && ruff . && mypy .
	@echo "Linting frontend code..."
	cd frontend && npm run lint

test:
	@echo "Running backend tests..."
	cd backend && pytest -v

clean:
	@echo "Cleaning up..."
	rm -rf backend/__pycache__
	rm -rf backend/*.pyc
	rm -rf backend/.pytest_cache
	rm -rf backend/.mypy_cache
	rm -rf frontend/node_modules
	rm -rf frontend/dist
	rm -rf frontend/.vite
	rm -rf backend/venv
	rm -f backend/data/*.db
	rm -f .coverage
	rm -rf htmlcov
	@echo "Clean complete!"

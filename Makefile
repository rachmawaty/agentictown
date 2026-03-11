.PHONY: help install init run test clean docker-up docker-down

help:
	@echo "🏘️  AgenticTown - Available Commands"
	@echo "======================================"
	@echo "  make install    - Install Python dependencies"
	@echo "  make init       - Initialize database and seed data"
	@echo "  make run        - Start the server"
	@echo "  make test       - Run tests"
	@echo "  make clean      - Clean temporary files"
	@echo "  make docker-up  - Start with Docker Compose"
	@echo "  make docker-down - Stop Docker containers"
	@echo ""

install:
	pip install -r requirements.txt

init:
	python scripts/init_town.py

run:
	python -m app.main

test:
	pytest tests/ -v

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.log" -delete

docker-up:
	docker-compose up -d
	@echo "Waiting for database..."
	@sleep 5
	@echo "Initializing town..."
	docker-compose exec server python scripts/init_town.py

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f server

status:
	@curl -s http://localhost:8000/status | python -m json.tool

trigger-cycle:
	@curl -X POST http://localhost:8000/cycle/trigger
	@echo "\nCycle triggered!"

.PHONY: up down build ingest reembed test eval eval-ab loadtest scale-test demo lint clean

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

ingest:
	docker compose run --rm ingest python -m ingest run --corpus /data/corpus

reembed:
	docker compose run --rm ingest python -m ingest run --corpus /data/corpus --reembed

test:
	docker compose run --rm api pytest /app/tests/ -v

eval:
	docker compose --profile eval run --rm eval-runner python -m eval.run --set /app/eval/scenarios.jsonl --prompt-variant researcher.v1 --out /app/docs/results/eval_latest.json

eval-ab:
	docker compose --profile eval run --rm eval-runner python -m eval.run --ab --set /app/eval/scenarios.jsonl

loadtest:
	docker compose --profile loadtest up locust

scale-test:
	docker compose up -d --scale agent-worker=3

demo:
	@echo "See docs/DEMO.md for demo instructions"

lint:
	docker compose run --rm api ruff check /app && mypy /app --ignore-missing-imports

clean:
	docker compose down -v --remove-orphans
	docker image prune -f

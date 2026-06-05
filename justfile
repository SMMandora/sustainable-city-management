set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

default:
    @just --list

setup:
    cd services/backend && uv sync

up:
    docker compose -f deploy/docker-compose.yml up -d

up-build:
    docker compose -f deploy/docker-compose.yml up -d --build

down:
    docker compose -f deploy/docker-compose.yml down

down-volumes:
    docker compose -f deploy/docker-compose.yml down -v

logs service="":
    docker compose -f deploy/docker-compose.yml logs -f {{service}}

ps:
    docker compose -f deploy/docker-compose.yml ps

migrate:
    cd services/backend && uv run python manage.py migrate

makemigrations:
    cd services/backend && uv run python manage.py makemigrations

shell:
    cd services/backend && uv run python manage.py shell

test:
    cd services/backend && uv run pytest

test-cov:
    cd services/backend && uv run pytest --cov --cov-branch --cov-report=term-missing --cov-report=html

lint:
    cd services/backend && uv run ruff check .
    cd services/backend && uv run ruff format --check .

format:
    cd services/backend && uv run ruff check --fix .
    cd services/backend && uv run ruff format .

typecheck:
    cd services/backend && uv run mypy apps config

security:
    cd services/backend && uv run bandit -c pyproject.toml -r apps

precommit-install:
    pre-commit install

precommit:
    pre-commit run --all-files

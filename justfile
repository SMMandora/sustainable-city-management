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

# Local K8s staging (kind)
kind-up:
    bash scripts/kind-up.sh

kind-down:
    kind delete cluster --name scm

# Build images into kind's local cache so the manifests can use them.
kind-load:
    docker compose -f deploy/docker-compose.yml build web frontend
    kind load docker-image scm-backend:dev --name scm
    kind load docker-image scm-frontend:dev --name scm

deploy-staging:
    kubectl apply -k deploy/k8s/overlays/kind
    kubectl rollout status -n scm deployment/web --timeout=180s
    kubectl rollout status -n scm deployment/worker --timeout=180s
    kubectl rollout status -n scm deployment/beat --timeout=180s
    kubectl rollout status -n scm deployment/frontend --timeout=180s
    @echo
    @echo "Open http://scm.localtest.me in your browser."

undeploy-staging:
    kubectl delete -k deploy/k8s/overlays/kind

load-test:
    k6 run tests/load/query-api.js

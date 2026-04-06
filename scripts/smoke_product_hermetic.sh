#!/bin/bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-dealwatch}"
COMPOSE_DEFAULT_NETWORK="${COMPOSE_PROJECT_NAME}_default"
POSTGRES_PORT="${POSTGRES_PORT:-55432}"
POSTGRES_USER="${POSTGRES_USER:-dealwatch}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-dealwatch}"
POSTGRES_DB="${POSTGRES_DB:-dealwatch}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-dealwatch-postgres}"
# Maximum number of 1-second wait attempts for short operations such as
# container and network create/remove.
MAX_SHORT_WAIT_ATTEMPTS=30
# Maximum number of 1-second wait attempts for longer PostgreSQL startup work.
MAX_LONG_WAIT_ATTEMPTS=150
export POSTGRES_PORT POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB

wait_for_container_removal() {
  for _ in $(seq 1 "${MAX_SHORT_WAIT_ATTEMPTS}"); do
    if ! docker container inspect "${POSTGRES_CONTAINER}" >/dev/null 2>&1; then
      return 0
    fi
    docker rm -f "${POSTGRES_CONTAINER}" >/dev/null 2>&1 || true
    sleep 1
  done

  echo "PostgreSQL container ${POSTGRES_CONTAINER} is still present after cleanup" >&2
  return 1
}

wait_for_container_creation() {
  for _ in $(seq 1 "${MAX_SHORT_WAIT_ATTEMPTS}"); do
    if docker container inspect "${POSTGRES_CONTAINER}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  echo "PostgreSQL container ${POSTGRES_CONTAINER} was not created by docker compose" >&2
  return 1
}

wait_for_network_removal() {
  for _ in $(seq 1 "${MAX_SHORT_WAIT_ATTEMPTS}"); do
    if ! docker network inspect "${COMPOSE_DEFAULT_NETWORK}" >/dev/null 2>&1; then
      return 0
    fi
    docker network rm "${COMPOSE_DEFAULT_NETWORK}" >/dev/null 2>&1 || true
    sleep 1
  done

  echo "Docker network ${COMPOSE_DEFAULT_NETWORK} is still present after cleanup" >&2
  return 1
}

wait_for_postgres_ready() {
  for _ in $(seq 1 "${MAX_LONG_WAIT_ATTEMPTS}"); do
    if docker exec "${POSTGRES_CONTAINER}" pg_isready -U "${POSTGRES_USER}" -d postgres >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  echo "PostgreSQL server did not become ready inside ${POSTGRES_CONTAINER}" >&2
  return 1
}

wait_for_database_creation() {
  for _ in $(seq 1 "${MAX_LONG_WAIT_ATTEMPTS}"); do
    if docker exec "${POSTGRES_CONTAINER}" psql -U "${POSTGRES_USER}" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${POSTGRES_DB}'" | grep -q 1; then
      return 0
    fi
    sleep 1
  done

  echo "PostgreSQL database ${POSTGRES_DB} was not created inside ${POSTGRES_CONTAINER}" >&2
  return 1
}

cleanup() {
  POSTGRES_PORT="${POSTGRES_PORT}" docker compose down -v >/dev/null 2>&1 || true
}

trap cleanup EXIT

POSTGRES_PORT="${POSTGRES_PORT}" docker compose down -v >/dev/null 2>&1 || true
wait_for_container_removal
wait_for_network_removal
POSTGRES_PORT="${POSTGRES_PORT}" docker compose up -d postgres
wait_for_container_creation
wait_for_postgres_ready
wait_for_database_creation

./scripts/smoke_product.sh

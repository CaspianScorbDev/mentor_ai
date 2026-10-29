#!/bin/sh
set -e

# Bring the schema up to date before serving. Safe to re-run: alembic is a no-op
# when the database is already at head.
alembic upgrade head

exec "$@"

#!/bin/sh
set -e

# Migrations run on every start, so a fresh clone needs no manual step.
# They are idempotent — an up-to-date database is a no-op.
python manage.py migrate --noinput

# exec replaces this shell with the actual command, so the container
# forwards signals properly and stops cleanly.
exec "$@"

#!/bin/sh
set -e

# Migrations run on every start, so a fresh clone needs no manual step.
# They are idempotent — an up-to-date database is a no-op.
python manage.py migrate --noinput

# Demo data, also idempotent — a fresh clone has something to look at
# without a second command. A production entrypoint would not do this.
#
# --with-images generates a placeholder per product. Only the first start
# pays for it; afterwards every product already has one and the step is a
# no-op. Worth it, because an empty image field reads as an unimplemented
# requirement rather than as missing photographs.
python manage.py seed_demo_data --with-images

# exec replaces this shell with the actual command, so the container
# forwards signals properly and stops cleanly.
exec "$@"

#!/usr/bin/env bash
# Exit immediately if a command exits with a non-zero status
set -o errexit

# Install production dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Run static assets collection, database migrations, and admin initialization
python manage.py collectstatic --noinput
python manage.py migrate
python manage.py init_admin

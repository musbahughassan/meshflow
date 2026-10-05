#!/bin/sh
python manage.py collectstatic --noinput
python manage.py migrate
exec daphne -b 0.0.0.0 -p 8001 meshflow.asgi:application
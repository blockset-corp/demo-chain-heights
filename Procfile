web: gunicorn server.wsgi:application --access-logfile - --error-logfile -
worker: celery -A server worker -l info
beat: celery -A server beat -l info
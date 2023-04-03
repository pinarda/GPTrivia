import os

workers = 3
bind = "0.0.0.0:8000"

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "GPTrivia.settings")

module = "GPTrivia.wsgi:application"
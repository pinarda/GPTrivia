import sys

workers = 3
bind = "0.0.0.0:8000"

module = "GPTrivia.wsgi:application"

raw_env = ["DJANGO_SETTINGS_MODULE=GPTrivia.settings"]

sys.path.insert(0, "/Users/rawrhouse/git/GPTrivia")

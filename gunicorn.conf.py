import sys

workers = 3
bind = "0.0.0.0:8000"

module = "GPTrivia.wsgi:application"
timeout = 600

sys.path.insert(0, "/Users/rawrhouse/git/GPTrivia")

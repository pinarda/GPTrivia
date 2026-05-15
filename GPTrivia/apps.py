import logging
import os
import sys

from django.apps import AppConfig


logger = logging.getLogger(__name__)


class GPTriviaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'GPTrivia'

    def ready(self):
        if os.environ.get('GPTRIVIA_DISABLE_ANALYSIS_WORKER') == '1':
            return

        blocked_commands = {
            'check',
            'test',
            'makemigrations',
            'migrate',
            'collectstatic',
            'shell',
            'dbshell',
            'showmigrations',
        }
        if any(argument in blocked_commands for argument in sys.argv[1:]):
            return

        try:
            from .round_analysis import ensure_round_analysis_worker_running

            ensure_round_analysis_worker_running()
        except Exception:
            logger.exception("Could not start the round analysis worker.")

        try:
            from .views import ensure_home_presentation_build_worker_for_pending_jobs

            ensure_home_presentation_build_worker_for_pending_jobs()
        except Exception:
            logger.exception("Could not start the home presentation build worker.")

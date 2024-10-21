from django.apps import AppConfig
from .tasks import start_scheduler

class SchedulerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'scheduler'

    def ready(self):
        start_scheduler()

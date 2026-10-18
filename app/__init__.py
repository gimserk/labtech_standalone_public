from .celery import app as celery_app
from .celery_config import app as celery2_app

default_app_config = 'app.apps.AppConfig'

__all__ = ('celery_app', 'celery2_app')

import os
from celery import Celery

# Point to your project's settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

# The celery app is named 'app'
app = Celery('app')

app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

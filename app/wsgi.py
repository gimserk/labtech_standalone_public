import os

from django.core.wsgi import get_wsgi_application

# This line points to your project's settings file.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

# This line creates the application object that Gunicorn will use.
application = get_wsgi_application()
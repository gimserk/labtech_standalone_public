#!/bin/bash

# Change to the directory where your manage.py file is located.
# This is crucial so that your settings.py can find the .env file.
cd /opt/labtech/labtech/

# Now, run the management command using the absolute path to your virtual environment's Python.
/opt/labtech/venv/bin/python manage.py cleanup_expired_labs

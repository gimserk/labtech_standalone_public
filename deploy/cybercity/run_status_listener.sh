#!/usr/bin/env bash
# Use the already installed LabTech Python environment, no venv rebuild.
set -Eeuo pipefail
INSTALL_DIR=/opt/labtech
if [[ -f /etc/labtech/deployment_settings.py ]]; then
  export DJANGO_SETTINGS_MODULE=deployment_settings
  export PYTHONPATH="/etc/labtech:$INSTALL_DIR${PYTHONPATH:+:$PYTHONPATH}"
fi
if [[ -x "$INSTALL_DIR/venv/bin/python" ]]; then
  PYTHON="$INSTALL_DIR/venv/bin/python"
elif [[ -x /opt/venv/bin/python ]]; then
  PYTHON=/opt/venv/bin/python
else
  echo "LabTech Python virtual environment not found" >&2
  exit 1
fi
exec "$PYTHON" "$INSTALL_DIR/manage.py" listen_cybercity_status --all-cities

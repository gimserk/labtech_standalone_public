#!/bin/bash

# Exit immediately if a command fails
set -e

# Configuration
ENV_FILE=".env"
VENV_DIR="../venv"
SERVICE_NAME="labtech"

echo "=========================================="
echo " Starting Database Setup & Deployment"
echo "=========================================="

# 1. Check for .env file
if [ ! -f "$ENV_FILE" ]; then
    echo "Error: $ENV_FILE file not found in $(pwd)!"
    exit 1
fi

# 2. Activate Virtual Environment
if [ -d "$VENV_DIR" ]; then
    echo "[1/5] Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
else
    echo "Error: Virtual environment directory '$VENV_DIR' not found!"
    exit 1
fi

# 3. Read DB & Superuser variables cleanly using Python
echo "[2/5] Parsing environment parameters from $ENV_FILE..."
eval $(python3 -c "
import dotenv, os
dotenv.load_dotenv('$ENV_FILE')
print(f'DB_NAME=\"{os.getenv(\"DB_NAME\")}\"')
print(f'DB_USER=\"{os.getenv(\"DB_USER\")}\"')
print(f'DB_PASSWORD=\"{os.getenv(\"DB_PASSWORD\")}\"')
print(f'DB_HOST=\"{os.getenv(\"DB_HOST\", \"localhost\")}\"')
print(f'SU_USER=\"{os.getenv(\"DJANGO_SUPERUSER_USERNAME\", \"\")}\"')
print(f'SU_EMAIL=\"{os.getenv(\"DJANGO_SUPERUSER_EMAIL\", \"\")}\"')
print(f'SU_PASS=\"{os.getenv(\"DJANGO_SUPERUSER_PASSWORD\", \"\")}\"')
")

if [ -z "$DB_NAME" ] || [ -z "$DB_USER" ] || [ -z "$DB_PASSWORD" ]; then
    echo "Error: Missing required database parameters (DB_NAME, DB_USER, DB_PASSWORD) in $ENV_FILE!"
    exit 1
fi

# 4. Check for existing database & offer reset option
DB_EXISTS=$(sudo mysql -NB -e "SHOW DATABASES LIKE '${DB_NAME}';" | grep -c "${DB_NAME}" || true)

if [ "$DB_EXISTS" -gt 0 ]; then
    echo ""
    read -p "Database '${DB_NAME}' already exists. Do you want to WIPE IT and start over? (y/N): " CONFIRM_RESET
    if [[ "$CONFIRM_RESET" =~ ^[Yy]$ ]]; then
        echo "Wiping existing database '${DB_NAME}'..."
        sudo mysql -e "DROP DATABASE \`${DB_NAME}\`;"
    fi
fi

# 5. Provision MariaDB Database and User
echo "[3/5] Provisioning MariaDB database and user permissions..."
sudo mysql -e "
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'${DB_HOST}' IDENTIFIED BY '${DB_PASSWORD}';
ALTER USER '${DB_USER}'@'${DB_HOST}' IDENTIFIED BY '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'${DB_HOST}';
FLUSH PRIVILEGES;
"

# 6. Run Django Migrations
echo "[4/5] Running Django makemigrations and migrate..."
python manage.py makemigrations
python manage.py migrate

# 7. Create Superuser
echo "[5/5] Checking Superuser setup..."
if [ -n "$SU_USER" ] && [ -n "$SU_EMAIL" ] && [ -n "$SU_PASS" ]; then
    echo "Creating superuser '$SU_USER' from .env credentials..."
    python manage.py createsuperuser --noinput || echo "Superuser '$SU_USER' already exists or creation skipped."
else
    read -p "Would you like to create a Django superuser interactively? (y/N): " CREATE_SU
    if [[ "$CREATE_SU" =~ ^[Yy]$ ]]; then
        python manage.py createsuperuser
    fi
fi

# 8. Restart Service
echo "Restarting service: $SERVICE_NAME..."
if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    sudo systemctl restart "$SERVICE_NAME"
    echo "Service $SERVICE_NAME restarted successfully."
else
    echo "Service $SERVICE_NAME is not active. Attempting to start it..."
    sudo systemctl start "$SERVICE_NAME"
    echo "Service $SERVICE_NAME started successfully."
fi

echo "=========================================="
echo " Setup, migration, and deployment complete!"
echo "=========================================="

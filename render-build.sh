#!/bin/bash
# Render deployment script

set -o errexit

echo ">>> Installing dependencies..."
pip install -r requirements.txt

echo ">>> Collecting static files..."
python manage.py collectstatic --noinput --clear

echo ">>> Running migrations..."
python manage.py migrate

echo ">>> Creating superuser if needed..."
python manage.py shell << 'EOF'
from django.contrib.auth import get_user_model

User = get_user_model()

username = 'admin'
email    = 'admin@genxzimbabwe.com'
password = 'admin123'

if User.objects.filter(username=username).exists():
    print(f"ℹ️  Superuser '{username}' already exists — skipping.")
else:
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f"✅  Superuser '{username}' created successfully.")
EOF
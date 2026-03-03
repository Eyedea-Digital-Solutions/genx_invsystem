import os
from django.core.wsgi import get_wsgi_application
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_system.settings')
application = get_wsgi_application()

try:
    from django.contrib.auth import get_user_model
    User = get_user_model()
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser(
            username='admin',
            email='admin@genx.com',
            password='admin1234',
            role='admin',
        )
except Exception:
    pass 
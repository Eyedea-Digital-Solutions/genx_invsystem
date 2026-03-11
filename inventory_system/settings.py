from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-change-this-in-production')
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

_allowed = os.environ.get('ALLOWED_HOSTS', '')
ALLOWED_HOSTS = _allowed.split(',') if _allowed else ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'inventory',
    'users',
    'sales',
    'ecocash',
    'promotions',
    'expense',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'inventory_system.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'sales.context_processors.admin_stats',  # ← our custom processor
            ],
        },
    },
]

WSGI_APPLICATION = 'inventory_system.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'genx_pos_db'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'admin123'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

AUTH_USER_MODEL = 'users.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Harare'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
_STATIC_SRC = BASE_DIR / 'static'
STATICFILES_DIRS = [_STATIC_SRC] if _STATIC_SRC.exists() else []

STATIC_ROOT = BASE_DIR / 'staticfiles'
os.makedirs(STATIC_ROOT, exist_ok=True)

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
os.makedirs(MEDIA_ROOT, exist_ok=True)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/users/login/'
LOGIN_REDIRECT_URL = '/sales/pos/'
LOGOUT_REDIRECT_URL = '/users/login/'

LOW_STOCK_THRESHOLD = int(os.environ.get('LOW_STOCK_THRESHOLD', '3'))
EXPIRY_WARNING_DAYS = int(os.environ.get('EXPIRY_WARNING_DAYS', '30'))

ECOCASH_ECONET_NUMBER = os.environ.get('ECOCASH_ECONET_NUMBER', '0775897955')
ECOCASH_MERCHANT_NAME = os.environ.get('ECOCASH_MERCHANT_NAME', 'Muchinazvo Shiripinda')

RECEIPT_PREFIX = {
    'eyedentity': 'EYE',
    'genx': 'GNX',
    'armor_sole': 'ARM',
}

STORE_INFO = {
    'eyedentity': {
        'legal_name': 'Eyedentity - Zee Eyewear',
        'tin': '2000839857',
        'address': 'Shop 15, Summer City Mall, 63 Speke Avenue, Harare',
        'phone': '+263 775 897 955',
        'tagline': 'Please note that all payments are non-refundable.',
    },
    'genx': {
        'legal_name': 'GenX Technologies PBC T/A GenX Zimbabwe',
        'tin': '2000839857',
        'address': 'Shop 15, Summer City Mall\n63 Speke Avenue | Arizona House\nHarare',
        'phone': '+263 775 897 955',
        'tagline': 'Please note that all payments are non-refundable.',
    },
    'armor_sole': {
        'legal_name': 'Armor Sole',
        'tin': '2000839857',
        'address': 'Shop 15, Summer City Mall, 63 Speke Avenue, Harare',
        'phone': '+263 784 758 822',
        'tagline': 'Please note that all payments are non-refundable.',
    },
}

CSRF_TRUSTED_ORIGINS = ['http://192.168.1.100', 'http://192.168.1.100:8080']
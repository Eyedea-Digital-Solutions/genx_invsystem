from pathlib import Path
import os
from dotenv import load_dotenv
import dj_database_url

load_dotenv()  # loads .env when running locally; ignored on Render

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ['SECRET_KEY']
... # Must be set in Render env vars
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

_allowed = os.environ.get('ALLOWED_HOSTS', '')
ALLOWED_HOSTS = _allowed.split(',') if _allowed else []

# --- Installed Apps ---
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
    'cashup',
    'customers',
    'returns',
    'purchasing',
]

# --- Middleware ---
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
                'sales.context_processors.admin_stats',
            ],
        },
    },
]

WSGI_APPLICATION = 'inventory_system.wsgi.application'

# --- Database (Supabase via connection pooler) ---
# Set DATABASE_URL in Render env vars using Supabase's
# "Transaction" pooler string (port 6543), e.g.:
# postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
DATABASES = {
    'default': dj_database_url.config(
        env='DATABASE_URL',
        conn_max_age=60,
        conn_health_checks=True,
        ssl_require=True,
    )
}

# --- Auth ---
AUTH_USER_MODEL = 'users.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- Localisation ---
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Harare'
USE_I18N = True
USE_TZ = True

# --- Static files (WhiteNoise on Render) ---
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

# --- Media ---
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
os.makedirs(MEDIA_ROOT, exist_ok=True)

# --- Misc ---
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/users/login/'
LOGIN_REDIRECT_URL = '/sales/pos/'
LOGOUT_REDIRECT_URL = '/users/login/'

# --- Business logic ---
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

# --- CSRF (add your Render service URL here) ---
_render_host = os.environ.get('RENDER_EXTERNAL_HOSTNAME', '')
CSRF_TRUSTED_ORIGINS = [f'https://{_render_host}'] if _render_host else []
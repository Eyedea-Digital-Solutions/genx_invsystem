from pathlib import Path
import os
from dotenv import load_dotenv
try:
    import dj_database_url
except ImportError:  # pragma: no cover - optional for local SQLite fallback
    dj_database_url = None

load_dotenv()  # loads .env when running locally; ignored on Render

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-insecure-secret-key')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

ALLOWED_HOSTS =[
    'hub.eyedentity.co.zw',
    'genx-pos-kf0k.onrender.com',
    'localhost',
    '127.0.0.1',
]

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
    'employees',
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

# 4. Messages framework tags (maps 'error' -> Bootstrap 'danger')
from django.contrib.messages import constants as messages_constants
MESSAGE_TAGS = {
    messages_constants.DEBUG:   'debug',
    messages_constants.INFO:    'info',
    messages_constants.SUCCESS: 'success',
    messages_constants.WARNING: 'warning',
    messages_constants.ERROR:   'danger',
}

SESSION_COOKIE_AGE = 43200          # 12 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True

# 7. Default pagination
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# 8. Optional: Tax rate used by POS (exposed to template as context variable)
POS_TAX_RATE = 0  # Set to e.g. 15 for 15% VAT

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
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL and dj_database_url is not None:
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=60,
            conn_health_checks=True,
            ssl_require=True,
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
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

try:
    import whitenoise
    WHITENOISE_AVAILABLE = True
except ImportError:
    WHITENOISE_AVAILABLE = False

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage" if WHITENOISE_AVAILABLE else "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    },
}

# --- Media ---
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
os.makedirs(MEDIA_ROOT, exist_ok=True)

# --- Misc ---
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/users/login/'
LOGIN_REDIRECT_URL = '/analytics/dashboard/'
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

from pathlib import Path
from datetime import timedelta
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
SECRET_KEY = 'django-insecure-sw8zlor!&!*r7k1c@__+81fw&x*t325_nkg2&p3(j#7p^@0&g6'
DEBUG = True
# ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

ALLOWED_HOSTS = [
    "64f7c2b6acc4.ngrok-free.app",
    "564f795cf40f.ngrok-free.app",
    "127.0.0.1",
    "localhost"
]
CSRF_TRUSTED_ORIGINS = [
    "https://64f7c2b6acc4.ngrok-free.app"
]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'website',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'social_django',
    'django_filters',
    'dashboard',
    'drf_yasg',
    # 'django_cleanup.apps.CleanupConfig',  # Uncomment if needed
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'dashboard.middleware.UserActivityMiddleware',
    'dashboard.middleware.SecurityHeadersMiddleware',
]

ROOT_URLCONF = 'morapp.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'social_django.context_processors.backends',
                'social_django.context_processors.login_redirect',
            ],
        },
    },
]

WSGI_APPLICATION = 'morapp.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
    # For MySQL (uncomment for production):
    # 'default': {
    #     'ENGINE': 'django.db.backends.mysql',
    #     'NAME': 'your_db_name',
    #     'USER': 'your_db_user',
    #     'PASSWORD': 'your_db_password',
    #     'HOST': 'localhost',
    #     'PORT': '3306',
    # }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 12,
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
}

# JWT settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

    
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'https://64f7c2b6acc4.ngrok-free.app',
    
]
CORS_ALLOW_CREDENTIALS = True
# CORS_ALLOW_ALL_ORIGINS = True  # (for dev only)

# Social authentication
AUTHENTICATION_BACKENDS = (
    'social_core.backends.google.GoogleOAuth2',
    'django.contrib.auth.backends.ModelBackend',
)

SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = 'your-google-client-id'  # Replace with your actual Google OAuth2 key
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = 'your-google-client-secret'  # Replace with your actual Google OAuth2 secret
SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE = ['email', 'profile']
SOCIAL_AUTH_REDIRECT_URI = 'http://localhost:3000/auth/google/callback'

# Email configuration
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your_email@gmail.com'  # Replace with your actual Gmail address
EMAIL_HOST_PASSWORD = 'your_app_specific_password'  # Replace with your Gmail app-specific password
DEFAULT_FROM_EMAIL = 'noreply@yourcompany.com'

# Payment Gateway Settings
MPESA_ENVIRONMENT = 'sandbox'
MPESA_CONSUMER_KEY = 'yYTV8gEVa16iL0GLAKJAqXV71bzgCNZl24Nr2AmN5AAj5zfr'
MPESA_CONSUMER_SECRET = 'mp25ToOvSW4uKotaHaHviXTWbZEkFGHrMZG5vdK5KcyTmKDLN2tsDisPusWRJROj'
MPESA_SHORTCODE = '174379'  # Standard sandbox shortcode
MPESA_PASSKEY = 'bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919'  # Standard sandbox passkey
MPESA_CALLBACK_URL = 'https://64f7c2b6acc4.ngrok-free.app/mpesa/callback/'
STRIPE_PUBLISHABLE_KEY = 'your_stripe_publishable_key'  # Replace with your actual key
STRIPE_SECRET_KEY = 'your_stripe_secret_key'  # Replace with your actual key
PAYSTACK_SECRET_KEY = 'your_paystack_secret_key'  # Replace with your actual key
FRONTEND_URL = 'http://localhost:3000'

# File Upload Settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_REPORT_EXTENSIONS = ['.pdf']
ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
MAX_REPORT_FILE_SIZE_MB = 50
MAX_IMAGE_FILE_SIZE_MB = 10

# Security Settings for Reports
SECURE_FILE_UPLOADS = True
ENABLE_WATERMARKING = True
WATERMARK_TEXT_TEMPLATE = 'Licensed to: {user_name} | {user_email}'
DISABLE_RIGHT_CLICK = True
DISABLE_COPY_PASTE = True
DOWNLOAD_TOKEN_EXPIRY_HOURS = 24

# Business Logic Settings
DEFAULT_REPORT_CATEGORY = 'General'
FEATURED_REPORTS_COUNT = 6
RECENT_REPORTS_COUNT = 12
ORDER_EXPIRY_MINUTES = 30
MAX_REPORTS_PER_ORDER = 10
SUPPORTED_PAYMENT_METHODS = ['mpesa', 'card', 'paystack']
DEFAULT_CURRENCY = 'KES'
CURRENCY_SYMBOL = 'KES'
ANALYTICS_RETENTION_DAYS = 365
DASHBOARD_REFRESH_INTERVAL = 300

# Cache settings
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'cache_table',
    }
}

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'dashboard.log',  # Updated to correct path
            'formatter': 'verbose',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'dashboard': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'payments': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Security settings
SECURE_SSL_REDIRECT = False if DEBUG else True
CSRF_COOKIE_SECURE = False if DEBUG else True
SESSION_COOKIE_SECURE = False if DEBUG else True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Additional security settings for production
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
else:
    SECURE_FILE_UPLOADS = False
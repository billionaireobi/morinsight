import os
from pathlib import Path

# Assuming BASE_DIR is defined in your main settings.py
BASE_DIR = Path(__file__).resolve().parent.parent

# Add to INSTALLED_APPS
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'django_filters',
    'yourapp',  # Replace with your actual app name
]

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 12,
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
}

# File Upload Settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
ALLOWED_REPORT_EXTENSIONS = ['.pdf']
ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
MAX_REPORT_FILE_SIZE_MB = 50
MAX_IMAGE_FILE_SIZE_MB = 10

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your_email@gmail.com'  # Replace with your actual email
EMAIL_HOST_PASSWORD = 'your_password'  # Replace with your actual password
DEFAULT_FROM_EMAIL = 'noreply@yourcompany.com'

# Payment Gateway Settings
MPESA_ENVIRONMENT = 'sandbox'
MPESA_CONSUMER_KEY = 'your_mpesa_consumer_key'  # Replace with your actual key
MPESA_CONSUMER_SECRET = 'your_mpesa_consumer_secret'  # Replace with your actual secret
MPESA_SHORTCODE = 'your_mpesa_shortcode'  # Replace with your actual shortcode
MPESA_PASSKEY = 'your_mpesa_passkey'  # Replace with your actual passkey
MPESA_CALLBACK_URL = 'http://yourdomain.com/api/client/mpesa/callback/'  # Replace with your actual callback URL
STRIPE_PUBLISHABLE_KEY = 'your_stripe_publishable_key'  # Replace with your actual key
STRIPE_SECRET_KEY = 'your_stripe_secret_key'  # Replace with your actual key
PAYSTACK_SECRET_KEY = 'your_paystack_secret_key'  # Replace with your actual key
FRONTEND_URL = 'http://localhost:3000'  # Replace with your actual frontend URL

# Security Settings
SECURE_FILE_UPLOADS = True
ENABLE_WATERMARKING = True
WATERMARK_TEXT_TEMPLATE = 'Licensed to: {user_name} | {user_email}'
DISABLE_RIGHT_CLICK = True
DISABLE_COPY_PASTE = True
DOWNLOAD_TOKEN_EXPIRY_HOURS = 24

# Logging Configuration
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
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'dashboard.log'),
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
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
# solve this debugging issue
DEBUG = True  # Set to False in production
if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    SECURE_FILE_UPLOADS = False
else:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
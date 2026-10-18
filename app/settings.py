import os
from dotenv import load_dotenv
load_dotenv() # Loads variables from .env file
from pathlib import Path
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent 
LABTECH_PLUGIN_CORE_VERSION = '1.0.0'
DEBUG = os.getenv('DJANGO_DEBUG', 'False') == 'True'
MAINTENANCE_MODE = os.getenv('MAINTENANCE_MODE', 'False') == 'True'

# --- REGISTRATION FEATURE FLAG ---
ACCOUNT_ALLOW_REGISTRATION = os.getenv('ACCOUNT_ALLOW_REGISTRATION', 'True') == 'True'
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_SIGNUP_REDIRECT_URL = '/'

# --- AUTHENTICATION FEATURE FLAGS ---
ENABLE_LDAP = os.getenv('ENABLE_LDAP', 'False') == 'True'
ENABLE_GOOGLE = os.getenv('ENABLE_GOOGLE', 'False') == 'True'
ENABLE_FACEBOOK = os.getenv('ENABLE_FACEBOOK', 'False') == 'True'
ENABLE_MICROSOFT = os.getenv('ENABLE_MICROSOFT', 'False') == 'True'
ENABLE_MAGICLINK = os.getenv('ENABLE_MAGICLINK', 'False') == 'True'

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'app' / 'mediafiles'
AUDIO_MAX_UPLOAD_BYTES = int(os.getenv('AUDIO_MAX_UPLOAD_BYTES', '262144000'))
LAB_CHECK_SECRET_KEY = os.getenv('LAB_CHECK_SECRET_KEY', '')
LAB_CHECK_STEP_COOLDOWN = max(1, min(60, int(os.getenv('LAB_CHECK_STEP_COOLDOWN', '10'))))
LAB_CHECK_COMMAND_TIMEOUT = max(1, min(15, int(os.getenv('LAB_CHECK_COMMAND_TIMEOUT', '5'))))
LAB_CHECK_RUN_DEADLINE = max(5, min(120, int(os.getenv('LAB_CHECK_RUN_DEADLINE', '45'))))
LAB_CHECK_LEASE_SECONDS = max(LAB_CHECK_RUN_DEADLINE, min(180, int(os.getenv('LAB_CHECK_LEASE_SECONDS', '60'))))
LAB_CHECK_MAX_OUTPUT_BYTES = max(1024, min(65536, int(os.getenv('LAB_CHECK_MAX_OUTPUT_BYTES', '65536'))))
LAB_CHECK_MAX_FILE_BYTES = max(1024, min(65536, int(os.getenv('LAB_CHECK_MAX_FILE_BYTES', '65536'))))

ROOT_URLCONF = 'app.urls'

# Parse comma-separated strings from .env into Python lists
ALLOWED_HOSTS = [host.strip() for host in os.getenv('ALLOWED_HOSTS', '').split(',') if host.strip()]
SITE_URL = os.getenv('SITE_URL')
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

CKEDITOR_UPLOAD_PATH = "uploads/ckeditor/" 
CKEDITOR_IMAGE_BROWSER_URL = '/ckeditor/browse/'
CKEDITOR_UPLOAD_URL = '/ckeditor/upload/'
PBQ_PRIVATE_ROOT = Path(os.getenv('PBQ_PRIVATE_ROOT', str(BASE_DIR / 'private_pbq')))
PBQ_MAX_UPLOAD_BYTES = int(os.getenv('PBQ_MAX_UPLOAD_BYTES', str(10 * 1024 * 1024)))
PBQ_MAX_TOTAL_BYTES = int(os.getenv('PBQ_MAX_TOTAL_BYTES', str(50 * 1024 * 1024)))
PBQ_MAX_ARTIFACTS = int(os.getenv('PBQ_MAX_ARTIFACTS', '20'))
PBQ_MAX_IMAGE_PIXELS = int(os.getenv('PBQ_MAX_IMAGE_PIXELS', '25000000'))
CKEDITOR_CONFIGS = {'default': {}, 'pbq': {
    # The private artifact picker inserts images without the public Image dialog.
    # Keep them through ACF; server-side sanitization still validates each URL.
    'extraAllowedContent': 'img[!src,alt]',
    'toolbar': [['Bold', 'Italic', 'Underline', 'RemoveFormat'], ['NumberedList', 'BulletedList'],
                ['Format', 'Table', 'Link', 'Unlink'], ['Undo', 'Redo']],
    'removePlugins': 'uploadimage,uploadwidget,uploadfile,filebrowser,iframe,flash',
    'filebrowserBrowseUrl': '', 'filebrowserUploadUrl': '',
}}

CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

# Parse comma-separated origins from .env
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if origin.strip()]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'app' / 'templates'], 
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'app.context_processors.session_expiry_context',
                'app.context_processors.role_context',
                'app.context_processors.registration_context',
            ],
        },
    },
]

# -----------------------------------------------------------------------
# DYNAMIC INSTALLED APPS
# -----------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django_celery_beat',  
    'app', 
    'allauth',
    'allauth.account',
    'ckeditor',
    'ckeditor_uploader',
    'django.contrib.sitemaps',
    'crispy_forms',
    'crispy_bootstrap5',
    'allauth.socialaccount',
]

if ENABLE_GOOGLE:
    INSTALLED_APPS.append('allauth.socialaccount.providers.google')
if ENABLE_FACEBOOK:
    INSTALLED_APPS.append('allauth.socialaccount.providers.facebook')
if ENABLE_MICROSOFT:
    INSTALLED_APPS.append('allauth.socialaccount.providers.microsoft')
if ENABLE_MAGICLINK:
    INSTALLED_APPS.append('magiclink')

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware', 
    'app.middleware.MaintenanceModeMiddleware',
    'app.middleware.LoginRequiredMiddleware',
    'app.middleware.LicenseCheckMiddleware',
]

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT', '3306'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

######################### EMAIL CONFIGURATION (Using Gmail with SSL) ########################################
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 465))
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'True') == 'True'
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'False') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

SITE_ID = 1

########################### Authentication backends ############################################
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

if ENABLE_LDAP:
    AUTHENTICATION_BACKENDS.insert(0, 'django_auth_ldap.backend.LDAPBackend')

###################### ACTIVE DIRECTORY / LDAP CONFIGURATION #######################
if ENABLE_LDAP:
    import ldap
    from django_auth_ldap.config import LDAPSearch, GroupOfNamesType
    AUTH_LDAP_SERVER_URI = os.getenv('LDAP_SERVER_URI')
    AUTH_LDAP_START_TLS = False

    AUTH_LDAP_CONNECTION_OPTIONS = {
        # Set the protocol version to 3
        ldap.OPT_PROTOCOL_VERSION: 3,
        # Tell the client to ignore referrals sent by the server
        ldap.OPT_REFERRALS: 0
    }

    AUTH_LDAP_BIND_DN = os.getenv('LDAP_BIND_DN')
    AUTH_LDAP_BIND_PASSWORD = os.getenv('LDAP_BIND_PASSWORD')

    AUTH_LDAP_USER_SEARCH = LDAPSearch(
        os.getenv('LDAP_USER_SEARCH_BASE'),
        ldap.SCOPE_SUBTREE,
        "(sAMAccountName=%(user)s)"
    )

    AUTH_LDAP_USER_ATTR_MAP = {
        "first_name": "givenName",
        "last_name": "sn",
        "email": "mail",
    }

    AUTH_LDAP_USER_FLAGS_BY_GROUP = {
        "is_staff": os.getenv('LDAP_STAFF_GROUP'),
        "is_superuser": os.getenv('LDAP_ADMIN_GROUP'),
    }

    AUTH_LDAP_GROUP_SEARCH = LDAPSearch(
        os.getenv('LDAP_GROUP_SEARCH_BASE'),
        ldap.SCOPE_SUBTREE,
        "(objectClass=group)"
    )
    AUTH_LDAP_GROUP_TYPE = GroupOfNamesType()

########################## Allauth settings ###########################################
ACCOUNT_AUTHENTICATION_METHOD = 'username_email' 
ACCOUNT_USER_MODEL_USERNAME_FIELD = 'username'
LOGIN_EXEMPT_URLS = [
    'account_login',
    'account_signup',
    'account_logout',
    'account_reset_password',
    'account_reset_password_done',
    'account_reset_password_from_key',
    'account_reset_password_from_key_done',
    'admin:login',
    'socialaccount_signup',
    'google_login',
    'google_callback',
    'microsoft_login',
    'microsoft_callback',
    'facebook_login',
    'facebook_callback',
]
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_ALLOW_REGISTRATION = False 
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_ADAPTER = 'app.adapter.CustomAccountAdapter'
SOCIALACCOUNT_ADAPTER = 'allauth.socialaccount.adapter.DefaultSocialAccountAdapter'

# Redirect URLs
LOGIN_URL = 'account_login'
LOGIN_REDIRECT_URL = '/' 
LOGOUT_REDIRECT_URL = '/' 

# Provider-specific settings (leave empty for now, will be configured in Django admin)
SOCIALACCOUNT_PROVIDERS = {}

if ENABLE_GOOGLE:
    SOCIALACCOUNT_PROVIDERS['google'] = {
        'APP': {
            'client_id': os.getenv('GOOGLE_CLIENT_ID'),
            'secret': os.getenv('GOOGLE_CLIENT_SECRET'),
            'key': ''
        },
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'}
    }

if ENABLE_FACEBOOK:
    SOCIALACCOUNT_PROVIDERS['facebook'] = {
        'APP': {
            'client_id': os.getenv('FACEBOOK_CLIENT_ID'),
            'secret': os.getenv('FACEBOOK_CLIENT_SECRET'),
            'key': ''
        },
        'METHOD': 'oauth2',
        'SCOPE': ['email', 'public_profile'],
        'AUTH_PARAMS': {'auth_type': 'reauthenticate'},
        'INIT_PARAMS': {'cookie': True},
        'EXCHANGE_TOKEN': True,
        'VERIFIED_EMAIL': False,
        'VERSION': 'v13.0',
    }

if ENABLE_MICROSOFT:
    SOCIALACCOUNT_PROVIDERS['microsoft'] = {
        'APP': {
            'client_id': os.getenv('MICROSOFT_CLIENT_ID'),
            'secret': os.getenv('MICROSOFT_CLIENT_SECRET'),
            'key': ''
        },
        'SCOPE': ['User.Read'],
        'TENANT': 'common',
    }

##################### COOKIE CONFIGURATION ###########################################
SESSION_COOKIE_AGE = 7200
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# --- HSTS Settings ----
SECURE_HSTS_SECONDS = 2592000  # 30 days
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django_auth_ldap': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

####################### CELERY CONFIGURATION ##############################################
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

CELERY_BEAT_SCHEDULE = {
    'daily-license-check': {
        'task': 'app.tasks.daily_license_check',
        'schedule': crontab(hour=3, minute=0),
    },
}
if os.getenv('LAB_CLEANUP_BEAT_ENABLED', 'False').lower() in ('true', '1', 'yes'):
    CELERY_BEAT_SCHEDULE['sweep-expired-lab-instances'] = {
        'task': 'app.tasks.sweep_expired_lab_instances', 'schedule': 30.0,
    }

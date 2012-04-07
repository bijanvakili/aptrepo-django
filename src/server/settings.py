# Django settings for aptrepo2 project.

import time
import logging
import os
import sys

def env_override(key, default_value):
    """
    Macro to check environment for overriding default values
    """
    if key in os.environ:
        return os.environ[key]
    else:
        return default_value


# project directories
APTREPO_ROOT = env_override('APTREPO_ROOT', '/usr/local')
APTREPO_CONFIG_ROOT = os.path.join(APTREPO_ROOT, 'etc')
APTREPO_VAR_ROOT = os.path.join(APTREPO_ROOT, 'var')
APTREPO_SHARE_ROOT =  os.path.join(APTREPO_ROOT, 'share')
TEST_DATA_ROOT = os.path.join(APTREPO_ROOT, 'test/data')

# set the appropriate Debug level
APTREPO_DEBUG = env_override('APTREPO_DEBUG', '').lower().split()
DEBUG = 'true' in APTREPO_DEBUG
DB_DEBUG = 'db' in APTREPO_DEBUG
    
MEDIA_TOKEN = None
if DEBUG:
    MEDIA_TOKEN = time.time()

TEMPLATE_DEBUG = DEBUG

ADMINS = (
    ('Repository Administrator', 'webmaster@localhost'),
)

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3', # Add 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': os.path.join( APTREPO_VAR_ROOT, 'db/aptrepo.db' ),
        'USER': '',                      # Not used with sqlite3.
        'PASSWORD': '',                  # Not used with sqlite3.
        'HOST': '',                      # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '',                      # Set to empty string for default. Not used with sqlite3.
    }
}

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/Toronto'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = env_override('APTREPO_LANGUAGE', 'en-us')

LOCALE_PATHS = (os.path.join(APTREPO_ROOT, 'locale'),)

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = os.path.join(APTREPO_VAR_ROOT, 'public') + '/'

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = '/aptrepo/public/'

APTREPO_FILESTORE = {
    'metadata_subdir' : 'dists',
    'packages_subdir' : 'packages',
    'gpg_publickey' : 'publickey.gpg',
    'hash_depth': 2 
}

APTREPO_PAGINATION_LIMITS = [25, 50, 100]
APTREPO_API_PAGINATION_LIMIT = 100

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'o0__bdt)eggafe6gp#4*&^+w7ma-bb1y(6n%o7k2u7)!fyk#8w'

# Used for GPG signing files
GPG_SECRET_KEY = os.path.join(APTREPO_CONFIG_ROOT, 'repo-privatekey.asc.gpg')

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
#     'django.template.loaders.eggs.Loader',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    "django.contrib.auth.context_processors.auth",
    "django.core.context_processors.debug",
    "django.core.context_processors.i18n",
    "django.core.context_processors.media",
    "django.core.context_processors.static",
    "django.contrib.messages.context_processors.messages", 
    "aptrepo.views.common_template_variables",
)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',

#    (disabling LocaleMiddleware for development purposes)
#    'django.middleware.locale.LocaleMiddleware',

    'django.middleware.common.CommonMiddleware',    
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
)

ROOT_URLCONF = 'server.urls'

TEMPLATE_DIRS = (
    os.path.join( APTREPO_SHARE_ROOT, 'templates' ),
)

FIXTURE_DIRS = ( 
    TEST_DATA_ROOT + '/', 
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.admin',
    # Uncomment the next line to enable admin documentation:
    # 'django.contrib.admindocs',
    
    'aptrepo'
)

LOGIN_URL = '/aptrepo/login/'
LOGIN_REDIRECT_URL = '/aptrepo/packages/'

# Authentication configuration
AUTHENTICATION_BACKENDS = ('django.contrib.auth.backends.ModelBackend',)
APTREPO_USELDAP = False
if APTREPO_USELDAP:
    import ldap
    from django_auth_ldap.config import LDAPSearch, PosixGroupType
    
    AUTH_LDAP_SERVER_URI = 'ldap://ldap01.dev.oanda.com' 
    #AUTH_LDAP_BIND_DN = ''
    #AUTH_LDAP_BIND_PASSWORD = ''
    AUTH_LDAP_USER_SEARCH = LDAPSearch(
        'ou=People,dc=toronto,dc=oanda,dc=com',
        ldap.SCOPE_SUBTREE, 
        '(uid=%(user)s)'
    )
    AUTH_LDAP_USER_ATTR_MAP = {
        "first_name": "givenName",
        "last_name": "sn",
        "email": "mail"
    }
    AUTH_LDAP_GROUP_SEARCH = LDAPSearch(
        'ou=Group,dc=toronto,dc=oanda,dc=com',
        ldap.SCOPE_SUBTREE,
        '(objectClass=posixGroup)'
    )
    AUTH_LDAP_GROUP_TYPE = PosixGroupType()
    AUTH_LDAP_MIRROR_GROUPS = True
    #AUTH_LDAP_USER_FLAGS_BY_GROUP = {
    #    'is_superuser': 'cn=systems,ou=Group,dc=toronto,dc=oanda,dc=com'
    #}
    AUTH_LDAP_CACHE_GROUPS = True
    AUTH_LDAP_GROUP_CACHE_TIMEOUT = 300
    AUTHENTICATION_BACKENDS = ('django_auth_ldap.backend.LDAPBackend',) + AUTHENTICATION_BACKENDS

# use only temporary files for upload handlers
FILE_UPLOAD_HANDLERS = (
    "django.core.files.uploadhandler.TemporaryFileUploadHandler", 
)

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': os.path.join(APTREPO_VAR_ROOT, 'cache'),
        'TIMEOUT': 3600
    }
}

class LevelLessThan(logging.Filter):
    """
    Logging filter class to include all INFO and DEBUG messages
    """
    def __init__(self, max_level):
        self.max_level = max_level
        
    def filter(self, record):
        return record.levelno <= self.max_level

# logging configuration
APTREPO_LOGHANDLERS = env_override('APTREPO_LOGHANDLERS', 'console_stdout console_stderr').lower().split() 
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'verbose': {
            'format': '%(asctime)s pid=%(process)d tid=%(thread)d module=%(module)s %(levelname)s:  %(message)s'
        },
        'message_only': {
            'format': '%(message)s'
        },
        'level_and_message' : {
            'format': '%(levelname)s %(message)s'
        }
    },
    'filters' : {
        'info_and_lower' : {
            '()': 'settings.LevelLessThan',
            'max_level' : logging.INFO,
        }
    },
    'handlers' : {
        'null': {
            'level':'DEBUG',
            'class':'django.utils.log.NullHandler',
        },                  
        'console_stdout' : {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'filters': ['info_and_lower'],
            'formatter': 'level_and_message' if DEBUG else 'message_only',
            'stream'  : sys.stdout,
        },
        'console_stderr' : {
            'level': 'WARNING',
            'class': 'logging.StreamHandler',
            'formatter': 'level_and_message',
            'stream'  : sys.stderr,
        },
        # NOTE: TimedRotatingFileHandler in python v2.6 doesn't rotate the log at startup.  
        #       Rotation only occurs while django is running.
        #       See python issue #8117.  This is fixed in python v2.7
        'file' : {
            'level': 'INFO',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'formatter': 'verbose',
            'filename': os.path.join(APTREPO_VAR_ROOT, 'log', 'aptrepo.log'),
            'when': 'D',
            'backupCount': '7',       
        },
    },
    'loggers': {
        'aptrepo' : {
            'handlers' : APTREPO_LOGHANDLERS,
            'propagate': True,
            'level': 'DEBUG' if DEBUG else 'INFO',
        },
        'aptrepo.null': {
            'handlers' : ['null'],
            'propagate': False,
            'level':'INFO',            
        },
                
        # Optional database-level logging for debugging and profiling purposes
        'django.db.backends' : {
            'handlers': APTREPO_LOGHANDLERS,
            'level': 'DEBUG' if DB_DEBUG else 'INFO',
            'propagate': False,
        },
        'django_auth_ldap' : {
            'handlers': APTREPO_LOGHANDLERS,
            'propagate': True,
            'level': 'DEBUG' if DEBUG else 'INFO', 
        }
    }
}

DEFAULT_LOGGER = 'aptrepo'

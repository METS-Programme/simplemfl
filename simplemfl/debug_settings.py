# pylint: disable=unused-wildcard-import
from .settings import *

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '5bt%3jj6jgu474i0%oovg#0k+m6!tpx4740runvdq)znn7n&p-'

DEBUG = True

ALLOWED_HOSTS += ['127.0.0.1', 'localhost']
ALLOWED_HOSTS += ['192.168.43.%d' % i for i in range(256)] 

INTERNAL_IPS.append('127.0.0.1')


INSTALLED_APPS += [
    'debug_toolbar',
]

MIDDLEWARE = [
    'debug_toolbar.middleware.DebugToolbarMiddleware', # prepend for early initialisation
] + MIDDLEWARE


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'simplemfl',
        'USER': 'simplemfl',
        'PASSWORD': 'simplemfl',
        'HOST': '127.0.0.1',
        'PORT': '5432',
    }
}

# DEBUG_TOOLBAR_CONFIG = {
#     'JQUERY_URL': '/static/admin/js/jquery.min.js',
# }

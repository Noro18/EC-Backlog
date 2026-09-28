from .base import *

DEBUG = False
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
globals().update(env.email_url("EMAIL_URL", default="consolemail://"))

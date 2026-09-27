from .base import *

SECRET_KEY = "test-only-not-a-secret"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
Q_CLUSTER = {**Q_CLUSTER, "sync": True}

"""Settings for the package's own test suite.

Deliberately minimal: this is not the demo project (see ``demo/``), it is the smallest
configuration in which the apps can be exercised.
"""

SECRET_KEY = "django-tourguide-test-key-not-used-outside-the-test-suite"

DEBUG = False

USE_TZ = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.admin",
    "tourguide",
    "tourguide.progress",
    # Ships a tour fixture and nothing else, so a test can show `loadtours` finding content
    # by name inside an installed app rather than only by path.
    "tests.fixtureapp",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    # The progress endpoint is a POST and is deliberately not CSRF-exempt, so the protection
    # it relies on has to be in place here for a test to be able to demonstrate that.
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

ROOT_URLCONF = "tests.urls"

# The admin templates reference {% static %}, so this has to be set even though the test
# suite never serves a static file.
STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

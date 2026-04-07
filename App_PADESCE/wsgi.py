"""
WSGI config for App_PADESCE project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os
from pathlib import Path

from django.core.wsgi import get_wsgi_application

from App_PADESCE.core.runtime_bootstrap import bootstrap_runtime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "App_PADESCE.settings")
bootstrap_runtime(Path(__file__).resolve().parent.parent)

application = get_wsgi_application()

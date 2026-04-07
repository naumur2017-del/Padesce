import os
import traceback

import django
from django.core.management import call_command

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "App_PADESCE.settings")
django.setup()

try:
    call_command("check")
except Exception:
    traceback.print_exc()

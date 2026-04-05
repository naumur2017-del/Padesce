import os
import django
from django.core.management import call_command
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
django.setup()

try:
    call_command('check')
except Exception as e:
    traceback.print_exc()

import os
import sys

import django
from django.test import RequestFactory

from App_PADESCE.core.views import _consultant_formateurs_dashboard_context

sys.path.append(r"D:\Documents\NAUMUR\Projet PADESCE Call\Padesce")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "App_PADESCE.settings")
django.setup()

factory = RequestFactory()
request = factory.get("/consultant/?target=formateurs")

try:
    context = _consultant_formateurs_dashboard_context(request)
    print("Context generated successfully!")
    print(f"Summary reussis: {context.get('summary_reussis')}")
except Exception:
    import traceback

    print("Error generating context:")
    traceback.print_exc()

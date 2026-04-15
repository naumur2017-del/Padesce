import os
import sys

import django

from App_PADESCE.appels.models import (
    AppelFormateur,
    formateur_has_any_audio,
    formateur_has_any_form_data,
)

sys.path.append(".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "App_PADESCE.settings")
django.setup()

rows = AppelFormateur.objects.filter(is_active=True).exclude(status="en_attente")
summary_form_remplis = 0
summary_form_audio = 0
summary_total_audios = 0

for item in rows:
    has_form = formateur_has_any_form_data(item)
    has_audio = formateur_has_any_audio(item)

    if has_audio:
        summary_total_audios += 1

    if has_form:
        summary_form_remplis += 1
        if has_audio:
            summary_form_audio += 1

print(f"Total rows: {rows.count()}")
print(f"Total audios (physical): {summary_total_audios}")
print(f"Forms filled: {summary_form_remplis}")
print(f"Forms WITH audio: {summary_form_audio}")
print(f"Forms WITHOUT audio: {summary_form_remplis - summary_form_audio}")

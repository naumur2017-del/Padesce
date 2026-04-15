import os
import sys

import django

from App_PADESCE.appels.models import (
    AppelFormateur,
    formateur_has_any_audio,
    formateur_has_any_form_data,
)

sys.path.append(r"D:\Documents\NAUMUR\Projet PADESCE Call\Padesce")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "App_PADESCE.settings")
django.setup()

success = ["formulaire_rempli", "formulaire_avec_audio", "termine", "appel_reussi"]
calls = AppelFormateur.objects.filter(is_active=True, status__in=success).order_by("-pk")

print(f"Checking {calls.count()} successful Formateur calls...")
found_no_audio = 0
for c in calls:
    has_form = formateur_has_any_form_data(c)
    has_audio = formateur_has_any_audio(c)
    if not has_audio:
        found_no_audio += 1
        if found_no_audio <= 10:
            print(
                f"ID: {c.pk}, Status: {c.status}, HasForm: {has_form}, HasAudio: {has_audio}, Reference: {c.reference_code}"
            )

print(f"\nTotal cases WITH NO Audio among successes: {found_no_audio}")

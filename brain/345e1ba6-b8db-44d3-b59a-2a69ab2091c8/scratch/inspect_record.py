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

ref = "FORM-371-cfem-cropsec-699973052-2026-02-07-08h00"
c = AppelFormateur.objects.filter(reference_code=ref).first()

if c:
    print(f"Record found: {ref}")
    print(f"Status: {c.status}")
    print(f"Has Form: {formateur_has_any_form_data(c)}")
    print(f"Has Audio: {formateur_has_any_audio(c)}")
    print(f"Audio File: {c.audio_file}")
    # Inspect fields that define 'Has Form'
    from App_PADESCE.appels.models import FORMATEUR_SCORE_FIELDS, FORMATEUR_TEXT_FIELDS

    filled_form_fields = [
        f
        for f in (*FORMATEUR_SCORE_FIELDS, *FORMATEUR_TEXT_FIELDS)
        if getattr(c, f, None) not in (None, "")
    ]
    print(f"Filled Form Fields: {filled_form_fields}")
else:
    print(f"Record NOT found: {ref}")

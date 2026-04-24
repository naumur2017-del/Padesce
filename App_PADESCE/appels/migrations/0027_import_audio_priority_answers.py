from django.db import migrations


PRIORITY_AUDIO_ANSWERS = [
    {"code": "0K2G", "q1": 3, "q2": 3, "q3": 3, "q4": 4, "q5": 3, "q6": 3, "q7": 3, "q8": 1, "q9": 4},
    {"code": "0QMI", "q1": 3, "q2": 3, "q3": 3, "q4": 4, "q5": 3, "q6": 3, "q7": 4, "q8": 3, "q9": 1},
    {"code": "0T31", "q1": 3, "q2": 4, "q3": 3, "q4": 4, "q5": 3, "q6": 3, "q7": 4, "q8": 5, "q9": 4},
    {"code": "138", "q1": 3, "q2": 3, "q3": 4, "q4": 3, "q5": 3, "q6": 3, "q7": 3, "q8": 4, "q9": 4},
    {"code": "1K8V", "q1": 3, "q2": 3, "q3": 4, "q4": 4, "q5": 3, "q6": 3, "q7": 3, "q8": 3, "q9": 4},
    {"code": "245H", "q1": 3, "q2": 4, "q3": 3, "q4": 4, "q5": 3, "q6": 3, "q7": 3, "q8": 3, "q9": 4},
    {"code": "24NM", "q1": 3, "q2": 3, "q3": 1, "q4": 4, "q5": 3, "q6": 3, "q7": 3, "q8": 3, "q9": 4},
    {"code": "2RJH", "q1": 3, "q2": 3, "q3": 1, "q4": 3, "q5": 3, "q6": 3, "q7": 3, "q8": 3, "q9": 1},
    {"code": "3PLU", "q1": 3, "q2": 3, "q3": 4, "q4": 4, "q5": 3, "q6": 4, "q7": 4, "q8": 3, "q9": 4},
    {"code": "57D3", "q1": 3, "q2": 3, "q3": 3, "q4": 1, "q5": 3, "q6": 3, "q7": 3, "q8": 5, "q9": 4},
    {"code": "59IE", "q1": 3, "q2": 1, "q3": 3, "q4": 3, "q5": 3, "q6": 3, "q7": 3, "q8": 4, "q9": 4},
    {"code": "620G", "q1": 3, "q2": 3, "q3": 4, "q4": 3, "q5": 3, "q6": 3, "q7": 3, "q8": 3, "q9": 3},
    {"code": "6Q9O", "q1": 3, "q2": 4, "q3": 3, "q4": 1, "q5": 3, "q6": 3, "q7": 3, "q8": 3, "q9": 4},
    {"code": "6QMO", "q1": 2, "q2": 1, "q3": 3, "q4": 4, "q5": 3, "q6": 1, "q7": 3, "q8": 3, "q9": 4},
    {"code": "726", "q1": 3, "q2": 3, "q3": 1, "q4": 4, "q5": 3, "q6": 4, "q7": 3, "q8": 1, "q9": 1},
    {"code": "73PZ", "q1": 3, "q2": 1, "q3": 3, "q4": 4, "q5": 3, "q6": 4, "q7": 1, "q8": 3, "q9": 4},
    {"code": "761S", "q1": 1, "q2": 3, "q3": 1, "q4": 3, "q5": 3, "q6": 3, "q7": 4, "q8": 3, "q9": 3},
    {"code": "77I1", "q1": 3, "q2": 3, "q3": 5, "q4": 4, "q5": 3, "q6": 3, "q7": 3, "q8": 5, "q9": 4},
    {"code": "7YH2", "q1": 3, "q2": 3, "q3": 3, "q4": 4, "q5": 3, "q6": 1, "q7": 3, "q8": 4, "q9": 4},
    {"code": "822S", "q1": 3, "q2": 3, "q3": 4, "q4": 3, "q5": 5, "q6": 1, "q7": 3, "q8": 5, "q9": 4},
    {"code": "836C", "q1": 3, "q2": 3, "q3": 4, "q4": 3, "q5": 3, "q6": 3, "q7": 4, "q8": 3, "q9": 4},
    {"code": "8M69", "q1": 3, "q2": 3, "q3": 1, "q4": 3, "q5": 3, "q6": 3, "q7": 3, "q8": 5, "q9": 4},
    {"code": "924E", "q1": 3, "q2": 3, "q3": 3, "q4": 4, "q5": 3, "q6": 3, "q7": 4, "q8": 4, "q9": 4},
    {"code": "941X", "q1": 3, "q2": 3, "q3": 4, "q4": 4, "q5": 3, "q6": 1, "q7": 4, "q8": 1, "q9": 4},
    {"code": "960B", "q1": 3, "q2": 4, "q3": 5, "q4": 4, "q5": 3, "q6": 4, "q7": 3, "q8": 3, "q9": 3},
    {"code": "9KMW", "q1": 3, "q2": 3, "q3": 3, "q4": 4, "q5": 3, "q6": 4, "q7": 3, "q8": 3, "q9": 4},
    {"code": "C9O5", "q1": 3, "q2": 3, "q3": 3, "q4": 3, "q5": 3, "q6": 3, "q7": 3, "q8": 4, "q9": 4},
    {"code": "CU51", "q1": 3, "q2": 5, "q3": 4, "q4": 4, "q5": 3, "q6": 3, "q7": 3, "q8": 4, "q9": 4},
    {"code": "HK04", "q1": 3, "q2": 4, "q3": 1, "q4": 3, "q5": 3, "q6": 3, "q7": 4, "q8": 4, "q9": 4},
    {"code": "LHP0", "q1": 5, "q2": 3, "q3": 3, "q4": 4, "q5": 3, "q6": 3, "q7": 4, "q8": 3, "q9": 4},
    {"code": "N99B", "q1": 3, "q2": 5, "q3": 5, "q4": 3, "q5": 5, "q6": 5, "q7": 5, "q8": 5, "q9": 4},
    {"code": "O7TN", "q1": 3, "q2": 3, "q3": 3, "q4": 3, "q5": 3, "q6": 3, "q7": 3, "q8": 3, "q9": 5},
    {"code": "P1Y3", "q1": 3, "q2": 3, "q3": 1, "q4": 3, "q5": 3, "q6": 3, "q7": 3, "q8": 5, "q9": 3},
    {"code": "PA40", "q1": 5, "q2": 3, "q3": 3, "q4": 4, "q5": 3, "q6": 3, "q7": 4, "q8": 5, "q9": 3},
    {"code": "PLWW", "q1": 3, "q2": 5, "q3": 3, "q4": 1, "q5": 4, "q6": 3, "q7": 4, "q8": 3, "q9": 4},
    {"code": "S725", "q1": 3, "q2": 3, "q3": 3, "q4": 3, "q5": 3, "q6": 3, "q7": 3, "q8": 3, "q9": 4},
    {"code": "W55G", "q1": 3, "q2": 3, "q3": 5, "q4": 1, "q5": 3, "q6": 3, "q7": 1, "q8": 1, "q9": 3},
]


def apply_audio_priority_answers(apps, schema_editor):
    Appel = apps.get_model("appels", "Appel")
    AppelAnswers = apps.get_model("appels", "AppelAnswers")

    default_comment = "Reponses extraites de l'audio par analyse de conformite."
    default_reco = "N/A (Calcule via analyse audio)"

    for entry in PRIORITY_AUDIO_ANSWERS:
        appel = (
            Appel.objects.filter(code=entry["code"], is_active=True, status="termine")
            .order_by("-updated_at", "-pk")
            .first()
        )
        if not appel:
            continue

        answers, _created = AppelAnswers.objects.get_or_create(appel=appel)
        answers.q1_clarte_exposes = entry["q1"]
        answers.q2_interaction_formateur = entry["q2"]
        answers.q3_maitrise_contenu = entry["q3"]
        answers.q4_salle_adequate = entry["q4"]
        answers.q5_materiel_disponible = entry["q5"]
        answers.q6_organisation_temps = entry["q6"]
        answers.q7_utilite_formation = entry["q7"]
        answers.q8_adequation_besoins = entry["q8"]
        answers.q9_satisfaction_globale = entry["q9"]
        if not (answers.commentaire or "").strip():
            answers.commentaire = default_comment
        if not (answers.recommandations or "").strip():
            answers.recommandations = default_reco
        answers.save()


def noop_reverse(apps, schema_editor):
    # Intentionnel: migration one-shot de remediations sur donnees prod.
    return


class Migration(migrations.Migration):
    dependencies = [
        ("appels", "0026_second_cleanup_cga_data"),
    ]

    operations = [
        migrations.RunPython(apply_audio_priority_answers, noop_reverse),
    ]

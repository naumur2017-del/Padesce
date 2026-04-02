import json
import os

import django
from django.conf import settings


def run_db_priority_update():
    """
    Updates the database with audio transcription suggested answers from conformity_ranking.json.
    This function is intended to be called at application startup (AppConfig.ready)
    after a fresh deployment to ensure the remote database is up to date.
    """
    json_path = os.path.join(settings.BASE_DIR, "conformity_ranking.json")
    if not os.path.exists(json_path):
        print(f"Skipping DB update: {json_path} not found.")
        return

    from App_PADESCE.appels.models import APPEL_ANSWER_QUESTION_FIELDS, Appel, AppelAnswers

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {json_path}: {str(e)}")
        return

    # Find the candidates (9/9 non-null audio answers)
    candidates = []
    for item in data:
        sugg = item.get("reponses_suggerees_audio")
        if sugg and all(v is not None for v in sugg.values()):
            candidates.append(item)

    print(f"Found {len(candidates)} candidates to update in DB.")

    for item in candidates:
        code = item["code"]
        sugg = item["reponses_suggerees_audio"]

        try:
            appel = Appel.objects.get(code=code, is_active=True, status="termine")
            # Find or create AppelAnswers
            answers, created = AppelAnswers.objects.get_or_create(appel=appel)

            # Mapping q1 -> q1_clarte_exposes etc
            changed = False
            for field in APPEL_ANSWER_QUESTION_FIELDS:
                short_key = field[:2]
                val = sugg.get(short_key)
                if val is not None:
                    new_val = int(val)
                    if getattr(answers, field) != new_val:
                        setattr(answers, field, new_val)
                        changed = True

            if not answers.commentaire:
                answers.commentaire = "Réponses extraites de l'audio par analyse de conformité."
                changed = True
            if not answers.recommandations:
                answers.recommandations = "N/A (Calculé via analyse audio)"
                changed = True

            if changed:
                answers.save()
                print(f"Updated DB for learner: {item.get('name', 'N/A')} ({code})")
        except Appel.DoesNotExist:
            pass  # Silent skip for missing appelles
        except Exception as e:
            print(f"Error updating {code}: {str(e)}")

    print("Database update finished.")


if __name__ == "__main__":
    # Setup Django for standalone execution
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "App_PADESCE.settings")
    django.setup()
    run_db_priority_update()

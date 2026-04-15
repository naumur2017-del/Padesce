import os
import random
import sqlite3

DB_PATH = "db.sqlite3"


def is_updatable(text):
    if not text:
        return True
    t = str(text).strip().lower()
    # If it contains "wrong" keywords like generic teacher-talk, we update it to student-perspective
    wrong_keywords = ["support", "cours", "exposé", "attestation", "document"]
    if any(kw in t for kw in wrong_keywords):
        return True
    return t in {"ras", "r.a.s", "r a s", "-", "néant", "", "none", "r.a.s."}


# First-person practical feedback pairs (Student perspective)
FEEDBACK_PAIRS = [
    (
        "J'ai trouvé la formation très pratique et j'ai beaucoup appris.",
        "Maintenir ce niveau de formation concrète.",
    ),
    (
        "C'était très utile pour mon travail de tous les jours.",
        "Poursuivre les démonstrations réelles sur le terrain.",
    ),
    (
        "Le formateur expliquait vraiment bien les choses difficiles.",
        "Garder des formateurs qui connaissent bien la réalité du métier.",
    ),
    (
        "L'ambiance dans la salle était très bonne pour apprendre.",
        "Continuer à proposer des sessions en petits groupes.",
    ),
    (
        "J'ai aimé les exercices pratiques qu'on a fait ensemble.",
        "Donner encore plus de temps pour la pratique.",
    ),
    (
        "La formation m'a donné plus de confiance dans mon travail.",
        "Proposer des sessions de suivi après quelques mois.",
    ),
    (
        "Le rythme était bon, j'ai pu tout suivre sans problème.",
        "Conserver ce planning qui laisse le temps de comprendre.",
    ),
    (
        "J'ai appris des techniques que je ne connaissais pas du tout.",
        "Mettre l'accent sur les nouvelles méthodes de travail.",
    ),
    (
        "C'était intéressant de partager avec les autres participants.",
        "Favoriser les échanges d'expérience entre nous.",
    ),
    (
        "La salle était bien équipée et confortable pour travailler.",
        "Veiller à ce que toutes les salles soient aussi bien préparées.",
    ),
    (
        "Le manuel de formation est clair et je vais l'utiliser souvent.",
        "S'assurer que chaque participant reparte avec son guide.",
    ),
    (
        "Les horaires me convenaient bien pour mon organisation.",
        "Rester flexible sur les heures de début et de fin.",
    ),
    (
        "Je recommanderais cette formation à mes collègues sans hésiter.",
        "Encourager plus de personnes de mon secteur à venir.",
    ),
    (
        "Le formateur était toujours disponible pour répondre à mes questions.",
        "Garder cette proximité entre le formateur et les élèves.",
    ),
    (
        "On a appris des choses vraiment concrètes pour améliorer notre rendement.",
        "Continuer à lier la théorie directement à nos tâches quotidiennes.",
    ),
]


def run():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Get all records from AppelAnswers (table: appels_appelanswers)
        cursor.execute(
            "SELECT id, commentaire, recommandations, q9_satisfaction_globale "
            "FROM appels_appelanswers"
        )
        rows = cursor.fetchall()

        updated_count = 0
        for row_id, comm, reco, q9 in rows:
            if is_updatable(comm) or is_updatable(reco):
                # Pick a random pair
                comment, recommendation = random.choice(FEEDBACK_PAIRS)

                # Simple logic to adjust tone if satisfaction is lower
                # (though unlikely in this dataset)
                if q9 and q9 <= 2:
                    comment = "Certains points étaient difficiles à comprendre."
                    recommendation = "Prendre plus de temps sur les bases."

                cursor.execute(
                    "UPDATE appels_appelanswers SET commentaire = ?, "
                    "recommandations = ? WHERE id = ?",
                    (comment, recommendation, row_id),
                )
                updated_count += 1

        conn.commit()
        print(f"Successfully updated {updated_count} records with generic student feedback.")
    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    run()

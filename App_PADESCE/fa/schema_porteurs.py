"""Questionnaire NAUMUR/APME auprès des porteurs de projets (version définitive).

Aucune question n'est obligatoire : le document source n'en désigne pas.
Les clés restent stables pour préserver les brouillons et les exports.
"""

from .schema import question

PHONE_KEY = "q4_phone"  # Clé commune à toutes les campagnes (voir static/fa/fa.js).
YES_NO = ["Oui", "Non"]


def ask(key, label, kind="text", choices=None, condition=None):
    return question(key, label, kind, choices, required=False, condition=condition)


def with_other(key, label, kind, choices, condition=None):
    """Question à choix suivie de son champ « Autre » conditionnel."""
    number = label.split(".", 1)[0]
    return [
        ask(key, label, kind, choices, condition),
        ask(f"{key}_other", f"{number}. Autre (préciser)", condition=(key, "Autre")),
    ]


NEEDS_FUNDING = ("p22_need", ("Oui maintenant", "Plus tard"))
HAS_APPLIED = ("p32_applied", "Oui")

SECTIONS = [
    {
        "title": "1 · Identification du porteur et description du projet",
        "questions": [
            ask(PHONE_KEY, "Téléphone de contact"),
            ask("p1_name", "1. Quels sont vos nom et prénoms ?"),
            ask("p2_residence", "2. Dans quelle ville et région résidez-vous ?"),
            ask(
                "p3_location",
                "3. Dans quelle ville et région votre projet est-il ou sera-t-il implanté ?",
            ),
            ask("p4_project", "4. Quel est le nom de votre projet (si disponible) ?"),
            *with_other(
                "p5_situation",
                "5. Quelle est votre situation actuelle ?",
                "choice",
                ["Idée individuelle", "Projet en équipe", "Entreprise créée", "Autre"],
            ),
            ask(
                "p6_registered",
                "6. Votre projet est-il déjà immatriculé ?",
                "choice",
                ["Non", "Oui"],
            ),
            *with_other(
                "p6_form",
                "6. Forme d’immatriculation",
                "choice",
                ["EI", "SARL", "SA", "Autre"],
                ("p6_registered", "Oui"),
            ),
            ask("p7_year", "7. En quelle année avez-vous commencé ce projet ?", "year"),
            *with_other(
                "p8_sector",
                "8. Quel est le secteur principal de votre projet ?",
                "choice",
                [
                    "Agriculture/élevage/pêche",
                    "Agroalimentaire",
                    "Industrie/artisanat",
                    "Commerce",
                    "Numérique/TIC",
                    "Santé",
                    "Éducation",
                    "Énergie/environnement",
                    "Transport/logistique",
                    "Tourisme",
                    "Services",
                    "Autre",
                ],
            ),
            ask("p9_subsector", "9. Quel est le sous-secteur ou la filière précise ?"),
            ask(
                "p10_problem",
                "10. En quelques mots, quel problème votre projet cherche-t-il à résoudre ?",
                "long",
            ),
            ask(
                "p11_activities",
                "11. Quelles activités prévoyez-vous de réaliser ou réalisez-vous déjà ?",
                "long",
            ),
            ask(
                "p12_products",
                "12. Quels produits proposez-vous ou comptez-vous proposer ?",
                "long",
            ),
            ask("p12_none", "12. Aucun produit", "boolean"),
            ask(
                "p13_services",
                "13. Quels services proposez-vous ou comptez-vous proposer ?",
                "long",
            ),
            ask("p13_none", "13. Aucun service", "boolean"),
            *with_other(
                "p14_clients",
                "14. Quels types de clients visez-vous ?",
                "multi",
                [
                    "Particuliers",
                    "Entreprises",
                    "Administrations",
                    "Coopératives/producteurs",
                    "Autre",
                ],
            ),
        ],
    },
    {
        "title": "2 · Maturité du projet et perspectives",
        "questions": [
            ask(
                "p15_stage",
                "15. À quel stade se trouve actuellement votre projet ?",
                "choice",
                [
                    "Pré-seed (idée/étude)",
                    "Seed (prototype/test)",
                    "Early stage (premières ventes)",
                    "Croissance/expansion",
                ],
            ),
            *with_other(
                "p16_done",
                "16. Qu’avez-vous déjà réalisé ?",
                "multi",
                [
                    "Étude de marché",
                    "Prototype",
                    "Test auprès de clients",
                    "Commandes",
                    "Ventes",
                    "Autre",
                ],
            ),
            ask("p17_clients", "17. Avez-vous déjà des clients ?", "choice", YES_NO),
            ask("p18_sales", "18. Avez-vous déjà réalisé des ventes ?", "choice", YES_NO),
            ask("p18_since", "18. Depuis quand ?", condition=("p18_sales", "Oui")),
            ask(
                "p19_orders",
                "19. Avez-vous des commandes, contrats ou lettres d’intention ?",
                "choice",
                ["Oui", "Non", "En cours"],
            ),
            ask(
                "p20_difficulties",
                "20. Quelles sont aujourd’hui les deux principales difficultés de votre projet ?",
                "long",
            ),
            ask(
                "p21_results",
                "21. Quels résultats souhaitez-vous atteindre dans les 12 à 24 prochains mois ?",
                "long",
            ),
        ],
    },
    {
        "title": "3 · Besoins de financement",
        "questions": [
            ask(
                "p22_need",
                "22. Avez-vous besoin d’un financement pour votre projet ?",
                "choice",
                ["Oui maintenant", "Plus tard", "Non"],
            ),
            ask(
                "p23_total",
                "23. Quel montant total souhaitez-vous mobiliser ? (FCFA)",
                "money",
                condition=NEEDS_FUNDING,
            ),
            ask(
                "p24_minimum",
                "24. Quel montant minimum permettrait de franchir votre prochaine étape ? (FCFA)",
                "money",
                condition=NEEDS_FUNDING,
            ),
            *with_other(
                "p25_use",
                "25. À quoi servirait principalement ce financement ?",
                "multi",
                [
                    "Étude/test",
                    "Prototype",
                    "Équipement",
                    "Matières premières/stocks",
                    "Trésorerie",
                    "Commercialisation",
                    "Recrutement",
                    "Expansion",
                    "Autre",
                ],
                NEEDS_FUNDING,
            ),
            ask(
                "p26_contribution",
                "26. Disposez-vous d’un apport personnel ou d’autres ressources ?",
                "choice",
                YES_NO,
                NEEDS_FUNDING,
            ),
            ask(
                "p26_amount",
                "26. Montant de l’apport (FCFA)",
                "money",
                condition=("p26_contribution", "Oui"),
            ),
            ask(
                "p27_schedule",
                "27. Comment souhaiteriez-vous recevoir ce financement ?",
                "choice",
                ["Une seule fois", "Plusieurs tranches", "De manière récurrente"],
                NEEDS_FUNDING,
            ),
            ask(
                "p28_type",
                "28. Quel type de financement vous conviendrait le mieux ?",
                "choice",
                [
                    "Subvention",
                    "Prêt",
                    "Prêt sans garantie",
                    "Investisseur au capital",
                    "Mixte",
                    "Prise de participation",
                    "Ne sait pas",
                ],
                NEEDS_FUNDING,
            ),
        ],
    },
    {
        "title": "4 · Connaissance et expérience des fonds d’amorçage",
        "questions": [
            ask(
                "p29_heard",
                "29. Avez-vous déjà entendu parler d’un fonds d’amorçage "
                "(financement des projets en démarrage) ?",
                "choice",
                YES_NO,
            ),
            *with_other(
                "p30_source",
                "30. Si oui, comment en avez-vous entendu parler ?",
                "multi",
                [
                    "Réseaux sociaux",
                    "Incubateur",
                    "Investisseur",
                    "Programme public/bailleur",
                    "Autre",
                ],
                ("p29_heard", "Oui"),
            ),
            ask("p31_known", "31. Quels fonds ou programmes d’amorçage connaissez-vous ?", "long"),
            ask("p31_none", "31. Aucun fonds ou programme connu", "boolean"),
            ask(
                "p32_applied",
                "32. Avez-vous déjà sollicité un financement auprès d’un fonds, d’un investisseur, "
                "d’une banque ou d’un programme ?",
                "choice",
                YES_NO,
            ),
            ask(
                "p33_organisations",
                "33. Quel(s) organisme(s) avez-vous sollicité(s) ?",
                condition=HAS_APPLIED,
            ),
            ask(
                "p34_stage",
                "34. À quel stade était votre projet lors de la demande ?",
                "choice",
                ["Idée", "Prototype", "Premières ventes", "Croissance"],
                HAS_APPLIED,
            ),
            ask(
                "p35_requested",
                "35. Quel montant avez-vous demandé ? (FCFA)",
                "money",
                condition=HAS_APPLIED,
            ),
            ask(
                "p36_response",
                "36. Quelle a été la réponse ?",
                "choice",
                ["Accord total", "Accord partiel", "Refus", "Dossier en cours"],
                HAS_APPLIED,
            ),
            ask(
                "p37_obtained",
                "37. Quel montant avez-vous effectivement obtenu ? (FCFA)",
                "money",
                condition=HAS_APPLIED,
            ),
            ask("p37_none", "37. Aucun montant obtenu", "boolean", condition=HAS_APPLIED),
            *with_other(
                "p38_reasons",
                "38. Quelles raisons de refus ou difficultés avez-vous rencontrées ?",
                "multi",
                [
                    "Dossier",
                    "Garanties",
                    "Stade trop précoce",
                    "Manque de ventes",
                    "Délais",
                    "Information",
                    "Autre",
                    "Sans objet",
                ],
                HAS_APPLIED,
            ),
        ],
    },
    {
        "title": "5 · Accompagnement et attentes",
        "questions": [
            ask(
                "p39_support",
                "39. Avez-vous déjà bénéficié d’un accompagnement pour votre projet ?",
                "choice",
                YES_NO,
            ),
            ask(
                "p40_organisation",
                "40. Si oui, par quel organisme ?",
                condition=("p39_support", "Oui"),
            ),
            *with_other(
                "p40_domains",
                "40. Dans quel domaine ?",
                "multi",
                [
                    "Mentorat",
                    "Gestion",
                    "Comptabilité/finance",
                    "Commercial",
                    "Technique",
                    "Investisseurs",
                    "Stratégie",
                    "Autre",
                ],
                ("p39_support", "Oui"),
            ),
            *with_other(
                "p41_barriers",
                "41. Qu’est-ce qui vous empêche le plus d’obtenir un financement aujourd’hui ?",
                "multi",
                [
                    "Manque d’information",
                    "Garanties",
                    "Formalisation",
                    "Projet peu avancé",
                    "Dossier technique",
                    "Autre",
                ],
            ),
            *with_other(
                "p42_effect",
                "42. Quel serait le principal effet d’un financement sur votre projet ?",
                "choice",
                [
                    "Lancement",
                    "Prototype",
                    "Production",
                    "Premières ventes",
                    "Emplois",
                    "Nouveaux marchés",
                    "Autre",
                ],
            ),
            ask(
                "p43_expectations",
                "43. Qu’attendez-vous principalement d’un fonds d’amorçage destiné aux porteurs "
                "de projets ?",
                "long",
            ),
        ],
    },
]

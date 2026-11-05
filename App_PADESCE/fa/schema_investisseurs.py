"""Questionnaire NAUMUR/APME auprès des fonds d'amorçage et investisseurs.

Le tableau « pratiques par stade » du document source devient cinq questions
par stade, affichées seulement pour les stades cochés à la question 5.
"""

from .schema_porteurs import PHONE_KEY, YES_NO, ask, with_other

INTRO = (
    "Bonjour, je suis [prénom] du Cabinet NAUMUR SARL. Nous réalisons pour l’APME une étude "
    "sur le financement des porteurs de projets. Nous recueillons votre expérience sur les "
    "projets financés, les conditions d’intervention et l’accompagnement. Les réponses "
    "partagées seront utilisées uniquement dans le cadre de cette étude. Accepteriez-vous de "
    "répondre à quelques questions ?"
)
CLOSING = (
    "Merci pour votre contribution. Les informations communiquées sont recueillies à des fins "
    "d’étude. Ne demander que des données que l’organisme accepte de partager."
)

STAGES = [
    ("preseed", "Pré-seed", "Pré-seed (idée)"),
    ("seed", "Seed", "Seed (prototype)"),
    ("early", "Early stage", "Early stage (premières ventes)"),
    ("growth", "Croissance", "Croissance"),
    ("capdev", "Capital-développement", "Capital-développement (expansion structurée)"),
]
INSTRUMENTS = [
    "SUB — Subvention",
    "PRE — Prêt",
    "AVR — Avance remboursable",
    "EQ — Equity / prise de participation",
    "QEQ — Quasi-fonds propres",
    "GAR — Garantie",
    "AUT — Autre",
    "Non financé",
]
ADVANTAGES = [
    "A1 — Potentiel de croissance",
    "A2 — Innovation",
    "A3 — Traction/ventes",
    "A4 — Impact",
    "A5 — Retour financier",
]
DIFFICULTIES = [
    "D1 — Risque d’échec",
    "D2 — Marché incertain",
    "D3 — Gouvernance",
    "D4 — Manque de données",
    "D5 — Impayés",
    "D6 — Sortie du capital",
    "D7 — Autre",
]


def stage_questions():
    questions = []
    for code, name, choice in STAGES:
        when = ("i5_stages", choice)
        questions += [
            ask(f"ib_{code}_min", f"{name} · Ticket d’entrée minimum (FCFA)", "money", None, when),
            ask(f"ib_{code}_usual", f"{name} · Ticket habituel (FCFA)", "money", None, when),
            ask(
                f"ib_{code}_instrument",
                f"{name} · Instrument principal",
                "choice",
                INSTRUMENTS,
                when,
            ),
            ask(f"ib_{code}_advantage", f"{name} · Avantage", "choice", ADVANTAGES, when),
            ask(f"ib_{code}_difficulty", f"{name} · Difficulté", "choice", DIFFICULTIES, when),
        ]
    return questions


SECTIONS = [
    {
        "title": "Fiche de l’organisme",
        "questions": [
            ask("i_org", "Organisme"),
            ask("i_city", "Ville / pays"),
            ask("i_contact", "Interlocuteur / fonction"),
            ask(PHONE_KEY, "Téléphone"),
            ask("i_email", "E-mail"),
        ],
    },
    {
        "title": "A · Positionnement, cible et stades d’intervention",
        "questions": [
            *with_other(
                "i1_nature",
                "1. Quelle est la nature de votre structure ?",
                "choice",
                [
                    "Fonds d’amorçage",
                    "Capital-investissement",
                    "Business angels",
                    "Banque/EMF",
                    "Fonds public",
                    "Autre",
                ],
            ),
            *with_other(
                "i2_target",
                "2. Quelle est votre cible principale ?",
                "choice",
                [
                    "Porteurs d’idées",
                    "Startups",
                    "TPE/PME",
                    "Entreprises innovantes",
                    "Coopératives",
                    "Autre",
                ],
            ),
            *with_other(
                "i3_sectors",
                "3. Quels secteurs / sous-secteurs financez-vous ?",
                "multi",
                [
                    "Agri/agroalimentaire",
                    "Industrie",
                    "Numérique",
                    "Commerce",
                    "Santé",
                    "Énergie",
                    "Services",
                    "Autre",
                ],
            ),
            ask(
                "i4_zones",
                "4. Dans quelles zones intervenez-vous ?",
                "multi",
                ["Cameroun", "CEMAC", "Afrique", "International"],
            ),
            ask("i4_priority", "4. Zones / villes prioritaires"),
            ask(
                "i5_stages",
                "5. À quels stades investissez-vous ? (plusieurs choix)",
                "multi",
                [choice for _code, _name, choice in STAGES],
            ),
        ],
    },
    {
        "title": "B · Zoom financement — pratiques par stade",
        "questions": [
            *stage_questions(),
            ask(
                "i6_projects",
                "6. Combien de projets avez-vous effectivement financés au cours des trois "
                "dernières années ?",
                "integer",
            ),
            ask("i6_unavailable", "6. Donnée indisponible", "boolean"),
            ask("i7_max", "7. Quel est votre ticket maximal par projet ? (FCFA)", "money"),
            ask("i7_duration", "7. Quelle est votre durée moyenne d’intervention ? (mois/années)"),
            *with_other(
                "i8_expenses",
                "8. Quelles dépenses financez-vous principalement ?",
                "multi",
                [
                    "Études",
                    "Prototype/R&D",
                    "Équipements",
                    "Stocks/BFR",
                    "Commercialisation",
                    "Expansion",
                    "Autre",
                ],
            ),
            *with_other(
                "i9_disbursement",
                "9. Quelles sont les modalités de décaissement ?",
                "multi",
                ["Une seule tranche", "Tranches selon jalons", "Au besoin", "Autre"],
            ),
            *with_other(
                "i10_exit",
                "10. Comment votre investissement prend-il fin ?",
                "multi",
                [
                    "Remboursement",
                    "Rachat des parts",
                    "Cession à investisseur",
                    "Sortie en bourse",
                    "Fin de subvention",
                    "Autre",
                ],
            ),
            ask(
                "i11_observed",
                "11. Quel résultat ou difficulté de financement avez-vous observé selon le stade ? "
                "Exemple court / données",
                "long",
            ),
        ],
    },
    {
        "title": "C · Entrée dans le dispositif, sélection et contrôle",
        "questions": [
            *with_other(
                "i12_access",
                "12. Comment les porteurs de projets accèdent-ils à vos financements ?",
                "multi",
                [
                    "Candidature directe",
                    "Appel à projets",
                    "Incubateur",
                    "Intermédiaire/partenaire",
                    "Recommandation",
                    "Autre",
                ],
            ),
            ask(
                "i13_intermediaries",
                "13. Travaillez-vous avec des intermédiaires ?",
                "choice",
                YES_NO,
            ),
            *with_other(
                "i13_types",
                "13. Lesquels ?",
                "multi",
                ["Incubateurs", "Accélérateurs", "Cabinets", "Réseaux d’anges", "Autre"],
                ("i13_intermediaries", "Oui"),
            ),
            *with_other(
                "i14_criteria",
                "14. Quels critères sont indispensables pour être éligible ?",
                "multi",
                [
                    "Projet viable",
                    "Équipe expérimentée",
                    "Prototype",
                    "Premières ventes",
                    "Immatriculation",
                    "Apport personnel",
                    "Autre",
                ],
            ),
            ask(
                "i15_experience",
                "15. Le nombre d’années d’expérience du promoteur compte-t-il ?",
                "choice",
                ["Éliminatoire", "Critère pondéré", "Non"],
            ),
            ask("i15_minimum", "15. Minimum éventuel (années)", "integer"),
            ask(
                "i16_audit",
                "16. Réalisez-vous un audit / une due diligence du projet avant financement ?",
                "choice",
                ["Toujours", "Selon le ticket", "Rarement", "Jamais"],
            ),
            ask(
                "i17_aspects",
                "17. Si oui, sur quels aspects porte l’audit ?",
                "multi",
                [
                    "Technique",
                    "Marché",
                    "Financier",
                    "Juridique/fiscal",
                    "Gouvernance",
                    "Environnement/social",
                ],
                ("i16_audit", ("Toujours", "Selon le ticket", "Rarement")),
            ),
            *with_other(
                "i18_decision",
                "18. Qui décide de l’octroi du financement ?",
                "multi",
                ["Comité d’investissement", "Direction", "Investisseurs", "Autre"],
            ),
            *with_other(
                "i19_refusal",
                "19. Quels sont les principaux motifs de refus ?",
                "multi",
                [
                    "Projet immature",
                    "Marché non prouvé",
                    "Risque élevé",
                    "Équipe insuffisante",
                    "Dossier incomplet",
                    "Autre",
                ],
            ),
            *with_other(
                "i20_control",
                "20. Comment vérifiez-vous l’utilisation des fonds ?",
                "multi",
                ["Justificatifs", "Visites", "Rapports", "Jalons/KPI", "Audit", "Autre"],
            ),
        ],
    },
    {
        "title": "D · Zoom accompagnement non financier et résultats",
        "questions": [
            ask(
                "i21_support",
                "21. Quels accompagnements non financiers fournissez-vous ?",
                "multi",
                [
                    "Incubation",
                    "Formation",
                    "Mentorat",
                    "Assistance technique",
                    "Gestion/finance",
                    "Accès au marché",
                    "Mise en réseau",
                    "Aucun",
                ],
            ),
            *with_other(
                "i22_provider",
                "22. Cet accompagnement est-il assuré par ?",
                "multi",
                [
                    "Équipe interne",
                    "Incubateurs partenaires",
                    "Consultants externes",
                    "Co-financeurs",
                    "Autre",
                ],
            ),
            ask(
                "i23_timing",
                "23. À quel moment accompagnez-vous le projet ?",
                "choice",
                ["Avant financement", "Pendant", "Après sortie", "À plusieurs étapes"],
            ),
            *with_other(
                "i24_indicators",
                "24. Quels indicateurs utilisez-vous pour suivre les projets ?",
                "multi",
                [
                    "Survie",
                    "Chiffre d’affaires",
                    "Emplois",
                    "Prototypes validés",
                    "Remboursement",
                    "Levées suivantes",
                    "Autre",
                ],
            ),
            *with_other(
                "i25_difficulties",
                "25. Quelles difficultés rencontrez-vous le plus dans l’accompagnement ?",
                "multi",
                [
                    "Compétences du promoteur",
                    "Suivi insuffisant",
                    "Coût de l’appui",
                    "Marché",
                    "Gouvernance",
                    "Autre",
                ],
            ),
        ],
    },
    {
        "title": "E · Investisseurs du fonds et retour d’expérience",
        "questions": [
            ask(
                "i26_funders",
                "26. Qui finance ou investit dans votre fonds / dispositif ? (plusieurs réponses)",
                "multi",
                [
                    "Personnes privées",
                    "Institutions publiques",
                    "Banques",
                    "Bailleurs/DFI",
                    "Entreprises",
                    "Fondations",
                    "Ressources propres",
                ],
            ),
            ask(
                "i27_public",
                "27. Quels investisseurs ou partenaires financiers pouvez-vous citer "
                "publiquement ?",
                "long",
            ),
            ask(
                "i28_best",
                "28. À quels stades avez-vous observé les meilleurs résultats ?",
                "multi",
                ["Pré-seed", "Seed", "Early stage", "Croissance", "Capital-développement"],
            ),
            ask("i28_reason", "28. Pour quelle raison ?", "long"),
            ask(
                "i29_improvements",
                "29. Selon vous, quelles sont les principales pistes d’amélioration du financement "
                "et de l’accompagnement des porteurs de projets au Cameroun ?",
                "long",
            ),
        ],
    },
]

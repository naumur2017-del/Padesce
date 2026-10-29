"""Questionnaire NAUMUR/APME fourni par le client, version section 4 accompagnement.

Keys stay stable so exports and saved drafts survive presentation changes.
"""

YES_NO = ["Oui", "Non"]
SUPPORT = [
    "Mentorat",
    "Gestion",
    "Comptabilité / finance",
    "Commercial",
    "Réseau / investisseurs",
    "Technique",
]


def question(key, label, kind="text", choices=None, required=True, condition=None):
    return {
        "key": key,
        "label": label,
        "kind": kind,
        "choices": choices or [],
        "required": required,
        "condition": condition,
    }


SECTIONS = [
    {
        "title": "1 · Identification de la startup / entreprise",
        "questions": [
            question("q1_name", "1. Nom de la startup / entreprise"),
            question("q2_respondent", "2. Nom et prénoms du répondant / promoteur"),
            question("q3_role", "3. Fonction"),
            question("q4_phone", "4. Téléphone / WhatsApp"),
            question("q4_email", "4. E-mail", "email", required=False),
            question("q5_city", "5. Ville / région d’implantation"),
            question("q6_year", "6. Année de création", "year"),
            question("q6_start", "6. Année de démarrage effectif", "year", required=False),
            question(
                "q7_legal",
                "7. Forme juridique",
                "choice",
                ["Entreprise individuelle", "SARL", "SA", "Autre"],
            ),
            question("q7_other", "7. Autre forme juridique", condition=("q7_legal", "Autre")),
            question("q8_sector", "8. Secteur d’activité principal"),
            question("q9_activity", "9. Décrivez brièvement votre activité", "long"),
            question("q10_products", "10. Principaux produits / services", "long"),
            question("q11_none", "11. Aucun salarié", "boolean", required=False),
            question("q11_permanent", "11. Effectif permanent", "integer", required=False),
            question("q11_temporary", "11. Effectif temporaire", "integer", required=False),
        ],
    },
    {
        "title": "2 · Besoin actuel de financement",
        "questions": [
            question(
                "q12_need",
                "12. Avez-vous actuellement besoin d’un financement ?",
                "choice",
                ["Oui", "Non", "À préciser"],
            ),
            question(
                "q13_amount",
                "13. Montant approximatif du besoin (FCFA)",
                "money",
                condition=("q12_need", "Oui"),
            ),
            question(
                "q14_purposes",
                "14. Objet du financement",
                "multi",
                [
                    "Acquisition de matériel / équipements",
                    "Développement de l’activité",
                    "Achat de matières premières / stocks",
                    "Fonds de roulement / trésorerie",
                    "Développement d’un produit / prototype",
                    "Recrutement / renforcement des équipes",
                    "Marketing / développement commercial",
                    "Digitalisation / technologie",
                    "Augmentation du capital",
                    "Expansion vers de nouveaux marchés",
                    "Autre",
                ],
                condition=("q12_need", "Oui"),
            ),
            question(
                "q14_other", "14. Autre objet du financement", condition=("q14_purposes", "Autre")
            ),
            question(
                "q15_priority",
                "15. Priorité principale du financement",
                "long",
                condition=("q12_need", "Oui"),
            ),
            question(
                "q16_frequency",
                "16. Nature du financement recherché",
                "choice",
                ["Ponctuel", "Récurrent", "Phase de croissance", "À préciser"],
                condition=("q12_need", "Oui"),
            ),
        ],
    },
    {
        "title": "3 · Connaissance des fonds d’amorçage",
        "questions": [
            question(
                "q17_aware",
                "17. Avez-vous déjà entendu parler des fonds d’amorçage ?",
                "choice",
                YES_NO,
            ),
            question(
                "q18_channels",
                "18. Comment en avez-vous entendu parler ?",
                "multi",
                [
                    "Réseaux sociaux",
                    "Incubateur / accélérateur",
                    "Investisseur",
                    "Programme / bailleur",
                    "Autre",
                ],
                condition=("q17_aware", "Oui"),
            ),
            question(
                "q18_other", "18. Autre source d’information", condition=("q18_channels", "Autre")
            ),
            question(
                "q19_funds", "19. Fonds / programmes d’amorçage connus", "long", required=False
            ),
            question(
                "q20_applied",
                "20. Avez-vous déjà essayé d’obtenir un financement auprès d’un fonds ou investisseur ?",
                "choice",
                YES_NO,
            ),
        ],
    },
    {
        "title": "4 · Expérience de recherche de financement",
        "questions": [
            question(
                "q21_investor",
                "21. Fonds d’amorçage / investisseur sollicité",
                condition=("q20_applied", "Oui"),
            ),
            question(
                "q22_requested", "22. Montant demandé", "money", condition=("q20_applied", "Oui")
            ),
            question(
                "q22_currency", "22. Monnaie (FCFA ou autre)", condition=("q20_applied", "Oui")
            ),
            question(
                "q23_result",
                "23. Le financement demandé a-t-il été accordé ?",
                "choice",
                ["Oui, intégralement", "Partiellement", "Non", "En cours"],
                condition=("q20_applied", "Oui"),
            ),
            question(
                "q24_received",
                "24. Montant effectivement obtenu (FCFA)",
                "money",
                condition=("q23_result", "Partiellement"),
            ),
            question(
                "q25_blocker",
                "25. Principale raison du blocage",
                "choice",
                [
                    "Dossier incomplet",
                    "Garanties",
                    "Projet trop risqué",
                    "Montant demandé",
                    "Traction / rentabilité",
                    "Autre",
                ],
                condition=("q23_result", "Non"),
            ),
            question(
                "q25_other", "25. Autre raison du blocage", condition=("q25_blocker", "Autre")
            ),
            question(
                "q26_difficulties",
                "26. Précisez les difficultés rencontrées",
                "long",
                required=False,
                condition=("q20_applied", "Oui"),
            ),
            question(
                "q27_supported",
                "27. Avez-vous déjà bénéficié d’un accompagnement ?",
                "choice",
                YES_NO,
            ),
            question(
                "q27_support_received",
                "27. Types d’accompagnement reçus",
                "multi",
                SUPPORT + ["Stratégique", "Autre"],
                condition=("q27_supported", "Oui"),
            ),
            question(
                "q27_support_desired",
                "27. Types d’accompagnement souhaités",
                "multi",
                SUPPORT + ["Stratégique", "Autre"],
                condition=("q27_supported", "Non"),
            ),
            question("q27_other", "27. Autre accompagnement", required=False),
        ],
    },
    {
        "title": "5 · Maturité et perspectives de développement",
        "questions": [
            question(
                "q28_stage",
                "28. Stade de développement de l’entreprise",
                "choice",
                ["Idée / projet", "Prototype / MVP", "Premières ventes", "Croissance", "Expansion"],
            ),
            question(
                "q29_sales", "29. Avez-vous déjà des clients ou des ventes ?", "choice", YES_NO
            ),
            question("q29_since", "29. Si oui, depuis quand ?", condition=("q29_sales", "Oui")),
            question(
                "q30_contracts",
                "30. Disposez-vous de contrats, commandes ou lettres d’intention ?",
                "choice",
                ["Oui", "Non", "En cours"],
            ),
            question("q31_goals", "31. Principaux objectifs à 12–24 mois", "long"),
            question(
                "q32_impact",
                "32. Impact principal du financement",
                "choice",
                ["CA", "Emplois", "Production", "Marché", "Innovation", "Autre"],
            ),
            question("q32_other", "32. Autre impact", condition=("q32_impact", "Autre")),
        ],
    },
    {
        "title": "6 · Perception et attentes vis-à-vis d’un fonds d’amorçage",
        "questions": [
            question(
                "q33_barriers",
                "33. Qu’est-ce qui vous empêcherait aujourd’hui d’obtenir un financement ?",
                "long",
            ),
            question(
                "q34_type",
                "34. Type de financement le plus adapté",
                "choice",
                [
                    "Prise de participation",
                    "Prêt",
                    "Subvention",
                    "Financement mixte",
                    "À déterminer",
                ],
            ),
            question(
                "q35_support",
                "35. Accompagnement souhaité en complément du financement",
                "multi",
                SUPPORT,
            ),
            question(
                "q36_recommendations",
                "36. Recommandations ou attentes particulières",
                "long",
                required=False,
            ),
        ],
    },
    {
        "title": "Déclaration du répondant",
        "questions": [
            question("declaration_name", "Nom du répondant déclarant"),
            question(
                "declaration_confirmed",
                "Le répondant confirme l’exactitude des informations et leur utilisation pour l’étude.",
                "boolean",
            ),
        ],
    },
]

QUESTIONS = [q for section in SECTIONS for q in section["questions"]]
QUESTION_MAP = {q["key"]: q for q in QUESTIONS}


def is_applicable(question, values):
    condition = question.get("condition")
    if not condition:
        return True
    parent, expected = condition
    if not is_applicable(QUESTION_MAP[parent], values):
        return False
    current = values.get(parent)
    return expected in current if isinstance(current, list) else current == expected

"""Contexte socio-geo-demo-politique du Cameroun pour l'evaluation des prestataires."""

REGIONS_CAMEROUN = {
    "Adamaoua": {
        "chef_lieu": "Ngaoundere",
        "population_estimee": 1_200_000,
        "reseau_mobile": "moyen",
        "electricite": "faible",
        "acces_route": "moyen",
        "climat": "tropical de transition",
        "langues": ["francais", "fulfuldé"],
        "defis": [
            "Enclavement partiel",
            "Faible couverture réseau mobile hors villes",
            "Coupures fréquentes d'électricité",
            "Routes en mauvais état en saison des pluies",
        ],
        "score_difficulte": 0.65,
        "vocations_economiques": ["élevage bovin", "agriculture vivrière", "apiculture", "commerce de bétail"],
        "formations_recommandees": ["élevage", "transformation laitière", "apiculture", "gestion de coopératives"],
    },
    "Centre": {
        "chef_lieu": "Yaounde",
        "population_estimee": 4_500_000,
        "reseau_mobile": "bon",
        "electricite": "bon",
        "acces_route": "bon",
        "climat": "equatorial",
        "langues": ["francais", "ewondo"],
        "vocations_economiques": ["services", "commerce", "agriculture périurbaine", "numérique"],
        "formations_recommandees": ["numérique", "entrepreneuriat", "gestion", "agriculture urbaine"],
        "defis": [
            "Embouteillages urbains",
            "Coût de vie élevé à Yaoundé",
        ],
        "score_difficulte": 0.25,
    },
    "East": {
        "chef_lieu": "Bertoua",
        "population_estimee": 850_000,
        "reseau_mobile": "faible",
        "electricite": "faible",
        "acces_route": "faible",
        "climat": "equatorial",
        "langues": ["francais"],
        "defis": [
            "Zone forestière très enclavée",
            "Réseau mobile quasi inexistant hors chef-lieu",
            "Routes non bitumées",
            "Insécurité frontalière (RCA)",
        ],
        "score_difficulte": 0.80,
        "vocations_economiques": ["exploitation forestière", "cacao", "chasse", "pêche artisanale"],
        "formations_recommandees": ["agroforesterie", "transformation du cacao", "menuiserie", "apiculture"],
    },
    "Far North": {
        "chef_lieu": "Maroua",
        "population_estimee": 4_000_000,
        "reseau_mobile": "faible",
        "electricite": "très faible",
        "acces_route": "moyen",
        "climat": "sahelien",
        "langues": ["francais", "fulfuldé", "arabe choa"],
        "defis": [
            "Insécurité (Boko Haram)",
            "Sécheresse et chaleur extrême",
            "Faible taux de scolarisation",
            "Réseau électrique très limité",
        ],
        "score_difficulte": 0.90,
        "vocations_economiques": ["élevage caprin/ovin", "oignon", "coton", "petit commerce"],
        "formations_recommandees": ["élevage", "irrigation", "maraîchage", "artisanat local"],
    },
    "Littoral": {
        "chef_lieu": "Douala",
        "population_estimee": 3_500_000,
        "reseau_mobile": "bon",
        "electricite": "bon",
        "acces_route": "bon",
        "climat": "equatorial humide",
        "langues": ["francais", "douala"],
        "defis": [
            "Inondations fréquentes",
            "Embouteillages à Douala",
        ],
        "score_difficulte": 0.20,
        "vocations_economiques": ["commerce international", "industrie", "pêche", "services portuaires"],
        "formations_recommandees": ["commerce", "logistique", "numérique", "pêche industrielle"],
    },
    "North": {
        "chef_lieu": "Garoua",
        "population_estimee": 2_500_000,
        "reseau_mobile": "moyen",
        "electricite": "faible",
        "acces_route": "moyen",
        "climat": "soudanien",
        "langues": ["francais", "fulfuldé"],
        "defis": [
            "Chaleur extrême",
            "Tensions intercommunautaires",
            "Faible couverture électrique rurale",
        ],
        "score_difficulte": 0.70,
        "vocations_economiques": ["coton", "élevage", "céréales", "pêche fluviale"],
        "formations_recommandees": ["agriculture céréalière", "élevage bovin", "transformation cotonnière"],
    },
    "North West": {
        "chef_lieu": "Bamenda",
        "population_estimee": 2_000_000,
        "reseau_mobile": "faible",
        "electricite": "faible",
        "acces_route": "faible",
        "climat": "tropical d'altitude",
        "langues": ["anglais", "pidgin"],
        "defis": [
            "Crise anglophone — insécurité majeure",
            "Coupures internet fréquentes",
            "Déplacements de populations",
            "Routes coupées par les groupes armés",
        ],
        "score_difficulte": 0.95,
        "vocations_economiques": ["café", "maraîchage", "élevage", "artisanat"],
        "formations_recommandees": ["agriculture résiliente", "élevage porcin", "couture", "gestion de coopératives"],
    },
    "West": {
        "chef_lieu": "Bafoussam",
        "population_estimee": 2_000_000,
        "reseau_mobile": "bon",
        "electricite": "moyen",
        "acces_route": "bon",
        "climat": "tropical d'altitude",
        "langues": ["francais", "ghomala"],
        "defis": [
            "Relief montagneux compliquant l'accès",
            "Densité de population élevée",
        ],
        "score_difficulte": 0.35,
        "vocations_economiques": ["café/cacao", "commerce", "maraîchage", "aviculture", "artisanat"],
        "formations_recommandees": ["aviculture", "commerce", "transformation agricole", "gestion PME"],
    },
    "South": {
        "chef_lieu": "Ebolowa",
        "population_estimee": 750_000,
        "reseau_mobile": "moyen",
        "electricite": "moyen",
        "acces_route": "moyen",
        "climat": "equatorial",
        "langues": ["francais", "boulou"],
        "defis": [
            "Faible densité — zones très isolées",
            "Routes forestières difficiles",
        ],
        "score_difficulte": 0.55,
        "vocations_economiques": ["cacao", "plantain", "pêche", "exploitation forestière"],
        "formations_recommandees": ["cacaoculture", "pisciculture", "transformation du manioc"],
    },
    "South West": {
        "chef_lieu": "Buea",
        "population_estimee": 1_500_000,
        "reseau_mobile": "moyen",
        "electricite": "moyen",
        "acces_route": "moyen",
        "climat": "equatorial humide",
        "langues": ["anglais", "pidgin"],
        "defis": [
            "Crise anglophone — insécurité",
            "Coupures internet",
            "Déplacements de populations",
        ],
        "score_difficulte": 0.85,
        "vocations_economiques": ["agriculture tropicale", "élevage", "pêche", "commerce frontalier"],
        "formations_recommandees": ["aviculture", "élevage porcin", "agriculture", "gestion de coopératives", "apiculture"],
    },
}

VILLES_CONNUES = {
    "Foumban": {"region": "West", "departement": "Noun", "reseau": "moyen", "electricite": "faible",
                "particularites": "Capitale culturelle Bamoun, réseau et électricité instables"},
    "Tiko": {"region": "South West", "departement": "Fako", "reseau": "moyen", "electricite": "moyen",
             "particularites": "Zone anglophone, crise sécuritaire, port industriel"},
    "Kumba": {"region": "South West", "departement": "Meme", "reseau": "faible", "electricite": "faible",
              "particularites": "Zone anglophone, insécurité majeure, massacre 2020"},
    "Douala": {"region": "Littoral", "departement": "Wouri", "reseau": "bon", "electricite": "bon",
               "particularites": "Capitale économique, bonne infrastructure"},
    "Yaounde": {"region": "Centre", "departement": "Mfoundi", "reseau": "bon", "electricite": "bon",
                "particularites": "Capitale politique, bonne infrastructure"},
    "Bamenda": {"region": "North West", "departement": "Mezam", "reseau": "faible", "electricite": "faible",
                "particularites": "Crise anglophone sévère, coupures internet fréquentes"},
    "Bafoussam": {"region": "West", "departement": "Mifi", "reseau": "bon", "electricite": "moyen",
                  "particularites": "Centre commercial de l'Ouest"},
    "Garoua": {"region": "North", "departement": "Benoue", "reseau": "moyen", "electricite": "faible",
               "particularites": "Chaleur extrême, infrastructure limitée"},
    "Maroua": {"region": "Far North", "departement": "Diamare", "reseau": "faible", "electricite": "très faible",
               "particularites": "Zone sahélienne, insécurité Boko Haram"},
    "Ngaoundere": {"region": "Adamaoua", "departement": "Vina", "reseau": "moyen", "electricite": "faible",
                   "particularites": "Plaque tournante ferroviaire, isolement relatif"},
    "Bertoua": {"region": "East", "departement": "Lom-et-Djerem", "reseau": "faible", "electricite": "faible",
                "particularites": "Zone forestière, frontière RCA"},
    "Ebolowa": {"region": "South", "departement": "Mvila", "reseau": "moyen", "electricite": "moyen",
                "particularites": "Zone forestière, faible densité"},
    "Buea": {"region": "South West", "departement": "Fako", "reseau": "moyen", "electricite": "moyen",
             "particularites": "Crise anglophone, ville universitaire"},
    "Limbe": {"region": "South West", "departement": "Fako", "reseau": "moyen", "electricite": "moyen",
              "particularites": "Ville côtière, tourisme, crise anglophone"},
    "Kribi": {"region": "South", "departement": "Ocean", "reseau": "moyen", "electricite": "moyen",
              "particularites": "Port en eau profonde, développement industriel"},
    "Nkongsamba": {"region": "Littoral", "departement": "Moungo", "reseau": "moyen", "electricite": "moyen",
                   "particularites": "Ancienne capitale, voie ferrée"},
}


def get_region_context(region_name: str) -> dict | None:
    for key, val in REGIONS_CAMEROUN.items():
        if key.lower() == region_name.lower() or region_name.lower() in key.lower():
            return {**val, "nom": key}
    return None


def get_city_context(city_name: str) -> dict | None:
    for key, val in VILLES_CONNUES.items():
        if key.lower() == city_name.lower() or city_name.lower() in key.lower():
            return {**val, "nom": key}
    return None


def identify_region_from_city(city_name: str) -> str | None:
    city = get_city_context(city_name)
    if city:
        return city["region"]
    return None

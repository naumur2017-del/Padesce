import unicodedata
from App_PADESCE.appels.models import AppelFormateur
from App_PADESCE.formations.models import Prestation, Formateur


def _build_formateur_prestation_indicators_table():
    """Construit une table agrégée des prestations avec les indicateurs de satisfaction pour les formateurs."""
    
    def _normalize_indicator_match_text(value: str) -> str:
        text = " ".join(str(value or "").split()).casefold()
        if not text:
            return ""
        normalized = unicodedata.normalize("NFKD", text)
        return "".join(ch for ch in normalized if not unicodedata.combining(ch))

    def _build_formateur_metrics_by_combo() -> dict[tuple[str, str], dict]:
        score_fields = (
            "q1_prerequis_apprenants",
            "q2_interaction_apprenants",
            "q3_competences_acquises",
        )
        text_fields = (
            "q4_gestion_administrative",
            "q5_gestion_financiere",
            "q6_communication",
        )
        grouped: dict[tuple[str, str], dict] = {}
        rows = AppelFormateur.objects.filter(is_active=True).values(
            "prestataire",
            "beneficiaire",
            "satisfaction_completed_at",
            *score_fields,
            *text_fields,
        )

        for row in rows:
            combo_key = (
                _normalize_indicator_match_text(row.get("prestataire")),
                _normalize_indicator_match_text(row.get("beneficiaire")),
            )
            if not any(combo_key):
                continue

            bucket = grouped.setdefault(
                combo_key,
                {
                    "count": 0,
                    "scores": {field: [] for field in score_fields},
                    "texts": {field: set() for field in text_fields},
                },
            )

            has_complete_scores = all(row.get(field) is not None for field in score_fields)
            if has_complete_scores:
                bucket["count"] += 1
                for field in score_fields:
                    bucket["scores"][field].append(float(row[field]))

            has_form_payload = has_complete_scores or bool(row.get("satisfaction_completed_at"))
            if not has_form_payload:
                has_form_payload = any(str(row.get(field) or "").strip() for field in text_fields)

            if has_form_payload:
                for field in text_fields:
                    text_value = str(row.get(field) or "").strip()
                    if text_value:
                        bucket["texts"][field].add(text_value)

        return grouped

    def _get_formateur_prestations_mapping() -> dict[int, set[int]]:
        """Récupérer les associations formateurs-prestations depuis la table de gestion"""
        formateur_prestations = {}
        formateurs = Formateur.objects.filter(actif=True).prefetch_related('prestations')
        for formateur in formateurs:
            linked_prestations = set(formateur.prestations.values_list('pk', flat=True))
            formateur_prestations[formateur.pk] = linked_prestations
        return formateur_prestations

    def _find_prestation_id_from_mapping(combo_key: tuple[str, str], formateur_prestations_mapping: dict[int, set[int]]) -> int | None:
        """Trouver l'ID de prestation correspondant à la combinaison prestataire-bénéficiaire"""
        # Créer un mapping inversé : prestation_id -> (prestataire, beneficiaire)
        prestation_to_combo = {}
        for formateur_pk, linked_prestations in formateur_prestations_mapping.items():
            for prestation_id in linked_prestations:
                try:
                    prest = Prestation.objects.get(pk=prestation_id, prestataire__isnull=False, beneficiaire__isnull=False)
                    prestataire_norm = _normalize_indicator_match_text(prest.prestataire.raison_sociale)
                    beneficiaire_norm = _normalize_indicator_match_text(prest.beneficiaire.nom_structure)
                    prestation_to_combo[prestation_id] = (prestataire_norm, beneficiaire_norm)
                except Prestation.DoesNotExist:
                    continue
        
        # Chercher une correspondance exacte
        for prestation_id, stored_combo in prestation_to_combo.items():
            if stored_combo == combo_key:
                return prestation_id
        
        return None

    formateur_metrics_by_combo = _build_formateur_metrics_by_combo()
    formateur_prestations_mapping = _get_formateur_prestations_mapping()

    # Récupérer toutes les prestations (même sans classes, elles apparaîtront vides)
    all_prestations = Prestation.objects.select_related("prestataire", "beneficiaire").order_by(
        "code"
    )

    table_data = []

    for prestation in all_prestations:
        combo_key = (
            _normalize_indicator_match_text(
                prestation.prestataire.raison_sociale if prestation.prestataire else ""
            ),
            _normalize_indicator_match_text(
                prestation.beneficiaire.nom_structure if prestation.beneficiaire else ""
            ),
        )
        formateur_metrics = formateur_metrics_by_combo.get(combo_key)
        
        # Vérifier si le code de prestation correspond à une combinaison valide
        # et si elle est associée à un formateur via la table de gestion
        is_linked_to_formateur = False
        for formateur_pk, linked_prestations in formateur_prestations_mapping.items():
            if prestation.pk in linked_prestations:
                is_linked_to_formateur = True
                break
        
        # Si aucune combinaison prestataire-bénéficiaire correspondante, Ne pas afficher cette prestation
        if not formateur_metrics and not is_linked_to_formateur:
            # Aucune combinaison trouvée - ne pas ajouter cette prestation à la table
            continue
        else:
            # Calculer les moyennes pour les données formateur
            formateur_data = {
                "q1_prerequis_apprenants": None,
                "q2_interaction_apprenants": None,
                "q3_competences_acquises": None,
                "count": int(formateur_metrics.get("count") or 0),
            }

            if formateur_metrics:
                for field in [
                    "q1_prerequis_apprenants",
                    "q2_interaction_apprenants",
                    "q3_competences_acquises",
                ]:
                    values = formateur_metrics["scores"].get(field, [])
                    if values:
                        formateur_data[field] = round(sum(values) / len(values), 2)

            table_data.append(
                {
                    "code": prestation.code,
                    "prestation_id": prestation.pk,  # Ajouter l'ID de la prestation
                    "prestataire": (
                        prestation.prestataire.raison_sociale if prestation.prestataire else ""
                    ),
                    "beneficiaire": (
                        prestation.beneficiaire.nom_structure if prestation.beneficiaire else ""
                    ),
                    "formateur": formateur_data,
                }
            )

    # Ajouter les combinaisons de appels formateurs sans correspondance avec les classes apprenants
    processed_combinations = set()
    for prestation in all_prestations:
        combo_key = (
            _normalize_indicator_match_text(
                prestation.prestataire.raison_sociale if prestation.prestataire else ""
            ),
            _normalize_indicator_match_text(
                prestation.beneficiaire.nom_structure if prestation.beneficiaire else ""
            ),
        )
        processed_combinations.add(combo_key)

    for combo_key, formateur_metrics in formateur_metrics_by_combo.items():
        if combo_key not in processed_combinations:
            # Créer les données formateur avec les moyennes
            formateur_data = {
                "q1_prerequis_apprenants": None,
                "q2_interaction_apprenants": None,
                "q3_competences_acquises": None,
                "count": int(formateur_metrics.get("count") or 0),
            }

            for field in [
                "q1_prerequis_apprenants",
                "q2_interaction_apprenants",
                "q3_competences_acquises",
            ]:
                values = formateur_metrics["scores"].get(field, [])
                if values:
                    formateur_data[field] = round(sum(values) / len(values), 2)

            # Ajouter cette combinaison avec les prestataires-bénéficiaires des appels formateurs
            # et un tiret dans le code prestation
            table_data.append(
                {
                    "code": "-",  # Tiret dans la colonne code prestation
                    "prestation_id": None,  # Pas d'ID de prestation pour les appels formateurs sans correspondance
                    "prestataire": combo_key[0],  # Prestataire des appels formateurs
                    "beneficiaire": combo_key[1],  # Bénéficiaire des appels formateurs
                    "formateur": formateur_data,  # Moyennes des appels formateurs
                }
            )

    return table_data

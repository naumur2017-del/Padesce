import base64
import csv
import io
import unicodedata
from decimal import Decimal, InvalidOperation

from openpyxl import load_workbook

from django.db.models import Avg, Count, Q, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import render
from contextlib import contextmanager
from django.db import connection, transaction, OperationalError
from django.contrib import messages
from django.utils.text import slugify

from App_PADESCE.apprenants.models import Apprenant, SmsLog
from App_PADESCE.environnement.models import EnqueteEnvironnement
from App_PADESCE.formations.models import Classe, Formation, Prestation, Prestataire, Beneficiaire, Lieu
from App_PADESCE.presences.models import Presence
from App_PADESCE.satisfaction_apprenants.models import SatisfactionApprenant
from App_PADESCE.satisfaction_formateurs.models import SatisfactionFormateur
from App_PADESCE.reporting.forms import ConsolidationUploadForm
from App_PADESCE.reporting.models import ConsolidationRecord


def _normalize_cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)
    return str(value).strip()


def _normalize_header(value: str) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", str(value))
    ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    ascii_only = ascii_only.lower().replace("&", "and").replace("’", "'")
    ascii_only = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in ascii_only)
    return " ".join(ascii_only.split())


MAX_CONSO_COLS = 40  # Augmenté pour être sûr de ne pas couper la colonne Classe ID

# Mapping plus tolérant pour "Classe ID"
CONSOLIDATION_HEADER_MAP = {
    "n": "numero",
    "nom et prenom 0 name first name": "nom_complet",
    "nom et prenom 0 name and first name": "nom_complet",
    "beneficiaires": "beneficiaire",
    "genre h0f 0 gender m0f": "genre",
    "age": "age",
    "fonction d c e m b": "fonction",
    "qualification chiffre 0 1 2 etc": "qualification",
    "nb d annees d experience chiffre 0 1 2 etc": "nb_annees_experience",
    "ville de residence de l appprenant": "ville_residence",
    "prestataire": "prestataire",
    "type de formation declaree": "intitule_formation_solicitee",
    "formation padesce": "intitule_formation_dispensee",
    "fenetre": "fenetre",
    "ville de la formation": "ville_formation",
    "arrondissement": "arrondissement",
    "departement": "departement",
    "region": "region",
    "lieux": "lieu_formation",
    "precision sur le lieu 0 quartier de formation": "precision_lieu",
    "coordonnees gps du lieu de formation longitude": "longitude",
    "coordonnees gps du lieu de formation latitude": "latitude",
    "1er no tel 0 tel no apprenant": "telephone1",
    "2e no tel 0 tel no apprenant si disponible": "telephone2",
    "cohorte": "cohorte",
    "tel formateur 0 point focal sur place": "tel_formateur",
    "code": "code",
    "cout unitaire subvention mcdc ttc": "cout_unitaire_subvention",
    "montant total subvention mcdc ttc": "montant_total_subvention",
    "statut de la prestation": "statut_prestation",

    # Variantes pour Classe ID – très tolérant
    "classe id": "classe_id",
    "class id": "classe_id",
    "classeid": "classe_id",
    "classid": "classe_id",
    "id classe": "classe_id",
    "classe": "classe_id",               # fallback si "ID" est absent
    "classe_id": "classe_id",
    "id de classe": "classe_id",
    "numero classe": "classe_id",
    "code classe": "classe_id",
}


SESSION_KEY_CONSO = "consolidation_upload"


def _ensure_prestataire(name: str) -> Prestataire | None:
    if not name:
        return None
    raw = str(name).strip()
    if not raw:
        return None
    code = raw[:50]
    obj, _ = Prestataire.objects.get_or_create(code=code, defaults={"raison_sociale": raw})
    if obj.raison_sociale != raw:
        obj.raison_sociale = raw
        obj.save(update_fields=["raison_sociale"])
    return obj


def _reset_consolidation_tables():
    """
    Empty the tables that are rebuilt from consolidation imports using raw SQL to avoid
    instantiating large querysets and keep the request from timing out.
    """
    tables = (
        SatisfactionApprenant,
        SatisfactionFormateur,
        Presence,
        SmsLog,
        Apprenant,
        Classe,
        Prestation,
        Formation,
        Prestataire,
        Beneficiaire,
        Lieu,
    )
    with connection.cursor() as cursor:
        needs_toggle = connection.vendor in {"sqlite", "mysql"}
        if needs_toggle:
            if connection.vendor == "sqlite":
                cursor.execute("PRAGMA foreign_keys = OFF")
            else:
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        for model in tables:
            table_name = connection.ops.quote_name(model._meta.db_table)
            cursor.execute(f"DELETE FROM {table_name}")
        if needs_toggle:
            if connection.vendor == "sqlite":
                cursor.execute("PRAGMA foreign_keys = ON")
            else:
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1")


def _ensure_formation(intitule: str, fenetre: str = "") -> Formation | None:
    if not intitule:
        return None
    raw = str(intitule).strip()
    if not raw:
        return None
    code = raw[:50]
    obj, _ = Formation.objects.get_or_create(code=code, defaults={"nom": raw, "fenetre": fenetre})
    if obj.nom != raw or (fenetre and obj.fenetre != fenetre):
        obj.nom = raw
        if fenetre:
            obj.fenetre = fenetre
        obj.save(update_fields=["nom", "fenetre"])
    return obj


def _ensure_beneficiaire(name: str, region: str = "", departement: str = "", arrondissement: str = "", ville: str = "") -> Beneficiaire | None:
    if not name:
        return None
    raw = str(name).strip()
    if not raw:
        return None
    obj, _ = Beneficiaire.objects.get_or_create(
        nom_structure=raw,
        defaults={"region": region, "departement": departement, "arrondissement": arrondissement, "ville": ville},
    )
    return obj


def _ensure_lieu(nom: str, region: str = "", departement: str = "", arrondissement: str = "", ville: str = "", longitude: str = "", latitude: str = "", precision: str = "") -> Lieu | None:
    if not nom:
        return None
    raw = str(nom).strip()
    if not raw:
        return None
    code = raw[:50]
    obj, _ = Lieu.objects.get_or_create(
        code=code,
        defaults={
            "nom_lieu": raw,
            "region": region,
            "departement": departement,
            "arrondissement": arrondissement,
            "ville": ville,
            "longitude": longitude,
            "latitude": latitude,
            "precision": precision,
        },
    )
    return obj


def _ensure_prestation(prestataire: Prestataire | None, formation: Formation | None, beneficiaire: Beneficiaire | None, code_hint: str = "") -> Prestation | None:
    if not prestataire or not formation:
        return None
    code_raw = (code_hint or "").strip()
    code = (code_raw or "null")[:50]
    obj, _ = Prestation.objects.get_or_create(
        code=code,
        defaults={"prestataire": prestataire, "formation": formation, "beneficiaire": beneficiaire},
    )
    return obj


def _ensure_classe(
    prestation: Prestation | None,
    formation: Formation | None,
    fenetre: str = "",
    cohorte: str = "",
    classe_id: str = "",
) -> Classe | None:
    if not prestation or not formation:
        return None

    # Priorité : utiliser classe_id comme code si présent et non vide
    code_raw = (classe_id or "").strip()
    if not code_raw:
        # Fallback si classe_id absent → code court unique
        code_raw = f"CL-{formation.code[:6] or 'XX'}-{fenetre or 'X'}-{cohorte or '1'}"

    code = code_raw[:20]

    # Construction du nom/intitulé lisible
    formation_nom = formation.nom.strip()
    if len(formation_nom) > 120:
        formation_nom = formation_nom[:117] + "..."

    # Format préféré : CLAxxx — Nom de la formation
    classe_nom = f"{code} — {formation_nom}"

    # Si cohorte > 1, on peut l'ajouter pour plus de clarté (optionnel)
    cohorte_int = _to_int(cohorte)
    if cohorte_int and cohorte_int > 1:
        classe_nom += f" (cohorte {cohorte_int})"

    obj, created = Classe.objects.get_or_create(
        code=code,
        defaults={
            "prestation": prestation,
            "formation": formation,
            "intitule_formation": formation_nom,
            "fenetre": fenetre or "",
            "cohorte": cohorte_int if cohorte_int else 1,
        },
    )

    # Mise à jour si déjà existant mais nom différent
    if not created:
        updated = False
        if obj.intitule_formation != formation_nom:
            obj.intitule_formation = formation_nom
            updated = True
        if updated:
            obj.save(update_fields=["intitule_formation"])

    return obj

def _to_int(value):
    try:
        if value is None or value == "":
            return None
        val = str(value).strip().replace(" ", "")
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _to_decimal(value):
    if value in (None, ""):
        return None
    try:
        cleaned = str(value).replace(" ", "").replace(",", ".")
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _read_consolidation_sheet(file_obj, max_rows: int | None = 60):
    wb = load_workbook(file_obj, data_only=True)
    if "Consolidation" not in wb.sheetnames:
        raise ValueError("Feuille 'Consolidation' introuvable dans le fichier.")
    ws = wb["Consolidation"]
    header = None
    rows = []
    for r_idx, row in enumerate(ws.iter_rows(values_only=True)):
        cells = [_normalize_cell(c) for c in row][:MAX_CONSO_COLS]
        if header is None:
            header = cells
            continue
        if not any(cells):
            continue
        rows.append(cells)
        if max_rows and len(rows) >= max_rows:
            break
    return header or [], rows


def _rows_to_records(header, rows):
    header_norm = [_normalize_header(h) for h in header]
    
    # Mapping index → field
    header_map = {}
    for idx, h in enumerate(header_norm):
        field = CONSOLIDATION_HEADER_MAP.get(h)
        if field:
            header_map[idx] = field
    
    records = []
    related_payload = []
    
    for row in rows:
        cells = [_normalize_cell(c) for c in row]
        if not any(cells):
            continue
            
        data = {}
        for idx, field in header_map.items():
            if idx < len(cells):
                data[field] = cells[idx]
                
        # Debug rapide (à commenter après test)
        # if "classe_id" not in data or not data["classe_id"]:
        #     print("Ligne sans classe_id →", data.get("nom_complet", "inconnu"))
                
        records.append(
            ConsolidationRecord(
                numero=data.get("numero", ""),
                nom_complet=data.get("nom_complet", ""),
                beneficiaire=data.get("beneficiaire", ""),
                genre=data.get("genre", ""),
                age=_to_int(data.get("age")),
                fonction=data.get("fonction", ""),
                qualification=data.get("qualification", ""),
                nb_annees_experience=_to_int(data.get("nb_annees_experience")),
                ville_residence=data.get("ville_residence", ""),
                prestataire=data.get("prestataire", ""),
                intitule_formation_solicitee=data.get("intitule_formation_solicitee", ""),
                intitule_formation_dispensee=data.get("intitule_formation_dispensee", ""),
                fenetre=data.get("fenetre", ""),
                ville_formation=data.get("ville_formation", ""),
                arrondissement=data.get("arrondissement", ""),
                departement=data.get("departement", ""),
                region=data.get("region", ""),
                lieu_formation=data.get("lieu_formation", ""),
                precision_lieu=data.get("precision_lieu", ""),
                longitude=data.get("longitude", ""),
                latitude=data.get("latitude", ""),
                telephone1=data.get("telephone1", ""),
                telephone2=data.get("telephone2", ""),
                cohorte=data.get("cohorte", ""),
                tel_formateur=data.get("tel_formateur", ""),
                code=data.get("code", ""),
                cout_unitaire_subvention=_to_decimal(data.get("cout_unitaire_subvention")),
                montant_total_subvention=_to_decimal(data.get("montant_total_subvention")),
                statut_prestation=data.get("statut_prestation", ""),
            )
        )
        related_payload.append(data)
    
    return records, related_payload


def _extract_unique_classe_ids(payload: list[dict]) -> list[str]:
    classes = {(item.get("classe_id") or "").strip() for item in payload}
    return sorted(code for code in classes if code)


def _save_related_from_payload(payload: list[dict]):
    seen_benef = {}
    seen_prest = {}
    seen_form = {}
    seen_lieu = {}
    seen_classe = {}
    created_apprenants = 0

    for item in payload:
        ben_name = item.get("beneficiaire", "").strip()
        ben_key = ben_name.lower()
        prest_name = item.get("prestataire", "").strip()
        prest_key = prest_name.lower()
        intitule = item.get("intitule_formation_dispensee") or item.get("intitule_formation_solicitee") or ""
        intitule_key = intitule.lower()
        fenetre = item.get("fenetre", "") or ""
        lieu_nom = item.get("lieu_formation", "").strip()
        lieu_key = lieu_nom.lower()
        classe_id = (item.get("classe_id") or "").strip()
        cohorte_raw = item.get("cohorte", "")

        region = item.get("region", "").strip()
        departement = item.get("departement", "").strip()
        arrondissement = item.get("arrondissement", "").strip()
        ville = item.get("ville_formation", "").strip()

        beneficiaire = seen_benef.get(ben_key) or _ensure_beneficiaire(
            ben_name, region=region, departement=departement, arrondissement=arrondissement, ville=ville
        )
        if beneficiaire:
            seen_benef[ben_key] = beneficiaire

        prestataire = seen_prest.get(prest_key) or _ensure_prestataire(prest_name)
        if prestataire:
            seen_prest[prest_key] = prestataire

        formation = seen_form.get(intitule_key) or _ensure_formation(intitule, fenetre=fenetre)
        if formation:
            seen_form[intitule_key] = formation

        lieu = seen_lieu.get(lieu_key) or _ensure_lieu(
            lieu_nom,
            region=region,
            departement=departement,
            arrondissement=arrondissement,
            ville=ville,
            longitude=item.get("longitude", ""),
            latitude=item.get("latitude", ""),
            precision=item.get("precision_lieu", ""),
        )
        if lieu:
            seen_lieu[lieu_key] = lieu

        prestation = _ensure_prestation(prestataire, formation, beneficiaire, code_hint=item.get("code", ""))
        
        # Clé unique pour la classe : on priorise classe_id si présent
        classe_key = classe_id.lower() if classe_id else f"{prestation.id if prestation else 'noprest'}-{fenetre}-{cohorte_raw}".lower()
        
        classe = seen_classe.get(classe_key)
        if not classe:
            classe = _ensure_classe(
                prestation,
                formation,
                fenetre=fenetre,
                cohorte=cohorte_raw,
                classe_id=classe_id,
            )
            if classe:
                seen_classe[classe_key] = classe

        if classe and formation:
            code_appr = (item.get("code") or "").strip()
            if not code_appr:
                code_appr = f"AP-{slugify(item.get('nom_complet','')[:12])}-{classe.code[:8]}"
            tel1 = (item.get("telephone1") or "").strip()
            tel2 = (item.get("telephone2") or "").strip()
            defaults = {
                "nom_complet": item.get("nom_complet", ""),
                "genre": item.get("genre", ""),
                "age": _to_int(item.get("age")),
                "fonction": item.get("fonction", ""),
                "qualification": item.get("qualification", ""),
                "nb_annees_experience": _to_int(item.get("nb_annees_experience")) or 0,
                "fenetre": fenetre,
                "telephone1": tel1 or None,
                "telephone2": tel2 or None,
                "ville_residence": item.get("ville_residence", ""),
                "region": region,
                "departement": departement,
                "arrondissement": arrondissement,
                "code_ville": item.get("ville_formation", ""),
                "appartenance_beneficiaire": True,
            }
            try:
                existing = None
                if tel1:
                    existing = Apprenant.objects.filter(formation=formation, telephone1=tel1).first()
                if existing:
                    for field, val in defaults.items():
                        setattr(existing, field, val)
                    existing.classe = classe
                    existing.formation = formation
                    existing.save()
                else:
                    obj, created = Apprenant.objects.get_or_create(
                        code=code_appr,
                        defaults={**defaults, "classe": classe, "formation": formation},
                    )
                    if created:
                        created_apprenants += 1
            except Exception:
                continue  # on saute la ligne en cas de conflit unique

    return created_apprenants


def consolidation_view(request):
    form = ConsolidationUploadForm(request.POST or None, request.FILES or None)
    headers = []
    preview_rows = []
    analysis = {"mapped": [], "missing": [], "extras": []}
    errors = []
    file_meta = request.session.get(SESSION_KEY_CONSO, {}).get("meta", {})
    save_requested = bool(request.POST.get("save"))
    extract_requested = bool(request.POST.get("extract_classes"))
    unique_classe_ids: list[str] = []

    if request.method == "POST" and form.is_valid():
        fichier = form.cleaned_data.get("fichier")
        try:
            content = None
            if fichier:
                content = fichier.read()
                file_meta = {
                    "name": getattr(fichier, "name", ""),
                    "size": getattr(fichier, "size", 0),
                }
                request.session[SESSION_KEY_CONSO] = {
                    "meta": file_meta,
                    "b64": base64.b64encode(content).decode("ascii"),
                }
                request.session.modified = True
            elif save_requested and request.session.get(SESSION_KEY_CONSO):
                cached = request.session.get(SESSION_KEY_CONSO, {})
                b64 = cached.get("b64")
                if b64:
                    content = base64.b64decode(b64)
                    file_meta = cached.get("meta", {})
            if not content:
                raise ValueError("Veuillez charger un fichier consolidé avant de valider.")

            buffer_preview = io.BytesIO(content)
            headers, preview_rows = _read_consolidation_sheet(buffer_preview, max_rows=60)
            analysis = _analyze_headers(headers)
            if save_requested or extract_requested:
                buffer_full = io.BytesIO(content)
                full_headers, all_rows = _read_consolidation_sheet(buffer_full, max_rows=None)
                records, payload = _rows_to_records(full_headers, all_rows)
                if not records:
                    raise ValueError("Aucune ligne valide à enregistrer.")
                unique_classe_ids = _extract_unique_classe_ids(payload)
                if save_requested:
                    try:
                        _reset_consolidation_tables()
                        ConsolidationRecord.objects.all().delete()
                        with transaction.atomic():
                            ConsolidationRecord.objects.bulk_create(records, ignore_conflicts=False)
                            created = _save_related_from_payload(payload)
                        messages.success(request, f"{len(records)} lignes importées → {created} apprenants créés/mis à jour (remplacement complet).")
                    except OperationalError:
                        errors.append("Base de données occupée (database locked). Réessayez dans un instant.")
        except Exception as exc:
            errors.append(str(exc))
            preview_rows = []

    return render(
        request,
        "reporting/consolidation.html",
        {
            "form": form,
            "headers": headers,
            "preview_rows": preview_rows,
            "analysis": analysis,
        "errors": errors,
        "file_meta": file_meta,
        "unique_classe_ids": unique_classe_ids,
        },
    )


# Les autres fonctions (reporting_home, get_table_data, etc.) restent inchangées
# (je ne les ai pas recopiées ici pour ne pas alourdir, mais elles doivent rester dans le fichier)

# Fonction d'analyse des headers (à conserver ou à réactiver pour debug)
def _analyze_headers(headers):
    normalized_headers = [_normalize_header(h or "") for h in headers]
    mapped_fields = set()
    for h in normalized_headers:
        mapped = CONSOLIDATION_HEADER_MAP.get(h)
        if mapped:
            mapped_fields.add(mapped)
    expected = {v for v in CONSOLIDATION_HEADER_MAP.values() if not v.startswith("cout") and not v.startswith("montant") and not v.startswith("statut")}
    missing = sorted(expected - mapped_fields)
    extras = [headers[idx] for idx, h in enumerate(normalized_headers) if h not in CONSOLIDATION_HEADER_MAP and h]
    return {
        "mapped": sorted(mapped_fields),
        "missing": missing,
        "extras": [e for e in extras if e],
    }
def _read_consolidation_sheet(file_obj, max_rows: int | None = 60):
    wb = load_workbook(file_obj, data_only=True)
    if "Consolidation" not in wb.sheetnames:
        raise ValueError("Feuille 'Consolidation' introuvable dans le fichier.")
    ws = wb["Consolidation"]
    header = None
    rows = []
    for r_idx, row in enumerate(ws.iter_rows(values_only=True)):
        # Stop after the expected columns, including "Classe ID".
        cells = [_normalize_cell(c) for c in row][:MAX_CONSO_COLS]
        if header is None:
            header = cells
            continue
        if not any(cells):
            continue
        rows.append(cells)
        if max_rows and len(rows) >= max_rows:
            break
    return header or [], rows


def _rows_to_records(header, rows):
    header_norm = [_normalize_header(h) for h in header[:MAX_CONSO_COLS]]
    header_map = {idx: CONSOLIDATION_HEADER_MAP[h] for idx, h in enumerate(header_norm) if h in CONSOLIDATION_HEADER_MAP}
    records = []
    related_payload = []
    for row in rows:
        cells = [_normalize_cell(c) for c in row][:29]
        if not any(cells):
            continue
        data = {}
        for idx, field in header_map.items():
            if idx < len(cells):
                data[field] = cells[idx]
        records.append(
            ConsolidationRecord(
                numero=data.get("numero", ""),
                nom_complet=data.get("nom_complet", ""),
                beneficiaire=data.get("beneficiaire", ""),
                genre=data.get("genre", ""),
                age=_to_int(data.get("age")),
                fonction=data.get("fonction", ""),
                qualification=data.get("qualification", ""),
                nb_annees_experience=_to_int(data.get("nb_annees_experience")),
                ville_residence=data.get("ville_residence", ""),
                prestataire=data.get("prestataire", ""),
                intitule_formation_solicitee=data.get("intitule_formation_solicitee", ""),
                intitule_formation_dispensee=data.get("intitule_formation_dispensee", ""),
                fenetre=data.get("fenetre", ""),
                ville_formation=data.get("ville_formation", ""),
                arrondissement=data.get("arrondissement", ""),
                departement=data.get("departement", ""),
                region=data.get("region", ""),
                lieu_formation=data.get("lieu_formation", ""),
                precision_lieu=data.get("precision_lieu", ""),
                longitude=data.get("longitude", ""),
                latitude=data.get("latitude", ""),
                telephone1=data.get("telephone1", ""),
                telephone2=data.get("telephone2", ""),
                cohorte=data.get("cohorte", ""),
                tel_formateur=data.get("tel_formateur", ""),
                code=data.get("code", ""),
                cout_unitaire_subvention=_to_decimal(data.get("cout_unitaire_subvention")),
                montant_total_subvention=_to_decimal(data.get("montant_total_subvention")),
                statut_prestation=data.get("statut_prestation", ""),
            )
        )
        related_payload.append(data)
    return records, related_payload


def _save_related_from_payload(payload: list[dict]):
    # Deduplicate creations for speed.
    seen_benef = {}
    seen_prest = {}
    seen_form = {}
    seen_lieu = {}
    seen_classe = {}
    created_apprenants = 0

    for item in payload:
        ben_name = item.get("beneficiaire", "").strip()
        ben_key = ben_name.lower()
        prest_name = item.get("prestataire", "").strip()
        prest_key = prest_name.lower()
        intitule = item.get("intitule_formation_dispensee") or item.get("intitule_formation_solicitee") or ""
        intitule_key = intitule.lower()
        fenetre = item.get("fenetre", "") or ""
        lieu_nom = item.get("lieu_formation", "").strip()
        lieu_key = lieu_nom.lower()
        classe_id = (item.get("classe_id") or "").strip()
        classe_id_key = classe_id.lower()
        cohorte_raw = item.get("cohorte", "")

        region = item.get("region", "").strip()
        departement = item.get("departement", "").strip()
        arrondissement = item.get("arrondissement", "").strip()
        ville = item.get("ville_formation", "").strip()

        beneficiaire = seen_benef.get(ben_key) or _ensure_beneficiaire(
            ben_name, region=region, departement=departement, arrondissement=arrondissement, ville=ville
        )
        if beneficiaire:
            seen_benef[ben_key] = beneficiaire

        prestataire = seen_prest.get(prest_key) or _ensure_prestataire(prest_name)
        if prestataire:
            seen_prest[prest_key] = prestataire

        formation = seen_form.get(intitule_key) or _ensure_formation(intitule, fenetre=fenetre)
        if formation:
            seen_form[intitule_key] = formation

        lieu = seen_lieu.get(lieu_key) or _ensure_lieu(
            lieu_nom,
            region=region,
            departement=departement,
            arrondissement=arrondissement,
            ville=ville,
            longitude=item.get("longitude", ""),
            latitude=item.get("latitude", ""),
            precision=item.get("precision_lieu", ""),
        )
        if lieu:
            seen_lieu[lieu_key] = lieu

        prestation = _ensure_prestation(prestataire, formation, beneficiaire, code_hint=item.get("code", ""))
        classe_key = classe_id_key or f"{prestation.id if prestation else 'noprest'}-{fenetre}-{cohorte_raw}".lower()
        classe = seen_classe.get(classe_key)
        if not classe:
            classe = _ensure_classe(
                prestation,
                formation,
                fenetre=fenetre,
                cohorte=cohorte_raw,
                classe_id=classe_id,
            )
            if classe:
                seen_classe[classe_key] = classe

        if classe and formation:
            code_appr = (item.get("code") or "").strip()
            if not code_appr:
                code_appr = f"AP-{slugify(item.get('nom_complet',''))[:6]}-{classe.code[:6]}"
            tel1 = (item.get("telephone1") or "").strip()
            tel2 = (item.get("telephone2") or "").strip()
            defaults = {
                "nom_complet": item.get("nom_complet", ""),
                "genre": item.get("genre", ""),
                "age": _to_int(item.get("age")),
                "fonction": item.get("fonction", ""),
                "qualification": item.get("qualification", ""),
                "nb_annees_experience": _to_int(item.get("nb_annees_experience")) or 0,
                "fenetre": fenetre,
                "telephone1": tel1 or None,
                "telephone2": tel2 or None,
                "ville_residence": item.get("ville_residence", ""),
                "region": region,
                "departement": departement,
                "arrondissement": arrondissement,
                "code_ville": item.get("ville_formation", ""),
                "appartenance_beneficiaire": True,
            }
            try:
                # Si un apprenant existe deja avec le meme tel1 dans la formation, on le met a jour.
                existing = None
                if tel1:
                    existing = Apprenant.objects.filter(formation=formation, telephone1=tel1).first()
                if existing:
                    for field, val in defaults.items():
                        setattr(existing, field, val)
                    existing.classe = classe
                    existing.formation = formation
                    existing.save()
                else:
                    obj, created = Apprenant.objects.get_or_create(
                        code=code_appr,
                        defaults={**defaults, "classe": classe, "formation": formation},
                    )
                    if created:
                        created_apprenants += 1
            except Exception:
                # En cas de conflit unique, on ignore la ligne pour ne pas casser l'import.
                continue
    return created_apprenants


def consolidation_view(request):
    form = ConsolidationUploadForm(request.POST or None, request.FILES or None)
    headers = []
    preview_rows = []
    analysis = {"mapped": [], "missing": [], "extras": []}
    errors = []
    file_meta = request.session.get(SESSION_KEY_CONSO, {}).get("meta", {})
    save_requested = bool(request.POST.get("save"))

    if request.method == "POST" and form.is_valid():
        fichier = form.cleaned_data.get("fichier")
        try:
            content = None
            if fichier:
                content = fichier.read()
                file_meta = {
                    "name": getattr(fichier, "name", ""),
                    "size": getattr(fichier, "size", 0),
                }
                request.session[SESSION_KEY_CONSO] = {
                    "meta": file_meta,
                    "b64": base64.b64encode(content).decode("ascii"),
                }
                request.session.modified = True
            elif save_requested and request.session.get(SESSION_KEY_CONSO):
                cached = request.session.get(SESSION_KEY_CONSO, {})
                b64 = cached.get("b64")
                if b64:
                    content = base64.b64decode(b64)
                    file_meta = cached.get("meta", {})
            if not content:
                raise ValueError("Veuillez charger un fichier consolide avant de valider.")

            buffer_preview = io.BytesIO(content)
            headers, preview_rows = _read_consolidation_sheet(buffer_preview, max_rows=60)
            analysis = _analyze_headers(headers)
            if save_requested:
                buffer_full = io.BytesIO(content)
                full_headers, all_rows = _read_consolidation_sheet(buffer_full, max_rows=None)
                records, payload = _rows_to_records(full_headers, all_rows)
                if not records:
                    raise ValueError("Aucune ligne valide a enregistrer.")
                try:
                    # Always wipe before inserting, even if the insert later fails, to behave like a seed/replace.
                    _reset_consolidation_tables()
                    ConsolidationRecord.objects.all().delete()
                    with transaction.atomic():
                        ConsolidationRecord.objects.bulk_create(records, ignore_conflicts=False)
                        _save_related_from_payload(payload)
                    messages.success(request, f"{len(records)} lignes consolidees enregistrees (remplacement complet).")
                except OperationalError:
                    errors.append("Base de donnees occupee (database locked). Reessayez dans un instant.")
        except Exception as exc:  # pragma: no cover - runtime feedback
            errors.append(str(exc))
            preview_rows = []

    return render(
        request,
        "reporting/consolidation.html",
        {
            "form": form,
            "headers": headers,
            "preview_rows": preview_rows,
            "analysis": analysis,
            "errors": errors,
            "file_meta": file_meta,
        },
    )


def safe_rate(num: float, den: float) -> float:
    return round((num / den) * 100, 2) if den else 0.0


def reporting_home(request):
    nb_classes = Classe.objects.count()
    nb_apprenants = Apprenant.objects.count()
    nb_formateurs = SatisfactionFormateur.objects.values("formateur").distinct().count()
    nb_enquetes_presence = Presence.objects.count()
    nb_sat_apprenants = SatisfactionApprenant.objects.count()
    nb_sat_formateurs = SatisfactionFormateur.objects.count()
    nb_env = EnqueteEnvironnement.objects.count()

    presence_rates = (
        Presence.objects.values("classe__code")
        .annotate(total=Count("id"), pr=Count("id", filter=Q(presence="PR")))
        .order_by("-total")[:10]
    )
    sat_appr_moy = (
        SatisfactionApprenant.objects.values("classe__code")
        .annotate(moy=Avg("q9_satisfaction_globale"))
        .order_by("-moy")[:10]
    )
    sat_form_moy = (
        SatisfactionFormateur.objects.values("classe__code")
        .annotate(moy=Avg("q9_satisfaction_globale_prestataire"))
        .order_by("-moy")[:10]
    )

    # Synthèses globales
    total_pres = Presence.objects.count()
    total_pr = Presence.objects.filter(presence="PR").count()
    taux_presence_global = safe_rate(total_pr, total_pres)

    # RES00-04
    sat_appr_agg = SatisfactionApprenant.objects.aggregate(total_q9=Sum("q9_satisfaction_globale"), count=Count("id"))
    sat_appr_sum = sat_appr_agg["total_q9"] or 0
    sat_appr_count = sat_appr_agg["count"] or 0
    taux_sat_appr_global = safe_rate(sat_appr_sum, sat_appr_count * 5)
    # RES00-05
    sat_form_agg = SatisfactionFormateur.objects.aggregate(total_q9=Sum("q9_satisfaction_globale_prestataire"), count=Count("id"))
    sat_form_sum = sat_form_agg["total_q9"] or 0
    sat_form_count = sat_form_agg["count"] or 0
    taux_sat_form_global = safe_rate(sat_form_sum, sat_form_count * 5)

    # Environnement : moyenne des booleens principaux (8 points indicatifs)
    env_bool_fields = [
        "tables",
        "chaises",
        "ecran",
        "videoprojecteur",
        "ventilation",
        "eclairage",
        "salle_propre",
        "salle_securisee",
    ]
    env_counts = EnqueteEnvironnement.objects.aggregate(
        total=Count("id"), **{f: Sum(f) for f in env_bool_fields}
    )
    env_score = safe_rate(
        sum((env_counts.get(f) or 0) for f in env_bool_fields),
        (env_counts.get("total") or 0) * len(env_bool_fields),
    )

    # Taux presence par axes
    def with_rate(qs):
        return [{**r, "taux": safe_rate(r.get("pr") or 0, r.get("total") or 0)} for r in qs]

    taux_presence_prestataire = with_rate(
        Presence.objects.values("classe__prestation__prestataire__raison_sociale")
        .annotate(total=Count("id"), pr=Count("id", filter=Q(presence="PR")))
        .order_by("-total")
    )
    taux_presence_prestation = with_rate(
        Presence.objects.values("classe__prestation__code")
        .annotate(total=Count("id"), pr=Count("id", filter=Q(presence="PR")))
        .order_by("-total")
    )
    taux_presence_beneficiaire = with_rate(
        Presence.objects.values("classe__prestation__beneficiaire__nom_structure")
        .annotate(total=Count("id"), pr=Count("id", filter=Q(presence="PR")))
        .order_by("-total")
    )
    taux_presence_formation = with_rate(
        Presence.objects.values("classe__formation__nom")
        .annotate(total=Count("id"), pr=Count("id", filter=Q(presence="PR")))
        .order_by("-total")
    )
    taux_presence_formation_harmo = with_rate(
        Presence.objects.values("classe__formation__nom_harmonise")
        .annotate(total=Count("id"), pr=Count("id", filter=Q(presence="PR")))
        .order_by("-total")
    )

    # Satisfaction globale par axes (apprenants)
    sat_appr_prestataire = (
        SatisfactionApprenant.objects.values("classe__prestation__prestataire__raison_sociale")
        .annotate(moy=Avg("q9_satisfaction_globale"))
        .order_by("-moy")
    )
    sat_appr_prestation = (
        SatisfactionApprenant.objects.values("classe__prestation__code")
        .annotate(moy=Avg("q9_satisfaction_globale"))
        .order_by("-moy")
    )
    sat_appr_benef = (
        SatisfactionApprenant.objects.values("classe__prestation__beneficiaire__nom_structure")
        .annotate(moy=Avg("q9_satisfaction_globale"))
        .order_by("-moy")
    )
    sat_appr_formation = (
        SatisfactionApprenant.objects.values("classe__formation__nom")
        .annotate(moy=Avg("q9_satisfaction_globale"))
        .order_by("-moy")
    )
    sat_appr_formation_harmo = (
        SatisfactionApprenant.objects.values("classe__formation__nom_harmonise")
        .annotate(moy=Avg("q9_satisfaction_globale"))
        .order_by("-moy")
    )

    # Satisfaction globale par axes (formateurs)
    sat_form_prestataire = (
        SatisfactionFormateur.objects.values("classe__prestation__prestataire__raison_sociale")
        .annotate(moy=Avg("q9_satisfaction_globale_prestataire"))
        .order_by("-moy")
    )
    sat_form_prestation = (
        SatisfactionFormateur.objects.values("classe__prestation__code")
        .annotate(moy=Avg("q9_satisfaction_globale_prestataire"))
        .order_by("-moy")
    )
    sat_form_benef = (
        SatisfactionFormateur.objects.values("classe__prestation__beneficiaire__nom_structure")
        .annotate(moy=Avg("q9_satisfaction_globale_prestataire"))
        .order_by("-moy")
    )
    sat_form_formation = (
        SatisfactionFormateur.objects.values("classe__formation__nom")
        .annotate(moy=Avg("q9_satisfaction_globale_prestataire"))
        .order_by("-moy")
    )
    sat_form_formation_harmo = (
        SatisfactionFormateur.objects.values("classe__formation__nom_harmonise")
        .annotate(moy=Avg("q9_satisfaction_globale_prestataire"))
        .order_by("-moy")
    )

    repart_apprenants_ville = Apprenant.objects.values("ville_residence").annotate(total=Count("id")).order_by("-total")
    repart_apprenants_region = Apprenant.objects.values("region").annotate(total=Count("id")).order_by("-total")
    repart_apprenants_formation = (
        Apprenant.objects.values("formation__nom")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    repart_apprenants_formation_harmo = (
        Apprenant.objects.values("formation__nom_harmonise")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    repart_apprenants_benef = (
        Apprenant.objects.values("classe__prestation__beneficiaire__nom_structure")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    repart_apprenants_prestataire = (
        Apprenant.objects.values("classe__prestation__prestataire__raison_sociale")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    # Effectifs / femmes / appartenance par prestation
    prestations_effectifs = (
        Prestation.objects.annotate(
            appr_total=Count("classes__apprenants", distinct=True),
            appr_femmes=Count("classes__apprenants", filter=Q(classes__apprenants__genre__iexact="f"), distinct=True),
            appr_appart=Count(
                "classes__apprenants",
                filter=Q(classes__apprenants__appartenance_beneficiaire=True),
                distinct=True,
            ),
        )
        .values(
            "code",
            "effectif_a_former",
            "femmes",
            "appr_total",
            "appr_femmes",
            "appr_appart",
            "prestataire__raison_sociale",
            "beneficiaire__nom_structure",
        )
        .order_by("code")
    )

    # Durées par prestation
    prestations_durees = Prestation.objects.values(
        "code", "prestataire__raison_sociale", "duree_prevue_heures", "duree_reelle_heures"
    ).order_by("code")

    # Environnement par lieu
    env_fields = [
        "tables",
        "chaises",
        "ecran",
        "videoprojecteur",
        "ventilation",
        "eclairage",
        "salle_propre",
        "salle_securisee",
    ]
    env_qs = (
        EnqueteEnvironnement.objects.values("classe__lieu__nom_lieu", "classe__lieu__region")
        .annotate(
            total=Count("id"),
            **{f: Sum(f) for f in env_fields},
        )
        .order_by("-total")
    )
    env_par_lieu = []
    for row in env_qs:
        total = row.get("total") or 0
        somme = sum((row.get(f) or 0) for f in env_fields)
        score = safe_rate(somme, total * len(env_fields))
        env_par_lieu.append(
            {
                "lieu": row.get("classe__lieu__nom_lieu"),
                "region": row.get("classe__lieu__region"),
                "total": total,
                "score": score,
            }
        )

    # Logic for RES02-03, RES02-04, RES02-05
    prestations_effectifs_list = []
    for p in prestations_effectifs:
        eff_ok = (p["appr_total"] or 0) >= (p["effectif_a_former"] or 0)
        femmes_ok = (p["appr_femmes"] or 0) >= (p["femmes"] or 0)
        p["respect_effectif"] = eff_ok
        p["respect_femmes"] = femmes_ok
        p["taux_appartenance"] = safe_rate(p["appr_appart"] or 0, p["appr_total"] or 0)
        prestations_effectifs_list.append(p)

    # Logic for RES03-01
    from App_PADESCE.formations.models import Lieu
    carte_lieux = []
    for l in Lieu.objects.filter(actif=True):
        if l.latitude and l.longitude:
             carte_lieux.append({"nom": l.nom_lieu, "lat": l.latitude, "lng": l.longitude})

    charts = [
        {"code": "RES00-01", "title": "Taux de présence global", "value": f"{taux_presence_global} %"},
        {"code": "RES00-02", "title": "Synthèse du suivi contractuel", "value": "N/A"},
        {"code": "RES00-03", "title": "Synthèse de l'évaluation de l'environnement (8 points)", "value": f"{env_score} %"},
        {"code": "RES00-04", "title": "Taux de satisfaction global apprenants", "value": f"{taux_sat_appr_global} %"},
        {"code": "RES00-05", "title": "Taux de satisfaction global formateurs", "value": f"{taux_sat_form_global} %"},
    ]

    context = {
        "nb_classes": nb_classes,
        "nb_apprenants": nb_apprenants,
        "nb_formateurs": nb_formateurs,
        "nb_enquetes_presence": nb_enquetes_presence,
        "nb_sat_apprenants": nb_sat_apprenants,
        "nb_sat_formateurs": nb_sat_formateurs,
        "nb_env": nb_env,
        "presence_rates": presence_rates,
        "sat_appr_moy": sat_appr_moy,
        "sat_form_moy": sat_form_moy,
        "formations": Formation.objects.all().order_by("nom")[:20],
        "charts": charts,
        "carte_lieux": carte_lieux,
        "taux_presence_prestataire": taux_presence_prestataire,
        "taux_presence_prestation": taux_presence_prestation,
        "taux_presence_beneficiaire": taux_presence_beneficiaire,
        "taux_presence_formation": taux_presence_formation,
        "taux_presence_formation_harmo": taux_presence_formation_harmo,
        "sat_appr_prestataire": sat_appr_prestataire,
        "sat_appr_prestation": sat_appr_prestation,
        "sat_appr_benef": sat_appr_benef,
        "sat_appr_formation": sat_appr_formation,
        "sat_appr_formation_harmo": sat_appr_formation_harmo,
        "sat_form_prestataire": sat_form_prestataire,
        "sat_form_prestation": sat_form_prestation,
        "sat_form_benef": sat_form_benef,
        "sat_form_formation": sat_form_formation,
        "sat_form_formation_harmo": sat_form_formation_harmo,
        "repart_apprenants_ville": repart_apprenants_ville,
        "repart_apprenants_region": repart_apprenants_region,
        "repart_apprenants_formation": repart_apprenants_formation,
        "repart_apprenants_formation_harmo": repart_apprenants_formation_harmo,
        "repart_apprenants_benef": repart_apprenants_benef,
        "repart_apprenants_prestataire": repart_apprenants_prestataire,
        "prestations_effectifs": prestations_effectifs_list,
        "prestations_durees": prestations_durees,
        "env_par_lieu": env_par_lieu,
    }
    return render(request, "reporting/index.html", context)


def _table_presence_rates(field: str):
    return Presence.objects.values(field).annotate(total=Count("id"), pr=Count("id", filter=Q(presence="PR"))).order_by(
        "-total"
    )


def _table_sat_avg(model, field: str, display: str):
    return model.objects.values(display).annotate(moy=Avg(field)).order_by("-moy")


def get_table_data(code: str) -> dict:
    code = code.lower()
    if code == "presence-classe":
        qs = _table_presence_rates("classe__code")[:10]
        return {
            "title": "Top presence (classe)",
            "headers": ["Classe", "PR", "Total"],
            "rows": [[r["classe__code"], r["pr"], r["total"]] for r in qs],
        }
    if code == "sat-appr-q9":
        qs = _table_sat_avg(SatisfactionApprenant, "q9_satisfaction_globale", "classe__code")[:10]
        return {
            "title": "Sat. apprenants (Q9)",
            "headers": ["Classe", "Moyenne"],
            "rows": [[r["classe__code"], round(r["moy"] or 0, 2)] for r in qs],
        }
    if code == "sat-form-q9":
        qs = _table_sat_avg(SatisfactionFormateur, "q9_satisfaction_globale_prestataire", "classe__code")[:10]
        return {
            "title": "Sat. formateurs (Q9)",
            "headers": ["Classe", "Moyenne"],
            "rows": [[r["classe__code"], round(r["moy"] or 0, 2)] for r in qs],
        }
    if code == "presence-prestataire":
        qs = _table_presence_rates("classe__prestation__prestataire__raison_sociale")
        return {
            "title": "Presence par prestataire",
            "headers": ["Prestataire", "PR", "Total", "Taux %"],
            "rows": [
                [r["classe__prestation__prestataire__raison_sociale"], r["pr"], r["total"], safe_rate(r["pr"], r["total"])]
                for r in qs
            ],
        }
    if code == "presence-prestation":
        qs = _table_presence_rates("classe__prestation__code")
        return {
            "title": "Presence par prestation",
            "headers": ["Prestation", "PR", "Total", "Taux %"],
            "rows": [[r["classe__prestation__code"], r["pr"], r["total"], safe_rate(r["pr"], r["total"])] for r in qs],
        }
    if code == "presence-beneficiaire":
        qs = _table_presence_rates("classe__prestation__beneficiaire__nom_structure")
        return {
            "title": "Presence par beneficiaire",
            "headers": ["Beneficiaire", "PR", "Total", "Taux %"],
            "rows": [
                [r["classe__prestation__beneficiaire__nom_structure"], r["pr"], r["total"], safe_rate(r["pr"], r["total"])]
                for r in qs
            ],
        }
    if code == "presence-formation":
        qs = _table_presence_rates("classe__formation__nom")
        return {
            "title": "Presence par formation",
            "headers": ["Formation", "PR", "Total", "Taux %"],
            "rows": [[r["classe__formation__nom"], r["pr"], r["total"], safe_rate(r["pr"], r["total"])] for r in qs],
        }
    if code == "presence-formation-harmo":
        qs = _table_presence_rates("classe__formation__nom_harmonise")
        return {
            "title": "Presence par formation harmonisee",
            "headers": ["Formation harmo.", "PR", "Total", "Taux %"],
            "rows": [
                [r["classe__formation__nom_harmonise"], r["pr"], r["total"], safe_rate(r["pr"], r["total"])] for r in qs
            ],
        }
    if code == "sat-appr-prestataire":
        qs = _table_sat_avg(
            SatisfactionApprenant, "q9_satisfaction_globale", "classe__prestation__prestataire__raison_sociale"
        )
        return {
            "title": "Satisfaction apprenants par axes",
            "headers": ["Groupe", "Moyenne"],
            "rows": [[r["classe__prestation__prestataire__raison_sociale"], round(r["moy"] or 0, 2)] for r in qs],
        }
    if code == "sat-form-prestataire":
        qs = _table_sat_avg(
            SatisfactionFormateur, "q9_satisfaction_globale_prestataire", "classe__prestation__prestataire__raison_sociale"
        )
        return {
            "title": "Satisfaction formateurs par axes",
            "headers": ["Groupe", "Moyenne"],
            "rows": [[r["classe__prestation__prestataire__raison_sociale"], round(r["moy"] or 0, 2)] for r in qs],
        }
    if code == "prestations-effectifs":
        qs = (
            Prestation.objects.annotate(
                appr_total=Count("classes__apprenants", distinct=True),
                appr_femmes=Count(
                    "classes__apprenants", filter=Q(classes__apprenants__genre__iexact="f"), distinct=True
                ),
                appr_appart=Count(
                    "classes__apprenants", filter=Q(classes__apprenants__appartenance_beneficiaire=True), distinct=True
                ),
            )
            .values("code", "effectif_a_former", "femmes", "appr_total", "appr_femmes", "appr_appart")
            .order_by("code")
        )
        rows = []
        for r in qs:
             eff_ok = (r["appr_total"] or 0) >= (r["effectif_a_former"] or 0)
             femmes_ok = (r["appr_femmes"] or 0) >= (r["femmes"] or 0)
             appart_rate = safe_rate(r["appr_appart"] or 0, r["appr_total"] or 0)
             rows.append([
                 r["code"],
                 r["effectif_a_former"], r["appr_total"], "OK" if eff_ok else "NOK",
                 r["femmes"], r["appr_femmes"], "OK" if femmes_ok else "NOK",
                 r["appr_appart"], f"{appart_rate} %"
             ])
        return {
            "title": "Effectifs / Femmes / Appartenance par prestation",
            "headers": ["Prestation", "Eff. prevu", "Eff. reel", "Resp. Eff", "Fem. prevues", "Fem. reelles", "Resp. Fem", "Appart.", "Taux App."],
            "rows": rows,
        }
    if code == "prestations-durees":
        qs = Prestation.objects.values("code", "duree_prevue_heures", "duree_reelle_heures").order_by("code")
        return {
            "title": "Durees par prestation",
            "headers": ["Prestation", "Duree prevue (h)", "Duree reelle (h)"],
            "rows": [[r["code"], r["duree_prevue_heures"], r["duree_reelle_heures"]] for r in qs],
        }
    if code == "repart-ville":
        qs = Apprenant.objects.values("ville_residence").annotate(total=Count("id")).order_by("-total")
        return {
            "title": "Repartition apprenants (villes)",
            "headers": ["Ville", "Total"],
            "rows": [[r["ville_residence"], r["total"]] for r in qs],
        }
    if code == "repart-region":
        qs = Apprenant.objects.values("region").annotate(total=Count("id")).order_by("-total")
        return {
            "title": "Repartition apprenants (regions)",
            "headers": ["Region", "Total"],
            "rows": [[r["region"], r["total"]] for r in qs],
        }
    if code == "repart-formation":
        qs = Apprenant.objects.values("formation__nom").annotate(total=Count("id")).order_by("-total")
        return {
            "title": "Repartition formations",
            "headers": ["Formation", "Total"],
            "rows": [[r["formation__nom"], r["total"]] for r in qs],
        }
    if code == "repart-formation-harmo":
        qs = Apprenant.objects.values("formation__nom_harmonise").annotate(total=Count("id")).order_by("-total")
        return {
            "title": "Repartition formations harmonisees",
            "headers": ["Formation harmonisee", "Total"],
            "rows": [[r["formation__nom_harmonise"], r["total"]] for r in qs],
        }
    if code == "repart-beneficiaire":
        qs = (
            Apprenant.objects.values("classe__prestation__beneficiaire__nom_structure")
            .annotate(total=Count("id"))
            .order_by("-total")
        )
        return {
            "title": "Repartition beneficiaires",
            "headers": ["Beneficiaire", "Total"],
            "rows": [[r["classe__prestation__beneficiaire__nom_structure"], r["total"]] for r in qs],
        }
    if code == "repart-prestataire":
        qs = (
            Apprenant.objects.values("classe__prestation__prestataire__raison_sociale")
            .annotate(total=Count("id"))
            .order_by("-total")
        )
        return {
            "title": "Repartition prestataires",
            "headers": ["Prestataire", "Total"],
            "rows": [[r["classe__prestation__prestataire__raison_sociale"], r["total"]] for r in qs],
        }
    if code == "env-lieu":
        env_fields = [
            "tables",
            "chaises",
            "ecran",
            "videoprojecteur",
            "ventilation",
            "eclairage",
            "salle_propre",
            "salle_securisee",
        ]
        env_qs = (
            EnqueteEnvironnement.objects.values("classe__lieu__nom_lieu", "classe__lieu__region")
            .annotate(total=Count("id"), **{f: Sum(f) for f in env_fields})
            .order_by("-total")
        )
        rows = []
        for row in env_qs:
            total = row.get("total") or 0
            somme = sum((row.get(f) or 0) for f in env_fields)
            rows.append(
                [
                    row.get("classe__lieu__nom_lieu"),
                    row.get("classe__lieu__region"),
                    total,
                    safe_rate(somme, total * len(env_fields)),
                ]
            )
        return {
            "title": "Environnement par lieu",
            "headers": ["Lieu", "Region", "Nb enquetes", "Score (8 pts)"],
            "rows": rows,
        }
    raise Http404("Table inconnue")


def export_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=reporting_summary.csv"
    writer = csv.writer(response)
    writer.writerow(["type", "label", "valeur"])
    writer.writerow(["nb_classes", "Classes", Classe.objects.count()])
    writer.writerow(["nb_apprenants", "Apprenants", Apprenant.objects.count()])
    writer.writerow(["nb_presences", "Enquetes presence", Presence.objects.count()])
    writer.writerow(["nb_sat_appr", "Sat apprenants", SatisfactionApprenant.objects.count()])
    writer.writerow(["nb_sat_form", "Sat formateurs", SatisfactionFormateur.objects.count()])
    writer.writerow(["nb_env", "Environnement", EnqueteEnvironnement.objects.count()])
    return response


def export_excel(request):
    # Simplified: reuse CSV content with .xls extension to keep it lightweight here.
    response = export_csv(request)
    response["Content-Disposition"] = "attachment; filename=reporting_summary.xls"
    return response


def reporting_embed(request, code: str):
    response = render(request, "reporting/embed.html", {"code": code.upper()})
    response["X-Frame-Options"] = "ALLOWALL"
    return response


def reporting_embed_table(request, code: str):
    payload = get_table_data(code)
    response = render(request, "reporting/embed_table.html", payload)
    response["X-Frame-Options"] = "ALLOWALL"
    return response

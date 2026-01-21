import csv
import io
import os
import re
import unicodedata
import uuid
from datetime import datetime

import pandas as pd
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render

from App_PADESCE.beneficiaires.models import BeneficiaireUpload

NUMERO_HEADERS = ["no", "numero", "num", "n", "numero ordre", "numero d ordre"]
NOM_HEADERS = [
    "nom et prenom",
    "nom prenom",
    "nom complet",
    "name and first name",
    "name & first name",
]
BENEFICIAIRE_HEADERS = [
    "beneficiaire",
    "beneficiaires",
    "beneficiary",
    "structure beneficiaire",
    "organisation beneficiaire",
]
GENRE_HEADERS = ["genre", "gender", "sexe"]
AGE_HEADERS = ["age"]
FONCTION_HEADERS = ["fonction", "function"]
DIPLOME_HEADERS = ["diplome", "diploma", "niveau diplome", "niveau d etude", "qualification"]
EXPERIENCE_HEADERS = ["nb d annees d experience", "annees d experience", "years of experience", "experience"]
VILLE_RESIDENCE_HEADERS = [
    "ville de residence de l apprenant",
    "ville residence apprenant",
    "learner s city of residence",
    "city of residence",
    "ville residence",
]
PRESTATAIRE_HEADERS = ["prestataire", "training provider", "organisme prestataire", "structure prestataire"]
FORMATION_SOL_HEADERS = [
    "intitule de la formation sollicitee",
    "formation sollicitee",
    "title of requested training",
    "requested training",
]
FORMATION_DISP_HEADERS = [
    "intitule de formation dispensee",
    "formation dispensee",
    "title of training delivered",
    "training delivered",
]
FENETRE_HEADERS = ["fenetre", "window"]
VILLE_FORMATION_HEADERS = ["ville de la formation", "training city", "ville formation"]
ARRONDISSEMENT_HEADERS = ["arrondissement de la formation", "training district", "arrondissement"]
DEPARTEMENT_HEADERS = ["departement de la formation", "training division", "departement"]
REGION_HEADERS = ["region de la formation", "training region", "region"]
LIEU_FORMATION_HEADERS = [
    "denomination du lieu de la formation",
    "training venue name",
    "nom du lieu",
    "lieu de la formation",
    "training venue",
]
PRECISION_LIEU_HEADERS = [
    "precision sur le lieu",
    "quartier de formation",
    "training area",
    "neighborhood details",
    "localisation precise",
    "precision lieu",
]
GPS_LONG_HEADERS = [
    "coordonnees gps du lieu de formation longitude",
    "training venue gps longitude",
    "gps longitude",
    "longitude",
]
GPS_LAT_HEADERS = [
    "coordonnees gps du lieu de formation latitude",
    "training venue gps latitude",
    "gps latitude",
    "latitude",
]
TELEPHONE1_HEADERS = [
    "1er no tel apprenant",
    "1er tel apprenant",
    "telephone apprenant 1",
    "learner s 1st phone number",
    "phone 1",
    "telephone1",
]
TELEPHONE2_HEADERS = [
    "2e no tel apprenant",
    "2e tel apprenant",
    "telephone apprenant 2",
    "learner s 2nd phone number",
    "phone 2",
    "telephone2",
]
COHORTE_HEADERS = ["cohorte", "cohort", "groupe", "lot"]
TEL_FORMATEUR_HEADERS = [
    "tel formateur",
    "telephone formateur",
    "trainer phone",
    "point focal",
    "contact formateur",
]
APPRENANT_COLUMN_GROUPS = [
    NUMERO_HEADERS,
    NOM_HEADERS,
    BENEFICIAIRE_HEADERS,
    GENRE_HEADERS,
    AGE_HEADERS,
    FONCTION_HEADERS,
    DIPLOME_HEADERS,
    EXPERIENCE_HEADERS,
    VILLE_RESIDENCE_HEADERS,
    PRESTATAIRE_HEADERS,
    FORMATION_SOL_HEADERS,
    FORMATION_DISP_HEADERS,
    FENETRE_HEADERS,
    VILLE_FORMATION_HEADERS,
    ARRONDISSEMENT_HEADERS,
    DEPARTEMENT_HEADERS,
    REGION_HEADERS,
    LIEU_FORMATION_HEADERS,
    PRECISION_LIEU_HEADERS,
    GPS_LONG_HEADERS,
    GPS_LAT_HEADERS,
    TELEPHONE1_HEADERS,
    TELEPHONE2_HEADERS,
    COHORTE_HEADERS,
    TEL_FORMATEUR_HEADERS,
]
EXPECTED_COLUMNS = {
    "numero": "No / Numero",
    "nom_complet": "Nom et prenom",
    "beneficiaire": "Beneficiaire",
    "genre": "Genre",
    "age": "Age",
    "fonction": "Fonction",
    "diplome": "Diplome",
    "experience": "Annees experience",
    "ville_residence": "Ville residence apprenant",
    "prestataire": "Prestataire",
    "formation_solicitee": "Intitule formation sollicitee",
    "formation_dispensee": "Intitule formation dispensee",
    "fenetre": "Fenetre",
    "ville_formation": "Ville formation",
    "arrondissement": "Arrondissement formation",
    "departement": "Departement formation",
    "region": "Region formation",
    "lieu_formation": "Lieu formation",
    "precision_lieu": "Precision lieu",
    "gps_longitude": "Longitude",
    "gps_latitude": "Latitude",
    "telephone1": "Telephone apprenant 1",
    "telephone2": "Telephone apprenant 2",
    "cohorte": "Cohorte",
    "telephone_formateur": "Telephone formateur",
}
RECAP_GLOBAL_PATH = "beneficiaires/recaps/recap_beneficiaires.xlsx"
HISTORY_PAGE_SIZE = 10


def _normalize_header(value: str) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return text


def _find_column(columns, candidates):
    normalized = {_normalize_header(col): col for col in columns}
    for candidate in candidates:
        cand_norm = _normalize_header(candidate)
        for col_norm, original in normalized.items():
            if col_norm == cand_norm:
                return original
            if col_norm.replace(" ", "") == cand_norm.replace(" ", ""):
                return original
            if cand_norm and cand_norm in col_norm:
                return original
    return None


def _normalize_value(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _extract_single_value(series: pd.Series, label: str):
    values = series.dropna().astype(str).map(_normalize_value)
    values = values[values != ""]
    if values.empty:
        return "", f"{label.capitalize()} introuvable dans le fichier.", f"missing_{label}"
    normalized = values.str.lower()
    unique_norm = list(dict.fromkeys(normalized.tolist()))
    unique_values = list(dict.fromkeys(values.tolist()))
    if len(unique_norm) > 1:
        sample = ", ".join(unique_values[:3])
        return unique_values[0], f"Plusieurs {label}s detectes: {sample}", f"multiple_{label}"
    return unique_values[0], None, None


def _is_missing(series: pd.Series) -> pd.Series:
    return series.isna() | series.astype(str).str.strip().eq("")


def _score_columns(columns) -> int:
    return sum(1 for candidates in APPRENANT_COLUMN_GROUPS if _find_column(columns, candidates))


def _load_dataframe(uploaded_file):
    filename = (uploaded_file.name or "").lower()
    if filename.endswith((".xlsx", ".xls", ".xlsm")):
        excel = pd.ExcelFile(uploaded_file)
        target_norm = _normalize_header("Liste des apprenants")
        target_sheet = None
        for sheet in excel.sheet_names:
            if target_norm in _normalize_header(sheet):
                target_sheet = sheet
                break
        if target_sheet:
            df = excel.parse(sheet_name=target_sheet)
        else:
            best_sheet = None
            best_score = -1
            for sheet in excel.sheet_names:
                try:
                    preview = excel.parse(sheet_name=sheet, nrows=0)
                except ValueError:
                    continue
                score = _score_columns(preview.columns)
                if score > best_score:
                    best_score = score
                    best_sheet = sheet
            if not best_sheet or best_score <= 0:
                sheets = ", ".join(excel.sheet_names) or "-"
                return None, (
                    "Feuille 'Liste des apprenants' introuvable. Feuilles disponibles: %s" % sheets
                )
            df = excel.parse(sheet_name=best_sheet)
    elif filename.endswith(".csv"):
        df = pd.read_csv(uploaded_file, sep=None, engine="python")
    else:
        return None, "Format non supporte. Utilisez CSV ou Excel."

    df = df.dropna(how="all")
    if df.empty:
        return None, "Le fichier est vide."
    return df, None


def _safe_str(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _normalize_gender(value) -> str:
    text = _normalize_value(value).upper()
    text = re.sub(r"\s+", "", text)
    if text in ("H", "HOMME"):
        return "H"
    if text in ("M", "MASCULIN"):
        return "M"
    if text in ("F", "FEMME", "FEMININ"):
        return "F"
    return text


def _slugify(value: str) -> str:
    text = _normalize_header(value)
    text = re.sub(r"\s+", "_", text).strip("_")
    return text or "beneficiaire"


def _to_float_series(series: pd.Series) -> pd.Series:
    cleaned = series.where(~series.isna(), "").astype(str).str.strip()
    cleaned = cleaned.str.replace(",", ".", regex=False)
    cleaned = cleaned.replace("", pd.NA)
    return pd.to_numeric(cleaned, errors="coerce")


def _build_error_exports(error_rows, beneficiaire_nom: str) -> dict:
    if not error_rows:
        return {"csv": "", "txt": "", "xlsx": ""}

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = _slugify(beneficiaire_nom or "beneficiaire")
    base_name = f"beneficiaires/errors/{slug}_{timestamp}_{uuid.uuid4().hex[:8]}"
    headers = ["beneficiaire", "ligne", "colonne", "valeur", "erreur"]
    rows = []
    for row in error_rows:
        rows.append(
            [
                beneficiaire_nom or "",
                row.get("ligne", ""),
                row.get("colonne", ""),
                row.get("valeur", ""),
                row.get("erreur", ""),
            ]
        )

    csv_buffer = io.StringIO()
    csv_writer = csv.writer(csv_buffer, delimiter=";")
    csv_writer.writerow(headers)
    csv_writer.writerows(rows)
    csv_saved = default_storage.save(
        f"{base_name}.csv", ContentFile(csv_buffer.getvalue().encode("utf-8-sig"))
    )

    txt_buffer = io.StringIO()
    txt_writer = csv.writer(txt_buffer, delimiter="\t", lineterminator="\n")
    txt_writer.writerow(headers)
    txt_writer.writerows(rows)
    txt_saved = default_storage.save(
        f"{base_name}.txt", ContentFile(txt_buffer.getvalue().encode("utf-8-sig"))
    )

    df = pd.DataFrame(rows, columns=headers)
    xlsx_buffer = io.BytesIO()
    with pd.ExcelWriter(xlsx_buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Erreurs")
    xlsx_saved = default_storage.save(f"{base_name}.xlsx", ContentFile(xlsx_buffer.getvalue()))

    return {
        "csv": default_storage.url(csv_saved),
        "txt": default_storage.url(txt_saved),
        "xlsx": default_storage.url(xlsx_saved),
    }


def _serialize_upload(upload: BeneficiaireUpload) -> dict:
    stats = upload.recap_stats or {}
    return {
        "id": upload.id,
        "beneficiaire_nom": upload.beneficiaire_nom,
        "prestataire_nom": upload.prestataire_nom,
        "fichier_nom": os.path.basename(upload.fichier.name or ""),
        "created_at": upload.created_at.strftime("%d/%m/%Y %H:%M") if upload.created_at else "",
        "est_rejete": bool(upload.est_rejete),
        "row_count": stats.get("row_count", 0),
        "telephone_anomalies": stats.get("telephone_anomalies", 0),
        "genre_anomalies": stats.get("genre_anomalies", 0),
        "cohorte_anomalies": stats.get("cohorte_anomalies", 0),
        "columns_with_issues": stats.get("columns_with_issues", 0),
        "total_anomalies": stats.get("total_anomalies", 0),
    }


def _build_recap_rows(uploads) -> list:
    rows = []
    for upload in uploads:
        stats = upload.recap_stats or {}
        rows.append(
            {
                "Beneficiaire": upload.beneficiaire_nom,
                "Prestataire": upload.prestataire_nom,
                "Fichier": os.path.basename(upload.fichier.name or ""),
                "Date": upload.created_at.strftime("%d/%m/%Y %H:%M") if upload.created_at else "",
                "Statut": "KO" if upload.est_rejete else "OK",
                "Lignes": stats.get("row_count", 0),
                "Anomalies telephone": stats.get("telephone_anomalies", 0),
                "Anomalies sexe": stats.get("genre_anomalies", 0),
                "Anomalies cohorte": stats.get("cohorte_anomalies", 0),
                "Colonnes en souci": stats.get("columns_with_issues", 0),
                "Total anomalies": stats.get("total_anomalies", 0),
            }
        )
    return rows


def _save_recap_excel(rows, storage_path: str) -> str:
    if not rows:
        return default_storage.url(storage_path) if default_storage.exists(storage_path) else ""
    df = pd.DataFrame(rows)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Recap")
    if default_storage.exists(storage_path):
        default_storage.delete(storage_path)
    saved = default_storage.save(storage_path, ContentFile(buffer.getvalue()))
    return default_storage.url(saved)


def _get_recap_global_url() -> str:
    return default_storage.url(RECAP_GLOBAL_PATH) if default_storage.exists(RECAP_GLOBAL_PATH) else ""


def _parse_date(value: str):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _get_history_choices() -> dict:
    prestataires = (
        BeneficiaireUpload.objects.values_list("prestataire_nom", flat=True)
        .distinct()
        .order_by("prestataire_nom")
    )
    beneficiaires = (
        BeneficiaireUpload.objects.values_list("beneficiaire_nom", flat=True)
        .distinct()
        .order_by("beneficiaire_nom")
    )
    return {
        "prestataires": list(prestataires),
        "beneficiaires": list(beneficiaires),
    }


def _build_history_payload(filters: dict, page: int = 1):
    qs = BeneficiaireUpload.objects.all()
    prestataire = (filters.get("prestataire") or "").strip()
    beneficiaire = (filters.get("beneficiaire") or "").strip()
    date_from = _parse_date(filters.get("date_from") or "")
    date_to = _parse_date(filters.get("date_to") or "")

    if prestataire:
        qs = qs.filter(prestataire_nom__iexact=prestataire)
    if beneficiaire:
        qs = qs.filter(beneficiaire_nom__iexact=beneficiaire)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    paginator = Paginator(qs, HISTORY_PAGE_SIZE)
    page_obj = paginator.get_page(page)
    items = [_serialize_upload(upload) for upload in page_obj.object_list]
    meta = {
        "page": page_obj.number,
        "pages": paginator.num_pages,
        "total": paginator.count,
        "page_size": HISTORY_PAGE_SIZE,
    }
    return items, meta


def _save_upload_result(uploaded_file, validation: dict, existing_id=None):
    if not uploaded_file:
        return None
    errors = validation.get("errors", [])
    upload = None
    if existing_id:
        upload = BeneficiaireUpload.objects.filter(pk=existing_id).first()
    if upload:
        upload.beneficiaire_nom = validation.get("beneficiaire_nom", "") or "Non renseigne"
        upload.prestataire_nom = validation.get("prestataire_nom", "") or "Non renseigne"
        upload.est_rejete = bool(errors)
        upload.erreurs = "\n".join(errors)
        upload.erreurs_types = list(validation.get("error_types", []))
        upload.recap_stats = validation.get("recap_stats", {})
        upload.save()
        return upload
    return BeneficiaireUpload.objects.create(
        beneficiaire_nom=validation.get("beneficiaire_nom", "") or "Non renseigne",
        prestataire_nom=validation.get("prestataire_nom", "") or "Non renseigne",
        fichier=uploaded_file,
        est_rejete=bool(errors),
        erreurs="\n".join(errors),
        erreurs_types=list(validation.get("error_types", [])),
        recap_stats=validation.get("recap_stats", {}),
    )


def _history_payload(filters=None, page: int = 1):
    if filters is None:
        filters = {}
    return _build_history_payload(filters, page)


def _validate_dataframe(df):
    errors = []
    error_types = set()
    preview_rows = []
    error_rows = []

    col_map = {
        "numero": _find_column(df.columns, NUMERO_HEADERS),
        "nom_complet": _find_column(df.columns, NOM_HEADERS),
        "beneficiaire": _find_column(df.columns, BENEFICIAIRE_HEADERS),
        "genre": _find_column(df.columns, GENRE_HEADERS),
        "age": _find_column(df.columns, AGE_HEADERS),
        "fonction": _find_column(df.columns, FONCTION_HEADERS),
        "diplome": _find_column(df.columns, DIPLOME_HEADERS),
        "experience": _find_column(df.columns, EXPERIENCE_HEADERS),
        "ville_residence": _find_column(df.columns, VILLE_RESIDENCE_HEADERS),
        "prestataire": _find_column(df.columns, PRESTATAIRE_HEADERS),
        "formation_solicitee": _find_column(df.columns, FORMATION_SOL_HEADERS),
        "formation_dispensee": _find_column(df.columns, FORMATION_DISP_HEADERS),
        "fenetre": _find_column(df.columns, FENETRE_HEADERS),
        "ville_formation": _find_column(df.columns, VILLE_FORMATION_HEADERS),
        "arrondissement": _find_column(df.columns, ARRONDISSEMENT_HEADERS),
        "departement": _find_column(df.columns, DEPARTEMENT_HEADERS),
        "region": _find_column(df.columns, REGION_HEADERS),
        "lieu_formation": _find_column(df.columns, LIEU_FORMATION_HEADERS),
        "precision_lieu": _find_column(df.columns, PRECISION_LIEU_HEADERS),
        "gps_longitude": _find_column(df.columns, GPS_LONG_HEADERS),
        "gps_latitude": _find_column(df.columns, GPS_LAT_HEADERS),
        "telephone1": _find_column(df.columns, TELEPHONE1_HEADERS),
        "telephone2": _find_column(df.columns, TELEPHONE2_HEADERS),
        "cohorte": _find_column(df.columns, COHORTE_HEADERS),
        "telephone_formateur": _find_column(df.columns, TEL_FORMATEUR_HEADERS),
    }

    missing = []
    for key, label in EXPECTED_COLUMNS.items():
        if not col_map.get(key):
            missing.append(label)

    if missing:
        errors.append("Colonnes manquantes: " + ", ".join(missing))
        error_types.add("missing_columns")
        recap_stats = {
            "row_count": len(df),
            "telephone_anomalies": 0,
            "genre_anomalies": 0,
            "cohorte_anomalies": 0,
            "columns_with_issues": len(missing),
            "total_anomalies": 0,
            "missing_columns": missing,
        }
        return {
            "errors": errors,
            "error_types": error_types,
            "preview_rows": preview_rows,
            "error_rows": error_rows,
            "row_count": len(df),
            "beneficiaire_nom": "",
            "prestataire_nom": "",
            "recap_stats": recap_stats,
            "missing_columns": missing,
        }

    prestataire_nom, prestataire_err, prestataire_err_type = _extract_single_value(
        df[col_map["prestataire"]], "prestataire"
    )
    beneficiaire_nom, beneficiaire_err, beneficiaire_err_type = _extract_single_value(
        df[col_map["beneficiaire"]], "beneficiaire"
    )
    if prestataire_err:
        errors.append(prestataire_err)
        if prestataire_err_type:
            error_types.add(prestataire_err_type)
    if beneficiaire_err:
        errors.append(beneficiaire_err)
        if beneficiaire_err_type:
            error_types.add(beneficiaire_err_type)

    numero_series = df[col_map["numero"]]
    nom_series = df[col_map["nom_complet"]]
    beneficiaire_series = df[col_map["beneficiaire"]]
    genre_series = df[col_map["genre"]]
    age_series = df[col_map["age"]]
    fonction_series = df[col_map["fonction"]]
    diplome_series = df[col_map["diplome"]]
    experience_series = df[col_map["experience"]]
    ville_residence_series = df[col_map["ville_residence"]]
    prestataire_series = df[col_map["prestataire"]]
    formation_solicitee_series = df[col_map["formation_solicitee"]]
    formation_dispensee_series = df[col_map["formation_dispensee"]]
    fenetre_series = df[col_map["fenetre"]]
    ville_formation_series = df[col_map["ville_formation"]]
    arrondissement_series = df[col_map["arrondissement"]]
    departement_series = df[col_map["departement"]]
    region_series = df[col_map["region"]]
    lieu_formation_series = df[col_map["lieu_formation"]]
    precision_lieu_series = df[col_map["precision_lieu"]]
    gps_longitude_series = df[col_map["gps_longitude"]]
    gps_latitude_series = df[col_map["gps_latitude"]]
    telephone1_series = df[col_map["telephone1"]]
    telephone2_series = df[col_map["telephone2"]]
    cohorte_series = df[col_map["cohorte"]]
    telephone_formateur_series = df[col_map["telephone_formateur"]]

    numero_missing = _is_missing(numero_series)
    nom_missing = _is_missing(nom_series)
    beneficiaire_missing = _is_missing(beneficiaire_series)
    genre_missing = _is_missing(genre_series)
    age_missing = _is_missing(age_series)
    fonction_missing = _is_missing(fonction_series)
    diplome_missing = _is_missing(diplome_series)
    experience_missing = _is_missing(experience_series)
    ville_residence_missing = _is_missing(ville_residence_series)
    prestataire_missing = _is_missing(prestataire_series)
    formation_solicitee_missing = _is_missing(formation_solicitee_series)
    formation_dispensee_missing = _is_missing(formation_dispensee_series)
    fenetre_missing = _is_missing(fenetre_series)
    ville_formation_missing = _is_missing(ville_formation_series)
    arrondissement_missing = _is_missing(arrondissement_series)
    departement_missing = _is_missing(departement_series)
    region_missing = _is_missing(region_series)
    lieu_formation_missing = _is_missing(lieu_formation_series)
    precision_lieu_missing = _is_missing(precision_lieu_series)
    gps_longitude_missing = _is_missing(gps_longitude_series)
    gps_latitude_missing = _is_missing(gps_latitude_series)
    telephone1_missing = _is_missing(telephone1_series)
    telephone2_missing = _is_missing(telephone2_series)
    cohorte_missing = _is_missing(cohorte_series)
    telephone_formateur_missing = _is_missing(telephone_formateur_series)

    numero_num = pd.to_numeric(numero_series, errors="coerce")
    numero_invalid = ~numero_missing & (
        numero_num.isna() | (numero_num <= 0) | ((numero_num % 1) != 0)
    )

    age_num = pd.to_numeric(age_series, errors="coerce")
    age_invalid = ~age_missing & (age_num.isna() | (age_num <= 0) | ((age_num % 1) != 0))

    experience_num = pd.to_numeric(experience_series, errors="coerce")
    experience_invalid = ~experience_missing & (
        experience_num.isna() | (experience_num < 0) | ((experience_num % 1) != 0)
    )

    diplome_num = pd.to_numeric(diplome_series, errors="coerce")
    diplome_allowed = {-1, 0, 1, 2, 3, 4, 5}
    diplome_invalid = ~diplome_missing & (
        diplome_num.isna() | ~diplome_num.isin(diplome_allowed)
    )

    genre_norm = genre_series.apply(_normalize_gender)
    genre_invalid = ~genre_missing & ~genre_norm.isin({"H", "M", "F"})
    male_codes = set(genre_norm[genre_norm.isin({"H", "M"})].unique())
    genre_mixed = len(male_codes) > 1
    genre_mixed_mask = pd.Series([genre_mixed] * len(df), index=df.index)

    fonction_norm = fonction_series.fillna("").astype(str).str.strip().str.upper()
    fonction_allowed = {"D", "C", "E", "M", "B"}
    fonction_invalid = ~fonction_missing & ~fonction_norm.isin(fonction_allowed)

    gps_longitude_num = _to_float_series(gps_longitude_series)
    gps_longitude_invalid = ~gps_longitude_missing & (
        gps_longitude_num.isna() | (gps_longitude_num < -180) | (gps_longitude_num > 180)
    )

    gps_latitude_num = _to_float_series(gps_latitude_series)
    gps_latitude_invalid = ~gps_latitude_missing & (
        gps_latitude_num.isna() | (gps_latitude_num < -90) | (gps_latitude_num > 90)
    )

    telephone1_digits = (
        telephone1_series.fillna("").astype(str).str.replace(r"\D", "", regex=True)
    )
    telephone1_invalid = ~telephone1_missing & (telephone1_digits.str.len() != 9)

    telephone2_digits = (
        telephone2_series.fillna("").astype(str).str.replace(r"\D", "", regex=True)
    )
    telephone2_invalid = ~telephone2_missing & (telephone2_digits.str.len() != 9)

    telephone_formateur_digits = (
        telephone_formateur_series.fillna("").astype(str).str.replace(r"\D", "", regex=True)
    )
    telephone_formateur_invalid = ~telephone_formateur_missing & (
        telephone_formateur_digits.str.len() != 9
    )

    missing_required = (
        numero_missing
        | nom_missing
        | beneficiaire_missing
        | genre_missing
        | age_missing
        | fonction_missing
        | diplome_missing
        | experience_missing
        | ville_residence_missing
        | prestataire_missing
        | formation_solicitee_missing
        | formation_dispensee_missing
        | fenetre_missing
        | ville_formation_missing
        | arrondissement_missing
        | departement_missing
        | region_missing
        | lieu_formation_missing
        | precision_lieu_missing
        | gps_longitude_missing
        | gps_latitude_missing
        | telephone1_missing
        | cohorte_missing
        | telephone_formateur_missing
    )
    if missing_required.any():
        errors.append(f"Valeurs manquantes detectees: {int(missing_required.sum())} ligne(s).")
        error_types.add("missing_values")

    if numero_invalid.any():
        errors.append(
            "Numero invalide: %s ligne(s). Valeur attendue: entier > 0." % int(numero_invalid.sum())
        )
        error_types.add("numero_invalid")
    if age_invalid.any():
        errors.append("Age invalide: %s ligne(s). Valeur attendue: entier > 0." % int(age_invalid.sum()))
        error_types.add("age_invalid")
    if fonction_invalid.any():
        errors.append(
            "Fonction invalide: %s ligne(s). Valeurs attendues: D, C, E, M, B."
            % int(fonction_invalid.sum())
        )
        error_types.add("fonction_invalid")
    if diplome_invalid.any():
        errors.append(
            "Diplome invalide: %s ligne(s). Valeurs attendues: -1, 0, 1, 2, 3, 4, 5."
            % int(diplome_invalid.sum())
        )
        error_types.add("diplome_invalid")
    if experience_invalid.any():
        errors.append(
            "Experience invalide: %s ligne(s). Valeur attendue: entier >= 0."
            % int(experience_invalid.sum())
        )
        error_types.add("experience_invalid")
    if genre_invalid.any():
        errors.append(
            "Genre invalide: %s ligne(s). Valeurs attendues: H/F ou M/F." % int(genre_invalid.sum())
        )
        error_types.add("genre_invalid")
    if genre_mixed:
        errors.append("Genre mixte detecte: utilisez H/F ou M/F, pas les deux.")
        error_types.add("genre_mixed")
    if gps_longitude_invalid.any():
        errors.append(
            "Longitude invalide: %s ligne(s). Intervalle attendu: -180 a 180."
            % int(gps_longitude_invalid.sum())
        )
        error_types.add("longitude_invalid")
    if gps_latitude_invalid.any():
        errors.append(
            "Latitude invalide: %s ligne(s). Intervalle attendu: -90 a 90."
            % int(gps_latitude_invalid.sum())
        )
        error_types.add("latitude_invalid")
    if telephone1_invalid.any():
        errors.append(
            "Telephone apprenant 1 invalide: %s ligne(s). Format attendu: 9 chiffres."
            % int(telephone1_invalid.sum())
        )
        error_types.add("telephone1_invalid")
    if telephone2_invalid.any():
        errors.append(
            "Telephone apprenant 2 invalide: %s ligne(s). Format attendu: 9 chiffres."
            % int(telephone2_invalid.sum())
        )
        error_types.add("telephone2_invalid")
    if telephone_formateur_invalid.any():
        errors.append(
            "Telephone formateur invalide: %s ligne(s). Format attendu: 9 chiffres."
            % int(telephone_formateur_invalid.sum())
        )
        error_types.add("telephone_formateur_invalid")

    prestataire_multi = prestataire_err_type == "multiple_prestataire"
    beneficiaire_multi = beneficiaire_err_type == "multiple_beneficiaire"
    prestataire_multi_mask = pd.Series([prestataire_multi] * len(df), index=df.index)
    beneficiaire_multi_mask = pd.Series([beneficiaire_multi] * len(df), index=df.index)

    checks = {
        "numero": [(numero_missing, "Numero manquant"), (numero_invalid, "Numero invalide")],
        "nom_complet": [(nom_missing, "Nom et prenom manquant")],
        "beneficiaire": [
            (beneficiaire_missing, "Beneficiaire manquant"),
            (beneficiaire_multi_mask, "Beneficiaire multiple"),
        ],
        "genre": [
            (genre_missing, "Genre manquant"),
            (genre_invalid, "Genre invalide"),
            (genre_mixed_mask, "Genre mixte (H/F vs M/F)"),
        ],
        "age": [(age_missing, "Age manquant"), (age_invalid, "Age invalide")],
        "fonction": [
            (fonction_missing, "Fonction manquante"),
            (fonction_invalid, "Fonction invalide"),
        ],
        "diplome": [(diplome_missing, "Diplome manquant"), (diplome_invalid, "Diplome invalide")],
        "experience": [
            (experience_missing, "Experience manquante"),
            (experience_invalid, "Experience invalide"),
        ],
        "ville_residence": [(ville_residence_missing, "Ville residence manquante")],
        "prestataire": [
            (prestataire_missing, "Prestataire manquant"),
            (prestataire_multi_mask, "Prestataire multiple"),
        ],
        "formation_solicitee": [(formation_solicitee_missing, "Formation sollicitee manquante")],
        "formation_dispensee": [(formation_dispensee_missing, "Formation dispensee manquante")],
        "fenetre": [(fenetre_missing, "Fenetre manquante")],
        "ville_formation": [(ville_formation_missing, "Ville formation manquante")],
        "arrondissement": [(arrondissement_missing, "Arrondissement manquant")],
        "departement": [(departement_missing, "Departement manquant")],
        "region": [(region_missing, "Region manquante")],
        "lieu_formation": [(lieu_formation_missing, "Lieu formation manquant")],
        "precision_lieu": [(precision_lieu_missing, "Precision lieu manquante")],
        "gps_longitude": [
            (gps_longitude_missing, "Longitude manquante"),
            (gps_longitude_invalid, "Longitude invalide"),
        ],
        "gps_latitude": [
            (gps_latitude_missing, "Latitude manquante"),
            (gps_latitude_invalid, "Latitude invalide"),
        ],
        "telephone1": [
            (telephone1_missing, "Telephone apprenant 1 manquant"),
            (telephone1_invalid, "Telephone apprenant 1 invalide"),
        ],
        "telephone2": [(telephone2_invalid, "Telephone apprenant 2 invalide")],
        "cohorte": [(cohorte_missing, "Cohorte manquante")],
        "telephone_formateur": [
            (telephone_formateur_missing, "Telephone formateur manquant"),
            (telephone_formateur_invalid, "Telephone formateur invalide"),
        ],
    }

    error_masks = {}
    for key, items in checks.items():
        combined = pd.Series([False] * len(df), index=df.index)
        for mask, _ in items:
            combined = combined | mask
        error_masks[key] = combined

    row_numbers = {idx: i + 2 for i, idx in enumerate(df.index)}
    series_map = {
        "numero": numero_series,
        "nom_complet": nom_series,
        "beneficiaire": beneficiaire_series,
        "genre": genre_series,
        "age": age_series,
        "fonction": fonction_series,
        "diplome": diplome_series,
        "experience": experience_series,
        "ville_residence": ville_residence_series,
        "prestataire": prestataire_series,
        "formation_solicitee": formation_solicitee_series,
        "formation_dispensee": formation_dispensee_series,
        "fenetre": fenetre_series,
        "ville_formation": ville_formation_series,
        "arrondissement": arrondissement_series,
        "departement": departement_series,
        "region": region_series,
        "lieu_formation": lieu_formation_series,
        "precision_lieu": precision_lieu_series,
        "gps_longitude": gps_longitude_series,
        "gps_latitude": gps_latitude_series,
        "telephone1": telephone1_series,
        "telephone2": telephone2_series,
        "cohorte": cohorte_series,
        "telephone_formateur": telephone_formateur_series,
    }

    for key, items in checks.items():
        col_name = col_map.get(key, EXPECTED_COLUMNS.get(key, key))
        series = series_map[key]
        for mask, message in items:
            if not mask.any():
                continue
            for idx in mask[mask].index:
                error_rows.append(
                    {
                        "ligne": row_numbers.get(idx, ""),
                        "colonne": col_name,
                        "valeur": _safe_str(series.loc[idx]),
                        "erreur": message,
                    }
                )

    preview_limit = 20
    for idx in df.index[:preview_limit]:
        row_errors = []
        for key, items in checks.items():
            for mask, message in items:
                if bool(mask.loc[idx]):
                    row_errors.append(message)

        preview_rows.append(
            {
                "numero": _safe_str(numero_series.loc[idx]),
                "nom_complet": _safe_str(nom_series.loc[idx]),
                "beneficiaire": _safe_str(beneficiaire_series.loc[idx]),
                "genre": _safe_str(genre_series.loc[idx]),
                "age": _safe_str(age_series.loc[idx]),
                "fonction": _safe_str(fonction_series.loc[idx]),
                "diplome": _safe_str(diplome_series.loc[idx]),
                "experience": _safe_str(experience_series.loc[idx]),
                "ville_residence": _safe_str(ville_residence_series.loc[idx]),
                "prestataire": _safe_str(prestataire_series.loc[idx]),
                "formation_solicitee": _safe_str(formation_solicitee_series.loc[idx]),
                "formation_dispensee": _safe_str(formation_dispensee_series.loc[idx]),
                "fenetre": _safe_str(fenetre_series.loc[idx]),
                "ville_formation": _safe_str(ville_formation_series.loc[idx]),
                "arrondissement": _safe_str(arrondissement_series.loc[idx]),
                "departement": _safe_str(departement_series.loc[idx]),
                "region": _safe_str(region_series.loc[idx]),
                "lieu_formation": _safe_str(lieu_formation_series.loc[idx]),
                "precision_lieu": _safe_str(precision_lieu_series.loc[idx]),
                "gps_longitude": _safe_str(gps_longitude_series.loc[idx]),
                "gps_latitude": _safe_str(gps_latitude_series.loc[idx]),
                "telephone1": _safe_str(telephone1_series.loc[idx]),
                "telephone2": _safe_str(telephone2_series.loc[idx]),
                "cohorte": _safe_str(cohorte_series.loc[idx]),
                "telephone_formateur": _safe_str(telephone_formateur_series.loc[idx]),
                "numero_error": bool(error_masks["numero"].loc[idx]),
                "nom_complet_error": bool(error_masks["nom_complet"].loc[idx]),
                "beneficiaire_error": bool(error_masks["beneficiaire"].loc[idx]),
                "genre_error": bool(error_masks["genre"].loc[idx]),
                "age_error": bool(error_masks["age"].loc[idx]),
                "fonction_error": bool(error_masks["fonction"].loc[idx]),
                "diplome_error": bool(error_masks["diplome"].loc[idx]),
                "experience_error": bool(error_masks["experience"].loc[idx]),
                "ville_residence_error": bool(error_masks["ville_residence"].loc[idx]),
                "prestataire_error": bool(error_masks["prestataire"].loc[idx]),
                "formation_solicitee_error": bool(error_masks["formation_solicitee"].loc[idx]),
                "formation_dispensee_error": bool(error_masks["formation_dispensee"].loc[idx]),
                "fenetre_error": bool(error_masks["fenetre"].loc[idx]),
                "ville_formation_error": bool(error_masks["ville_formation"].loc[idx]),
                "arrondissement_error": bool(error_masks["arrondissement"].loc[idx]),
                "departement_error": bool(error_masks["departement"].loc[idx]),
                "region_error": bool(error_masks["region"].loc[idx]),
                "lieu_formation_error": bool(error_masks["lieu_formation"].loc[idx]),
                "precision_lieu_error": bool(error_masks["precision_lieu"].loc[idx]),
                "gps_longitude_error": bool(error_masks["gps_longitude"].loc[idx]),
                "gps_latitude_error": bool(error_masks["gps_latitude"].loc[idx]),
                "telephone1_error": bool(error_masks["telephone1"].loc[idx]),
                "telephone2_error": bool(error_masks["telephone2"].loc[idx]),
                "cohorte_error": bool(error_masks["cohorte"].loc[idx]),
                "telephone_formateur_error": bool(error_masks["telephone_formateur"].loc[idx]),
                "statut": "OK" if not row_errors else "Erreur",
                "erreurs": ", ".join(row_errors),
            }
        )

    columns_with_issues = 0
    for key, items in checks.items():
        if any(mask.any() for mask, _ in items):
            columns_with_issues += 1

    telephone_mask = (
        telephone1_missing
        | telephone1_invalid
        | telephone2_invalid
        | telephone_formateur_missing
        | telephone_formateur_invalid
    )
    genre_mask = genre_missing | genre_invalid | genre_mixed_mask
    cohorte_mask = cohorte_missing

    recap_stats = {
        "row_count": len(df),
        "telephone_anomalies": int(telephone_mask.sum()),
        "genre_anomalies": int(genre_mask.sum()),
        "cohorte_anomalies": int(cohorte_mask.sum()),
        "columns_with_issues": int(columns_with_issues),
        "total_anomalies": int(len(error_rows)),
        "missing_columns": [],
    }

    return {
        "errors": errors,
        "error_types": error_types,
        "preview_rows": preview_rows,
        "error_rows": error_rows,
        "row_count": len(df),
        "beneficiaire_nom": beneficiaire_nom,
        "prestataire_nom": prestataire_nom,
        "recap_stats": recap_stats,
        "missing_columns": [],
    }

def beneficiaire_portal(request):
    history_filters = {
        "prestataire": (request.GET.get("prestataire") or "").strip(),
        "beneficiaire": (request.GET.get("beneficiaire") or "").strip(),
        "date_from": (request.GET.get("date_from") or "").strip(),
        "date_to": (request.GET.get("date_to") or "").strip(),
    }
    try:
        history_page = int(request.GET.get("page", "1"))
    except ValueError:
        history_page = 1
    history_items, history_meta = _history_payload(history_filters, history_page)
    history_choices = _get_history_choices()

    context = {
        "errors": [],
        "error_types": [],
        "preview_rows": [],
        "validation_ok": True,
        "validation_done": True,
        "row_count": 0,
        "upload_saved": False,
        "beneficiaire_nom": "",
        "prestataire_nom": "",
        "success_message": "",
        "errors_csv_url": "",
        "errors_txt_url": "",
        "errors_xlsx_url": "",
        "history_items": history_items,
        "history_meta": history_meta,
        "history_filters": history_filters,
        "history_choices": history_choices,
        "recap_global_url": _get_recap_global_url(),
        "validation_id": "",
    }

    if request.method == "POST":
        is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
        action = request.POST.get("action", "submit")
        existing_id = request.POST.get("validation_id") if action == "submit" else None
        uploaded_file = request.FILES.get("dataset")
        if not uploaded_file:
            context["errors"].append("Veuillez charger un fichier CSV ou Excel.")
            context["validation_done"] = True

        if uploaded_file and not context["errors"]:
            df, load_error = _load_dataframe(uploaded_file)
            if load_error:
                context["errors"].append(load_error)
                context["error_types"] = ["invalid_file"]
            else:
                validation = _validate_dataframe(df)
                context["errors"] = validation["errors"]
                validation["error_types"] = sorted(validation["error_types"])
                context["error_types"] = validation["error_types"]
                context["preview_rows"] = validation["preview_rows"]
                context["row_count"] = validation["row_count"]
                context["beneficiaire_nom"] = validation.get("beneficiaire_nom", "")
                context["prestataire_nom"] = validation.get("prestataire_nom", "")
                exports = _build_error_exports(
                    validation.get("error_rows", []), context["beneficiaire_nom"]
                )
                context["errors_csv_url"] = exports.get("csv", "")
                context["errors_txt_url"] = exports.get("txt", "")
                context["errors_xlsx_url"] = exports.get("xlsx", "")
                uploaded_file.seek(0)
                upload = _save_upload_result(uploaded_file, validation, existing_id=existing_id)
                if upload:
                    context["upload_saved"] = True
                    context["validation_id"] = upload.id
                    history_items, history_meta = _history_payload(history_filters, history_page)
                    context["history_items"] = history_items
                    context["history_meta"] = history_meta
                    context["history_choices"] = _get_history_choices()
                    recap_rows = _build_recap_rows(BeneficiaireUpload.objects.all())
                    context["recap_global_url"] = _save_recap_excel(recap_rows, RECAP_GLOBAL_PATH)
            context["validation_done"] = True
            context["validation_ok"] = not context["errors"]

            if context["validation_ok"]:
                context["success_message"] = (
                    "Soumission enregistree. Merci."
                    if action == "submit"
                    else "Verification terminee. Aucune erreur critique detectee."
                )

        if is_ajax:
            return JsonResponse(
                {
                    "errors": context["errors"],
                    "error_types": context["error_types"],
                    "preview_rows": context["preview_rows"],
                    "row_count": context["row_count"],
                    "beneficiaire_nom": context["beneficiaire_nom"],
                    "prestataire_nom": context["prestataire_nom"],
                    "validation_ok": context["validation_ok"],
                    "validation_done": context["validation_done"],
                    "upload_saved": context["upload_saved"],
                    "success_message": context["success_message"],
                    "errors_csv_url": context["errors_csv_url"],
                    "errors_txt_url": context["errors_txt_url"],
                    "errors_xlsx_url": context["errors_xlsx_url"],
                    "history": context["history_items"],
                    "history_meta": context.get("history_meta", {}),
                    "history_choices": context.get("history_choices", {}),
                    "recap_global_url": context["recap_global_url"],
                    "validation_id": context["validation_id"],
                }
            )

    return render(request, "beneficiaire/index.html", context)


def beneficiaire_history(request):
    if request.method != "GET":
        return JsonResponse({"errors": ["Methode non autorisee."]}, status=405)
    filters = {
        "prestataire": (request.GET.get("prestataire") or "").strip(),
        "beneficiaire": (request.GET.get("beneficiaire") or "").strip(),
        "date_from": (request.GET.get("date_from") or "").strip(),
        "date_to": (request.GET.get("date_to") or "").strip(),
    }
    try:
        page = int(request.GET.get("page", "1"))
    except ValueError:
        page = 1
    items, meta = _history_payload(filters, page)
    return JsonResponse({"history": items, "meta": meta})


def beneficiaire_recap(request):
    if request.method != "POST":
        return JsonResponse({"errors": ["Methode non autorisee."]}, status=405)
    ids = request.POST.getlist("history_ids")
    if not ids:
        return JsonResponse({"errors": ["Selectionnez au moins un fichier."]}, status=400)
    uploads = BeneficiaireUpload.objects.filter(id__in=ids)
    if not uploads.exists():
        return JsonResponse({"errors": ["Aucun fichier valide selectionne."]}, status=400)

    rows = _build_recap_rows(uploads.order_by("-created_at"))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"beneficiaires/recaps/recap_selection_{timestamp}_{uuid.uuid4().hex[:8]}.xlsx"
    recap_url = _save_recap_excel(rows, filename)
    return JsonResponse({"recap_xlsx_url": recap_url})

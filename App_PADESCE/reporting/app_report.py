"""
Module de rapport d'application pour App_PADESCE.

Fournit les fonctions de construction, d'export et d'envoi du rapport
journalier de l'application.
"""

import io
import logging
import re
from datetime import date, datetime, time, timedelta
from email.mime.image import MIMEImage
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage, get_connection
from django.db.models import Count, Max, Min, Q
from django.http import QueryDict
from django.utils import timezone

from App_PADESCE.appels.models import Appel, AppelFormateur
from App_PADESCE.core.analysis_rules import analysis_threshold_target
from App_PADESCE.core.models import UserActivity
from App_PADESCE.formations.models import Classe
from App_PADESCE.reporting.network_excel import build_padesce_source_index, normalize_network_lookup

logger = logging.getLogger(__name__)
CONSOLE_EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
SMTP_EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# ---------------------------------------------------------------------------
# Helpers — imports optionnels (python-docx)
# ---------------------------------------------------------------------------
try:
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor

    HAS_DOCX = True
except ImportError:  # pragma: no cover
    HAS_DOCX = False


# ---------------------------------------------------------------------------
# Utilitaires dates / config
# ---------------------------------------------------------------------------


def parse_report_dates(start_str: str | None, end_str: str | None) -> tuple[date, date]:
    today = timezone.localdate()
    try:
        start = date.fromisoformat(str(start_str).strip()) if start_str else today
    except ValueError:
        start = today
    try:
        end = date.fromisoformat(str(end_str).strip()) if end_str else today
    except ValueError:
        end = today
    if end < start:
        end = start
    return start, end


def get_report_email_recipients() -> list[str]:
    raw = (getattr(settings, "REPORT_EMAIL_TO", "") or "").strip()
    if not raw:
        raw = settings.__dict__.get("REPORT_EMAIL_TO") or ""
    return [addr.strip() for addr in raw.split(",") if addr.strip()]


def _build_report_email_connection() -> tuple[object | None, str | None]:
    backend = str(getattr(settings, "EMAIL_BACKEND", "") or "").strip()
    if backend != CONSOLE_EMAIL_BACKEND:
        return None, None

    missing = [
        field_name
        for field_name in (
            "EMAIL_HOST",
            "EMAIL_HOST_USER",
            "EMAIL_HOST_PASSWORD",
            "DEFAULT_FROM_EMAIL",
        )
        if not getattr(settings, field_name, "")
    ]
    if missing:
        return (
            None,
            "EMAIL_BACKEND est en mode console et la configuration SMTP est incomplète: "
            + ", ".join(missing),
        )

    logger.info("Envoi rapport: backend console détecté, bascule forcée vers SMTP.")
    return (
        get_connection(
            backend=SMTP_EMAIL_BACKEND,
            host=settings.EMAIL_HOST,
            port=getattr(settings, "EMAIL_PORT", None),
            username=settings.EMAIL_HOST_USER,
            password=settings.EMAIL_HOST_PASSWORD,
            use_tls=getattr(settings, "EMAIL_USE_TLS", False),
            use_ssl=getattr(settings, "EMAIL_USE_SSL", False),
            timeout=getattr(settings, "EMAIL_TIMEOUT", None),
        ),
        None,
    )


# ---------------------------------------------------------------------------
# Section 3 — Moteur principal
# ---------------------------------------------------------------------------


def build_application_report(
    start_date: date, end_date: date, selected_class_code: str | None = None
) -> dict:
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(start_date, time.min), tz)
    end_dt = timezone.make_aware(datetime.combine(end_date, time.max), tz)
    now = timezone.localtime()
    selected_class_code = (selected_class_code or "").strip()
    selected_class = _get_selected_class(selected_class_code)

    user_model = get_user_model()
    active_period_users = UserActivity.objects.filter(
        last_seen__gte=start_dt, last_seen__lte=end_dt
    )
    active_24h_users = UserActivity.objects.filter(last_seen__gte=now - timedelta(hours=24))

    padesce_qs = Appel.objects.filter(
        is_active=True, updated_at__gte=start_dt, updated_at__lte=end_dt
    )
    formateur_qs = AppelFormateur.objects.filter(
        is_active=True, updated_at__gte=start_dt, updated_at__lte=end_dt
    )

    call_sources = [
        _build_call_source_summary("PADESCE", padesce_qs),
        _build_call_source_summary("Formateurs", formateur_qs),
    ]
    call_totals = {
        "total": sum(source["total"] for source in call_sources),
        "completed": sum(source["completed"] for source in call_sources),
        "pending": sum(source["pending"] for source in call_sources),
        "in_progress": sum(source["in_progress"] for source in call_sources),
        "callbacks": sum(source["callbacks"] for source in call_sources),
        "with_audio": sum(source["with_audio"] for source in call_sources),
    }
    processed_total = sum(source["processed"] for source in call_sources)
    call_totals["processed"] = processed_total
    call_totals["completion_rate"] = (
        round((call_totals["completed"] / processed_total) * 100, 2) if processed_total else 0.0
    )

    hourly_rows = _build_hourly_rows(
        _hourly_completed_counts(padesce_qs),
        _hourly_completed_counts(formateur_qs),
    )
    best_hour = (
        max(hourly_rows, key=lambda row: (row["completed"], row["total"], -row["hour"]))
        if hourly_rows
        else None
    )

    bug_summary = _build_bug_summary(start_dt, end_dt)
    anomaly_summary = _build_anomaly_summary(
        selected_class, selected_class_code=selected_class_code
    )
    analysis_summary = _build_analysis_summary(padesce_qs)
    formateurs_summary = _build_formateurs_satisfaction_summary(start_dt, end_dt)
    user_call_rows = _build_user_call_rows(padesce_qs, formateur_qs)

    recipients = get_report_email_recipients()
    mail_status = {
        "configured_recipients": recipients,
        "missing_configuration": not bool(recipients),
        "smtp_ready": bool(getattr(settings, "EMAIL_HOST", ""))
        and bool(getattr(settings, "DEFAULT_FROM_EMAIL", "")),
    }

    return {
        "generated_at": now,
        "start_date": start_date,
        "end_date": end_date,
        "start_dt": start_dt,
        "end_dt": end_dt,
        "period_days": (end_date - start_date).days + 1,
        "users": {
            "total": user_model.objects.count(),
            "active": user_model.objects.filter(is_active=True).count(),
            "staff": user_model.objects.filter(is_staff=True).count(),
            "superusers": user_model.objects.filter(is_superuser=True).count(),
            "seen_24h": active_24h_users.count(),
            "seen_period": active_period_users.count(),
            "called_today": len(user_call_rows),
        },
        "calls": call_totals,
        "call_sources": call_sources,
        "hourly_rows": hourly_rows,
        "best_hour": best_hour,
        "bugs": bug_summary,
        "anomalies": anomaly_summary,
        "analysis": analysis_summary,
        "formateurs_summary": formateurs_summary,
        "user_call_rows": user_call_rows,
        "mail_status": mail_status,
        "selected_class_code": selected_class.code if selected_class else selected_class_code,
    }


# ---------------------------------------------------------------------------
# Section 4 — Export Word
# ---------------------------------------------------------------------------


def export_application_report_word(report: dict) -> bytes:
    if not HAS_DOCX:
        raise ImportError("python-docx est requis pour l'export Word.")

    document = Document()
    _configure_report_document(document)

    header_table = document.add_table(rows=1, cols=2)
    header_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    header_table.autofit = False
    logo_cell, text_cell = header_table.rows[0].cells
    _clear_cell_border(logo_cell)
    _clear_cell_border(text_cell)
    logo_path = _get_report_logo_path()
    if logo_path and logo_path.exists():
        logo_paragraph = logo_cell.paragraphs[0]
        logo_paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        logo_paragraph.add_run().add_picture(str(logo_path), width=Inches(1.35))

    title = text_cell.paragraphs[0]
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT
    title_run = title.add_run("RAPPORT JOURNALIER")
    title_run.bold = True
    title_run.font.size = Pt(18)
    title_run.font.color.rgb = RGBColor(76, 29, 149)

    subtitle = text_cell.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.LEFT
    subtitle_run = subtitle.add_run(
        f"Periode: du {report['start_date'].strftime('%d/%m/%Y')} au {report['end_date'].strftime('%d/%m/%Y')}"
    )
    subtitle_run.font.size = Pt(11)

    meta = text_cell.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.LEFT
    meta.add_run(
        f"Date de generation: {timezone.localtime(report['generated_at']).strftime('%d/%m/%Y a %H:%M')}"
    )

    best_hour_label = report["best_hour"]["label"] if report["best_hour"] else "Aucune donnee"
    best_hour_value = report["best_hour"]["completed"] if report["best_hour"] else 0

    document.add_paragraph("")
    _add_heading(document, "1. Resume")
    _add_metric_table(
        document,
        [
            ("Utilisateurs ayant appele", report["users"]["called_today"]),
            ("Appels termines", report["calls"]["completed"]),
            ("Heure la plus performante", f"{best_hour_label} ({best_hour_value} appels termines)"),
            ("Classes analysees", report["analysis"]["classes_count"]),
            ("Prestations analysees", report["analysis"]["prestations_count"]),
            ("Prestataires analyses", report["analysis"]["prestataires_count"]),
            ("Beneficiaires analyses", report["analysis"]["beneficiaires_count"]),
        ],
    )

    _add_heading(document, "2. Situation des appels")
    calls_table = document.add_table(rows=1, cols=5)
    calls_table.style = "Table Grid"
    calls_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers = ["Source", "Total", "Effectues", "Termines", "Audios"]
    for idx, label in enumerate(headers):
        _write_header_cell(calls_table.rows[0].cells[idx], label)
    for source in report["call_sources"]:
        row = calls_table.add_row().cells
        row[0].text = source["label"]
        row[1].text = str(source["total"])
        row[2].text = str(source["processed"])
        row[3].text = str(source["completed"])
        row[4].text = str(source["with_audio"])

    _add_heading(document, "3. Activite par utilisateur")
    users_table = document.add_table(rows=1, cols=6)
    users_table.style = "Table Grid"
    users_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for idx, label in enumerate(
        [
            "Utilisateur",
            "Appels effectues",
            "Appels termines",
            "Temps estime",
            "Premiere activite",
            "Derniere activite",
        ]
    ):
        _write_header_cell(users_table.rows[0].cells[idx], label)
    for item in report["user_call_rows"]:
        row = users_table.add_row().cells
        row[0].text = item["username"]
        row[1].text = str(item["calls_made"])
        row[2].text = str(item["completed_calls"])
        row[3].text = item["time_spent_label"]
        row[4].text = item["first_activity_label"]
        row[5].text = item["last_activity_label"]

    _add_heading(document, "4. Repartition horaire")
    hourly_table = document.add_table(rows=1, cols=3)
    hourly_table.style = "Table Grid"
    hourly_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for idx, label in enumerate(["Heure", "Total", "Termines"]):
        _write_header_cell(hourly_table.rows[0].cells[idx], label)
    top_hour_rows = sorted(
        report["hourly_rows"], key=lambda row: (-row["completed"], -row["total"], row["hour"])
    )[:8]
    for row_data in top_hour_rows:
        row = hourly_table.add_row().cells
        row[0].text = row_data["label"]
        row[1].text = str(row_data["total"])
        row[2].text = str(row_data["completed"])

    _add_heading(document, "5. Analyse satisfaction – Apprenants")
    _add_metric_table(
        document,
        [
            ("Classes analysees", report["analysis"]["classes_count"]),
            ("Prestations analysees", report["analysis"]["prestations_count"]),
            ("Prestataires analyses", report["analysis"]["prestataires_count"]),
            ("Beneficiaires analyses", report["analysis"]["beneficiaires_count"]),
        ],
    )

    fs = report.get("formateurs_summary", {})
    if fs:
        _add_heading(document, "6. Analyse satisfaction – Formateurs")
        _add_metric_table(
            document,
            [
                ("Appels formateurs termines (periode)", fs.get("total_termines", 0)),
                ("Avec scores Q1-Q3", fs.get("with_scores", 0)),
                ("Moy. Q1 – Prerequis apprenants", fs.get("avg_q1", 0)),
                ("Moy. Q2 – Interaction apprenants", fs.get("avg_q2", 0)),
                ("Moy. Q3 – Competences acquises", fs.get("avg_q3", 0)),
            ],
        )
        if fs.get("by_prestataire"):
            form_table = document.add_table(rows=1, cols=5)
            form_table.style = "Table Grid"
            form_table.alignment = WD_TABLE_ALIGNMENT.CENTER
            for idx, label in enumerate(["Prestataire", "Nb appels", "Q1", "Q2", "Q3"]):
                _write_header_cell(form_table.rows[0].cells[idx], label)
            for row_data in fs["by_prestataire"]:
                row = form_table.add_row().cells
                row[0].text = row_data["prestataire"]
                row[1].text = str(row_data["nb"])
                row[2].text = str(row_data["avg_q1"])
                row[3].text = str(row_data["avg_q2"])
                row[4].text = str(row_data["avg_q3"])

    _add_heading(document, "7. Incidents")
    _add_metric_table(
        document,
        [
            ("Bugs signales", report["bugs"]["alarms_total"]),
            ("Bugs resolus", report["bugs"]["alarms_resolved"]),
            ("Bugs ouverts", report["bugs"]["alarms_open"]),
            ("Erreurs logs", report["bugs"]["log_errors"]),
            ("Erreurs critiques", report["bugs"]["log_critical"]),
        ],
    )
    if report["bugs"]["recent_alarms"]:
        incidents_table = document.add_table(rows=1, cols=4)
        incidents_table.style = "Table Grid"
        incidents_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for idx, label in enumerate(["Incident", "Module", "Date", "Etat"]):
            _write_header_cell(incidents_table.rows[0].cells[idx], label)
        for alarm in report["bugs"]["recent_alarms"]:
            row = incidents_table.add_row().cells
            row[0].text = alarm["title"]
            row[1].text = alarm["module"]
            row[2].text = alarm["created_at"]
            row[3].text = alarm["status"]

    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


# ---------------------------------------------------------------------------
# Section 5 — Envoi mail + HTML
# ---------------------------------------------------------------------------


def send_report_by_email(report: dict) -> dict:
    recipients = get_report_email_recipients()
    if not recipients:
        return {"ok": False, "detail": "Aucun destinataire email configure"}
    if not getattr(settings, "EMAIL_HOST", ""):
        return {"ok": False, "detail": "EMAIL_HOST non configure"}
    if not getattr(settings, "DEFAULT_FROM_EMAIL", ""):
        return {"ok": False, "detail": "DEFAULT_FROM_EMAIL non configure"}
    connection, connection_error = _build_report_email_connection()
    if connection_error:
        return {"ok": False, "detail": connection_error}

    subject = (
        f"Rapport application NAUMUR CALL APP - {report['start_date']} au {report['end_date']}"
    )
    body = build_report_email_html(report)
    message = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
        connection=connection,
    )
    message.content_subtype = "html"
    logo_path = _get_report_logo_path()
    if logo_path and logo_path.exists():
        with logo_path.open("rb") as handle:
            logo_image = MIMEImage(handle.read())
            logo_image.add_header("Content-ID", "<logo_cga_naumur>")
            logo_image.add_header("Content-Disposition", "inline", filename=logo_path.name)
            message.attach(logo_image)
    if HAS_DOCX:
        try:
            word_payload = export_application_report_word(report)
            message.attach(
                f"rapport_application_{report['start_date']}_{report['end_date']}.docx",
                word_payload,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        except Exception:
            pass
    try:
        message.send(fail_silently=False)
    except Exception as exc:
        logger.exception("Echec d'envoi du rapport journalier par email.")
        return {"ok": False, "detail": f"Echec de l'envoi SMTP: {exc}"}
    return {"ok": True, "detail": f"Mail envoye a {len(recipients)} destinataire(s)"}


def build_report_text(report: dict) -> str:
    best_hour = report.get("best_hour")
    best_hour_text = (
        f"Heure la plus performante: {best_hour['label']} ({best_hour['completed']} appels termines)"
        if best_hour
        else "Heure la plus performante: aucune donnee"
    )
    lines = [
        "Rapport quotidien NAUMUR CALL APP",
        f"Periode: {report['start_date']} au {report['end_date']}",
        "",
        "Suivi journee",
        f"- Utilisateurs ayant appele: {report['users']['called_today']}",
        f"- Termines: {report['calls']['completed']}",
        best_hour_text,
        "",
        "Analyse satisfaction",
        f"- Classes analysees: {report['analysis']['classes_count']}",
        f"- Prestations analysees: {report['analysis']['prestations_count']}",
        f"- Prestataires analyses: {report['analysis']['prestataires_count']}",
        f"- Beneficiaires analyses: {report['analysis']['beneficiaires_count']}",
        "",
        "Incidents",
        f"- Bugs signales: {report['bugs']['alarms_total']}",
        f"- Bugs non resolus: {report['bugs']['alarms_open']}",
        f"- Erreurs logs: {report['bugs']['log_errors']}",
        f"- Critiques logs: {report['bugs']['log_critical']}",
    ]
    if report["user_call_rows"]:
        lines.extend(["", "Temps estime par utilisateur"])
        for row in report["user_call_rows"]:
            lines.append(
                f"- {row['username']}: {row['calls_made']} appels, "
                f"{row['completed_calls']} termines, temps estime {row['time_spent_label']}"
            )
    return "\n".join(lines)


def build_report_email_html(report: dict) -> str:
    best_hour_label = report["best_hour"]["label"] if report["best_hour"] else "Aucune donnee"
    best_hour_value = report["best_hour"]["completed"] if report["best_hour"] else 0
    user_rows = "".join(
        [
            (
                "<tr>"
                f"<td style='padding:10px;border-bottom:1px solid #eee7fb;'>{row['username']}</td>"
                f"<td style='padding:10px;border-bottom:1px solid #eee7fb;text-align:center;'>{row['calls_made']}</td>"
                f"<td style='padding:10px;border-bottom:1px solid #eee7fb;text-align:center;'>{row['completed_calls']}</td>"
                f"<td style='padding:10px;border-bottom:1px solid #eee7fb;text-align:center;'>{row['time_spent_label']}</td>"
                "</tr>"
            )
            for row in report["user_call_rows"][:8]
        ]
    ) or (
        "<tr><td colspan='4' style='padding:12px;text-align:center;color:#6b7280;'>"
        "Aucune activite utilisateur sur la periode.</td></tr>"
    )

    return f"""
<div style="margin:0;padding:24px;background:#f4f4f6;font-family:Calibri,Arial,sans-serif;color:#222222;">
  <div style="max-width:880px;margin:0 auto;background:#ffffff;border:1px solid #d9d9e3;">
    <div style="padding:24px 28px;border-bottom:3px solid #4c1d95;background:#ffffff;">
      <table role="presentation" style="width:100%;border-collapse:collapse;">
        <tr>
          <td style="width:120px;vertical-align:top;text-align:left;padding-right:16px;">
            <img src="cid:logo_cga_naumur" alt="Logo CGA Naumur" style="max-width:88px;height:auto;display:block;">
          </td>
          <td style="vertical-align:top;">
            <div style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#4c1d95;font-weight:700;">Rapport journalier</div>
            <h1 style="margin:8px 0 6px;font-size:24px;line-height:1.25;color:#1f1630;">Synthese d'activite</h1>
            <p style="margin:0;font-size:14px;color:#555555;">Periode du {report['start_date'].strftime('%d/%m/%Y')} au {report['end_date'].strftime('%d/%m/%Y')}</p>
            <p style="margin:4px 0 0;font-size:13px;color:#666666;">Genere le {timezone.localtime(report['generated_at']).strftime('%d/%m/%Y a %H:%M')}</p>
          </td>
        </tr>
      </table>
    </div>

    <div style="padding:24px 28px;">
      <div style="border:1px solid #dfe1ea;padding:16px 18px;margin-bottom:18px;">
        <div style="font-size:16px;font-weight:700;color:#4c1d95;margin-bottom:10px;">1. Resume</div>
        <table role="presentation" style="width:100%;border-collapse:collapse;">
          <tr>
            <td style="padding:8px 0;border-bottom:1px solid #ececf2;">Utilisateurs ayant appele</td>
            <td style="padding:8px 0;border-bottom:1px solid #ececf2;text-align:right;font-weight:700;">{report['users']['called_today']}</td>
          </tr>
          <tr>
            <td style="padding:8px 0;border-bottom:1px solid #ececf2;">Appels termines</td>
            <td style="padding:8px 0;border-bottom:1px solid #ececf2;text-align:right;font-weight:700;">{report['calls']['completed']}</td>
          </tr>
          <tr>
            <td style="padding:8px 0;border-bottom:1px solid #ececf2;">Heure la plus performante</td>
            <td style="padding:8px 0;border-bottom:1px solid #ececf2;text-align:right;font-weight:700;">{best_hour_label}</td>
          </tr>
          <tr>
            <td style="padding:8px 0;">Appels termines sur cette tranche</td>
            <td style="padding:8px 0;text-align:right;font-weight:700;">{best_hour_value}</td>
          </tr>
        </table>
      </div>

      <div style="border:1px solid #dfe1ea;padding:16px 18px;margin-bottom:18px;">
        <div style="font-size:16px;font-weight:700;color:#4c1d95;margin-bottom:10px;">2. Analyse satisfaction – Apprenants</div>
        <table role="presentation" style="width:100%;border-collapse:collapse;">
          <tr><td style="padding:8px 0;border-bottom:1px solid #ececf2;">Classes analysees</td><td style="padding:8px 0;border-bottom:1px solid #ececf2;text-align:right;font-weight:700;">{report['analysis']['classes_count']}</td></tr>
          <tr><td style="padding:8px 0;border-bottom:1px solid #ececf2;">Prestations analysees</td><td style="padding:8px 0;border-bottom:1px solid #ececf2;text-align:right;font-weight:700;">{report['analysis']['prestations_count']}</td></tr>
          <tr><td style="padding:8px 0;border-bottom:1px solid #ececf2;">Prestataires analyses</td><td style="padding:8px 0;border-bottom:1px solid #ececf2;text-align:right;font-weight:700;">{report['analysis']['prestataires_count']}</td></tr>
          <tr><td style="padding:8px 0;">Beneficiaires analyses</td><td style="padding:8px 0;text-align:right;font-weight:700;">{report['analysis']['beneficiaires_count']}</td></tr>
        </table>
      </div>

      <div style="border:1px solid #dfe1ea;padding:16px 18px;margin-bottom:18px;">
        <div style="font-size:16px;font-weight:700;color:#4c1d95;margin-bottom:10px;">3. Analyse satisfaction – Formateurs</div>
        <table role="presentation" style="width:100%;border-collapse:collapse;">
          <tr><td style="padding:8px 0;border-bottom:1px solid #ececf2;">Appels formateurs termines (periode)</td><td style="padding:8px 0;border-bottom:1px solid #ececf2;text-align:right;font-weight:700;">{report['formateurs_summary']['total_termines']}</td></tr>
          <tr><td style="padding:8px 0;border-bottom:1px solid #ececf2;">Avec scores Q1-Q3</td><td style="padding:8px 0;border-bottom:1px solid #ececf2;text-align:right;font-weight:700;">{report['formateurs_summary']['with_scores']}</td></tr>
          <tr><td style="padding:8px 0;border-bottom:1px solid #ececf2;">Moy. Q1 – Prerequis apprenants</td><td style="padding:8px 0;border-bottom:1px solid #ececf2;text-align:right;font-weight:700;">{report['formateurs_summary']['avg_q1']}/5</td></tr>
          <tr><td style="padding:8px 0;border-bottom:1px solid #ececf2;">Moy. Q2 – Interaction apprenants</td><td style="padding:8px 0;border-bottom:1px solid #ececf2;text-align:right;font-weight:700;">{report['formateurs_summary']['avg_q2']}/5</td></tr>
          <tr><td style="padding:8px 0;">Moy. Q3 – Competences acquises</td><td style="padding:8px 0;text-align:right;font-weight:700;">{report['formateurs_summary']['avg_q3']}/5</td></tr>
        </table>
      </div>

      <div style="border:1px solid #dfe1ea;padding:16px 18px;margin-bottom:18px;">
        <div style="font-size:16px;font-weight:700;color:#4c1d95;margin-bottom:10px;">3. Activite par utilisateur</div>
        <table style="width:100%;border-collapse:collapse;border:1px solid #e3e4eb;">
          <thead>
            <tr style="background:#f5f5fa;color:#3b2a59;">
              <th style="padding:10px;text-align:left;">Utilisateur</th>
              <th style="padding:10px;text-align:center;">Appels effectues</th>
              <th style="padding:10px;text-align:center;">Appels termines</th>
              <th style="padding:10px;text-align:center;">Temps estime</th>
            </tr>
          </thead>
          <tbody>{user_rows}</tbody>
        </table>
      </div>

      <div style="border:1px solid #dfe1ea;padding:16px 18px;">
        <div style="font-size:16px;font-weight:700;color:#4c1d95;margin-bottom:10px;">4. Observation</div>
        <p style="margin:0;font-size:14px;line-height:1.7;color:#333333;">
          La tranche horaire la plus performante est <strong>{best_hour_label}</strong>, avec <strong>{best_hour_value} appels termines</strong>.
          Le document Word joint reprend le rapport sous une forme plus complete pour impression ou partage.
        </p>
      </div>
    </div>
  </div>
</div>
""".strip()


# ---------------------------------------------------------------------------
# Section 6 — Helpers de calcul
# ---------------------------------------------------------------------------


def _source_class_apprenant_counts(source_bundle: dict | None) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in (source_bundle or {}).get("records", {}).values():
        classe_code = str(record.get("classe_id") or "").strip()
        if not classe_code:
            continue
        counts[classe_code] = counts.get(classe_code, 0) + 1
    return counts


def _qualified_prestation_codes(source_bundle: dict | None) -> set[str]:
    if not source_bundle:
        return set()
    source_classes = list((source_bundle.get("classes") or {}).values())
    if not source_classes:
        return set()

    terminated_by_class = {
        normalize_network_lookup(code): count
        for code, count in (
            Appel.objects.filter(is_active=True, status="termine")
            .exclude(classe_label="")
            .values("classe_label")
            .annotate(total=Count("id"))
            .values_list("classe_label", "total")
        )
    }
    apprenant_counts = {
        normalize_network_lookup(code): count
        for code, count in _source_class_apprenant_counts(source_bundle).items()
    }

    prestation_classes: dict[str, set[str]] = {}
    for source_class in source_classes:
        prestation_key = normalize_network_lookup(source_class.get("prestation_id", ""))
        classe_key = normalize_network_lookup(source_class.get("classe_id", ""))
        if not prestation_key or not classe_key:
            continue
        if int(apprenant_counts.get(classe_key) or 0) <= 0:
            continue
        prestation_classes.setdefault(prestation_key, set()).add(classe_key)

    qualified_codes: set[str] = set()
    for prestation_key, class_keys in prestation_classes.items():
        all_reached = True
        for class_key in class_keys:
            total_apprenants = int(apprenant_counts.get(class_key) or 0)
            if total_apprenants <= 0:
                all_reached = False
                break
            threshold_target = analysis_threshold_target(total_apprenants)
            total_termines = int(terminated_by_class.get(class_key) or 0)
            if total_termines < threshold_target:
                all_reached = False
                break
        if all_reached:
            qualified_codes.add(prestation_key)
    return qualified_codes


def _get_selected_class(selected_class_code: str | None) -> Classe | None:
    code = (selected_class_code or "").strip()
    if not code:
        return None
    return (
        Classe.objects.filter(actif=True)
        .select_related("prestation__prestataire", "formation")
        .filter(code__iexact=code)
        .first()
    )


def _extract_class_code(classe, classe_label: str | None) -> str:
    if classe and getattr(classe, "code", ""):
        return str(classe.code).strip()
    raw_label = str(classe_label or "").strip()
    if not raw_label:
        return ""
    match = re.match(r"^([A-Za-z0-9_]+)", raw_label)
    return (match.group(1) if match else raw_label.split()[0]).strip()


def _selected_class_code_matches(
    class_code: str, selected_class, selected_class_code: str | None
) -> bool:
    effective_code = (
        (selected_class.code if selected_class else (selected_class_code or "")).strip().lower()
    )
    if not effective_code:
        return True
    return str(class_code or "").strip().lower() == effective_code


def _build_not_formed_rows(
    selected_class=None,
    selected_class_code: str | None = None,
    source_records: dict[str, dict] | None = None,
) -> list[dict]:
    queryset = (
        Appel.objects.filter(is_active=True, flag_pas_forme=True)
        .select_related("classe")
        .order_by("classe_label", "nom")
    )
    rows: list[dict] = []
    for appel in queryset:
        class_code = _extract_class_code(appel.classe, appel.classe_label)
        if not _selected_class_code_matches(class_code, selected_class, selected_class_code):
            continue
        source_record = (source_records or {}).get(normalize_network_lookup(appel.code or "")) or {}
        rows.append(
            {
                "call_id": appel.id,
                "code": appel.code,
                "apprenant_id": source_record.get("apprenant_id") or appel.code,
                "name": appel.nom or "-",
                "phone_display": (appel.telephone1 or "").strip() or "-",
                "phone_normalized": _normalize_phone_number(appel.telephone1),
                "class_code": class_code,
                "class_label": _class_display_label(appel.classe, appel.classe_label),
                "anomaly_label": "Pas forme",
            }
        )
    return rows


def _build_false_name_rows(
    selected_class=None,
    selected_class_code: str | None = None,
    source_records: dict[str, dict] | None = None,
) -> list[dict]:
    queryset = (
        Appel.objects.filter(is_active=True, flag_faux_nom=True)
        .select_related("classe")
        .order_by("classe_label", "nom")
    )
    rows: list[dict] = []
    for appel in queryset:
        class_code = _extract_class_code(appel.classe, appel.classe_label)
        if not _selected_class_code_matches(class_code, selected_class, selected_class_code):
            continue
        source_record = (source_records or {}).get(normalize_network_lookup(appel.code or "")) or {}
        rows.append(
            {
                "call_id": appel.id,
                "code": appel.code,
                "apprenant_id": source_record.get("apprenant_id") or appel.code,
                "name": appel.nom or "-",
                "phone_display": (appel.telephone1 or "").strip() or "-",
                "phone_normalized": _normalize_phone_number(appel.telephone1),
                "class_code": class_code,
                "class_label": _class_display_label(appel.classe, appel.classe_label),
                "anomaly_label": "Faux nom",
            }
        )
    return rows


def _build_duplicate_phone_rows(
    selected_class=None,
    selected_class_code: str | None = None,
    source_records: dict[str, dict] | None = None,
) -> list[dict]:
    queryset = (
        Appel.objects.filter(is_active=True, flag_numero_double=True)
        .select_related("classe")
        .order_by("classe_label", "nom")
    )
    duplicate_rows: list[dict] = []
    for appel in queryset:
        normalized_phone = _normalize_phone_number(appel.telephone1)
        if not normalized_phone:
            continue
        class_code = _extract_class_code(appel.classe, appel.classe_label)
        if not _selected_class_code_matches(class_code, selected_class, selected_class_code):
            continue
        source_record = (source_records or {}).get(normalize_network_lookup(appel.code or "")) or {}
        duplicate_rows.append(
            {
                "call_id": appel.id,
                "code": appel.code,
                "apprenant_id": source_record.get("apprenant_id") or appel.code,
                "name": appel.nom or "-",
                "phone_display": (appel.telephone1 or "").strip() or normalized_phone,
                "phone_normalized": normalized_phone,
                "class_code": class_code,
                "class_label": _class_display_label(appel.classe, appel.classe_label),
                "anomaly_label": "Doublon",
            }
        )
    return duplicate_rows


def _build_anomaly_summary(selected_class=None, selected_class_code: str | None = None) -> dict:
    classes_qs = Classe.objects.filter(actif=True)
    classes_not_trained_count = classes_qs.exclude(statut="termine").count()

    try:
        source_records = (build_padesce_source_index() or {}).get("records", {})
    except Exception:
        source_records = {}

    not_formed_rows_all = _build_not_formed_rows(source_records=source_records)
    false_name_rows_all = _build_false_name_rows(source_records=source_records)
    duplicate_rows_all = _build_duplicate_phone_rows(source_records=source_records)

    selected_not_formed = _build_not_formed_rows(
        selected_class,
        selected_class_code,
        source_records=source_records,
    )
    selected_false_name = _build_false_name_rows(
        selected_class,
        selected_class_code,
        source_records=source_records,
    )
    selected_duplicate = _build_duplicate_phone_rows(
        selected_class,
        selected_class_code,
        source_records=source_records,
    )

    anomaly_options: dict[str, dict] = {}
    for row in not_formed_rows_all + false_name_rows_all + duplicate_rows_all:
        code = row["class_code"]
        if not code:
            continue
        if code not in anomaly_options:
            anomaly_options[code] = {
                "code": code,
                "label": row["class_label"],
                "has_not_formed": False,
                "has_duplicate": False,
                "has_false_name": False,
            }
        if row["anomaly_label"] == "Pas forme":
            anomaly_options[code]["has_not_formed"] = True
        if row["anomaly_label"] == "Doublon":
            anomaly_options[code]["has_duplicate"] = True
        if row["anomaly_label"] == "Faux nom":
            anomaly_options[code]["has_false_name"] = True

    anomaly_rows = sorted(
        selected_duplicate + selected_false_name + selected_not_formed,
        key=lambda row: (
            {"Doublon": 0, "Faux nom": 1, "Pas forme": 2}.get(row["anomaly_label"], 9),
            row["class_label"],
            row["code"],
            row["call_id"],
        ),
    )

    effective_selected_code = (
        selected_class.code if selected_class else (selected_class_code or "")
    ).strip()
    selected_class_summary = {
        "code": effective_selected_code,
        "label": _class_display_label(selected_class, effective_selected_code),
        "not_formed_count": len(selected_not_formed),
        "duplicate_numbers_count": len(selected_duplicate),
        "false_name_count": len(selected_false_name),
        "total_anomalies_count": len(selected_not_formed)
        + len(selected_duplicate)
        + len(selected_false_name),
    }

    return {
        "classes_not_trained_count": classes_not_trained_count,
        "duplicate_numbers_count": len(duplicate_rows_all),
        "duplicate_rows": selected_duplicate,
        "not_formed_rows": selected_not_formed,
        "false_name_rows": selected_false_name,
        "anomaly_rows": anomaly_rows,
        "selected_class": selected_class_summary,
        "class_options": sorted(anomaly_options.values(), key=lambda item: item["code"]),
    }


def _class_display_label(classe, label: str | None) -> str:
    if classe:
        return f"{classe.code} - {classe.intitule_formation}"
    return str(label or "-").strip()


def _normalize_phone_number(val) -> str:
    if not val:
        return ""
    digits = "".join(filter(str.isdigit, str(val)))
    if len(digits) == 9 and digits.startswith(("6", "2")):
        return f"237{digits}"
    return digits


def _build_analysis_summary(padesce_qs) -> dict:
    try:
        from App_PADESCE.satisfaction_apprenants.views import _build_satisfaction_dashboard_data

        query = QueryDict("", mutable=True)
        query["source"] = "cutoff"
        payload = _build_satisfaction_dashboard_data(SimpleNamespace(GET=query))
        context = payload["context"]
        return {
            "classes_count": context["analyzed_classes_count"],
            "prestations_count": context["analyzed_prestations_count"],
            "prestataires_count": context["analyzed_prestataires_count"],
            "beneficiaires_count": context["analyzed_beneficiaires_count"],
        }
    except Exception:
        pass

    terminated_rows = list(padesce_qs.filter(status="termine").select_related("classe__prestation"))
    classes = sorted(
        {
            (row.classe_label or "").strip()
            for row in terminated_rows
            if (row.classe_label or "").strip()
        }
    )
    prestataires = sorted(
        {
            (row.prestataire or "").strip()
            for row in terminated_rows
            if (row.prestataire or "").strip()
        }
    )
    beneficiaires = sorted(
        {
            (row.beneficiaire or "").strip()
            for row in terminated_rows
            if (row.beneficiaire or "").strip()
        }
    )
    try:
        source_bundle = build_padesce_source_index()
    except Exception:
        source_bundle = None
    qualified_codes = _qualified_prestation_codes(source_bundle)
    prestations = sorted(
        {
            normalize_network_lookup(getattr(row.classe.prestation, "code", ""))
            for row in terminated_rows
            if (
                getattr(row, "classe", None)
                and getattr(row.classe, "prestation", None)
                and getattr(row.classe.prestation, "code", "")
                and normalize_network_lookup(row.classe.prestation.code) in qualified_codes
            )
        }
    )
    return {
        "classes_count": len(classes),
        "prestations_count": len(prestations),
        "prestataires_count": len(prestataires),
        "beneficiaires_count": len(beneficiaires),
    }


def _build_formateurs_satisfaction_summary(start_dt, end_dt) -> dict:
    """Résumé satisfaction formateurs (Q1-Q3) pour le rapport quotidien."""
    from django.db.models import Avg as DjAvg

    qs = AppelFormateur.objects.filter(
        is_active=True,
        status="termine",
        updated_at__gte=start_dt,
        updated_at__lte=end_dt,
    )
    total = qs.count()
    with_scores = qs.filter(
        q1_prerequis_apprenants__isnull=False,
        q2_interaction_apprenants__isnull=False,
        q3_competences_acquises__isnull=False,
    ).count()

    avgs = qs.aggregate(
        avg_q1=DjAvg("q1_prerequis_apprenants"),
        avg_q2=DjAvg("q2_interaction_apprenants"),
        avg_q3=DjAvg("q3_competences_acquises"),
    )

    # Par prestataire
    by_prestataire = list(
        qs.values("prestataire")
        .annotate(
            nb=Count("id"),
            avg_q1=DjAvg("q1_prerequis_apprenants"),
            avg_q2=DjAvg("q2_interaction_apprenants"),
            avg_q3=DjAvg("q3_competences_acquises"),
        )
        .order_by("prestataire")[:10]
    )

    return {
        "total_termines": total,
        "with_scores": with_scores,
        "avg_q1": round(avgs["avg_q1"] or 0, 2),
        "avg_q2": round(avgs["avg_q2"] or 0, 2),
        "avg_q3": round(avgs["avg_q3"] or 0, 2),
        "by_prestataire": [
            {
                "prestataire": row["prestataire"] or "—",
                "nb": row["nb"],
                "avg_q1": round(row["avg_q1"] or 0, 2),
                "avg_q2": round(row["avg_q2"] or 0, 2),
                "avg_q3": round(row["avg_q3"] or 0, 2),
            }
            for row in by_prestataire
        ],
    }


def _build_user_call_rows(*querysets) -> list[dict]:
    merged: dict[int, dict] = {}
    for queryset in querysets:
        rows = (
            queryset.exclude(status="en_attente")
            .filter(locked_by__isnull=False)
            .values("locked_by_id", "locked_by__username")
            .annotate(
                calls_made=Count("id"),
                completed_calls=Count("id", filter=Q(status="termine")),
                first_activity=Min("updated_at"),
                last_activity=Max("updated_at"),
            )
        )
        for row in rows:
            user_id = row["locked_by_id"]
            if user_id not in merged:
                merged[user_id] = {
                    "username": row["locked_by__username"] or f"user-{user_id}",
                    "calls_made": 0,
                    "completed_calls": 0,
                    "first_activity": row["first_activity"],
                    "last_activity": row["last_activity"],
                }
            merged[user_id]["calls_made"] += int(row["calls_made"] or 0)
            merged[user_id]["completed_calls"] += int(row["completed_calls"] or 0)
            if row["first_activity"] and (
                not merged[user_id]["first_activity"]
                or row["first_activity"] < merged[user_id]["first_activity"]
            ):
                merged[user_id]["first_activity"] = row["first_activity"]
            if row["last_activity"] and (
                not merged[user_id]["last_activity"]
                or row["last_activity"] > merged[user_id]["last_activity"]
            ):
                merged[user_id]["last_activity"] = row["last_activity"]

    results = []
    for item in merged.values():
        first_activity = item["first_activity"]
        last_activity = item["last_activity"]
        duration = (
            (last_activity - first_activity) if (first_activity and last_activity) else timedelta(0)
        )
        results.append(
            {
                "username": item["username"],
                "calls_made": item["calls_made"],
                "completed_calls": item["completed_calls"],
                "time_spent_seconds": int(max(duration.total_seconds(), 0)),
                "time_spent_label": _format_duration(duration),
                "first_activity_label": (
                    timezone.localtime(first_activity).strftime("%H:%M") if first_activity else "-"
                ),
                "last_activity_label": (
                    timezone.localtime(last_activity).strftime("%H:%M") if last_activity else "-"
                ),
            }
        )
    return sorted(results, key=lambda row: (-row["calls_made"], row["username"].lower()))


def _format_duration(duration) -> str:
    total_seconds = int(max(duration.total_seconds(), 0))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}min"
    if minutes:
        return f"{minutes}min {seconds:02d}s"
    return f"{seconds}s"


def _email_card(label: str, value) -> str:
    return (
        "<div style='flex:1 1 180px;min-width:180px;padding:16px 18px;border-radius:18px;"
        "background:#ffffff;border:1px solid #ece5fb;box-shadow:0 10px 24px rgba(76,29,149,0.08);'>"
        f"<div style='font-size:13px;color:#7a67a5;margin-bottom:8px;'>{label}</div>"
        f"<div style='font-size:28px;font-weight:800;color:#4c1d95;line-height:1.2;'>{value}</div>"
        "</div>"
    )


def _email_stat(label: str, value) -> str:
    return (
        "<div style='padding:12px 14px;border-radius:14px;background:#ffffff;border:1px solid #ece5fb;'>"
        f"<div style='font-size:12px;color:#7a67a5;margin-bottom:5px;'>{label}</div>"
        f"<div style='font-size:20px;font-weight:800;color:#4c1d95;'>{value}</div>"
        "</div>"
    )


def _get_report_logo_path() -> Path | None:
    candidates = [
        Path(settings.BASE_DIR) / "LogoCGANaumur.png",
        Path(settings.BASE_DIR) / "media" / "LogoCGANaumur.png",
        Path(settings.BASE_DIR) / "media" / "img" / "LogoCGANaumur.png",
        Path(settings.BASE_DIR) / "static" / "LogoCGANaumur.png",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _clear_cell_border(cell) -> None:
    if not HAS_DOCX:
        return
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_borders = tc_pr.first_child_found_in("w:tcBorders")
    if tc_borders is None:
        tc_borders = OxmlElement("w:tcBorders")
        tc_pr.append(tc_borders)
    for edge in ("top", "left", "bottom", "right"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "nil")
        tc_borders.append(element)


# ---------------------------------------------------------------------------
# Helpers internes — construction du rapport
# ---------------------------------------------------------------------------


def _build_call_source_summary(label: str, queryset) -> dict:
    total = queryset.count()
    completed = queryset.filter(status="termine").count()
    pending = queryset.filter(status="en_attente").count()
    in_progress = queryset.filter(status="en_cours").count()
    callbacks = queryset.filter(status="a_rappeler").count()
    processed = total - pending
    with_audio = queryset.exclude(audio_file="").exclude(audio_file__isnull=True).count()
    return {
        "label": label,
        "total": total,
        "completed": completed,
        "pending": pending,
        "in_progress": in_progress,
        "callbacks": callbacks,
        "processed": processed,
        "with_audio": with_audio,
    }


def _hourly_completed_counts(queryset) -> dict[int, int]:
    """Compte les appels termines par heure (compatible SQLite et PostgreSQL)."""
    counts: dict[int, int] = {}
    tz = timezone.get_current_timezone()
    for updated_at in queryset.filter(status="termine").values_list("updated_at", flat=True):
        if updated_at is None:
            continue
        local_dt = (
            timezone.localtime(updated_at, tz) if timezone.is_aware(updated_at) else updated_at
        )
        hour = local_dt.hour
        counts[hour] = counts.get(hour, 0) + 1
    return counts


def _build_hourly_rows(*hourly_counts_list) -> list[dict]:
    merged: dict[int, dict] = {}
    for hourly_counts in hourly_counts_list:
        for hour, count in hourly_counts.items():
            if hour not in merged:
                merged[hour] = {
                    "hour": hour,
                    "label": f"{hour:02d}h00 - {hour:02d}h59",
                    "total": 0,
                    "completed": 0,
                }
            merged[hour]["completed"] += count
            merged[hour]["total"] += count
    return sorted(merged.values(), key=lambda row: row["hour"])


def _build_bug_summary(start_dt, end_dt) -> dict:
    """Résumé des bugs/alarmes sur la période."""
    try:
        from App_PADESCE.core.models import Alarm

        alarms_qs = Alarm.objects.filter(created_at__gte=start_dt, created_at__lte=end_dt)
        alarms_total = alarms_qs.count()
        alarms_resolved = alarms_qs.filter(status="resolved").count()
        alarms_open = alarms_total - alarms_resolved
        recent_alarms = [
            {
                "title": str(alarm.title or ""),
                "module": str(getattr(alarm, "module", "") or ""),
                "created_at": timezone.localtime(alarm.created_at).strftime("%d/%m/%Y %H:%M"),
                "status": str(alarm.status or ""),
            }
            for alarm in alarms_qs.order_by("-created_at")[:10]
        ]
    except Exception:
        alarms_total = 0
        alarms_resolved = 0
        alarms_open = 0
        recent_alarms = []

    log_errors = _count_log_level("ERROR", start_dt, end_dt)
    log_critical = _count_log_level("CRITICAL", start_dt, end_dt)

    return {
        "alarms_total": alarms_total,
        "alarms_resolved": alarms_resolved,
        "alarms_open": alarms_open,
        "log_errors": log_errors,
        "log_critical": log_critical,
        "recent_alarms": recent_alarms,
    }


def _count_log_level(level: str, start_dt, end_dt) -> int:
    """Compte les lignes de log contenant le niveau donné sur la période."""
    try:
        log_path = Path(settings.BASE_DIR) / "logs" / "app.log"
        if not log_path.exists():
            return 0
        start_str = timezone.localtime(start_dt).strftime("%Y-%m-%d")
        end_str = timezone.localtime(end_dt).strftime("%Y-%m-%d")
        count = 0
        with log_path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if level in line and (start_str <= line[:10] <= end_str):
                    count += 1
        return count
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Helpers Word — document
# ---------------------------------------------------------------------------


def _configure_report_document(document) -> None:
    if not HAS_DOCX:
        return
    from docx.shared import Pt as _Pt

    style = document.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = _Pt(11)


def _add_heading(document, text: str) -> None:
    if not HAS_DOCX:
        return
    paragraph = document.add_paragraph()
    run = paragraph.add_run(text)
    run.bold = True
    run.font.size = Pt(13)
    run.font.color.rgb = RGBColor(76, 29, 149)
    paragraph.space_before = Pt(14)
    paragraph.space_after = Pt(6)


def _add_metric_table(document, rows: list[tuple]) -> None:
    if not HAS_DOCX:
        return
    table = document.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for label, value in rows:
        row_cells = table.add_row().cells
        row_cells[0].text = str(label)
        row_cells[1].text = str(value)


def _write_header_cell(cell, text: str) -> None:
    if not HAS_DOCX:
        return
    cell.text = text
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            run.bold = True
            run.font.color.rgb = RGBColor(76, 29, 149)


# ---------------------------------------------------------------------------
# Exports CSV / Excel
# ---------------------------------------------------------------------------


def export_application_report_csv(report: dict) -> bytes:
    import csv
    import io as _io

    output = _io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Section", "Indicateur", "Valeur"])
    writer.writerow(["Appels", "Termines", report["calls"]["completed"]])
    writer.writerow(["Appels", "Effectues", report["calls"]["processed"]])
    writer.writerow(["Appels", "En attente", report["calls"]["pending"]])
    writer.writerow(["Appels", "En cours", report["calls"]["in_progress"]])
    writer.writerow(["Appels", "A rappeler", report["calls"]["callbacks"]])
    writer.writerow(["Appels", "Avec audio", report["calls"]["with_audio"]])
    writer.writerow(["Utilisateurs", "Ayant appele", report["users"]["called_today"]])
    writer.writerow(["Analyse", "Classes", report["analysis"]["classes_count"]])
    writer.writerow(["Analyse", "Prestations", report["analysis"]["prestations_count"]])
    writer.writerow(["Analyse", "Prestataires", report["analysis"]["prestataires_count"]])
    writer.writerow(["Analyse", "Beneficiaires", report["analysis"]["beneficiaires_count"]])
    for row in report["user_call_rows"]:
        writer.writerow(
            [
                "Utilisateur",
                row["username"],
                f"{row['calls_made']} appels, {row['completed_calls']} termines, {row['time_spent_label']}",
            ]
        )
    return output.getvalue().encode("utf-8-sig")


def export_application_report_excel(report: dict) -> bytes:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font

        wb = Workbook()
        ws = wb.active
        ws.title = "Rapport"

        def add_section(title, rows_data):
            ws.append([title])
            ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=13, color="4C1D95")
            for row in rows_data:
                ws.append(list(row))

        add_section(
            "Appels",
            [
                ("Termines", report["calls"]["completed"]),
                ("Effectues", report["calls"]["processed"]),
                ("En attente", report["calls"]["pending"]),
                ("En cours", report["calls"]["in_progress"]),
                ("A rappeler", report["calls"]["callbacks"]),
                ("Avec audio", report["calls"]["with_audio"]),
            ],
        )
        ws.append([])
        add_section(
            "Analyse satisfaction",
            [
                ("Classes", report["analysis"]["classes_count"]),
                ("Prestations", report["analysis"]["prestations_count"]),
                ("Prestataires", report["analysis"]["prestataires_count"]),
                ("Beneficiaires", report["analysis"]["beneficiaires_count"]),
            ],
        )
        ws.append([])
        add_section(
            "Activite utilisateurs",
            [
                (
                    row["username"],
                    row["calls_made"],
                    row["completed_calls"],
                    row["time_spent_label"],
                )
                for row in report["user_call_rows"]
            ],
        )

        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()
    except ImportError:
        return export_application_report_csv(report)

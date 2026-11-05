"""Registre des campagnes FA : chaque enquête a ses contacts et son questionnaire."""

from django.http import Http404
from django.urls import reverse
from django.utils.functional import cached_property

from . import schema, schema_investisseurs, schema_porteurs
from .models import Enterprise


class Campaign:
    def __init__(
        self,
        *,
        key,
        slug,
        label,
        title,
        description,
        sections,
        reference_prefix,
        respondent_key,
        contact_label,
        contact_plural,
        prefill,
        note,
        sector_label="Secteur",
        intro="",
        closing="",
        funding=None,
        aliases=None,
        unnamed_contacts=False,
        merge_same_name=False,
    ):
        self.key = key
        self.slug = slug
        self.label = label
        self.title = title
        self.description = description
        self.sections = sections
        self.reference_prefix = reference_prefix
        self.respondent_key = respondent_key
        self.contact_label = contact_label
        self.contact_plural = contact_plural
        self.prefill = prefill
        self.note = note
        self.sector_label = sector_label
        self.intro = intro
        self.closing = closing
        self.funding = funding
        self.aliases = aliases or {}
        self.unnamed_contacts = unnamed_contacts
        self.merge_same_name = merge_same_name
        self.questions = [q for section in sections for q in section["questions"]]
        self.question_map = {q["key"]: q for q in self.questions}
        self.has_required = any(q["required"] for q in self.questions)

    @property
    def is_pme(self):
        return self.key == Enterprise.CAMPAIGN_PME

    @cached_property
    def urls(self):
        slug = [self.slug]
        return {
            "index": reverse("fa_index") if self.is_pme else reverse("fa_campaign", args=slug),
            "analytics": reverse("fa_campaign_analytics", args=slug),
            "responses": reverse("fa_responses", args=slug),
            "export": reverse("fa_campaign_export", args=slug),
            "export_xlsx": reverse("fa_export_xlsx", args=slug),
            "import": reverse("fa_campaign_import", args=slug),
        }

    def initial(self, enterprise):
        return {**self.prefill(enterprise), **enterprise.answers}


PME = Campaign(
    key=Enterprise.CAMPAIGN_PME,
    slug="pme",
    label="PME",
    title="Appels PME",
    description="Enquête sur les besoins de financement des startups et PME.",
    sections=schema.SECTIONS,
    reference_prefix="FA",
    respondent_key="q2_respondent",
    contact_label="Entreprise",
    contact_plural="entreprises",
    prefill=lambda e: {
        "q1_name": e.name,
        "q4_phone": e.phone,
        "q5_city": e.city,
        "q8_sector": e.sector,
        "q22_currency": "FCFA",
    },
    note=(
        "Étude NAUMUR / APME sur la mise en place d’un fonds d’amorçage · "
        "entretien de 5 à 10 minutes."
    ),
    funding={"need": "q12_need", "yes": "Oui", "amount": "q13_amount"},
)
PORTEURS = Campaign(
    key=Enterprise.CAMPAIGN_PORTEURS,
    slug="porteurs",
    label="Porteurs de projets",
    title="Porteurs de projets",
    description="Profil des porteurs, stade du projet, besoins et expériences de financement.",
    sections=schema_porteurs.SECTIONS,
    reference_prefix="FP",
    respondent_key="p1_name",
    contact_label="Porteur",
    contact_plural="porteurs",
    prefill=lambda e: {"q4_phone": e.phone},
    note="Étude NAUMUR / APME · enquête auprès des porteurs de projets.",
    closing="Merci pour votre participation.",
    aliases={
        "country_code": "source_number",
        "public_name": "name",
        "phone_number": "phone_raw",
        "country_name": "country",
    },
    unnamed_contacts=True,
)
INVESTISSEURS = Campaign(
    key=Enterprise.CAMPAIGN_INVESTORS,
    slug="investisseurs",
    label="Fonds et investisseurs",
    title="Fonds et investisseurs",
    description="Pratiques de financement, sélection et accompagnement des acteurs du financement.",
    sections=schema_investisseurs.SECTIONS,
    reference_prefix="FI",
    respondent_key="i_contact",
    contact_label="Structure",
    contact_plural="structures",
    prefill=lambda e: {
        "i_org": e.name,
        "i_city": e.city,
        "q4_phone": e.phone,
        "i_email": e.email,
    },
    note="Étude NAUMUR / APME · enquête auprès des fonds d’amorçage et investisseurs.",
    sector_label="Type de structure",
    intro=schema_investisseurs.INTRO,
    closing=schema_investisseurs.CLOSING,
    aliases={
        "structure / dispositif": "name",
        "type": "sector",
        "ville / pays": "city",
        "courriel": "email",
        "precisions / points a confirmer": "notes",
    },
    merge_same_name=True,
)

CAMPAIGNS = (PME, PORTEURS, INVESTISSEURS)
FUNDS_CAMPAIGNS = (PORTEURS, INVESTISSEURS)
_BY_KEY = {campaign.key: campaign for campaign in CAMPAIGNS}
_BY_SLUG = {campaign.slug: campaign for campaign in CAMPAIGNS}


def campaign_for_slug(slug):
    try:
        return _BY_SLUG[slug]
    except KeyError:
        raise Http404("Campagne inconnue.") from None


def campaign_for_enterprise(enterprise):
    try:
        return _BY_KEY[enterprise.campaign]
    except KeyError:
        raise Http404("Campagne inconnue.") from None

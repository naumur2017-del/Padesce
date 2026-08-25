"""Diagnostic non destructif d'un identifiant de connexion."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from App_PADESCE.core.operator_auth import normalize_login_identifier


class Command(BaseCommand):
    help = "Diagnostique un identifiant sans afficher de mot de passe ni hash."

    def add_arguments(self, parser):
        parser.add_argument("--identifier", required=True)

    def handle(self, *args, **options):
        raw = str(options["identifier"])
        normalized = normalize_login_identifier(raw)
        if not normalized:
            raise CommandError("Identifiant vide après normalisation.")
        User = get_user_model()
        field = User.USERNAME_FIELD
        # This is a diagnostic command, not a login query. Comparing normalized
        # Python values makes its result independent from SQLite/PostgreSQL
        # differences in Unicode case-insensitive lookups.
        matches = [
            user
            for user in User._default_manager.all().prefetch_related("groups")
            if normalize_login_identifier(getattr(user, field, "")) == normalized
        ]
        self.stdout.write(
            "normalisation: unicode_nfkc; suppression_caracteres_invisibles; "
            f"casse_unicode; identifiant_non_vide={bool(normalized)}"
        )
        self.stdout.write(f"comptes_correspondants: {len(matches)}")
        if not matches:
            self.stdout.write("raison_probable: identifiant_inexistant_ou_difference_unicode")
            return
        for user in matches:
            groups = sorted(user.groups.values_list("name", flat=True))
            self.stdout.write(
                f"compte: actif={user.is_active}; staff={user.is_staff}; superuser={user.is_superuser}; "
                f"mot_de_passe_utilisable={user.has_usable_password()}; groupes={','.join(groups) or '-'}"
            )
        if len(matches) > 1:
            self.stdout.write("raison_probable: doublon_d_identifiant_insensible_a_la_casse")
        elif raw != normalized:
            self.stdout.write("raison_probable: identifiant_normalise_modifie")
        elif matches[0].is_active is False:
            self.stdout.write("raison_probable: compte_inactif")
        else:
            self.stdout.write("raison_probable: verifier_mot_de_passe_session_et_droits_metier")

"""Diagnostic non destructif d'un identifiant de connexion."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Diagnostique un identifiant sans afficher de mot de passe ni hash."

    def add_arguments(self, parser):
        parser.add_argument("--identifier", required=True)

    def handle(self, *args, **options):
        raw = str(options["identifier"])
        normalized = raw.strip()
        if not normalized:
            raise CommandError("Identifiant vide après normalisation.")
        User = get_user_model()
        field = User.USERNAME_FIELD
        matches = list(
            User._default_manager.filter(**{f"{field}__iexact": normalized}).prefetch_related(
                "groups"
            )
        )
        self.stdout.write(f"normalisation: trim; identifiant_non_vide={bool(normalized)}")
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
            self.stdout.write("raison_probable: espaces_avant_ou_apres_l_identifiant")
        elif matches[0].is_active is False:
            self.stdout.write("raison_probable: compte_inactif")
        else:
            self.stdout.write("raison_probable: verifier_mot_de_passe_session_et_droits_metier")

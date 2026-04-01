from __future__ import annotations

from django.contrib.auth.models import Group, User
from django.test import TransactionTestCase
from django.utils import timezone

from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.core.db_migration import copy_database_contents
from App_PADESCE.core.models import AuditLog, UserActivity
from App_PADESCE.formations.models import Beneficiaire, Classe, Formateur, Formation, Lieu, Prestataire, Prestation


class DatabaseCopyTests(TransactionTestCase):
    databases = {"default", "sqlite"}

    def test_copy_database_contents_between_sqlite_aliases(self) -> None:
        source_alias = "sqlite"
        target_alias = "default"
        source_objects = self._seed_source_database(source_alias)

        result = copy_database_contents(
            source_alias=source_alias,
            target_alias=target_alias,
            batch_size=2,
        )

        self.assertTrue(result.inserted > 0)
        self.assertFalse(result.count_mismatches)

        self.assertEqual(User.objects.using(target_alias).count(), User.objects.using(source_alias).count())
        self.assertEqual(Apprenant.objects.using(target_alias).count(), Apprenant.objects.using(source_alias).count())
        self.assertEqual(
            AuditLog.objects.using(target_alias).count(),
            AuditLog.objects.using(source_alias).count(),
        )

        user = User.objects.using(target_alias).get(username="migration-user")
        self.assertTrue(user.groups.filter(name="Inspecteur").exists())

        apprenant = Apprenant.objects.using(target_alias).get(code="APP001")
        self.assertTrue(apprenant.appartenance_beneficiaire)
        self.assertEqual(apprenant.classe.code, "CLA001")

        audit = AuditLog.objects.using(target_alias).get(object_pk=str(source_objects["apprenant"].pk))
        self.assertEqual(audit.extra, {"source": "sqlite", "copie": True})

        new_formation = Formation.objects.db_manager(target_alias).create(
            code="FOR999",
            nom="Formation cible",
            nom_harmonise="Formation cible",
            statut="en_cours",
            fenetre="F3",
            actif=True,
        )
        self.assertGreater(new_formation.pk, source_objects["formation"].pk)

    def _seed_source_database(self, alias: str) -> dict[str, object]:
        user = User.objects.db_manager(alias).create_user(
            username="migration-user",
            password="secret",
            email="migration@example.com",
        )
        group = Group.objects.db_manager(alias).create(name="Inspecteur")
        user.groups.add(group)
        UserActivity.objects.db_manager(alias).create(user=user, last_seen=timezone.now())

        formateur = Formateur.objects.db_manager(alias).create(
            code="FORMA001",
            nom_complet="Jean Formateur",
            specialite="Entrepreneuriat",
            qualification="Senior",
            nb_annees_experience=8,
            fenetre="F2",
            telephone="670000001",
            ville_residence="Douala",
            autres_infos="Disponible",
            actif=True,
        )
        prestataire = Prestataire.objects.db_manager(alias).create(
            code="PRES001",
            raison_sociale="Prestataire Demo",
            type_structure="ONG",
            telephone="670000002",
            email="prestataire@example.com",
            actif=True,
        )
        formation = Formation.objects.db_manager(alias).create(
            code="FORM001",
            nom="Culture maraichere",
            nom_harmonise="Culture maraichere",
            statut="en_cours",
            fenetre="F2",
            actif=True,
        )
        beneficiaire = Beneficiaire.objects.db_manager(alias).create(
            nom_structure="Association Test",
            type_structure="Association",
            region="Littoral",
            departement="Wouri",
            arrondissement="Douala 5e",
            ville="Douala",
            contact="M. Test",
            email="beneficiaire@example.com",
            actif=True,
        )
        prestation = Prestation.objects.db_manager(alias).create(
            code="PREST001",
            prestataire=prestataire,
            formation=formation,
            beneficiaire=beneficiaire,
            effectif_a_former=25,
            femmes=16,
            cout_unitaire_psoaf=1000,
            montant_formation_psoaf_ttc=25000,
            cout_unitaire_mcdc_ttc=800,
            montant_mcdc_ttc=20000,
            duree_prevue_heures=40,
            duree_reelle_heures=38,
            jalons_contractuels="J1;J2",
            actif=True,
        )
        lieu = Lieu.objects.db_manager(alias).create(
            code="LIEU001",
            nom_lieu="Salle Polyvalente",
            region="Littoral",
            departement="Wouri",
            arrondissement="Douala 5e",
            ville="Douala",
            longitude="9.7000",
            latitude="4.0500",
            precision="Quartier Bonamoussadi",
            actif=True,
        )
        classe = Classe.objects.db_manager(alias).create(
            code="CLA001",
            prestation=prestation,
            lieu=lieu,
            formation=formation,
            intitule_formation="Culture maraichere",
            formateur=formateur,
            fenetre="F2",
            cohorte=1,
            statut="en_cours",
            actif=True,
        )
        apprenant = Apprenant.objects.db_manager(alias).create(
            numero="1",
            code="APP001",
            classe=classe,
            formation=formation,
            nom_complet="Alice Apprenante",
            beneficiaire="Association Test",
            genre="F",
            age=29,
            fonction="Productrice",
            qualification="Technicienne",
            nb_annees_experience=4,
            fenetre="F2",
            prestataire="Prestataire Demo",
            intitule_formation_solicitee="Culture maraichere",
            intitule_formation_dispensee="Culture maraichere",
            ville_formation="Douala",
            telephone1="690000001",
            telephone2="690000002",
            cohorte="1",
            tel_formateur="670000001",
            ville_residence="Douala",
            region="Littoral",
            departement="Wouri",
            arrondissement="Douala 5e",
            lieu_formation="Salle Polyvalente",
            precision_lieu="Quartier Bonamoussadi",
            longitude="9.7000",
            latitude="4.0500",
            code_ville="DLA",
            appartenance_beneficiaire=True,
            actif=True,
        )
        AuditLog.objects.db_manager(alias).create(
            actor=user,
            model_name="Apprenant",
            object_pk=str(apprenant.pk),
            object_repr=apprenant.nom_complet,
            action="created",
            extra={"source": "sqlite", "copie": True},
        )

        return {
            "user": user,
            "formation": formation,
            "apprenant": apprenant,
        }

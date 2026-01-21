from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='ConsolidationRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero', models.CharField(blank=True, max_length=20)),
                ('nom_complet', models.CharField(blank=True, max_length=255)),
                ('beneficiaire', models.CharField(blank=True, max_length=255)),
                ('genre', models.CharField(blank=True, max_length=10)),
                ('age', models.PositiveIntegerField(blank=True, null=True)),
                ('fonction', models.CharField(blank=True, max_length=100)),
                ('qualification', models.CharField(blank=True, max_length=100)),
                ('nb_annees_experience', models.PositiveIntegerField(blank=True, null=True)),
                ('ville_residence', models.CharField(blank=True, max_length=120)),
                ('prestataire', models.CharField(blank=True, max_length=255)),
                ('intitule_formation_solicitee', models.CharField(blank=True, max_length=255)),
                ('intitule_formation_dispensee', models.CharField(blank=True, max_length=255)),
                ('fenetre', models.CharField(blank=True, max_length=50)),
                ('ville_formation', models.CharField(blank=True, max_length=120)),
                ('arrondissement', models.CharField(blank=True, max_length=120)),
                ('departement', models.CharField(blank=True, max_length=120)),
                ('region', models.CharField(blank=True, max_length=120)),
                ('lieu_formation', models.CharField(blank=True, max_length=255)),
                ('precision_lieu', models.CharField(blank=True, max_length=255)),
                ('longitude', models.CharField(blank=True, max_length=50)),
                ('latitude', models.CharField(blank=True, max_length=50)),
                ('telephone1', models.CharField(blank=True, max_length=30)),
                ('telephone2', models.CharField(blank=True, max_length=30)),
                ('cohorte', models.CharField(blank=True, max_length=50)),
                ('tel_formateur', models.CharField(blank=True, max_length=30)),
                ('code', models.CharField(blank=True, max_length=20)),
                ('cout_unitaire_subvention', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ('montant_total_subvention', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ('statut_prestation', models.CharField(blank=True, max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['numero', 'nom_complet'],
            },
        ),
        migrations.AddIndex(
            model_name='consolidationrecord',
            index=models.Index(fields=['code'], name='reporting_c_code_96f31f_idx'),
        ),
        migrations.AddIndex(
            model_name='consolidationrecord',
            index=models.Index(fields=['nom_complet'], name='reporting_c_nom_co_4906c5_idx'),
        ),
    ]

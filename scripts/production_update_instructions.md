## Mise à jour production — Présence C1..C4

But: remplacer les C1..C4 vides (NULL/"") par `-` en production, après backup.

Fichiers ajoutés:
- `scripts/apply_presence_updates.sql` — SQL à exécuter (générique SQLite/Postgres).
- `scripts/apply_prod_updates.ps1` — script PowerShell pour faire le backup et appliquer l'update (mode `sqlite` ou `postgres`).

Usage recommandé (PowerShell):

1) Pour SQLite (chemin vers fichier DB):

```powershell
.\scripts\apply_prod_updates.ps1 -DbType sqlite -SqlFile .\scripts\apply_presence_updates.sql -SqliteFile 'C:\path\to\prod.sqlite3'
```

2) Pour Postgres (remplacez les valeurs):

```powershell
.\scripts\apply_prod_updates.ps1 -DbType postgres -SqlFile .\scripts\apply_presence_updates.sql -PgHost db.example.org -PgPort 5432 -PgUser deploy -PgPassword 'SECRET' -PgDatabase prod_db
```

Conseils de sécurité:
- Toujours vérifier le backup créé (`*.pre_sync_*.bak` ou `*.pre_sync_*.sql`) avant toute restauration.
- Exécutez d'abord en environnement de staging et vérifiez l'affichage de la classe (ex: `CLA017`).
- Si votre production est gérée via Kubernetes/CI, préférez exécuter `pg_dump`/`psql` ou l'équivalent via vos pipelines sécurisés.

Vérifications post-apply:
- Exécuter la requête pour lister les apprenants encore vides:

```sql
SELECT id, code, c1, c2, c3, c4 FROM apprenants_apprenant
WHERE c1 IS NULL OR TRIM(c1) = '' OR c2 IS NULL OR TRIM(c2) = '' OR c3 IS NULL OR TRIM(c3) = '' OR c4 IS NULL OR TRIM(c4) = '';
```

- Comparez avec le rapport généré: `verification_report_20260428_122833.json`.

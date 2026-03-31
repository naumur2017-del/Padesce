# Synchronisation des bases SQLite

Un outil de fusion permet de recopier une ou plusieurs bases SQLite source vers une base SQLite cible, par exemple la base du reseau.

## Ce que fait l'outil

- ajoute les lignes absentes dans la base cible ;
- met a jour les lignes existantes si la source est plus recente ;
- cree une sauvegarde automatique avant ecriture ;
- propose un mode apercu avec `--dry-run`.

Tables exclues par defaut :

- `django_migrations`
- `django_session`
- `django_admin_log`
- `core_useractivity`

## Commande Django

```powershell
python manage.py sync_sqlite `
  --source .\db.sqlite3 `
  --target "\\serveur\partage\PADESCE\db.sqlite3" `
  --dry-run
```

Execution reelle :

```powershell
python manage.py sync_sqlite `
  --source .\db.sqlite3 `
  --target "\\serveur\partage\PADESCE\db.sqlite3"
```

Plusieurs sources :

```powershell
python manage.py sync_sqlite `
  --source .\db.sqlite3 `
  --source .\ancienne_copie.sqlite3 `
  --target "\\serveur\partage\PADESCE\db.sqlite3"
```

## Lanceur PowerShell

```powershell
.\scripts\sync_network_db.ps1 `
  -Source .\db.sqlite3 `
  -Target "\\serveur\partage\PADESCE\db.sqlite3" `
  -DryRun
```

Puis :

```powershell
.\scripts\sync_network_db.ps1 `
  -Source .\db.sqlite3 `
  -Target "\\serveur\partage\PADESCE\db.sqlite3"
```

## Options utiles

- `--conflict-strategy newer` : garde la ligne la plus recente.
- `--conflict-strategy source` : la source ecrase la cible.
- `--conflict-strategy target` : la cible n'est jamais ecrasee.
- `--table nom_table` : limite la fusion a certaines tables.
- `--exclude-table nom_table` : exclut certaines tables.
- `--backup-dir chemin` : change le dossier de sauvegarde.

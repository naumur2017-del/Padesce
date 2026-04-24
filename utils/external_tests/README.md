# Scripts de tests externes

Ce dossier contient des scripts qui dépendent de **serveurs externes** pour leurs tests.

## 🌐 Scripts de test externe

### test_formateur_stats.py
**Utilité** : Test HTTP externe de la page de stats des formateurs  
**Cible** : https://call.naumur.com/?scope=formateur&section=stats  
**Dépendances** : Serveur externe accessible, BeautifulSoup, requests  
**Fonctionnalités** : Analyse HTML, extraction prestations, détection erreurs  

## ⚠️ Conditions d'utilisation

### Prérequis
- Accès internet fonctionnel
- Serveur call.naumur.com accessible
- Modules Python : `requests`, `beautifulsoup4`

### Exécution
```bash
python test_formateur_stats.py
```

## 🚨 Limitations

- **Dépendant du serveur externe** : Ne fonctionne pas si le serveur est down
- **Peut être obsolète** : Si l'URL ou la structure HTML a changé
- **Timeout** : 30 secondes maximum par requête

## 📋 Résultats attendus

- Status HTTP de la page
- Nombre de tables trouvées
- Liste des prestations (codes PRESTA*)
- Noms des prestataires uniques
- Détection d'éventuelles erreurs

## 🔧 Maintenance

Ces scripts nécessitent une **maintenance régulière** pour :
- Mettre à jour les URLs si nécessaire
- Adapter les sélecteurs CSS/HTML
- Vérifier la compatibilité avec les changements du serveur externe

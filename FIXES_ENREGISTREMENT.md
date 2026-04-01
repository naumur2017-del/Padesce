# Corrections Enregistrement Questionnaire PADESCE

## 🎯 Objectifs Réalisés

### ✅ 1. Questionnaire toujours enregistré (PRIMORDIAL)
- Les réponses Q1-Q9 sont maintenant **TOUJOURS** envoyées au serveur
- Même si l'utilisateur laisse les valeurs par défaut (3 partout), elles sont enregistrées
- **Avant**: Aucune réponse n'était envoyée si l'utilisateur ne modifiait pas les radios
- **Après**: Les réponses sont toujours envoyées

### ✅ 2. Réponses précédentes chargées correctement
- Les réponses précédentes se chargent pour **TOUS les statuts** (pas seulement "a_rappeler")
- Les commentaires et recommandations sont conservés après chargement
- **Avant**: Seul les appels avec statut "a_rappeler" retrouvaient leurs réponses
- **Après**: Tous les appels retrouvent leurs données

### ✅ 3. Statut passe correctement à "Terminé"
- Quand on clique "Terminer et sauvegarder", le statut de l'Appel passe à "termine"
- La SatisfactionApprenant est créée/mise à jour immédiatement
- **Flux**: Questionnaire → Audio → Statut "termine"

### ✅ 4. Audio enregistré après le questionnaire
- Le questionnaire est **d'abord** enregistré (données primordiales)
- L'audio/transcription est enregistré **ensuite** (données secondaires)
- Si l'audio échoue, le questionnaire reste sauvegardé
- **Avant**: L'audio était traité avant le questionnaire
- **Après**: Ordre correct pour non-perte de données

### ✅ 5. ID Apprenant récupéré pour analyses
- Les logs enregistrent: **apprenant_id**, classe, prestataire, bénéficiaire
- Format: `"Satisfaction enregistrée. apprenant_id=%s classe=%s prestataire=%s beneficiaire=%s"`
- À consulter dans les logs Django (settings.LOGGING)

---

## 🧪 Guide de Test

### Test 1: Enregistrer avec réponses par défaut
1. Allez sur la page Appels
2. Cliquez "Démarrer le registrement" sur une ligne
3. **NE MODIFIEZ AUCUNE RÉPONSE** (laissez Q1-Q9 à 3)
4. Facultatif: Laissez commentaire vide
5. Cliquez "Terminer l'appel et Sauvegarder"
6. ✅ **Attendu**: 
   - Message "Satisfaction apprenant enregistrée"
   - Statut → "Termine"
   - Log: `apprenant_id=XX classe=... prestataire=... beneficiaire=...`

### Test 2: Enregistrer avec réponses modifiées
1. Allez sur la page Appels
2. Cliquez "Démarrer le registrement" sur une ligne
3. **MODIFIEZ** Q9 (Satisfaction globale) à 5
4. Ajoutez un commentaire: "Test OK"
5. Cliquez "Terminer l'appel et Sauvegarder"
6. ✅ **Attendu**:
   - SatisfactionApprenant.q9_satisfaction_globale = 5
   - commentaire = "Test OK"
   - Base de données enregistrée

### Test 3: Réouvrir pour vérifier persistence
1. Allez sur la page Appels
2. Sur le même appel que Test 2, cliquez "Démarrer le registrement" à nouveau
3. ✅ **Attendu**:
   - Q9 affiche la valeur 5 (cochée)
   - Commentaire affiche "Test OK"
   - Toutes les données précédentes sont restaurées

### Test 4: Enregistrer et consulter SatisfactionApprenant
1. Complétez Test 1 et Test 2
2. Allez sur la page "Satisfaction Apprenants"
3. Consultez le tableau "Dernières enquêtes"
4. ✅ **Attendu**:
   - Les deux enregistrements apparaissent
   - Q9 affiche les valeurs correctes
   - commentaire affiche les textes corrects

### Test 5: Consulter les logs pour apprenant_id, classe, prestataire
1. Après Test 1 ou Test 2
2. Consultez les logs Django (fichier ou console)
3. ✅ **Attendu**:
   ```
   Satisfaction enregistrée. apprenant_id=5 classe=CLASSE001 prestataire=PrestaXYZ beneficiaire=BeneXYZ
   ```

### Test 6: Audio + Questionnaire ensemble
1. Cliquez "Démarrer le registrement"
2. Enregistrez un audio (parlé quelque chose)
3. Modifiez une réponse (par ex. Q5 = 4)
4. Cliquez "Terminer l'appel et Sauvegarder"
5. ✅ **Attendu**:
   - Questionnaire enregistré avec Q5=4
   - Audio enregistré dans media/...
   - SatisfactionApprenant.audio_appel = fichier audio
   - Statut "termine"

---

## 📋 Fichiers Modifiés

### 1. `templates/appels/index.html`
**Lignes 754-772**: Récupération des réponses
- Toutes les réponses Q1-Q9 sont envoyées
- Formule: `const value = checked?.value || "3"`

**Lignes 988-1014**: Chargement des données précédentes  
- Charge pour TOUS les statuts
- Garde les commentaires/recommandations

### 2. `App_PADESCE/appels/views.py`

**Imports (ligne 3)**:
- Ajout: `import logging`
- Ajout: `logger = logging.getLogger(__name__)`  au niveau module

**Ligne 964-987**: `finalize_appel()` - Construction manual_data
- Toutes les réponses incluses (défaut "3")
- Plus de filtrage qui supprimait les réponses

**Lignes 1087-1189**: `_auto_process_satisfaction_from_appel()`
- Questionnaire d'abord, audio ensuite
- Gestion robuste des erreurs audio
- Logging avec métadonnées apprenant

---

## 🔍 Points d'attention

### ⚠️ Convertissez bien les chaînes en entiers
```python
# ✅ BON
int(results.get("q1_clarte_exposes") or 3)

# ❌ MAUVAIS  
int(results.get("q1_clarte_exposes", 3)) # Peut échouer si None
```

### ⚠️ Les commentaires/recommandations doivent avoir un défaut
```python
# ✅ BON
"commentaire": str(results.get("commentaire", "") or ""),
"recommandations": str(results.get("recommandations", "") or ""),

# ❌ MAUVAIS
"commentaire": results.get("commentaire"),  # Peut être None
```

### ⚠️ Ne pas filtrer les réponses avec valeur "3"
```python
# ❌ ANCIEN (BUG)
manual_data = {k: v for k, v in manual_data.items() if v is not None and v != ""}
# Ceci supprimait "3" puisque "3" != ""

# ✅ NOUVEAU
manual_data = {
    "q1_clarte_exposes": request.POST.get("q1") or "3",
    ...
}
```

---

## 📊 Schéma du flux de travail

```
Utilisateur clique "Démarrer le registrement"
         ↓
Modale s'ouvre avec Q1-Q9 (par défaut 3)
         ↓
Modale charge les réponses précédentes (si existe)
         ↓
Utilisateur peut modifier les réponses
         ↓
Utilisateur optionnel: Enregistre audio
         ↓
Utilisateur clique "Terminer et sauvegarder"
         ↓
JavaScript envoie TOUTES réponses Q1-Q9 (même "3") ← CHANGEMENT CLEF
         ↓
Serveur reçoit dans finalize_appel()
         ↓
Appel.status = "termine" ✅
         ↓
manual_data construit avec toutes les réponses ← CHANGEMENT CLEF
         ↓
_auto_process_satisfaction_from_appel() appelé
         ↓
Questionnaire enregistré EN PREMIER dans SatisfactionApprenant ← CHANGEMENT CLEF
         ↓
Audio/Transcription enregistré EN DEUXIÈME (si fourni)
         ↓
Logging: apprenant_id=%s classe=%s prestataire=%s beneficiaire=%s ← CHANGEMENT CLEF
         ↓
Utilisateur réouvre le même appel
         ↓
Modale charge les réponses depuis SatisfactionApprenant ✅
         ↓
Utilisateur voit toutes ses données précédentes ✅
```

---

## 🐛 Bugs Corrigés

| Bug | Symptôme | Solution |
|-----|----------|----------|
| Réponses non envoyées | Valeurs par défaut Q3=3 jamais sauvegardées | Toujours envoyer "3" si pas modifié |
| Données non restituées | Réouverture = données vides | Charger pour tous les statuts |
| Commentaires perdus | "RAS" à la place du texte | Garder après chargement |
| Audio traité avant questionnaire | Si erreur audio = données perdues | Questionnaire d'abord |
| Pas d'analyse possible | Aucune métadonnée apprenant | Logger avec apprenant_id |

---

## 💾 Validation de la base de données

Après les tests, vérifiez dans la base de données:

```sql
-- Vérifier SatisfactionApprenant
SELECT id, apprenant_id, classe_id, q1_clarte_exposes, q9_satisfaction_globale, 
       commentaire, audio_appel, created_at 
FROM satisfaction_apprenants 
ORDER BY created_at DESC 
LIMIT 5;

-- Vérifier Appel.status  
SELECT id, code, nom, status, updated_at 
FROM appels 
WHERE status = 'termine' 
ORDER BY updated_at DESC 
LIMIT 5;

-- Vérifier Transcription
SELECT id, apprenant_id, transcript, extracted_answers_json, created_at
FROM transcriptions
ORDER BY created_at DESC
LIMIT 5;
```

---

## 📞 Support

En cas de problème:
1. Consultez les logs Django: `tail -f logs/django.log`
2. Cherchez: `"Satisfaction enregistrée"` avec apprenant_id
3. Vérifiez que apprenant_id n'est pas "N/A"
4. Si "N/A": L'apprenant n'a pas été trouvé → Vérifiez code/tel/nom dans Appel

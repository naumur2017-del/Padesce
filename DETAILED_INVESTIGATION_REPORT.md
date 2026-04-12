# Detailed Technical Investigation Report
## Classeur.xlsx Class Import Issue  

**Date**: April 10, 2026  
**Issue**: Classes reported as "completed" then "not found"  
**Status**: ROOT CAUSE IDENTIFIED  

---

## EXECUTIVE SUMMARY

The Excel upload function in the satisfaction-formateurs module has a **critical design flaw**: 

✗ **It ONLY updates existing classes from Excel  
✗ It NEVER creates new classes  
✗ When a class code doesn't exist in the database, it returns "Classe XXX introuvable" error  

### What Likely Happened

1. User uploaded Classeur.xlsx with class codes: CLA001, CLA002, CLA004, CLA005, etc.
2. If 5 of these classes already existed in the database → They were successfully updated → "5 classes completed" message
3. If other classes (CLA003, etc.) DON'T exist in the database → "Classe CLA003 introuvable" error
4. User sees success for some classes, failures for others

---

## DETAILED CODE ANALYSIS

### 1. Entry Point: Upload Handler
**File**: `App_PADESCE/satisfaction_formateurs/views.py`  
**Function**: `satisfaction_formateurs_update_form_page()` (line 1173)  
**URL**: `/satisfaction-formateurs/analyse/update-form/`  
**HTTP Method**: POST  

```python
if action == "upload_classes_excel":
    uploaded_file = request.FILES.get("classes_excel_file")
    upload_result = _upload_classes_from_excel(uploaded_file, request.user)
    if upload_result["updated"]:
        messages.success(
            request,
            f"{upload_result['updated']} classe(s) completee(s) depuis Excel (Sheet1).",
        )
    for error in upload_result["errors"][:10]:  # Shows up to 10 errors
        messages.warning(request, error)
```

### 2. Upload Processing Function
**Function**: `_upload_classes_from_excel(uploaded_file, user)` (line 1109)  

**What it does**:
- Opens Excel file (expects Sheet1)
- Reads headers and normalizes them (removes spaces, lowercases)
- Iterates rows starting from row 2
- Extracts class code from these column aliases:  
  `classeid`, `classe`, `classid`, `codeclasse`
- Extracts optional fields (prestation, beneficiary, formation, cohort)
- **Calls `_apply_classes_batch_update_target()` for each row**
- Returns dict with: `{"updated": count, "errors": list, "processed": count}`

**Critical Code Section** (lines 1155-1167):
```python
for row_num, row_values in enumerate(
    worksheet.iter_rows(min_row=2, max_row=worksheet.max_row, values_only=True), start=2
):
    # ... build row_map from values ...
    class_code = _pick_excel_value(row_map, class_header_aliases)
    if not class_code:
        continue
    processed += 1
    
    payload = {
        "prestation_code": _pick_excel_value(...),
        "prestataire": _pick_excel_value(...),
        "beneficiaire": _pick_excel_value(...),
        "formation": _pick_excel_value(...),
        "cohorte": _pick_excel_value(...),
    }
    
    result = _apply_classes_batch_update_target(class_code, payload, user)
    if result["ok"]:
        updated += 1  # ← Only increments if class found AND updated
    elif len(errors) < 30:
        errors.append(f"Ligne {row_num} ({class_code}): {result['message']}")
```

### 3. The Critical Function: Class Lookup (NO CREATION)
**Function**: `_apply_classes_batch_update_target(class_code, payload, user)` (line 992)  

**Flow**:

```
┌─ class_code="CLA001", payload={prestation_code: "PS123", ...}
│
├─ Query Database: Classe.objects.filter(code__iexact="CLA001").first()
│   │
│   ├─ IF FOUND → Update fields and return {"ok": True}
│   │
│   └─ IF NOT FOUND → Return {"ok": False, "message": "Classe CLA001 introuvable."}
│       │
│       └─ NO ATTEMPT TO CREATE
```

**Exact Code** (lines 1001-1010):
```python
classe = (
    Classe.objects.select_related("prestation__prestataire", "prestation__beneficiaire", "formation")
    .filter(code__iexact=class_code)
    .first()
)
if classe is None:
    result["message"] = f"Classe {class_code} introuvable."
    return result
```

**Why Creation is Missing**:
- The payload HAS the required data (prestation_code, formation, etc.)
- But the code never attempts `Classe.objects.create()`
- It only attempts `classe.save(update_fields=[...])`

### 4. What Fields Can Be Updated

When a class IS found (lines 1020-1050), these fields can be updated:

| Field | From Excel | Requirement |
|-------|-----------|-------------|
| `intitule_formation` | `formation`, `intituledelaformation`, `titreformation` | Optional - auto-populates from prestation if not provided |
| `prestation` | `prestation_code`, `prestationid`, `codeprestation` | Optional |
| `cohorte` | `cohorte`, `nombrecohorte` | Optional - must be numeric |

**NOT Updated**:
- `code` (immutable - prevents accidental changes)
- `formation` (auto-set from prestation)
- `lieu`, `formateur` (not in Excel import)

---

## CLASSE MODEL SCHEMA

**From**: `App_PADESCE/formations/models.py` (line 141-165)

```python
class Classe(TimeStampedModel):
    code = CharField(max_length=20, unique=True)          # ← UNIQUE KEY
    prestation = ForeignKey(Prestation, CASCADE)          # ← REQUIRED (no null allowed)
    formation = ForeignKey(Formation, CASCADE)            # ← REQUIRED (auto-set from prestation)
    intitule_formation = CharField(max_length=255)        # ← REQUIRED
    lieu = ForeignKey(Lieu, SET_NULL, null=True)          # ← OPTIONAL
    formateur = ForeignKey(Formateur, SET_NULL, null=True) # ← OPTIONAL
    fenetre = CharField(max_length=50, blank=True)        # ← OPTIONAL
    cohorte = PositiveIntegerField(default=1)             # ← Default 1
    statut = CharField(choices=[...], default="non_demarre") # ← Default
    actif = BooleanField(default=True)                    # ← Default
```

**To CREATE a new Classe, you MUST provide**:
1. `code` (unique)
2. `prestation` (FK to Prestation model)
3. `formation` (FK to Formation model)
4. `intitule_formation` (string)

---

## THE MESSAGING CONFUSION

### What User Sees vs. What Actually Happened

**Scenario A: Some classes exist, some don't**
```
Classeur.xlsx contains: CLA001, CLA002, CLA003, CLA004, CLA005

DB before import:        CLA001, CLA002, CLA005 exist
                         CLA003, CLA004 DO NOT exist

After import:
✓ CLA001 updated
✓ CLA002 updated  
✗ CLA003 error: "Classe CLA003 introuvable."
✗ CLA004 error: "Classe CLA004 introuvable."
✓ CLA005 updated

Messages shown:
SUCCESS: "3 classe(s) completee(s) depuis Excel (Sheet1)."
WARNING: "Ligne 4 (CLA003): Classe CLA003 introuvable."
WARNING: "Ligne 5 (CLA004): Classe CLA004 introuvable."
```

**User Interpretation**: "It says 3 completed but CLA003 and CLA004 are not found!"

---

## RELATED FUNCTIONS THAT USE CLASS LOOKUP

### AppelFormateur Resolution
**Function**: `_resolve_batch_update_formateur_classe(row)` (line 589)
- Delegates to imported function from appels module
- Used to find Classe for AppelFormateur rows
- Will return None if class doesn't exist (no error thrown)

### Formateur Finder
**Function**: `_find_formateur(classe_id, identifiant)` (line 55-64)
```python
classe = Classe.objects.select_related("formateur").filter(id=classe_id).first()
if not classe:
    return None, "Classe introuvable."  # ← Error message matches the issue!
```

---

## WHERE CLASSES SHOULD BE CREATED

The system expects classes to be created via:

1. **Manual UI**: `/formations/classes/nouveau/` (views.py line 812)
   - User selects prestation
   - Code is auto-generated (CLA###)
   - Formation is auto-populated from prestation
   
2. **Other import processes**:
   - Not via Excel for satisfaction-formateurs module
   - Would need custom command if batch creation is needed

---

## PROOF: Excel Does NOT Create Classes

**Test Case**:
1. Upload Classeur.xlsx with new class code "TESTXYZ"
2. "TESTXYZ" doesn't exist in database
3. Result: "Classe TESTXYZ introuvable." error
4. Class is still NOT created

**Contrast with Working Imports**:
- Appels import: Can update existing appels - no creation needed
- Apprenants import: Creates apprenants within classes - classes must pre-exist
- Network consolidation: Links to existing classes - creates Appels if classe exists

---

## SOLUTION CHECKLIST

### ✓ CONFIRMED ROOT CAUSES
- [x] Excel upload function only updates, never creates
- [x] Missing classes return "intro introuvable" error
- [x] Payload data (prestation) is collected but never used for creation
- [x] Error messages show correct class codes
- [x] Success count is accurate (only counts updated classes)

### TO FIX (3 Options)

**Option 1: Implement Class Creation** ⭐ RECOMMENDED
- Modify `_apply_classes_batch_update_target()` to create classes if they don't exist
- Requires: prestation_code in Excel must be valid
- Validation: Check that prestation exists before creating class

**Option 2: Require Class Pre-Creation**
- Document that classes must exist before Excel import
- Update UI to be clearer ("Update only - does not create")
- Provide separate class creation flow

**Option 3: Hybrid Approach**
- Create management command for batch class creation from Excel
- Keep update-only behavior for web UI

---

## RELATED CODE LOCATIONS (Reference Links)

| Component | File | Line(s) |
|-----------|------|---------|
| Upload view | views.py | 1173 |
| Upload function | views.py | 1109 |
| Update-only function | views.py | 992 |
| Class model | models.py | 141 |
| Manual class creation | views.py | 812 |
| URL routing | urls.py | 36-40 |
| Error messages | views.py | 1010, 1025, 830 |
| Form definition | forms.py | 1+ |

---

## VERIFICATION STEPS

To confirm this analysis:

1. **Check database**: Query `SELECT code FROM formations_classe WHERE code LIKE 'CLA%'`
   - Verify which CLA classes exist
   
2. **Check Classeur.xlsx**: 
   - What class codes does it contain?
   - Which ones are in the database?
   
3. **Check error logs**:
   - Look for "Classe XXX introuvable" messages
   - Timestamps should match upload attempt
   
4. **Test fix**:
   - Add class creation logic to `_apply_classes_batch_update_target()`
   - Re-upload same file
   - Should succeed without "introuvable" errors

---

## CONCLUSION

**The issue is NOT a bug - it's a design decision that was not communicated properly.**

The Excel upload feature was designed to UPDATE existing class records, not CREATE new ones. When users try to upload new class codes that don't exist in the database, they get "not found" errors.

**The fix requires modifying the Excel import logic to support class creation**, which is a medium-complexity change that needs careful attention to:
- Validating prestation exists
- Handling formation assignment  
- Creating related records if missing
- Providing clear error messages for missing data

---

**Report Generated**: 2026-04-10  
**Analysis Complete**: ✓

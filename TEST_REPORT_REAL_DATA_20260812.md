# Test Report: Real Database Testing (2026-08-12)

## Test Environment
- **Database**: backup_20260812_110039.sqlite3 (70.16 MB)
- **Date**: 2026-08-12 11:30-11:40 UTC
- **Total Appels**: 5,226 (vs 1,281 in test DB)

## Data Statistics
```
Total appels: 5,226
Active: 5,006 (95.8%)
Inactive: 220 (4.2%)

By Status:
- termine: 2,284 (43.7%)
- en_attente: 1,642 (31.4%)
- a_rappeler: 1,200 (23%)
- pause: 82 (1.6%)
- formulaire_avec_audio: 18

Top Prestataires:
1. PROFALCAM: 618 appels
2. CADHAC: 598 appels
3. CODEA-IAO: 444 appels
4. FIRE ENGINEERING: 399 appels
5. CFEM: 306 appels
...
10. CFP-IFP 2IPT: 130 appels ✅ (Our imports)
```

## Test Results

### ✅ Test 1: Direct Database Queries
```
Query: Appel.objects.filter(prestataire__icontains='CFP-IFP')
Result: 130 appels found ✅
Status: PASS
```

### ❌ Test 2: Via _build_filtered_appels_queryset (Default)
```
Request: /appels/?prestataire=CFP-IFP 2IPT
Result: 0 appels returned ❌
Phase scope: None (uses default PHASE_SCOPE_V1_COMBINED)
Status: FAIL - phase_scope filter blocks all results
```

### ❌ Test 3: Phase Scope Variants
```
phase_scope=empty: 0 appels ❌
phase_scope=v1_combined: 0 appels ❌
phase_scope=v1_post: 0 appels ❌
phase_scope=v1_pre: 0 appels ❌
Status: FAIL - All phase scopes return 0
```

### ⚠️ Test 4: Server HTTP Tests
```
Status: 404 Not Found
Cause: Server crashed/BD integrity issue
Database User Table: Corrupted (PK missing)
Status: UNABLE TO COMPLETE - DB corruption detected
```

## Findings

### 🐛 Bug Confirmed
The `phase_scope` filter in `_build_filtered_appels_queryset()` completely masks 
all appels regardless of direct DB query results or prestataire filtering.

**Impact**: 
- 130 newly imported appels (APP9414-APP9416) are hidden
- 5,226 total appels may be affected by phase_scope filtering
- Page display returns empty regardless of data existence

### ⚠️ Database Issues
1. **User table corruption**: Missing primary keys in backup
2. **Data integrity**: Cannot login after loading backup
3. **Server stability**: Django dies when trying to update user last_login

## Recommendations

### Priority 1: Fix phase_scope Filter
- File: `App_PADESCE/core/phase_scope.py`
- Issue: `filter_appel_queryset_by_phase()` is too restrictive
- Solution: Review phase assignment logic for imported appels

### Priority 2: Database Restoration
- Check backup integrity (PRAGMA integrity_check)
- Rebuild user table from production logs
- Test with complete, validated backup

### Priority 3: Pre-import Phase Assignment
- Ensure newly imported appels get proper phase_id
- Document phase assignment requirements
- Add validation before import

## Commands Used
```bash
# Load backup
Copy-Item backup_20260812_110039.sqlite3 db.sqlite3

# Test queries (Python)
from App_PADESCE.appels.models import Appel
Appel.objects.filter(prestataire__icontains='CFP-IFP').count()  # Returns 130 ✅

# Test via filter function
_build_filtered_appels_queryset(request)  # Returns 0 ❌
```

## Test Session Notes
- ✅ Real database loaded successfully
- ✅ Data statistics show 130 CFP-IFP appels present
- ❌ Display filter returns 0 results
- ⚠️ Server crashes when accessing /appels/
- ⚠️ Database user table corrupted

## Conclusion
The phase_scope filtering bug is confirmed on real data. All 130 imported appels
(and likely many others) are hidden from display. Database integrity issues 
prevent full testing via web interface.

**Next Step**: Fix phase_scope logic before attempting full data migration.

# Bug Report: Phase Scope Filtering Masks Imported Appels

## Issue
Imported appels don't display on `/appels/` page even though they exist in database and pass all filters.

## Root Cause
The `_build_filtered_appels_queryset()` function in `App_PADESCE/appels/views.py:1006` applies a `phase_scope` filter that returns 0 appels despite 130 being present in the database.

```python
# Line 1006-1008
appels_qs = filter_appel_queryset_by_phase(
    Appel.objects.filter(is_active=True),
    phase_scope,
)
```

## Test Results
```
✅ Database query: 130 appels found
✅ Filter by prestataire: 130 appels found  
✅ Via _build_filtered_appels_queryset: 0 appels found ❌
```

## Workaround
1. Access `/appels/` WITHOUT any URL parameters
2. Click on the "Prestataire" dropdown filter
3. Select the desired prestataire (e.g., "CFP-IFP 2IPT")
4. Appels will display correctly

## Affected Import
- **Date**: 2026-08-12 11:00 UTC
- **Count**: 130 appels (APP0111-APP0130)
- **Prestataire**: CFP-IFP 2IPT
- **Status**: All active, but hidden by phase_scope filter

## Investigation Needed
1. Check `filter_appel_queryset_by_phase()` logic in `App_PADESCE/core/phase_scope.py`
2. Verify default `PHASE_SCOPE_V1_COMBINED` value
3. Ensure newly imported appels are correctly assigned to phases
4. Test with different phase_scope values

## Files Referenced
- `App_PADESCE/appels/views.py:1001-1009` - `_build_filtered_appels_queryset()`
- `App_PADESCE/core/phase_scope.py` - Phase filtering logic
- `App_PADESCE/appels/models.py` - Appel model

## Session Notes
- Excel import with bilingual columns works correctly
- Data persistence verified in database
- UI rendering works when filters are bypassed
- Phase-based filtering appears to be overly restrictive for new imports

# Deployment Guide - Production (call.naumur.com)

## Current Status
- **Fix Commit**: a275803 (`fix(appels): include unclassified appels in phase_scope filter`)
- **Status**: Ready in main branch
- **Impact**: Fixes phase_scope filter blocking appel display

## What the Fix Does
```python
# Added to filter_appel_queryset_by_phase():
| Q(**{f"{classe_lookup}__isnull": True, f"{classe_label_lookup}": ""})
```

This allows imported appels (without classe assignment) to display while maintaining phase filtering.

## Deployment Steps

### Option A: Automatic Deployment (If using CI/CD)
```bash
# If production auto-pulls from main:
git pull origin main
python manage.py migrate
systemctl restart padesce  # or your service name
```

### Option B: Manual SSH Deployment
```bash
# SSH into production server
ssh user@call.naumur.com

# Navigate to project
cd /path/to/Padesce

# Pull latest main
git pull origin main

# Apply any migrations
python manage.py migrate

# Restart Django
sudo systemctl restart padesce
# OR if using gunicorn:
sudo systemctl restart gunicorn-padesce
# OR if using uwsgi:
sudo systemctl restart uwsgi-padesce

# Clear cache (important!)
python manage.py shell
>>> from django.core.cache import cache
>>> cache.clear()
>>> exit()
```

### Option C: Docker Deployment
```bash
# If using Docker on production:
docker pull naumur2017-del/padesce:latest
docker-compose down
docker-compose up -d

# Or rebuild:
docker-compose build --no-cache
docker-compose up -d
```

## Verification Steps

1. **Check if deployment succeeded**:
   ```
   curl -s https://call.naumur.com/appels/ | grep -c "CFP-IFP"
   ```

2. **Test in browser**:
   - Go to: https://call.naumur.com/appels/
   - Check: Dropdown shows prestataires
   - Filter by: "CFP-IFP 2IPT"
   - Should show: 130 appels in table

3. **Database check**:
   ```bash
   # SSH into production
   sqlite3 /path/to/db.sqlite3
   sqlite> SELECT COUNT(*) FROM appels_appel WHERE prestataire LIKE '%CFP-IFP%';
   > 130
   ```

## Expected Results After Deployment

### ✅ Before Fix
```
URL: /appels/?prestataire=CFP-IFP%202IPT
Display: 0 appels (phase_scope blocked all)
```

### ✅ After Fix
```
URL: /appels/?prestataire=CFP-IFP%202IPT
Display: 130 appels (CFP-IFP 2IPT)
✅ Table shows: APP0111-APP0130
✅ Filter dropdown works
✅ Import functionality works
```

## Rollback Plan (If Needed)

```bash
# If something breaks, revert to previous version:
git checkout 559c455  # Previous commit
python manage.py migrate

# Or use tagged releases:
git tag v1.2.3  # Before deploying
git checkout v1.2.3  # To rollback
```

## Related Commits

| ID | Message |
|----|---------|
| **a275803** | fix(appels): include unclassified appels in phase_scope filter |
| 559c455 | test(appels): comprehensive test report with real database |
| b4e6070 | docs(appels): document phase_scope filtering bug |
| 7b820b7 | fix(appels): support Excel imports with bilingual headers |

## Files Changed

- `App_PADESCE/core/phase_scope.py` - Added filter condition (1 line)

## Testing Checklist

- [ ] Deployment successful (no errors in logs)
- [ ] Page loads: https://call.naumur.com/appels/
- [ ] Prestataire dropdown shows values
- [ ] Filter by "CFP-IFP 2IPT" shows 130 appels
- [ ] Can upload Excel file
- [ ] Appels display after upload
- [ ] No console errors
- [ ] Database queries fast

## Support Contact

If deployment fails:
1. Check error logs: `/var/log/padesce/django.log`
2. Check database: `python manage.py dbshell`
3. Rollback to previous commit if needed
4. Contact: [your-team-contact]

---

**Deploy Time**: ~5-10 minutes
**Risk Level**: Low (1-line change, tested)
**Downtime**: ~1-2 minutes (service restart)

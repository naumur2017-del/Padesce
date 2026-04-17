import csv
import os
import sys
import django

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
django.setup()

from App_PADESCE.apprenants.models import Apprenant

def run():
    absents_path = r'D:\Documents\NAUMUR\tmp_apprenants_absents_excel.csv'
    incomplets_path = r'D:\Documents\NAUMUR\tmp_apprenants_controles_incomplets.csv'

    # 1. Absents
    if os.path.exists(absents_path):
        with open(absents_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            ids = [row['apprenant_id'].strip() for row in reader]
            print(f"Read {len(ids)} IDs from absents csv")
            count = Apprenant.objects.filter(code__in=ids).update(c1='', c2='', c3='', c4='')
            print(f"Updated {count} absents (C1-C4 set to empty)")
    else:
        print(f"File not found: {absents_path}")

    # 2. Incomplets
    if os.path.exists(incomplets_path):
        with open(incomplets_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            updated_count = 0
            processed_rows = 0
            for row in reader:
                processed_rows += 1
                app_id = row['apprenant_id'].strip()
                missing_str = row.get('missing_controls', '')
                if not missing_str:
                    continue
                missing = missing_str.lower().split('/')
                updates = {}
                for col in missing:
                    col = col.strip()
                    if col in ['c1', 'c2', 'c3', 'c4']:
                        updates[col] = ''
                if updates:
                    res = Apprenant.objects.filter(code=app_id).update(**updates)
                    updated_count += res
                    if app_id == 'APP005':
                        print(f"DEBUG: Found APP005, missing={missing}, updates={updates}, result={res}")
            print(f"Processed {processed_rows} rows from incomplets csv, updated {updated_count} records")
    else:
        print(f"File not found: {incomplets_path}")

if __name__ == "__main__":
    run()

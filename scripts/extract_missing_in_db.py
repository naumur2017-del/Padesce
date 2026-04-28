"""Extract codes with status 'missing_in_db' from a db_sync_summary JSON file and write CSV."""
import sys
import json
import csv
from pathlib import Path

def main(summary_path):
    p = Path(summary_path)
    out = p.with_suffix('.missing_in_db.csv')
    data = json.loads(p.read_text())
    # data expected to be a list of objects with {code, status}
    missing = [item.get('code') for item in data if item.get('status') == 'missing_in_db']
    with out.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['code'])
        for c in missing:
            writer.writerow([c])
    print(f'Wrote {len(missing)} codes to {out}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: extract_missing_in_db.py <db_sync_summary.json>')
        sys.exit(2)
    main(sys.argv[1])

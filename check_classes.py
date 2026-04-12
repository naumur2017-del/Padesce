#!/usr/bin/env python
import sqlite3
import sys

db_path = 'db.sqlite3'
try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Count total classes
    cursor.execute('SELECT COUNT(*) FROM formations_classe')
    total = cursor.fetchone()[0]
    print(f'Total classes in database: {total}')
    
    # Find CLA classes
    cursor.execute('SELECT code FROM formations_classe WHERE code LIKE "CLA%" ORDER BY code')
    cla_rows = cursor.fetchall()
    print(f'\nCLA-prefixed classes ({len(cla_rows)}):')
    for row in cla_rows[:20]:
        print(f'  {row[0]}')
    
    if len(cla_rows) > 20:
        print(f'  ... and {len(cla_rows) - 20} more')
    
    # Check for the specific classes mentioned
    print('\nChecking for specific classes from uploads:')
    for code in ['CLA001', 'CLA002', 'CLA003', 'CLA004', 'CLA005']:
        cursor.execute('SELECT id FROM formations_classe WHERE code = ?', (code,))
        result = cursor.fetchone()
        print(f'  {code}: {"EXISTS" if result else "NOT FOUND"}')
    
    cursor.close()
    conn.close()
except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)

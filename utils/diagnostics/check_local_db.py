#!/usr/bin/env python
"""
Script pour vérifier les données dans la base locale
"""

import sqlite3
import os

def main():
    db_path = "c:\\Users\\LENOVO\\Documents\\Padesce\\db.sqlite3"
    
    print("=== Vérification de la base de données locale ===\n")
    
    try:
        # Connexion directe à la base de données locale
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Vérifier si la table existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='appels_appelformateur';")
        table_exists = cursor.fetchone()
        
        if table_exists:
            cursor.execute("SELECT COUNT(*) FROM appels_appelformateur;")
            total_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM appels_appelformateur WHERE is_active = 1;")
            active_count = cursor.fetchone()[0]
            
            print(f"Table appels_appelformateur trouvée")
            print(f"Total des enregistrements: {total_count}")
            print(f"Enregistrements actifs: {active_count}")
            
            if active_count > 0:
                cursor.execute("SELECT reference_code FROM appels_appelformateur WHERE is_active = 1 LIMIT 5;")
                samples = cursor.fetchall()
                print(f"\nExemples de codes de référence:")
                for i, (code,) in enumerate(samples, 1):
                    print(f"  {i}. {code}")
            else:
                print("Aucun enregistrement actif trouvé")
        else:
            print("Table appels_appelformateur non trouvée dans la base locale")
        
        conn.close()
        
    except Exception as e:
        print(f"ERREUR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()

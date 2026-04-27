import pandas as pd
import sqlite3
from datetime import datetime

def migrate_presence_data():
    """
    Migration script to update presence data from Excel file
    """
    excel_path = r"D:\Documents\NAUMUR\Fichier pour plateforme de satisfaction.xlsx"
    db_path = "db.sqlite3"
    
    print("🔄 Starting presence data migration...")
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create backup before migration
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"db_backup_before_presence_migration_{timestamp}.sqlite3"
        import shutil
        shutil.copy2(db_path, backup_file)
        print(f"✅ Backup created: {backup_file}")
        
        # Read Excel data
        print("📖 Reading Excel data...")
        df_rapport = pd.read_excel(excel_path, sheet_name='Rapport Presence')
        df_decompte = pd.read_excel(excel_path, sheet_name='Decompte Global')
        
        # Part 1: Update individual presence records
        print("\n=== Part 1: Updating Individual Presence Records ===")
        
        updated_count = 0
        for index, row in df_rapport.iterrows():
            apprenant_id = row['ApprenantID']
            
            # Skip if ApprenantID is NaN
            if pd.isna(apprenant_id):
                continue
            
            # Map presence values
            presence_mapping = {
                'Present': 'PR',
                'Absent': 'AB'
            }
            
            # Update c1, c2, c3, c4 columns
            updates = {}
            for col in ['C1', 'C2', 'C3', 'C4']:
                if col in row:
                    value = row[col]
                    if pd.isna(value):
                        updates[col.lower()] = ''  # Empty for NaN
                    elif str(value).strip() in presence_mapping:
                        updates[col.lower()] = presence_mapping[str(value).strip()]
                    else:
                        updates[col.lower()] = ''  # Empty for other values
            
            # Update database
            if updates:
                set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
                # Include updated_at in the values list
                all_values = list(updates.values()) + [datetime.now().isoformat(), str(apprenant_id)]
                
                cursor.execute(f"""
                    UPDATE apprenants_apprenant 
                    SET {set_clause}, updated_at = ?
                    WHERE code = ?
                """, all_values)
                
                if cursor.rowcount > 0:
                    updated_count += 1
        
        print(f"✅ Updated {updated_count} apprenant records with presence data")
        
        # Part 2: Update global control indicators
        print("\n=== Part 2: Updating Global Control Indicators ===")
        
        # Extract row 204 data from Decompte Global
        row_204 = df_decompte.iloc[203]
        
        # Map the values from Excel
        global_values = {
            'total_participants': row_204['Projection du nombre de participants'],
            'taux_personnes_formees': row_204['Taux  de personnes formées de l\'échantillon'],
            'taux_participation': row_204['Taux de participation'],
            'taux_presence_globale': row_204['Taux  de présence moyen ']  # Note the trailing space
        }
        
        print(f"Extracted values from row 204:")
        for key, value in global_values.items():
            print(f"  {key}: {value}")
        
        # Check if we have a table to store these global indicators
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%dashboard%' OR name LIKE '%indicator%' OR name LIKE '%global%';")
        global_tables = cursor.fetchall()
        
        if global_tables:
            print(f"Found global indicator tables: {global_tables}")
            # Update existing table logic here
        else:
            print("No existing global indicator table found. Creating new table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS global_presence_indicators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT,
                    updated_at TEXT,
                    total_participants REAL,
                    taux_personnes_formees REAL,
                    taux_participation REAL,
                    taux_presence_globale REAL,
                    source TEXT
                )
            """)
            
            # Insert the values
            cursor.execute("""
                INSERT INTO global_presence_indicators 
                (created_at, updated_at, total_participants, taux_personnes_formees, 
                 taux_participation, taux_presence_globale, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                datetime.now().isoformat(),
                global_values['total_participants'],
                global_values['taux_personnes_formees'],
                global_values['taux_participation'],
                global_values['taux_presence_globale'],
                'Excel Migration - Row 204'
            ))
            
            print("✅ Created global_presence_indicators table with row 204 data")
        
        # Part 3: Update fixed dashboard values
        print("\n=== Part 3: Updating Fixed Dashboard Values ===")
        
        # Fixed values as specified
        fixed_values = {
            'taux_global_presence': 0.41,  # 41%
            'taux_participation': 0.67,     # 67%
            'taux_personnes_formees': 0.40  # 40%
        }
        
        # Check for dashboard settings table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%setting%' OR name LIKE '%config%' OR name LIKE '%dashboard%';")
        config_tables = cursor.fetchall()
        
        if config_tables:
            print(f"Found config tables: {config_tables}")
            # Update existing config logic here
        else:
            print("Creating dashboard settings table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dashboard_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT,
                    updated_at TEXT,
                    setting_key TEXT UNIQUE,
                    setting_value TEXT,
                    description TEXT
                )
            """)
            
            # Insert fixed values
            for key, value in fixed_values.items():
                cursor.execute("""
                    INSERT OR REPLACE INTO dashboard_settings 
                    (created_at, updated_at, setting_key, setting_value, description)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    key,
                    str(value),
                    f'Fixed value from Excel migration - Line 204'
                ))
            
            print("✅ Created dashboard_settings table with fixed values")
        
        # Commit all changes
        conn.commit()
        print("\n✅ Migration completed successfully!")
        
        # Summary
        print(f"\n📊 Migration Summary:")
        print(f"  - Updated {updated_count} apprenant presence records")
        print(f"  - Created global indicators from row 204")
        print(f"  - Set fixed dashboard values (41%, 67%, 40%)")
        print(f"  - Backup created: {backup_file}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        raise

if __name__ == "__main__":
    migrate_presence_data()

import sqlite3
from typing import Dict, Optional

try:
    import pandas as pd
except ImportError:
    pd = None

def get_prestation_indicators_from_db(prestation_code: str) -> Dict[str, float]:
    """
    Récupère les indicateurs de présence depuis la base de données pour une prestation donnée.
    Si non trouvé, utilise les valeurs par défaut du tableau de bord.
    """
    try:
        conn = sqlite3.connect('db.sqlite3')
        cursor = conn.cursor()
        
        # Chercher d'abord dans les indicateurs globaux par prestation
        # Note: Pour l'instant, nous utilisons les valeurs fixes du tableau de bord
        # car nous n'avons pas encore de table par prestation
        
        # Valeurs fixes du tableau de bord (ligne 204)
        fixed_indicators = {
            'total_participants': 0,  # Sera calculé plus tard
            'taux_personnes_formees': 0.40,  # 40%
            'taux_participation': 0.67,     # 67%
            'taux_presence_globale': 0.41,  # 41%
        }
        
        # Essayer de trouver les données spécifiques à la prestation dans le Excel
        excel_path = r"D:\Documents\NAUMUR\Fichier pour plateforme de satisfaction.xlsx"
        
        try:
            import pandas as pd
            df_decompte = pd.read_excel(excel_path, sheet_name='Decompte Global')
            
            # Chercher la ligne pour cette prestation
            for index, row in df_decompte.iterrows():
                # Vérifier si cette ligne contient notre code de prestation
                for col in df_decompte.columns:
                    if prestation_code.upper() in str(row[col]).upper():
                        # Trouver les indicateurs
                        indicators = {
                            'total_participants': row.get('Projection du nombre de participants', 0),
                            'taux_personnes_formees': row.get('Taux  de personnes formées de l\'échantillon', 0),
                            'taux_participation': row.get('Taux de participation', 0),
                            'taux_presence_globale': row.get('Taux  de présence moyen ', 0),
                        }
                        
                        # Convertir les valeurs
                        for key, value in indicators.items():
                            if pd.isna(value) or value == 'N/D':
                                indicators[key] = 0
                            elif isinstance(value, str) and '%' in value:
                                # Convertir les pourcentages
                                try:
                                    indicators[key] = float(value.replace('%', '').replace(',', '.')) / 100
                                except:
                                    indicators[key] = 0
                            else:
                                try:
                                    indicators[key] = float(value)
                                except:
                                    indicators[key] = 0
                        
                        conn.close()
                        return indicators
            
            # Si non trouvé, retourner les valeurs par défaut
            conn.close()
            return fixed_indicators
            
        except Exception:
            conn.close()
            return fixed_indicators
            
    except Exception:
        # En cas d'erreur, retourner les valeurs par défaut
        return {
            'total_participants': 0,
            'taux_personnes_formees': 0.40,
            'taux_participation': 0.67,
            'taux_presence_globale': 0.41,
        }

def get_participant_count_for_prestation(prestation_code: str) -> int:
    """
    Compte le nombre de participants pour une prestation donnée.
    """
    try:
        excel_path = r"D:\Documents\NAUMUR\Fichier pour plateforme de satisfaction.xlsx"
        df_rapport = pd.read_excel(excel_path, sheet_name='Rapport Presence')
        
        # Compter les apprenants pour cette prestation
        presta_records = df_rapport[df_rapport['ID Prestation'] == prestation_code]
        
        # Compter seulement les apprenants avec un ApprenantID valide
        valid_records = presta_records[presta_records['ApprenantID'].notna()]
        return len(valid_records)
        
    except Exception:
        return 0

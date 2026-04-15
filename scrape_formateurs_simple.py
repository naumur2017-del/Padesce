#!/usr/bin/env python3
"""
Script simplifié pour extraire les formateurs depuis le site web call.naumur.com
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re

def scrape_formateurs():
    """
    Extrait les formateurs depuis le site web
    """
    url = "https://call.naumur.com/?scope=formateur&section=principal"
    
    print("Extraction des formateurs depuis le site web...")
    
    try:
        # Requête simple sans headers complexes
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        print(f"Status: {response.status_code}")
        
        # Parser le HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Chercher tous les tableaux
        tables = soup.find_all('table')
        print(f"Tableaux trouvés: {len(tables)}")
        
        formateurs = []
        
        for i, table in enumerate(tables):
            print(f"\nAnalyse du tableau {i+1}:")
            
            # Extraire les lignes
            rows = table.find_all('tr')
            print(f"  Lignes trouvées: {len(rows)}")
            
            if len(rows) <= 1:
                continue
            
            # Extraire les en-têtes
            headers = []
            for th in rows[0].find_all(['th', 'td']):
                headers.append(th.get_text(strip=True))
            
            print(f"  Colonnes: {headers}")
            
            # Vérifier si c'est un tableau de formateurs
            header_text = ' '.join(headers).lower()
            if any(keyword in header_text for keyword in ['nom', 'téléphone', 'telephone', 'tel', 'phone']):
                print("  -> Tableau de formateurs détecté!")
                
                # Extraire les données
                for row in rows[1:]:  # Skip header
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        formateur = {}
                        
                        for j, cell in enumerate(cells):
                            if j < len(headers):
                                header_name = headers[j].lower()
                                cell_text = cell.get_text(strip=True)
                                
                                # Mapper les colonnes importantes
                                if any(keyword in header_name for keyword in ['nom', 'name']):
                                    formateur['nom'] = cell_text
                                elif any(keyword in header_name for keyword in ['téléphone', 'telephone', 'tel', 'phone']):
                                    # Nettoyer le numéro de téléphone
                                    phone = re.sub(r'[^\d+]', '', cell_text)
                                    formateur['telephone'] = phone
                                elif any(keyword in header_name for keyword in ['prestataire', 'prestation']):
                                    formateur['prestataire'] = cell_text
                                elif any(keyword in header_name for keyword in ['formation', 'classe', 'cohorte']):
                                    formateur['formation'] = cell_text
                        
                        # Ajouter seulement si on a un nom ou un téléphone
                        if formateur.get('nom') or formateur.get('telephone'):
                            formateurs.append(formateur)
                
                print(f"  -> {len(formateurs)} formateurs extraits")
        
        print(f"\nTotal des formateurs extraits: {len(formateurs)}")
        return formateurs
        
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()
        return []

def read_excel_formateurs():
    """
    Lit le fichier Excel pour extraire les formateurs
    """
    excel_file = "fichier_concatene (1) 1 (1).xlsx"
    
    try:
        df = pd.read_excel(excel_file, engine='openpyxl')
        print(f"Fichier Excel lu: {df.shape}")
        
        formateurs = []
        
        for index, row in df.iterrows():
            if index >= 200:  # Limiter
                break
            
            formateur = {
                'nom': '',
                'telephone': '',
                'prestataire': '',
                'formation': '',
                'ligne_excel': index + 2
            }
            
            # Chercher les colonnes de formateurs
            for col_name, value in row.items():
                if pd.isna(value):
                    continue
                
                col_str = str(col_name).lower()
                val_str = str(value).strip()
                
                if 'formateur' in col_str and 'nom' in col_str:
                    formateur['nom'] = val_str
                elif 'formateur' in col_str and 'téléphone' in col_str:
                    phone = re.sub(r'[^\d+]', '', val_str)
                    formateur['telephone'] = phone
                elif 'prestataire' in col_str:
                    formateur['prestataire'] = val_str
                elif 'formation' in col_str:
                    formateur['formation'] = val_str
            
            if formateur['nom'] or formateur['telephone']:
                formateurs.append(formateur)
        
        print(f"Formateurs extraits du Excel: {len(formateurs)}")
        return formateurs
        
    except Exception as e:
        print(f"Erreur lecture Excel: {e}")
        return []

def create_comparison(web_formateurs, excel_formateurs):
    """
    Crée le tableau de comparaison
    """
    comparison = []
    
    # Créer des dictionnaires pour la recherche
    web_by_phone = {f['telephone'].strip(): f for f in web_formateurs if f.get('telephone')}
    excel_by_phone = {f['telephone'].strip(): f for f in excel_formateurs if f.get('telephone')}
    
    all_phones = set(web_by_phone.keys()) | set(excel_by_phone.keys())
    
    for phone in all_phones:
        web = web_by_phone.get(phone)
        excel = excel_by_phone.get(phone)
        
        comparison.append({
            'Téléphone': phone,
            'Nom_Site': web.get('nom', '') if web else '',
            'Prestataire_Site': web.get('prestataire', '') if web else '',
            'Formation_Site': web.get('formation', '') if web else '',
            'Nom_Excel': excel.get('nom', '') if excel else '',
            'Prestataire_Excel': excel.get('prestataire', '') if excel else '',
            'Formation_Excel': excel.get('formation', '') if excel else '',
            'Ligne_Excel': excel.get('ligne_excel', '') if excel else '',
            'Statut': 'Présent dans les deux' if web and excel else ('Seulement site web' if web else 'Seulement fichier Excel')
        })
    
    # Trier par téléphone
    comparison.sort(key=lambda x: x['Téléphone'])
    
    return comparison

def main():
    """
    Fonction principale
    """
    print("Début de l'extraction des formateurs...")
    print("=" * 50)
    
    # 1. Scraper le site
    web_formateurs = scrape_formateurs()
    
    # 2. Lire Excel
    excel_formateurs = read_excel_formateurs()
    
    # 3. Créer la comparaison
    comparison = create_comparison(web_formateurs, excel_formateurs)
    
    # 4. Sauvegarder
    if comparison:
        df = pd.DataFrame(comparison)
        df.to_excel('comparaison_formateurs_final.xlsx', index=False)
        
        print(f"\nRésultats sauvegardés dans comparaison_formateurs_final.xlsx")
        print(f"Total site web: {len(web_formateurs)}")
        print(f"Total Excel: {len(excel_formateurs)}")
        print(f"Communs: {len([r for r in comparison if 'Présent dans les deux' in r['Statut']])}")
        print(f"Seulement site web: {len([r for r in comparison if 'Seulement site web' in r['Statut']])}")
        print(f"Seulement Excel: {len([r for r in comparison if 'Seulement fichier Excel' in r['Statut']])}")
    else:
        print("Aucune donnée à sauvegarder")

if __name__ == "__main__":
    main()

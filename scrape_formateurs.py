#!/usr/bin/env python3
"""
Script pour extraire les formateurs depuis le site web call.naumur.com
et les comparer avec le fichier Excel concaténé.
"""

import os
import sys
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urljoin

def scrape_formateurs_from_website():
    """
    Extrait les formateurs depuis le site web call.naumur.com
    """
    base_url = "https://call.naumur.com"
    formateurs_url = "https://call.naumur.com/?scope=formateur&section=principal"
    
    print("Extraction des formateurs depuis le site web...")
    
    # Configuration des headers pour éviter d'être bloqué
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'fr-FR,fr;q=0.8,en-US;q=0.5,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    all_formateurs = []
    page = 1
    
    try:
        while True:
            # Construire l'URL avec le paramètre de page
            if page == 1:
                url = formateurs_url
            else:
                url = f"{formateurs_url}&page={page}"
            
            print(f"  Extraction de la page {page}...")
            
            # Faire la requête
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Parser le HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Chercher le tableau des formateurs
            table = soup.find('table', {'class': 'table'}) or soup.find('table', id='formateurs-table')
            
            if not table:
                # Essayer de trouver un tableau par d'autres moyens
                tables = soup.find_all('table')
                if tables:
                    table = tables[0]  # Prendre le premier tableau trouvé
                    print(f"  Tableau trouvé (alternative)")
                else:
                    print(f"  Aucun tableau trouvé sur la page {page}")
                    break
            
            # Extraire les lignes du tableau
            rows = table.find_all('tr')
            
            if len(rows) <= 1:  # Seulement l'en-tête
                print(f"  Pas de données trouvées sur la page {page}")
                break
            
            # Extraire les en-têtes
            headers_row = rows[0]
            headers = []
            for th in headers_row.find_all(['th', 'td']):
                headers.append(th.get_text(strip=True))
            
            print(f"  Colonnes trouvées: {headers}")
            
            # Extraire les données des formateurs
            page_formateurs = []
            for row in rows[1:]:  # Skip header row
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:  # Au moins 2 colonnes
                    formateur_data = {}
                    
                    for i, cell in enumerate(cells):
                        if i < len(headers):
                            header_name = headers[i].lower()
                            cell_text = cell.get_text(strip=True)
                            
                            # Nettoyer le texte
                            cell_text = re.sub(r'\s+', ' ', cell_text)
                            
                            # Mapper les colonnes importantes
                            if any(keyword in header_name for keyword in ['nom', 'name']):
                                formateur_data['nom'] = cell_text
                            elif any(keyword in header_name for keyword in ['téléphone', 'telephone', 'tel', 'phone']):
                                # Nettoyer le numéro de téléphone
                                phone = re.sub(r'[^\d+]', '', cell_text)
                                formateur_data['telephone'] = phone
                            elif any(keyword in header_name for keyword in ['prestataire', 'prestation']):
                                formateur_data['prestataire'] = cell_text
                            elif any(keyword in header_name for keyword in ['formation', 'classe', 'cohorte']):
                                formateur_data['formation'] = cell_text
                            elif any(keyword in header_name for keyword in ['email']):
                                formateur_data['email'] = cell_text
                            else:
                                # Garder toutes les colonnes pour le débogage
                                formateur_data[f'col_{i}'] = cell_text
                    
                    # Ajouter seulement si on a un nom ou un téléphone
                    if formateur_data.get('nom') or formateur_data.get('telephone'):
                        formateur_data['page'] = page
                        page_formateurs.append(formateur_data)
            
            print(f"  {len(page_formateurs)} formateurs extraits de la page {page}")
            all_formateurs.extend(page_formateurs)
            
            # Vérifier s'il y a une page suivante
            next_link = soup.find('a', string=re.compile(r'suivant|next|»', re.IGNORECASE))
            if not next_link:
                # Vérifier s'il y a une pagination
                pagination = soup.find('div', {'class': 'pagination'}) or soup.find('nav', {'class': 'pagination'})
                if pagination:
                    page_links = pagination.find_all('a')
                    current_page_found = False
                    has_next = False
                    
                    for link in page_links:
                        link_text = link.get_text(strip=True)
                        if link_text == str(page):
                            current_page_found = True
                        elif current_page_found and link_text.isdigit():
                            has_next = True
                            break
                    
                    if not has_next:
                        break
                else:
                    break
            
            page += 1
            time.sleep(1)  # Pause pour ne pas surcharger le serveur
            
    except requests.RequestException as e:
        print(f"Erreur lors de la requête HTTP: {e}")
        return []
    except Exception as e:
        print(f"Erreur lors de l'extraction: {e}")
        import traceback
        traceback.print_exc()
        return []
    
    print(f"Total de {len(all_formateurs)} formateurs extraits")
    return all_formateurs

def read_excel_file():
    """
    Lit le fichier Excel concaténé pour extraire les numéros de formateurs
    """
    excel_file = "fichier_concatene (1) 1 (1).xlsx"
    
    if not os.path.exists(excel_file):
        print(f"Fichier Excel non trouvé: {excel_file}")
        return []
    
    try:
        # Essayer différentes méthodes de lecture
        df = None
        
        # Méthode 1: openpyxl
        try:
            df = pd.read_excel(excel_file, engine='openpyxl')
        except:
            pass
        
        # Méthode 2: xlrd
        if df is None:
            try:
                df = pd.read_excel(excel_file, engine='xlrd')
            except:
                pass
        
        # Méthode 3: lecture sans spécifier de moteur
        if df is None:
            try:
                df = pd.read_excel(excel_file)
            except:
                pass
        
        if df is None:
            print("Impossible de lire le fichier Excel")
            return []
        
        print(f"Fichier Excel lu: {df.shape[0]} lignes, {df.shape[1]} colonnes")
        print(f"Colonnes: {list(df.columns)}")
        
        # Chercher les colonnes pertinentes
        formateurs_excel = []
        
        for index, row in df.iterrows():
            if index >= 200:  # Limiter pour éviter les problèmes
                break
            
            formateur_data = {
                'ligne_excel': index + 2,
                'nom': '',
                'telephone': '',
                'prestataire': '',
                'formation': ''
            }
            
            # Extraire les données en cherchant dans les colonnes
            for col_name, value in row.items():
                if pd.isna(value):
                    continue
                
                col_str = str(col_name).lower()
                val_str = str(value).strip()
                
                if any(keyword in col_str for keyword in ['nom', 'name']):
                    formateur_data['nom'] = val_str
                elif any(keyword in col_str for keyword in ['téléphone', 'telephone', 'tel', 'phone']):
                    # Nettoyer le numéro de téléphone
                    phone = re.sub(r'[^\d+]', '', val_str)
                    formateur_data['telephone'] = phone
                elif any(keyword in col_str for keyword in ['prestataire', 'prestation']):
                    formateur_data['prestataire'] = val_str
                elif any(keyword in col_str for keyword in ['formation', 'classe', 'cohorte']):
                    formateur_data['formation'] = val_str
            
            # Ajouter seulement si on a un téléphone ou un nom
            if formateur_data['telephone'] or formateur_data['nom']:
                formateurs_excel.append(formateur_data)
        
        print(f"{len(formateurs_excel)} formateurs extraits du fichier Excel")
        return formateurs_excel
        
    except Exception as e:
        print(f"Erreur lecture Excel: {e}")
        import traceback
        traceback.print_exc()
        return []

def create_comparison_table(web_formateurs, excel_formateurs):
    """
    Crée un tableau de comparaison
    """
    print("Création du tableau de comparaison...")
    
    # Créer des dictionnaires pour la recherche
    web_by_phone = {}
    for f in web_formateurs:
        phone = f.get('telephone', '').strip()
        if phone:
            web_by_phone[phone] = f
    
    excel_by_phone = {}
    for f in excel_formateurs:
        phone = f.get('telephone', '').strip()
        if phone:
            excel_by_phone[phone] = f
    
    # Tous les numéros uniques
    all_phones = set(web_by_phone.keys()) | set(excel_by_phone.keys())
    
    comparison_data = []
    
    for phone in all_phones:
        web = web_by_phone.get(phone)
        excel = excel_by_phone.get(phone)
        
        comparison_row = {
            'Téléphone': phone,
            'Nom_Site': web.get('nom', '') if web else '',
            'Prestataire_Site': web.get('prestataire', '') if web else '',
            'Formation_Site': web.get('formation', '') if web else '',
            'Email_Site': web.get('email', '') if web else '',
            'Page_Site': web.get('page', '') if web else '',
            'Nom_Excel': excel.get('nom', '') if excel else '',
            'Prestataire_Excel': excel.get('prestataire', '') if excel else '',
            'Formation_Excel': excel.get('formation', '') if excel else '',
            'Ligne_Excel': excel.get('ligne_excel', '') if excel else '',
            'Statut': ''
        }
        
        # Déterminer le statut
        if web and excel:
            comparison_row['Statut'] = 'Présent dans les deux'
        elif web and not excel:
            comparison_row['Statut'] = 'Seulement site web'
        elif not web and excel:
            comparison_row['Statut'] = 'Seulement fichier Excel'
        else:
            comparison_row['Statut'] = 'Erreur'
        
        comparison_data.append(comparison_row)
    
    # Trier par téléphone
    comparison_data.sort(key=lambda x: x['Téléphone'])
    
    return comparison_data

def save_to_excel(comparison_data, filename="comparaison_formateurs_site.xlsx"):
    """
    Sauvegarde le tableau de comparaison en Excel
    """
    try:
        df = pd.DataFrame(comparison_data)
        
        # Statistiques
        stats = [
            ['Statistiques', '', '', '', '', '', '', '', '', '', '', ''],
            ['Total site web', len([r for r in comparison_data if r['Page_Site']]), '', '', '', '', '', '', '', '', '', ''],
            ['Total fichier Excel', len([r for r in comparison_data if r['Ligne_Excel']]), '', '', '', '', '', '', '', '', '', ''],
            ['Communs', len([r for r in comparison_data if 'Présent dans les deux' in r['Statut']]), '', '', '', '', '', '', '', '', '', ''],
            ['Seulement site web', len([r for r in comparison_data if 'Seulement site web' in r['Statut']]), '', '', '', '', '', '', '', '', '', ''],
            ['Seulement fichier Excel', len([r for r in comparison_data if 'Seulement fichier Excel' in r['Statut']]), '', '', '', '', '', '', '', '', '', ''],
            ['', '', '', '', '', '', '', '', '', '', '', ''],
        ]
        
        # Combiner les données
        final_data = stats + [list(df.columns)] + df.values.tolist()
        final_df = pd.DataFrame(final_data[1:], columns=final_data[0])
        
        # Sauvegarder
        final_df.to_excel(filename, index=False, engine='openpyxl')
        
        print(f"Fichier sauvegardé: {filename}")
        print("Statistiques:")
        print(f"  - Site web: {len([r for r in comparison_data if r['Page_Site']])}")
        print(f"  - Excel: {len([r for r in comparison_data if r['Ligne_Excel']])}")
        print(f"  - Communs: {len([r for r in comparison_data if 'Présent dans les deux' in r['Statut']])}")
        print(f"  - Seulement site web: {len([r for r in comparison_data if 'Seulement site web' in r['Statut']])}")
        print(f"  - Seulement Excel: {len([r for r in comparison_data if 'Seulement fichier Excel' in r['Statut']])}")
        
    except Exception as e:
        print(f"Erreur sauvegarde Excel: {e}")
        import traceback
        traceback.print_exc()

def main():
    """
    Fonction principale
    """
    print("Début de l'extraction et comparaison des formateurs...")
    print("=" * 60)
    
    # 1. Extraire depuis le site web
    print("\n1. Extraction depuis le site web...")
    web_formateurs = scrape_formateurs_from_website()
    
    # 2. Lire le fichier Excel
    print("\n2. Lecture du fichier Excel...")
    excel_formateurs = read_excel_file()
    
    # 3. Créer la comparaison
    print("\n3. Création du tableau de comparaison...")
    comparison_data = create_comparison_table(web_formateurs, excel_formateurs)
    
    # 4. Sauvegarder
    print("\n4. Sauvegarde des résultats...")
    save_to_excel(comparison_data)
    
    print("\nComparaison terminée!")
    print("=" * 60)

if __name__ == "__main__":
    main()

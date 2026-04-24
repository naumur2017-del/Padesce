#!/usr/bin/env python3
"""
Script pour tester la page de stats des formateurs
"""

import requests
from bs4 import BeautifulSoup
import re

def test_formateur_stats():
    """
    Test la page de stats des formateurs pour vérifier l'affichage des prestations
    """
    url = "https://call.naumur.com/?scope=formateur&section=stats"
    
    try:
        # Test avec headers de navigateur
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.8,en-US;q=0.5,en;q=0.3',
        }
        
        print(f"Test de la page: {url}")
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Chercher les tables de stats
            tables = soup.find_all('table')
            print(f"Nombre de tables trouvées: {len(tables)}")
            
            # Chercher spécifiquement les prestations dans les tables
            prestation_count = 0
            prestataires = set()
            
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    for cell in cells:
                        text = cell.get_text(strip=True)
                        # Chercher des codes de prestation (commencent par PRESTA)
                        if re.match(r'PRESTA\d+', text):
                            prestation_count += 1
                            print(f"  Prestation trouvée: {text}")
                        
                        # Chercher des noms de prestataires
                        if len(text) > 3 and text not in ['Code', 'Prestataire', 'Bénéficiaire', 'Effectif', 'Score']:
                            prestataires.add(text)
            
            print(f"\nTotal de prestations trouvées: {prestation_count}")
            print(f"Prestataires uniques: {len(prestataires)}")
            if prestataires:
                print("Liste des prestataires:")
                for prestataire in sorted(prestataires):
                    if len(prestataire) > 5:  # Filtrer les courts
                        print(f"  - {prestataire}")
            
            # Vérifier s'il y a des messages d'erreur
            error_elements = soup.find_all(text=re.compile(r'erreur|error|exception', re.I))
            if error_elements:
                print(f"\nErreurs trouvées: {len(error_elements)}")
                for error in error_elements[:3]:
                    print(f"  - {error.strip()}")
        
        else:
            print(f"Erreur HTTP: {response.status_code}")
            print(f"Contenu de la réponse (premiers 500 caractères):")
            print(response.text[:500])
            
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_formateur_stats()

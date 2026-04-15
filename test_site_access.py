#!/usr/bin/env python3
"""
Script pour tester l'accès au site call.naumur.com et diagnostiquer l'erreur 500
"""

import requests
import sys

def test_site_access():
    """
    Teste l'accès au site et affiche les détails de l'erreur
    """
    url = "https://call.naumur.com/"
    
    print(f"Test d'accès à: {url}")
    print("=" * 50)
    
    try:
        # Test avec headers de navigateur
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.8,en-US;q=0.5,en;q=0.3',
        }
        
        print("Envoi de la requête...")
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        
        print(f"Status Code: {response.status_code}")
        print(f"Headers de réponse:")
        for key, value in response.headers.items():
            print(f"  {key}: {value}")
        
        print(f"\nContenu de la réponse (premiers 500 caractères):")
        print(response.text[:500])
        
        if response.status_code == 500:
            print("\n" + "="*50)
            print("ERREUR 500 DÉTECTÉE")
            print("="*50)
            print("Causes possibles:")
            print("1. Erreur de configuration du serveur")
            print("2. Problème de base de données")
            print("3. Erreur dans le code de l'application")
            print("4. Fichiers manquants ou permissions incorrectes")
            print("5. Problème de migration de données récente")
            
            # Vérifier si le contenu contient des indices
            if "Internal Server Error" in response.text:
                print("Le serveur renvoie une erreur interne standard")
            elif "DatabaseError" in response.text or "database" in response.text.lower():
                print("Problème de base de détecté dans la réponse")
            elif "ImportError" in response.text or "ModuleNotFoundError" in response.text:
                print("Problème d'import de module détecté")
            elif "migration" in response.text.lower():
                print("Problème de migration détecté")
        
        return response.status_code
        
    except requests.exceptions.ConnectionError:
        print("ERREUR: Impossible de se connecter au serveur")
        print("Causes possibles:")
        print("- Site hors ligne")
        print("- Problème DNS")
        print("- Problème réseau")
        return None
    except requests.exceptions.Timeout:
        print("ERREUR: Timeout de la requête")
        return None
    except Exception as e:
        print(f"ERREUR: {e}")
        return None

def test_specific_page():
    """
    Teste l'accès à la page spécifique des formateurs
    """
    url = "https://call.naumur.com/?scope=formateur&section=principal"
    
    print(f"\nTest d'accès à la page formateurs: {url}")
    print("=" * 50)
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 500:
            print("ERREUR 500 sur la page formateurs également")
        else:
            print(f"Réponse reçue: {len(response.text)} caractères")
            if "table" in response.text.lower():
                print("Tableau détecté dans la réponse")
        
        return response.status_code
        
    except Exception as e:
        print(f"ERREUR: {e}")
        return None

def main():
    """
    Fonction principale
    """
    print("Diagnostic de l'erreur 500 sur call.naumur.com")
    print("=" * 60)
    
    # Test de la page principale
    main_status = test_site_access()
    
    # Test de la page formateurs
    formateur_status = test_specific_page()
    
    print("\n" + "=" * 60)
    print("RÉSUMÉ DU DIAGNOSTIC")
    print("=" * 60)
    print(f"Page principale: {main_status}")
    print(f"Page formateurs: {formateur_status}")
    
    if main_status == 500:
        print("\nRECOMMANDATIONS:")
        print("1. Vérifier les logs du serveur Django")
        print("2. Vérifier que les migrations ont été appliquées")
        print("3. Vérifier la configuration de la base de données")
        print("4. Redémarrer le serveur application")
        print("5. Vérifier les fichiers de configuration récents")

if __name__ == "__main__":
    main()

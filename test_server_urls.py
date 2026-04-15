#!/usr/bin/env python3
"""
Script pour tester les URLs du serveur Django après restauration
"""

import requests
from bs4 import BeautifulSoup

def test_urls():
    """Test les URLs principales du serveur"""
    base_url = "http://127.0.0.1:8000"
    
    urls_to_test = [
        "/",
        "/?scope=formateur&section=principal",
        "/?scope=formateur&section=stats", 
        "/prestation/PRESTA046/",
        "/prestation/PRESTA046/?tab=formateurs",
        "/prestation/PRESTA001/",
        "/admin/"
    ]
    
    for url_path in urls_to_test:
        full_url = base_url + url_path
        try:
            response = requests.get(full_url, timeout=10)
            print(f"URL: {url_path}")
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                title = soup.find('title')
                if title:
                    print(f"  Title: {title.get_text().strip()}")
                else:
                    print(f"  Title: No title found")
            elif response.status_code == 404:
                print(f"  Error: Page not found")
            elif response.status_code == 500:
                print(f"  Error: Internal server error")
            else:
                print(f"  Status: {response.status_code}")
            
            print()
            
        except requests.exceptions.ConnectionError:
            print(f"URL: {url_path}")
            print(f"  Error: Cannot connect to server")
            print()
        except Exception as e:
            print(f"URL: {url_path}")
            print(f"  Error: {e}")
            print()

if __name__ == "__main__":
    test_urls()

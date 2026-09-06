import requests
from bs4 import BeautifulSoup
import pdfplumber
import json
import os

URL_STRONY = "https://www.mazowieckie.com.pl/pl/podstawowe-informacje/rozklad-jazdy-pociagow-km-wazny-w-dniach-30-viii-24-x-2026r"

def pobierz_link_do_pdf(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    for link in soup.find_all('a'):
        href = link.get('href')
        if href and 'Zestawienie' in href and href.endswith('.pdf'):
            if not href.startswith('http'):
                href = "https://www.mazowieckie.com.pl" + href
            return href
    return None

def konwertuj_pdf_na_json(sciezka_pdf):
    baza_pociagow = {}
    
    with pdfplumber.open(sciezka_pdf) as pdf:
        for strona in pdf.pages:
            tabele = strona.extract_tables()
            for tabela in tabele:
                for wiersz in tabela:
                    # UWAGA: Logika dostosowana do konkretnego PDF!
                    # Zakładamy testowo, że kolumna 0 to numer, a kolumna 3 to model.
                    if wiersz and len(wiersz) > 5 and wiersz[0] and wiersz[0].isdigit():
                        nr_pociagu = wiersz[0].strip()
                        model = wiersz[5].replace('\n', ' ').strip()
                        baza_pociagow[nr_pociagu] = {"model": model}
    
    with open('train_models.json', 'w', encoding='utf-8') as f:
        json.dump(baza_pociagow, f, ensure_ascii=False, indent=4)
    print("Gotowe! Zapisano dane do train_models.json")

# Główna funkcja uruchamiająca
link = pobierz_link_do_pdf(URL_STRONY)
if link:
    print(f"Znaleziono PDF: {link}")
    plik_pdf = "zestawienie_tymczasowe.pdf"
    
    with open(plik_pdf, 'wb') as f:
        f.write(requests.get(link).content)
        
    konwertuj_pdf_na_json(plik_pdf)
    os.remove(plik_pdf) # Sprzątanie
else:
    print("Nie znaleziono linku do zestawienia na stronie.")

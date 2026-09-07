import requests
from bs4 import BeautifulSoup
import pdfplumber
import json
import os

# Baza strony i ogólna kategoria rozkładów
BASE_URL = "https://www.mazowieckie.com.pl"
ROZKLADY_URL = f"{BASE_URL}/pl/kategoria/rozklady-jazdy"

def pobierz_najnowszy_pdf():
    try:
        # KROK 1: Pobieramy stronę główną z listą rozkładów
        print("Łączenie ze stroną główną KM...")
        response = requests.get(ROZKLADY_URL, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Szukamy linków do artykułów o rozkładach
        for a in soup.find_all('a', href=True):
            href = a['href']
            # Jeśli link wygląda jak artykuł o rozkładzie
            if 'rozklad-jazdy' in href.lower() or 'zestawienie' in href.lower():
                if not href.startswith('http'):
                    href = BASE_URL + href
                
                # KROK 2: Wchodzimy w ten konkretny artykuł
                resp_art = requests.get(href, timeout=10)
                soup_art = BeautifulSoup(resp_art.text, 'html.parser')
                
                # Szukamy pliku PDF z zestawieniem
                for link in soup_art.find_all('a', href=True):
                    pdf_href = link['href']
                    if 'Zestawienie' in pdf_href and pdf_href.endswith('.pdf'):
                        if not pdf_href.startswith('http'):
                            pdf_href = BASE_URL + pdf_href
                        return pdf_href
                        
    except Exception as e:
        print(f"Wystąpił błąd podczas przeszukiwania strony: {e}")
        
    return None

def konwertuj_pdf_na_json(sciezka_pdf):
    baza_pociagow = {}
    
    try:
        with pdfplumber.open(sciezka_pdf) as pdf:
            for strona in pdf.pages:
                tabele = strona.extract_tables()
                for tabela in tabele:
                    for wiersz in tabela:
                        # Sprawdzamy czy wiersz ma odpowiednią liczbę kolumn i czy pierwsza to numer
                        if wiersz and len(wiersz) > 5 and wiersz[0] and str(wiersz[0]).strip().isdigit():
                            nr_pociagu = str(wiersz[0]).strip()
                            # UWAGA: Kolumna 5 (szósta w tabeli) to model wg Twoich ustaleń
                            model = str(wiersz[5]).replace('\n', ' ').strip()
                            baza_pociagow[nr_pociagu] = {"model": model}
        
        with open('train_models.json', 'w', encoding='utf-8') as f:
            json.dump(baza_pociagow, f, ensure_ascii=False, indent=4)
            
        print(f"Gotowe! Zapisano dane o {len(baza_pociagow)} pociągach do pliku train_models.json")
        
    except Exception as e:
        print(f"Błąd podczas konwersji PDF: {e}")

# --- GŁÓWNA LOGIKA SKRYPTU ---
if __name__ == "__main__":
    link_do_pdf = pobierz_najnowszy_pdf()

    if link_do_pdf:
        print(f"Znaleziono najnowszy PDF: {link_do_pdf}")
        plik_pdf = "zestawienie_tymczasowe.pdf"
        
        print("Trwa pobieranie pliku...")
        try:
            pdf_response = requests.get(link_do_pdf, timeout=30)
            with open(plik_pdf, 'wb') as f:
                f.write(pdf_response.content)
                
            print("Rozpoczynam konwersję do JSON...")
            konwertuj_pdf_na_json(plik_pdf)
            
        except Exception as e:
            print(f"Błąd podczas pobierania pliku: {e}")
        finally:
            # Sprzątanie - bot usuwa pobranego PDF-a, zostawia tylko wygenerowany JSON
            if os.path.exists(plik_pdf):
                os.remove(plik_pdf)
                print("Usunięto plik tymczasowy PDF.")
    else:
        print("Nie znaleziono linku do zestawienia na stronie KM. Sprawdź strukturę strony.")

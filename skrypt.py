import pdfplumber
import json
import re
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# ==========================================
# KONFIGURACJA ZAUTOMATYZOWANA - DWUETAPOWA
# ==========================================
STRONA_GLOWNA_KM = "https://www.mazowieckie.com.pl/pl/kategoria/tabele-rozkladow-jazdy"
JSON_PATH = "train_models.json"

znane_modele = [
    "ER160", "EN57AKM", "EN57AL", "EN57", "45WE", "22WE", "31WE", 
    "VT627", "VT628", "VT", "SA135",
    "PUSH-PULL", "PUSH PULL", "TWINDEXX", "SUNDECK", "PIĘTROWE", 
    "WAGONY PIĘTROWE", "EU47", "111EB", "GAMA", "TRAXX",
    "FLIRT", "IMPULS", "ELF", "EN76", "ER75", "EN71", "EW60", "222M"
]

def znajdz_i_pobierz_pdfy():
    print(f"KROK 1: Skanowanie strony głównej... {STRONA_GLOWNA_KM}")
    pdf_pliki = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        response_main = requests.get(STRONA_GLOWNA_KM, headers=headers)
        response_main.raise_for_status()
        soup_main = BeautifulSoup(response_main.text, 'html.parser')
        
        # POPRAWKA 1: Używamy listy zamiast "zbioru (set)", 
        # aby zachować kolejność odczytu. KM wrzuca najnowsze rozkłady na samą górę!
        podstrony = [] 
        for link in soup_main.find_all('a', href=True):
            href = link['href']
            if 'rozklad-jazdy' in href.lower():
                pelny_link_podstrony = urljoin(STRONA_GLOWNA_KM, href)
                if pelny_link_podstrony not in podstrony:
                    podstrony.append(pelny_link_podstrony)
                
        print(f"Znaleziono {len(podstrony)} podstron z rozkładami. Rozpoczynam KROK 2...")
        
        licznik = 1
        for url_podstrony in podstrony:
            print(f"Skanowanie podstrony: {url_podstrony}")
            try:
                resp_sub = requests.get(url_podstrony, headers=headers)
                soup_sub = BeautifulSoup(resp_sub.text, 'html.parser')
                
                for link in soup_sub.find_all('a', href=True):
                    href = link['href']
                    if href.lower().endswith('.pdf') and 'zestawieni' in href.lower():
                        pelny_url_pdf = urljoin(url_podstrony, href)
                        
                        nazwa_pliku = f"km_rozklad_{licznik}.pdf"
                        print(f" ⬇️ Pobieranie PDF: {pelny_url_pdf} -> {nazwa_pliku}")
                        
                        pdf_resp = requests.get(pelny_url_pdf, headers=headers)
                        with open(nazwa_pliku, 'wb') as f:
                            f.write(pdf_resp.content)
                            
                        pdf_pliki.append(nazwa_pliku)
                        licznik += 1
            except Exception as e:
                print(f" ❌ Błąd skanowania podstrony {url_podstrony}: {e}")
                
        return pdf_pliki
    except Exception as e:
        print(f"❌ Błąd podczas łączenia ze stroną KM: {e}")
        return []

def konwertuj_pdf_na_json(pdf_pliki):
    train_db = {}
    print(f"\nRozpoczynam ekstrakcję z {len(pdf_pliki)} plików PDF...")
    
    for pdf_path in pdf_pliki:
        print(f"Czytanie pliku: {pdf_path}")
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    tabele = page.extract_tables()
                    for tabela in tabele:
                        for wiersz in tabela:
                            if not wiersz:
                                continue
                            
                            tekst_wiersza = " ".join([str(komorka).strip().upper() for komorka in wiersz if komorka])
                            
                            dopasowania = re.finditer(r'(?<!\d)(\d{4,5})(?:[\/\-](\d+))?(?!\d)', tekst_wiersza)
                            numery_w_wierszu = []
                            for match in dopasowania:
                                baza_numer = match.group(1) 
                                numery_w_wierszu.append(baza_numer)
                                koncowka = match.group(2) 
                                if koncowka:
                                    if len(koncowka) <= len(baza_numer):
                                        drugi_numer = baza_numer[:-len(koncowka)] + koncowka
                                        numery_w_wierszu.append(drugi_numer)
                            
                            znaleziony_model = None
                            for model in sorted(znane_modele, key=len, reverse=True):
                                if model in tekst_wiersza:
                                    if model in ["PUSH-PULL", "PUSH PULL", "TWINDEXX", "SUNDECK", "PIĘTROWE", "WAGONY PIĘTROWE", "EU47", "111EB", "GAMA", "TRAXX"]:
                                        znaleziony_model = "Wagony Piętrowe (Push-Pull)"
                                    else:
                                        znaleziony_model = model
                                    break
                            
                            if numery_w_wierszu and znaleziony_model:
                                for nr in numery_w_wierszu:
                                    # POPRAWKA 2: Zero podwójnych modeli!
                                    # Ponieważ skanujemy najnowsze pliki jako pierwsze, 
                                    # jeśli numer jest już w bazie, po prostu ignorujemy starsze wpisy.
                                    if nr not in train_db:
                                        train_db[nr] = {"model": znaleziony_model}
        except Exception as e:
            print(f"❌ Błąd analizy {pdf_path}: {e}")

    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(train_db, f, indent=4, ensure_ascii=False)
        
    print(f"\n✅ Zakończono sukcesem! Zapisano pociągów ze WSZYSTKICH rozkładów: {len(train_db)}")

if __name__ == "__main__":
    pliki_do_przetworzenia = znajdz_i_pobierz_pdfy()
    
    if pliki_do_przetworzenia:
        konwertuj_pdf_na_json(pliki_do_przetworzenia)
        
        print("\nSprzątanie plików tymczasowych...")
        for pdf_file in pliki_do_przetworzenia:
            if os.path.exists(pdf_file):
                os.remove(pdf_file)
        print("🧹 Gotowe!")
    else:
        print("❌ Nie znaleziono żadnych plików PDF z zestawieniami.")

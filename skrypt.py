import pdfplumber
import json
import re
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# ==========================================
# KONFIGURACJA ZAUTOMATYZOWANA
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
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response_main = requests.get(STRONA_GLOWNA_KM, headers=headers)
        response_main.raise_for_status()
        soup_main = BeautifulSoup(response_main.text, 'html.parser')
        
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
            try:
                resp_sub = requests.get(url_podstrony, headers=headers)
                soup_sub = BeautifulSoup(resp_sub.text, 'html.parser')
                
                for link in soup_sub.find_all('a', href=True):
                    href = link['href']
                    if href.lower().endswith('.pdf') and 'zestawieni' in href.lower():
                        pelny_url_pdf = urljoin(url_podstrony, href)
                        nazwa_pliku = f"km_rozklad_{licznik}.pdf"
                        print(f" ⬇️ Pobieranie PDF: {nazwa_pliku}")
                        
                        pdf_resp = requests.get(pelny_url_pdf, headers=headers)
                        with open(nazwa_pliku, 'wb') as f:
                            f.write(pdf_resp.content)
                        pdf_pliki.append(nazwa_pliku)
                        licznik += 1
            except Exception as e:
                print(f" ❌ Błąd skanowania podstrony {url_podstrony}: {e}")
                
        return pdf_pliki
    except Exception as e:
        print(f"❌ Błąd: {e}")
        return []

def konwertuj_pdf_na_json(pdf_pliki):
    train_db = {}
    print(f"\nRozpoczynam ekstrakcję z {len(pdf_pliki)} plików PDF...")
    
    for pdf_path in pdf_pliki:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    for tabela in page.extract_tables():
                        for wiersz in tabela:
                            if not wiersz: continue
                            
                            tekst_wiersza = " ".join([str(k).strip().upper() for k in wiersz if k])
                            dopasowania = re.finditer(r'(?<!\d)(\d{4,5})(?:[\/\-](\d+))?(?!\d)', tekst_wiersza)
                            
                            numery = []
                            for match in dopasowania:
                                b = match.group(1)
                                numery.append(b)
                                k = match.group(2)
                                if k and len(k) <= len(b):
                                    numery.append(b[:-len(k)] + k)
                            
                            znaleziony_model = None
                            ogon_tekstu = ""
                            
                            for model in sorted(znane_modele, key=len, reverse=True):
                                if model in tekst_wiersza:
                                    if model in ["PUSH-PULL", "PUSH PULL", "TWINDEXX", "SUNDECK", "PIĘTROWE", "WAGONY PIĘTROWE", "EU47", "111EB", "GAMA", "TRAXX"]:
                                        znaleziony_model = "Wagony Piętrowe (Push-Pull)"
                                    else:
                                        znaleziony_model = model
                                    
                                    # Magia wycinania jednostek i terminu:
                                    idx = tekst_wiersza.find(model)
                                    ogon_tekstu = tekst_wiersza[idx + len(model):].strip()
                                    break
                            
                            if numery and znaleziony_model:
                                jednostki = "1"
                                termin = ogon_tekstu
                                
                                # Sprawdzamy czy pierwszy znak po modelu to liczba jednostek (np. 1 lub 2)
                                parts = ogon_tekstu.split(' ', 1)
                                if len(parts) > 0 and parts[0] in ['1', '2', '3']:
                                    jednostki = parts[0]
                                    termin = parts[1] if len(parts) > 1 else ""
                                
                                wariant = {
                                    "model": znaleziony_model,
                                    "jednostki": jednostki,
                                    "termin_surowy": termin
                                }
                                
                                for nr in numery:
                                    if nr not in train_db:
                                        train_db[nr] = []
                                    # Dodajemy wariant tylko, jeśli takiego jeszcze nie ma
                                    if wariant not in train_db[nr]:
                                        train_db[nr].append(wariant)
        except Exception as e:
            print(f"❌ Błąd analizy {pdf_path}: {e}")

    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(train_db, f, indent=4, ensure_ascii=False)
    print(f"\n✅ Zakończono! Zapisano {len(train_db)} unikalnych pociągów z wariantami.")

if __name__ == "__main__":
    pliki = znajdz_i_pobierz_pdfy()
    if pliki:
        konwertuj_pdf_na_json(pliki)
        for pdf_file in pliki:
            if os.path.exists(pdf_file): os.remove(pdf_file)

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
# Strona, na której KM publikuje PDF-y z zestawieniami
STRONA_KM_URL = "https://www.mazowieckie.com.pl/pl/podstawowe-informacje/zestawienie-pociagow-km"
JSON_PATH = "train_models.json"

znane_modele = [
    "ER160", "EN57AKM", "EN57AL", "EN57", "45WE", "22WE", "31WE", 
    "VT627", "VT628", "VT", "SA135",
    "PUSH-PULL", "PUSH PULL", "TWINDEXX", "SUNDECK", "PIĘTROWE", 
    "WAGONY PIĘTROWE", "EU47", "111EB", "GAMA", "TRAXX",
    "FLIRT", "IMPULS", "ELF", "EN76", "ER75", "EN71", "EW60", "222M"
]

def znajdz_i_pobierz_pdfy():
    print(f"Skanowanie strony KM: {STRONA_KM_URL}...")
    pdf_pliki = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(STRONA_KM_URL, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        linki = soup.find_all('a', href=True)
        
        for link in linki:
            href = link['href']
            # Szukamy linków, które kończą się na .pdf i mają w nazwie "zestawienie" lub "zestawienia"
            if href.lower().endswith('.pdf') and 'zestawieni' in href.lower():
                pelny_url = urljoin(STRONA_KM_URL, href)
                nazwa_pliku = pelny_url.split('/')[-1]
                
                print(f"Znaleziono rozkład: {nazwa_pliku}")
                # Pobieranie
                pdf_resp = requests.get(pelny_url, headers=headers)
                with open(nazwa_pliku, 'wb') as f:
                    f.write(pdf_resp.content)
                pdf_pliki.append(nazwa_pliku)
                
        return pdf_pliki
    except Exception as e:
        print(f"❌ Błąd podczas skanowania strony: {e}")
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
                                    # Inteligentne łączenie: jeśli numer już jest, ale model się różni
                                    if nr in train_db:
                                        obecny_model = train_db[nr]["model"]
                                        if znaleziony_model not in obecny_model:
                                            train_db[nr]["model"] = f"{obecny_model} / {znaleziony_model}"
                                    else:
                                        train_db[nr] = {"model": znaleziony_model}
        except Exception as e:
            print(f"❌ Błąd analizy {pdf_path}: {e}")

    # Zapis do złączonego pliku JSON
    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(train_db, f, indent=4, ensure_ascii=False)
        
    print(f"\n✅ Zakończono sukcesem! Zapisano pociągów ze WSZYSTKICH rozkładów: {len(train_db)}")

# ==========================================
# URUCHOMIENIE I SPRZĄTANIE
# ==========================================
if __name__ == "__main__":
    pliki_do_przetworzenia = znajdz_i_pobierz_pdfy()
    
    if pliki_do_przetworzenia:
        konwertuj_pdf_na_json(pliki_do_przetworzenia)
        
        # Sprzątanie - usuwamy pobrane PDF-y, żeby nie zajmowały miejsca
        print("\nSprzątanie plików tymczasowych...")
        for pdf_file in pliki_do_przetworzenia:
            if os.path.exists(pdf_file):
                os.remove(pdf_file)
        print("🧹 Gotowe!")
    else:
        print("❌ Nie znaleziono żadnych plików PDF na stronie.")

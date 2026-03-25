import requests
from bs4 import BeautifulSoup
from curl_cffi import requests as requests_cffi

# ==========================================
#              MODUŁ: HELION
# ==========================================
def pobierz_dane_helion(url):
    # Helion jest dość przyjazny, ale kultura wymaga, by się przedstawić jako przeglądarka
    naglowki = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    # 1. Wysyłamy żądanie na stronę
    odpowiedz = requests.get(url, headers=naglowki)
    
    if odpowiedz.status_code != 200:
        return f"Błąd: Serwer zwrócił kod {odpowiedz.status_code}"
        
    # 2. Robimy zupę (czyli parsujemy HTML)
    zupa = BeautifulSoup(odpowiedz.text, 'html.parser')
    
    # 3. Szukamy ceny. Na Helionie cena promocyjna/główna często siedzi w tagu <ins> lub <p class="price">.
    # Używamy inspektora przeglądarki, żeby znaleźć odpowiednią klasę.
    
    cena = "Brak ceny"
    # Szukamy elementu z id "cena" (tak Helion często oznacza główny blok cenowy)
    blok_ceny = zupa.find(id='cena_d', class_='product-page-main-price')
    
    if blok_ceny:
        cena = blok_ceny.text.strip().split('\n')[0].strip()

    # --- 2. WYCIĄGAMY TYTUŁ ---
    tytul = "Nieznany tytuł"
    # Szukamy diva z tytułem
    blok_tytulu = zupa.find('div', class_='title-group')
    if blok_tytulu and blok_tytulu.h1:
        # .find('span') znajduje domyślnie tylko PIERWSZY tag span, czyli nasz tytuł, ignorując autora!
        span_z_tytulem = blok_tytulu.h1.find('span') 
        if span_z_tytulem:
            tytul = span_z_tytulem.text.strip()
            
    # --- 3. ZWRACAMY SŁOWNIK ---
    return {
        "tytul": tytul,
        "cena": cena
    }

# ==========================================
#              MODUŁ: X-KOM
# ==========================================
def pobierz_dane_xkom(url):
    try: 
        # "Wytrych" na cloudflare
        odpowiedz = requests_cffi.get(url, impersonate="chrome110")

        if odpowiedz.status_code != 200:
            return {"blad": f"Serwer zwrócił kod {odpowiedz.status_code}"}
        
        zupa = BeautifulSoup(odpowiedz.text, 'html.parser')

        # Wyciąganie tytułu 
        tytul = "Nieznany tytuł"
        # Szukamy nagłówka h1, który ma atrybut data-name="productTitle"
        blok_tytulu = zupa.find('h1', attrs={'data-name': 'productTitle'})
        if blok_tytulu:
            tytul = blok_tytulu.text.strip()

        # Wyciąganie ceny 
        cena = "Brak ceny"
        # Szukamy głównego diva z ceną
        kontener_ceny = zupa.find('div', attrs={'data-name': 'productPrice'})
        if kontener_ceny:
            # Pierwszy span wewnątrz tego kontenera ma pełny tekst dla czytników ekranowych
            span_czytnika = kontener_ceny.find('span')
            if span_czytnika:
                # Wyciągnie "Cena: 1 549,00 zł", więc usuwamy słowo "Cena: " żeby mieć czystą kwotę
                cena = span_czytnika.text.replace("Cena:", "").strip()

        return {"tytul": tytul, "cena": cena}

    except Exception as e:
        return {"blad": f"Błąd połączenia z X-kom: {e}"}


# ==========================================
#              TESTY Z KONSOLI
# ==========================================
if __name__ == "__main__":
    print("--- URUCHAMIAM SILNIK PRICE TRACKERA ---\n")
    
    # Test Helion
    url_helion = "https://helion.pl/ksiazki/identyfikacja-i-autoryzacja-poradnik-administratora-i-inzyniera-devops-jerzy-wawro,idaupa.htm#format/d"
    wynik_helion = pobierz_dane_helion(url_helion)
    print(f"[HELION] Tytuł: {wynik_helion.get('tytul')}")
    print(f"[HELION] Cena: {wynik_helion.get('cena')}\n")
    

    # Test X-kom
    url_xkom = "https://www.x-kom.pl/p/1361497-monitor-led-27-265-284-samsung-odyssey-g5-s27fg500sux-g50sf.html"
    wynik_xkom = pobierz_dane_xkom(url_xkom)
    print(f"[X-KOM] Tytuł: {wynik_xkom.get('tytul')}")
    print(f"[X-KOM] Cena: {wynik_xkom.get('cena')}\n")

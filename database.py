import sqlite3
from datetime import datetime

# Nazwa naszego pliku z bazą (pojawi się w folderze projektu)
NAZWA_BAZY = "price_tracker.db"

def stworz_baze():
    """Tworzy plik bazy i tabelę, jeśli jeszcze nie istnieją."""
    # Łączymy się z plikiem (Python sam go stworzy, jeśli go nie ma)
    conn = sqlite3.connect(NAZWA_BAZY)
    kursor = conn.cursor()
    
    # Piszemy czysty kod SQL do stworzenia tabeli
    kursor.execute('''
        CREATE TABLE IF NOT EXISTS historia_cen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sklep TEXT,
            tytul TEXT,
            url TEXT,
            cena TEXT,
            data_zapisu DATETIME
        )
    ''')
    
    # Zapisujemy zmiany i zamykamy połączenie
    conn.commit()
    conn.close()

def zapisz_cene(sklep, tytul, url, cena):
    """Zapisuje pojedynczy pomiar do bazy danych."""
    # Zabezpieczenie przed zapisywaniem "pustych" błędów
    if not tytul or not cena or tytul == "Nieznany tytuł" or cena == "Brak ceny":
        print(f"[BAZA - ODRZUCONO] Brak poprawnych danych dla: {url}")
        return

    conn = sqlite3.connect(NAZWA_BAZY)
    kursor = conn.cursor()
    
    # Pobieramy aktualną datę i czas komputera
    teraz = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Znak zapytania (?) to super ważne zabezpieczenie w SQL (tzw. parametryzacja)
    kursor.execute('''
        INSERT INTO historia_cen (sklep, tytul, url, cena, data_zapisu)
        VALUES (?, ?, ?, ?, ?)
    ''', (sklep, tytul, url, cena, teraz))
    
    conn.commit()
    conn.close()
    print(f"[BAZA - ZAPISANO] {sklep} | {tytul} -> {cena}")


def pokaz_baze():
    """Wyciąga i drukuje wszystko, co mamy w bazie."""
    conn = sqlite3.connect(NAZWA_BAZY)
    kursor = conn.cursor()
    
    # Prosty SQL: Wybierz WSZYSTKO z tabeli historia_cen
    kursor.execute('SELECT id, sklep, tytul, cena, data_zapisu FROM historia_cen')
    wiersze = kursor.fetchall()
    
    print("\n--- ZAWARTOŚĆ TWOJEJ BAZY DANYCH ---")
    for wiersz in wiersze:
        print(wiersz)
        
    conn.close()

# ==========================================
#              TESTY Z KONSOLI
# ==========================================
if __name__ == "__main__":
    pokaz_baze()
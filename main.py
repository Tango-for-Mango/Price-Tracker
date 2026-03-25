# Importujemy nasze własne moduły!
from scraper import pobierz_dane_helion, pobierz_dane_xkom
from database import stworz_baze, zapisz_cene

def uruchom_pobieranie():
    print("--- START SYSTEMU ŚLEDZENIA CEN ---")
    
    # 1. Upewniamy się, że baza i tabele istnieją (jeśli już są, ta funkcja nic nie zepsuje)
    stworz_baze()
    
    # 2. Definiujemy nasze linki do śledzenia
    url_helion = "https://helion.pl/ksiazki/identyfikacja-i-autoryzacja-poradnik-administratora-i-inzyniera-devops-jerzy-wawro,idaupa.htm#format/d"
    url_xkom = "https://www.x-kom.pl/p/1361497-monitor-led-27-265-284-samsung-odyssey-g5-s27fg500sux-g50sf.html"
    
    # 3. Pobieramy i zapisujemy HELION
    print("\nSprawdzam Helion...")
    dane_helion = pobierz_dane_helion(url_helion)
    if "blad" not in dane_helion:
        zapisz_cene("Helion", dane_helion['tytul'], url_helion, dane_helion['cena'])
    else:
        print(f"Błąd Helion: {dane_helion['blad']}")

    # 4. Pobieramy i zapisujemy X-KOM
    print("\nSprawdzam X-Kom...")
    dane_xkom = pobierz_dane_xkom(url_xkom)
    if "blad" not in dane_xkom:
        zapisz_cene("X-Kom", dane_xkom['tytul'], url_xkom, dane_xkom['cena'])
    else:
        print(f"Błąd X-Kom: {dane_xkom['blad']}")
        
    print("\n--- ZAKOŃCZONO POBIERANIE ---")

if __name__ == "__main__":
    uruchom_pobieranie()
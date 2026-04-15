from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

# Importujemy nasze własne pliki
import models
from models import SessionLocal, engine
from security import get_password_hash, verify_password
from scraper import pobierz_dane_helion, pobierz_dane_xkom

# Inicjalizujemy serwer FastAPI
app = FastAPI(title="Price Tracker API")

# --- DEPENDENCY ---
# Funkcja otwierająca i zamykająca połączenie z bazą dla każdego zapytania
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- SCHEMATY PYDANTIC ---
# Klasa określająca, jakich danych wymagamy od użytkownika przy rejestracji
class UzytkownikRejestracja(BaseModel):
    username: str
    password: str
# Klasa do przechowywania i przekazywania linku do produktu podanego przez uzytkownika
class NowyProdukt(BaseModel):
    url: str

# ==========================================
#              ENDPOINTY (ŚCIEŻKI)
# ==========================================

@app.get("/")
def powitanie():
    return {"wiadomosc": "Witaj w API Price Trackera! Serwer działa."}

@app.post("/rejestracja")
def zarejestruj_uzytkownika(dane: UzytkownikRejestracja, db: Session = Depends(get_db)):
    # 1. Sprawdzamy, czy użytkownik o takiej nazwie już istnieje w bazie
    istniejacy = db.query(models.Uzytkownik).filter(models.Uzytkownik.username == dane.username).first()
    if istniejacy:
        raise HTTPException(status_code=400, detail="Ta nazwa użytkownika jest już zajęta!")
        
    # 2. Szyfrowanie hasła (funkcja z security.py)
    zhashowane_haslo = get_password_hash(dane.password)
    
    # 3. Tworzenie obiektu użytkownika i zapisywanie go w bazie
    nowy_uzytkownik = models.Uzytkownik(username=dane.username, hashed_password=zhashowane_haslo)
    db.add(nowy_uzytkownik)
    db.commit()
    
    return {"wiadomosc": f"Sukces! Użytkownik {dane.username} został zarejestrowany."}

@app.post("/logowanie")
def zaloguj_uzytkownika(dane: UzytkownikRejestracja, db: Session = Depends(get_db)):
    # 1. Szukanie użytkownika w bazie po nazwie
    uzytkownik = db.query(models.Uzytkownik).filter(models.Uzytkownik.username == dane.username).first()
    
    # 2. Sprawdzanie czy istnieje i czy hasło się zgadza
    if not uzytkownik or not verify_password(dane.password, uzytkownik.hashed_password):
        # Kod 401 oznacza "Unauthorized" (Brak autoryzacji)
        raise HTTPException(status_code=401, detail="Nieprawidłowa nazwa użytkownika lub hasło")
        
    return {"wiadomosc": f"Witaj {dane.username}! Zalogowano pomyślnie."}

@app.post("/dodaj-produkt")
def dodaj_produkt(dane: NowyProdukt, db: Session = Depends(get_db)):
    url = dane.url
    
    # 1. Automatyczne rozpoznawanie sklepu po linku
    if "helion.pl" in url:
        sklep = "Helion"
        wynik = pobierz_dane_helion(url)
    elif "x-kom.pl" in url:
        sklep = "X-Kom"
        wynik = pobierz_dane_xkom(url)
    else:
        # Kod 400 (Bad Request) - Użytkownik podał zły link
        raise HTTPException(status_code=400, detail="Obsługujemy tylko linki z Helion i X-Kom!")
        
    # 2. Sprawdzanie, czy scraper zgłosił jakiś problem
    if "blad" in wynik:
        raise HTTPException(status_code=400, detail=f"Błąd pobierania danych: {wynik['blad']}")
        
    # 3. Zapisujemy dane do bazy przy pomocy SQLAlchemy (ORM)
    # data_zapisu wygeneruje się sama, bo tak ustawiliśmy w models.py!
    nowy_rekord = models.HistoriaCen(
        sklep=sklep,
        tytul=wynik['tytul'],
        url=url,
        cena=wynik['cena']
    )
    db.add(nowy_rekord)
    db.commit()
    
    # 4. Zwracamy radosny komunikat i pobrane dane
    return {
        "wiadomosc": "Sukces! Produkt został dodany do bazy.",
        "sklep": sklep,
        "tytul": wynik['tytul'],
        "cena": wynik['cena']
    }
from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler

# Importujemy nasze własne pliki
import models
from models import SessionLocal, engine
from security import get_password_hash, verify_password
from scraper import pobierz_dane_helion, pobierz_dane_xkom

# Inicjalizujemy serwer FastAPI
app = FastAPI(title="Price Tracker API")
# Wskazujemy FastAPI, gdzie leżą nasze pliki HTML
templates = Jinja2Templates(directory="templates")

# --- DEPENDENCY ---
# Funkcja otwierająca i zamykająca połączenie z bazą dla każdego zapytania
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- ROBOT DO AKTUALIZACJI CEN W TLE ---
def sprawdz_ceny_w_tle():
    print("🤖 [ROBOT] Rozpoczynam sprawdzanie cen w tle...")
    
    # Ponieważ nie jesteśmy w endpoincie, musimy sami otworzyć sesję z bazą
    db = models.SessionLocal()
    try:
        # Wyciągamy z bazy tylko unikalne linki i ich sklepy, żeby nie sprawdzać 10 razy tego samego
        unikalne_produkty = db.query(models.HistoriaCen.url, models.HistoriaCen.sklep).distinct().all()
        
        if not unikalne_produkty:
            print("🤖 [ROBOT] Baza jest pusta. Nie mam czego sprawdzać.")
            return

        for produkt in unikalne_produkty:
            url = produkt.url
            sklep = produkt.sklep
            print(f"🤖 [ROBOT] Sprawdzam: {url}")
            
            # Odpalamy scrapery
            if sklep == "Helion":
                wynik = pobierz_dane_helion(url)
            elif sklep == "X-Kom":
                wynik = pobierz_dane_xkom(url)
            else:
                continue
                
            # Jeśli scraper zadziałał, zapisujemy nowy punkt w historii!
            if "blad" not in wynik:
                nowy_rekord = models.HistoriaCen(
                    sklep=sklep,
                    tytul=wynik['tytul'],
                    url=url,
                    cena=wynik['cena']
                )
                db.add(nowy_rekord)
                
        # Zapisujemy wszystko na sam koniec
        db.commit()
        print("🤖 [ROBOT] Wszystkie ceny zostały zaktualizowane!")
        
    except Exception as e:
        print(f"🤖 [ROBOT] Wystąpił błąd: {e}")
    finally:
        db.close() # Pamiętamy o sprzątaniu!

# --- SCHEMATY PYDANTIC ---
# Klasa określająca,jakie dane wymagane od użytkownika
class UzytkownikRejestracja(BaseModel):
    username: str
    password: str
# Klasa do przechowywania i przekazywania linku do produktu podanego przez uzytkownika
class NowyProdukt(BaseModel):
    url: str
# ================================
#           ONSTARTUP
# ================================

@app.on_event("startup")
def start_scheduler():
    scheduler = BackgroundScheduler()
    # Długość cyklu (TO DO ustawic na hours=24)
    scheduler.add_job(sprawdz_ceny_w_tle, 'interval', minutes=1)
    scheduler.start()



# ==========================================
#               ENDPOINTY
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
        
    # 2. Szyfrowanie hasła
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
        # Kod 401, "Unauthorized"
        raise HTTPException(status_code=401, detail="Nieprawidłowa nazwa użytkownika lub hasło")
        
    return {"wiadomosc": f"Witaj {dane.username}! Zalogowano pomyślnie."}

@app.get("/produkty")
def pokaz_wszystkie_produkty(db: Session = Depends(get_db)):
    # SQLAlchemy wyciąga wszystko z tabeli HistoriaCen
    wszystkie_wpisy = db.query(models.HistoriaCen).all()
    return wszystkie_wpisy

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
        # Kod 400 (Bad Request)
        raise HTTPException(status_code=400, detail="Obsługujemy tylko linki z Helion i X-Kom!")
        
    # 2. Sprawdzanie, czy scraper zgłosił jakiś problem
    if "blad" in wynik:
        raise HTTPException(status_code=400, detail=f"Błąd pobierania danych: {wynik['blad']}")
        
    # 3. Zapisujemy dane do bazy przy pomocy SQLAlchemy (ORM)
    # data_zapisu autogenerowana
    nowy_rekord = models.HistoriaCen(
        sklep=sklep,
        tytul=wynik['tytul'],
        url=url,
        cena=wynik['cena']
    )
    db.add(nowy_rekord)
    db.commit()
    
    # 4. Zwracamy pobrane dane
    return {
        "wiadomosc": "Sukces! Produkt został dodany do bazy.",
        "sklep": sklep,
        "tytul": wynik['tytul'],
        "cena": wynik['cena']
    }

# --- FRONTEND ENDPOINTY ---

@app.get("/login", response_class=HTMLResponse)
def strona_logowania(request: Request):
    # Podajemy argumenty z ich oficjalnymi nazwami
    return templates.TemplateResponse(request=request, name="login.html")

@app.post("/zaloguj-html")
def zaloguj_z_formularza(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    # Szukamy użytkownika
    uzytkownik = db.query(models.Uzytkownik).filter(models.Uzytkownik.username == username).first()
    
    # Sprawdzamy hasło
    if not uzytkownik or not verify_password(password, uzytkownik.hashed_password):
        # Odświeżamy stronę logowania, ale tym razem przekazujemy zmienną "blad"
        return templates.TemplateResponse(
            request=request, 
            name="login.html", 
            context={"blad": "Nieprawidłowy login lub hasło!"}
        )
        
    # Jeśli wszystko się zgadza, przekierowujemy do panelu głównego (Dashboarda)
    return RedirectResponse(url="/dashboard", status_code=303)

@app.get("/dashboard", response_class=HTMLResponse)
def panel_glowny(request: Request, db: Session = Depends(get_db)):
    # Wyciągamy z bazy całą historię cen, sort od najnowszych
    produkty_z_bazy = db.query(models.HistoriaCen).order_by(models.HistoriaCen.data_zapisu.desc()).all()
    
    # Przekazujemy listę do naszego pliku HTML jako zmienną "produkty"
    return templates.TemplateResponse(
        request=request, 
        name="dashboard.html", 
        context={"produkty": produkty_z_bazy}
    )

@app.post("/dodaj-produkt-html")
def dodaj_produkt_z_formularza(url: str = Form(...), db: Session = Depends(get_db)):
    # Identyczna logika rozpoznawania sklepu jak wcześniej
    if "helion.pl" in url:
        sklep = "Helion"
        wynik = pobierz_dane_helion(url)
    elif "x-kom.pl" in url:
        sklep = "X-Kom"
        wynik = pobierz_dane_xkom(url)
    else:
        # Jeśli zły link, wracamy do panelu (TO DO obsluga bledu)
        return RedirectResponse(url="/dashboard", status_code=303)
        
    if "blad" not in wynik:
        nowy_rekord = models.HistoriaCen(
            sklep=sklep,
            tytul=wynik['tytul'],
            url=url,
            cena=wynik['cena']
        )
        db.add(nowy_rekord)
        db.commit()
        
    # Po pomyślnym dodaniu produktu powrót do panelu głównego
    return RedirectResponse(url="/dashboard", status_code=303)

@app.get("/rejestracja", response_class=HTMLResponse)
def strona_rejestracji(request: Request):
    return templates.TemplateResponse(request=request, name="rejestracja.html")

@app.post("/zarejestruj-html")
def zarejestruj_z_formularza(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    # Sprawdzamy czy nazwa jest wolna
    istniejacy = db.query(models.Uzytkownik).filter(models.Uzytkownik.username == username).first()
    if istniejacy:
        return templates.TemplateResponse(
            request=request, 
            name="rejestracja.html", 
            context={"blad": "Ta nazwa użytkownika jest już zajęta!"}
        )
        
    # Szyfrujemy i zapisujemy nowego usera
    zhashowane_haslo = get_password_hash(password)
    nowy_uzytkownik = models.Uzytkownik(username=username, hashed_password=zhashowane_haslo)
    db.add(nowy_uzytkownik)
    db.commit()
    
    # Wyświetlamy komunikat o sukcesie na tej samej stronie
    return templates.TemplateResponse(
        request=request, 
        name="rejestracja.html", 
        context={"sukces": "Konto utworzone! Możesz się teraz zalogować."}
    )
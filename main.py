import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
from fastapi import FastAPI, Depends, HTTPException, Request, Form, Response
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler

# Importujemy własne pliki
import models
from models import SessionLocal, engine
from security import get_password_hash, verify_password
from scraper import pobierz_dane_helion, pobierz_dane_xkom

# Inicjalizujemy serwer FastAPI
app = FastAPI(title="Price Tracker API")
# Wskazujemy FastAPI, gdziesą pliki HTML
templates = Jinja2Templates(directory="templates")

# --- KONFIGURACJA EMAIL ---
GMAIL_ADRES = "jankowalskipricetracker@gmail.com" # Wpisz adres tego nowego konta
GMAIL_HASLO = "jdjwspkkqfoumhnr" # Bez spacji!

def wyslij_powiadomienie_email(tytul_produktu, stara_cena, nowa_cena, link):
    try:
        # Konstruujemy wiadomość
        msg = MIMEMultipart()
        msg['From'] = GMAIL_ADRES
        # W ramach testów wysyłamy maila... sami do siebie, żeby zobaczyć czy działa!
        msg['To'] = GMAIL_ADRES 
        msg['Subject'] = f"📉 Spadek ceny! {tytul_produktu}"

        body = f"""Cześć!

Cena obserwowanego przez Ciebie produktu wlasnie spadła!

Produkt: {tytul_produktu}
Stara cena: {stara_cena}
Nowa cena: {nowa_cena}

Kup teraz: {link}

Pozdrawia,
Twój zautomatyzowany Price Tracker 🤖
"""
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # Łączymy się z serwerem Google
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls() # Szyfrowanie połączenia
        server.login(GMAIL_ADRES, GMAIL_HASLO)
        
        # Wysyłamy i zamykamy!
        text = msg.as_string()
        server.sendmail(GMAIL_ADRES, GMAIL_ADRES, text)
        server.quit()
        print(f"📧 [EMAIL] Wysłano radosną nowinę o spadku ceny!")
        
    except Exception as e:
        print(f"📧 [EMAIL ERROR] Nie udało się wysłać maila: {e}")

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
    db = models.SessionLocal()
    try:
        # Wyciągamy unikalne linki, żeby nie męczyć stron (np. jak 5 osób śledzi to samo)
        unikalne_produkty = db.query(models.HistoriaCen.url, models.HistoriaCen.sklep).distinct().all()
        
        if not unikalne_produkty:
            print("🤖 [ROBOT] Baza jest pusta. Nie mam czego sprawdzać.")
            return

        for produkt in unikalne_produkty:
            url = produkt.url
            sklep = produkt.sklep
            
            if sklep == "Helion":
                wynik = pobierz_dane_helion(url)
            elif sklep == "X-Kom":
                wynik = pobierz_dane_xkom(url)
            else:
                continue
                
            if "blad" not in wynik:
                # Szukamy, jacy użytkownicy śledzą ten konkretny link
                zainteresowani = db.query(models.HistoriaCen.uzytkownik_id).filter(models.HistoriaCen.url == url).distinct().all()
                
                for (user_id,) in zainteresowani:
                    
                    # MAGIA POWIADOMIEŃ: Wyciągamy ostatnią zapisaną cenę dla tego usera
                    ostatni_rekord = db.query(models.HistoriaCen).filter(
                        models.HistoriaCen.uzytkownik_id == user_id, 
                        models.HistoriaCen.url == url
                    ).order_by(models.HistoriaCen.data_zapisu.desc()).first()
                    
                    # Jeśli mamy z czym porównać (to nie jest pierwsze dodanie)
                    if ostatni_rekord:
                        # Tłumaczymy tekst (np. "59,40 zł") na liczby ułamkowe do matematyki
                        stara_cena_float = float(ostatni_rekord.cena.replace(" zł", "").replace(",", ".").replace(" ", ""))
                        nowa_cena_float = float(wynik['cena'].replace(" zł", "").replace(",", ".").replace(" ", ""))
                        
                        # Jeśli jest taniej - wysyłamy maila! (zmiana na == dla testu)!!!
                        if nowa_cena_float < stara_cena_float:
                            print(f"📉 [PROMOCJA] {wynik['tytul']} jest tańszy! Wysyłam maila...")
                            wyslij_powiadomienie_email(wynik['tytul'], ostatni_rekord.cena, wynik['cena'], url)
                    
                    # Normalnie dodajemy nowy wpis do bazy (niezależnie czy spadło czy nie)
                    nowy_rekord = models.HistoriaCen(
                        sklep=sklep,
                        tytul=wynik['tytul'],
                        url=url,
                        cena=wynik['cena'],
                        uzytkownik_id=user_id
                    )
                    db.add(nowy_rekord)
                    
        db.commit()
        print("🤖 [ROBOT] Wszystkie ceny zostały zaktualizowane!")
    except Exception as e:
        print(f"🤖 [ROBOT] Wystąpił błąd: {e}")
    finally:
        db.close()

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
    # Ktokolwiek wejdzie na główny adres, od razu ląduje w formularzu logowania
    return RedirectResponse(url="/login", status_code=303)

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
    uzytkownik = db.query(models.Uzytkownik).filter(models.Uzytkownik.username == username).first()
    
    if not uzytkownik or not verify_password(password, uzytkownik.hashed_password):
        return templates.TemplateResponse(
            request=request, 
            name="login.html", 
            context={"blad": "Nieprawidłowy login lub hasło!"}
        )
        
    # SUKCES! Zamiast po prostu przekierować, tworzymy obiekt odpowiedzi
    response = RedirectResponse(url="/dashboard", status_code=303)
    # Naklejamy na niego ciasteczko (ważne przez jeden dzień), żeby serwer nas pamiętał
    response.set_cookie(key="zalogowany_uzytkownik", value=uzytkownik.username, max_age=86400)
    
    return response

@app.get("/dashboard", response_class=HTMLResponse)
def panel_glowny(request: Request, db: Session = Depends(get_db)):
    aktywny_user = request.cookies.get("zalogowany_uzytkownik")
    if not aktywny_user:
        return RedirectResponse(url="/login", status_code=303)
        
    uzytkownik = db.query(models.Uzytkownik).filter(models.Uzytkownik.username == aktywny_user).first()
    
    # Wyciągamy dane do tabeli HTML (od najnowszych)
    produkty_z_bazy = db.query(models.HistoriaCen).filter(models.HistoriaCen.uzytkownik_id == uzytkownik.id).order_by(models.HistoriaCen.data_zapisu.desc()).all()
    
    # --- PRZYGOTOWANIE DANYCH DLA CHART.JS ---
    # Do wykresu wyciągamy od najstarszych, żeby czas szedł od lewej do prawej
    produkty_rosnaco = db.query(models.HistoriaCen).filter(models.HistoriaCen.uzytkownik_id == uzytkownik.id).order_by(models.HistoriaCen.data_zapisu.asc()).all()
    
    dane_wykresow = {}
    for p in produkty_rosnaco:
        if p.tytul not in dane_wykresow:
            dane_wykresow[p.tytul] = {"daty": [], "ceny": []}
            
        # Zmieniamy tekst "59,40 zł" na ułamek 59.40
        czysta_cena = p.cena.replace(" zł", "").replace(",", ".").replace(" ", "")
        try:
            cena_float = float(czysta_cena)
        except ValueError:
            continue # Pomijamy ewentualne błędy parsowania
            
        # Skracamy format daty, żeby ładnie wyglądał na wykresie
        data_str = p.data_zapisu.strftime("%Y-%m-%d %H:%M")
        
        dane_wykresow[p.tytul]["daty"].append(data_str)
        dane_wykresow[p.tytul]["ceny"].append(cena_float)
        
    # Pakujemy słownik w format JSON
    dane_json = json.dumps(dane_wykresow)
    
    return templates.TemplateResponse(
        request=request, 
        name="dashboard.html", 
        context={
            "produkty": produkty_z_bazy, 
            "username": aktywny_user,
            "dane_wykresow": dane_json # Wysyłamy nową paczkę na stronę!
        }
    )

@app.post("/dodaj-produkt-html")
def dodaj_produkt_z_formularza(request: Request, url: str = Form(...), db: Session = Depends(get_db)):
    # 1. Sprawdzamy kto dodaje link (wyciągamy z ciasteczka)
    aktywny_user = request.cookies.get("zalogowany_uzytkownik")
    if not aktywny_user:
        return RedirectResponse(url="/login", status_code=303)
        
    uzytkownik = db.query(models.Uzytkownik).filter(models.Uzytkownik.username == aktywny_user).first()
    
    # 2. Rozpoznawanie sklepu i skrapowanie
    if "helion.pl" in url:
        sklep = "Helion"
        wynik = pobierz_dane_helion(url)
    elif "x-kom.pl" in url:
        sklep = "X-Kom"
        wynik = pobierz_dane_xkom(url)
    else:
        return RedirectResponse(url="/dashboard?blad=Nieobsługiwany link! Obsługujemy tylko Helion i X-Kom.", status_code=303)
        
    if "blad" in wynik:
        # Jeśli scraper rzucił błędem (np. strona nie istnieje)
        return RedirectResponse(url=f"/dashboard?blad=Błąd pobierania: {wynik['blad']}", status_code=303)

    # 3. Zapisujemy dane i podpinamy je pod uzytkownik_id!
    if "blad" not in wynik:
        nowy_rekord = models.HistoriaCen(
            sklep=sklep,
            tytul=wynik['tytul'],
            url=url,
            cena=wynik['cena'],
            uzytkownik_id=uzytkownik.id  # <--- MAGIA IZOLACJI DANYCH
        )
        db.add(nowy_rekord)
        db.commit()
        
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

@app.get("/wyloguj")
def wyloguj():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("zalogowany_uzytkownik") # Usuwamy ciasteczko!
    return response
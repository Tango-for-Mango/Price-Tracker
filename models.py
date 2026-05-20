from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime

# --- KONFIGURACJA BAZY DANYCH ---
SQLALCHEMY_DATABASE_URL = "sqlite:///./price_tracker.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# --- MODELE BAZY DANYCH ---
class Uzytkownik(Base):
    __tablename__ = "uzytkownicy"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    
    # Relacja z produktami
    produkty = relationship("HistoriaCen", back_populates="wlasciciel")

class HistoriaCen(Base):
    __tablename__ = "historia_cen"
    
    id = Column(Integer, primary_key=True, index=True)
    sklep = Column(String)
    tytul = Column(String)
    url = Column(String)
    cena = Column(String)
    data_zapisu = Column(DateTime, default=datetime.utcnow)
    
    # Klucz obcy - przypisanie do użytkownika
    uzytkownik_id = Column(Integer, ForeignKey("uzytkownicy.id"))
    
    # Relacja zwrotna
    wlasciciel = relationship("Uzytkownik", back_populates="produkty")

# Ta linijka mówi bazie: "Stwórz wszystkie tabele na podstawie powyższych klas"
Base.metadata.create_all(bind=engine)
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

# 1. Konfiguracja połączenia z istniejącą bazą SQLite
SQLALCHEMY_DATABASE_URL = "sqlite:///./price_tracker.db"

# "silnik" łączący się z bazą
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False} # Wymagane dla SQLite w FastAPI
)

# Fabryka sesji (będzie używana do każdego zapytania do bazy)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Baza dla naszych klas (od niej będą dziedziczyć modele)
Base = declarative_base()

# ==========================================
#             MODELE (TABELE)
# ==========================================

class Uzytkownik(Base):
    __tablename__ = "uzytkownicy"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

class HistoriaCen(Base):
    __tablename__ = "historia_cen"

    id = Column(Integer, primary_key=True, index=True)
    sklep = Column(String)
    tytul = Column(String)
    url = Column(String)
    cena = Column(String)
    data_zapisu = Column(DateTime, default=datetime.utcnow)

# Tworzy tabele w bazie danych (jeśli jeszcze nie istnieją)
Base.metadata.create_all(bind=engine)
from passlib.context import CryptContext

# kontekst szyfrowania na algorytm bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """Zamienia zwykłe hasło na nieczytelny ciąg znaków."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Sprawdza, czy podane hasło pasuje do tego w bazie."""
    return pwd_context.verify(plain_password, hashed_password)
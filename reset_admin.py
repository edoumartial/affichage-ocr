import bcrypt
from sqlalchemy import create_engine, text

# Même URL que dans caso.py
DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/affichage_ocr_db"
engine = create_engine(DATABASE_URL)

new_password = "admin".encode('utf-8') # Mettez votre mot de passe simple ici
hashed = bcrypt.hashpw(new_password, bcrypt.gensalt()).decode('utf-8')

with engine.connect() as conn:
    conn.execute(text("UPDATE users SET password_hash = :hash WHERE username = 'admin'"), {"hash": hashed})
    conn.commit()
    print("Mot de passe admin réinitialisé à 'admin'")
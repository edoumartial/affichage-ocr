import bcrypt
from sqlalchemy import create_engine, text

# Configuration
DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/caso_ocr_db"
engine = create_engine(DATABASE_URL)

def migrer_mots_de_passe():
    with engine.connect() as conn:
        # 1. Récupérer les utilisateurs
        users = conn.execute(text("SELECT id, username, password_hash FROM users")).fetchall()
        
        for user in users:
            # Vérifier si c'est déjà un hash (commence par $2b$)
            if user.password_hash and not user.password_hash.startswith("$2b$"):
                print(f"Migration de : {user.username}")
                
                # 2. Hachage avec bcrypt natif
                # On tronque à 72 octets max pour éviter l'erreur de bcrypt
                pwd_bytes = user.password_hash[:72].encode('utf-8')
                salt = bcrypt.gensalt()
                hashed = bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')
                
                # 3. Mise à jour
                conn.execute(
                    text("UPDATE users SET password_hash = :hash WHERE id = :id"),
                    {"hash": hashed, "id": user.id}
                )
        conn.commit()
    print("Migration terminée avec succès.")

if __name__ == "__main__":
    migrer_mots_de_passe()
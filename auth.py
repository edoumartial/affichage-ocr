import bcrypt
from datetime import datetime, timedelta
from jose import jwt

SECRET_KEY = "VOTRE_CLE_TRES_SECRETE_ET_UNIQUE" # À changer impérativement
ALGORITHM = "HS256"

# Vérification du mot de passe
def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

# Génération du Token JWT
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=60)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
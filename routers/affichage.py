from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from typing import List
import shutil
import os
from pathlib import Path
from extraction import affiner_extraction
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError
from auth import SECRET_KEY, ALGORITHM, verify_password, create_access_token
import bcrypt

##################
def safe_truncate(text, length=100):
    if text is None: return "Non trouvé"
    return str(text)[:length]
##################

router = APIRouter()

DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/affichage_ocr_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("sub") is None:
            raise HTTPException(status_code=401, detail="Token invalide")
        return payload  # On retourne tout le payload pour avoir accès au rôle
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalide")
    

def check_admin(user: dict = Depends(get_current_user)):
    # On convertit le rôle en minuscule pour comparer avec la base
    role = user.get("role", "").lower()
    if role != "admin": 
        raise HTTPException(
            status_code=403, 
            detail="Accès réservé aux administrateurs"
        )
    return user

@router.post("/ajouter-utilisateur/")
async def ajouter_utilisateur(
    username: str = Form(...), 
    password: str = Form(...), 
    role: str = Form("Utilisateur"),
    db: Session = Depends(get_db),
    admin: dict = Depends(check_admin) # <--- La sécurité est appliquée ici
):
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    try:
        db.execute(text("INSERT INTO users (username, password_hash, role) VALUES (:u, :p, :r)"), 
                   {"u": username, "p": hashed, "r": role})
        db.commit()
        return {"message": "Utilisateur créé avec succès"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Erreur lors de la création")

# --- LOGIN ---
@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Récupérer le hash ET le rôle
    user = db.execute(text("SELECT password_hash, role FROM users WHERE username = :u"), {"u": form_data.username}).fetchone()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Identifiants incorrects")
    
    # Inclusion du rôle dans le token
    return {
        "access_token": create_access_token(data={"sub": form_data.username, "role": user.role}), 
        "token_type": "bearer"
    }

# --- UPLOAD MULTIPLE ---
@router.post("/upload-multiple/")
async def upload_multiple(files: List[UploadFile] = File(...), current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    BASE_DIR = Path(__file__).resolve().parent.parent
    UPLOAD_DIR = BASE_DIR / "uploads"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
    # Extraction sécurisée du nom d'utilisateur
    username = current_user.get("sub") 
    
    for file in files:
        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Insertion document : on utilise 'username' (str) et non 'current_user' (dict)
        doc_id = db.execute(text("INSERT INTO documents (filename, uploaded_by) VALUES (:fn, :u) RETURNING id"), 
                           {"fn": file.filename, "u": username}).scalar()
        db.commit()
        
        # OCR
        extracted_data = affiner_extraction(str(file_path))
        if "error" in extracted_data:
            # Gérer l'erreur (ex: loguer ou arrêter le traitement du fichier)
            raise HTTPException(status_code=500, detail=extracted_data["error"])
        
        # Insertion dans affichage_data
        # --- Dans upload_multiple ---
        # Insertion dans affichage_data (remplace l'ancienne insertion)
        db.execute(text("""
            INSERT INTO affichage_data (
                document_id, lettre_date, requerant, parcelle, section, 
                commune, lieu_dit, extraction_ocr
            )
            VALUES (:did, :ld, :r, :p, :s, :c, :ldt, :raw)
        """), {
            "did": doc_id,
            "ld": safe_truncate(extracted_data.get("lettre_date")),
            "r": safe_truncate(extracted_data.get("requerant")),
            "p": safe_truncate(extracted_data.get("parcelle")),
            "s": safe_truncate(extracted_data.get("section")),
            "c": safe_truncate(extracted_data.get("commune")),
            "ldt": safe_truncate(extracted_data.get("lieu_dit")),
            "raw": extracted_data.get("extraction_ocr")
        })
        db.commit()
    return {"message": "Upload et OCR terminés"}


# --- VALIDER DOCUMENT ---
@router.post("/valider-document/{caso_id}")
async def valider_document(
    caso_id: int, 
    numero_affichage: str = Form(...),  # Correspond au champ "N° Affichage"
    lettre_date: str = Form(...),       # Correspond au champ "Date Lettre"
    validated_at: str = Form(...),      # Correspond au champ "Upload" de l'interface
    requerant: str = Form(...),
    parcelle: str = Form(...),
    section: str = Form(...),
    commune: str = Form(...),
    lieu_dit: str = Form(...),
    extraction_ocr: str = Form(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # 1. Vérification de l'existence du document
    doc_result = db.execute(
        text("SELECT statut FROM affichage_data WHERE id = :id"), 
        {"id": caso_id}
    ).fetchone()

    if not doc_result:
        raise HTTPException(status_code=404, detail="Document non trouvé")
    
    # 2. Règle de sécurité : Seul un admin peut modifier un document déjà validé
    statut_actuel = doc_result[0]
    if statut_actuel == 'valide' and current_user.get("role") != "Administrateur":
        raise HTTPException(
            status_code=403, 
            detail="Ce document est déjà validé. Seul un administrateur peut le modifier."
        )

    # 3. Mise à jour de la base de données
    try:
        db.execute(text("""
            UPDATE affichage_data 
            SET numero_affichage = :na,
                lettre_date = :ld,
                validated_at = :vat,
                requerant = :r, 
                parcelle = :p, 
                section = :s, 
                commune = :c, 
                lieu_dit = :ldt, 
                extraction_ocr = :raw, 
                statut = 'valide',
                valide_par = :vp
            WHERE id = :id
        """), {
            "id": caso_id,
            "na": numero_affichage,
            "ld": lettre_date,
            "vat": validated_at,  # Valeur du champ "Upload"
            "r": requerant,
            "p": parcelle,
            "s": section,
            "c": commune,
            "ldt": lieu_dit,
            "raw": extraction_ocr,
            "vp": current_user.get("sub")
        })
        
        db.commit() 
        return {"message": "Document validé et enregistré avec succès"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de la mise à jour : {str(e)}")


# --- Dans get_tous_documents ---
@router.get("/tous-les-documents/")
async def get_tous_documents(
    current_user: dict = Depends(get_current_user), 
    db: Session = Depends(get_db)
):    
    """
    Récupère la liste de tous les documents avec leurs données d'affichage associées.
    """
    try:
        # Exécution de la requête SQL pour joindre les tables documents et affichage_data
        result = db.execute(text("""
            SELECT 
                c.id AS id, 
                d.filename, 
                c.lettre_date, 
                c.requerant, 
                c.parcelle, 
                c.section, 
                c.commune, 
                c.lieu_dit, 
                c.statut, 
                d.created_at,
                c.extraction_ocr 
            FROM affichage_data c 
            JOIN documents d ON c.document_id = d.id
            ORDER BY d.created_at DESC
        """))
        
        # Transformation des résultats en une liste de dictionnaires
        # row._mapping permet d'accéder aux colonnes par leur nom
        documents = [dict(row._mapping) for row in result]
        
        # Conversion optionnelle des objets datetime en chaînes de caractères 
        # pour éviter les erreurs de sérialisation JSON
        for doc in documents:
            if doc.get("created_at"):
                doc["created_at"] = doc["created_at"].isoformat()
        
        return documents
        
    except Exception as e:
        # Gestion des erreurs de base de données
        raise HTTPException(
            status_code=500, 
            detail=f"Erreur lors de la récupération des documents : {str(e)}"
        )

# --- CRUD USERS ---

@router.get("/users/")
async def get_users(db: Session = Depends(get_db), admin: dict = Depends(check_admin)):
    # On sélectionne les colonnes réelles de votre table
    users = db.execute(text("SELECT id, username, role, is_active FROM users")).fetchall()
    return [dict(row._mapping) for row in users]

@router.post("/users/")
async def create_user(
    username: str = Form(...), 
    password: str = Form(...), 
    role: str = Form("correcteur"), 
    db: Session = Depends(get_db),
    admin: dict = Depends(check_admin)
):
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    try:
        # Utilisation de password_hash et is_active
        db.execute(text("""
            INSERT INTO users (username, password_hash, role, is_active) 
            VALUES (:u, :p, :r, true)
        """), {"u": username, "p": hashed, "r": role})
        db.commit()
        return {"message": "Utilisateur créé"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    

@router.delete("/users/{user_id}")
async def delete_user(user_id: int, db: Session = Depends(get_db), admin: dict = Depends(check_admin)):
    db.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
    db.commit()
    return {"message": "Utilisateur supprimé"}

@router.put("/users/{user_id}")
async def update_user(
    user_id: int, 
    data: dict, # On utilise 'dict' au lieu de 'UserUpdateSchema'
    db: Session = Depends(get_db), 
    admin: dict = Depends(check_admin)
):
    # Récupération des données du dictionnaire
    username = data.get("username")
    password = data.get("password")
    
    # Logique de mise à jour
    if password and password.strip() != "":
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        db.execute(text("UPDATE users SET username = :u, password_hash = :p WHERE id = :id"), 
                   {"u": username, "p": hashed, "id": user_id})
    else:
        db.execute(text("UPDATE users SET username = :u WHERE id = :id"), 
                   {"u": username, "id": user_id})
    
    db.commit()
    return {"message": "Utilisateur mis à jour avec succès"}
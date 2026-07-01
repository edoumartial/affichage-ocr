import os
# Évite le conflit de DLL OpenMP sous Windows
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import easyocr
from routers import affichage
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

# Initialisation de l'application
app = FastAPI(
    title="AFFICHAGE OCR API",
    description="API d'extraction utilisant EasyOCR et FastAPI",
    version="1.0.0"
)

# Configuration CORS pour autoriser les requêtes depuis votre interface (Live Server, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURATION FICHIERS STATIQUES ---
# Assurez-vous que le dossier 'uploads' existe bien à la racine de votre projet
if not os.path.exists("uploads"):
    os.makedirs("uploads")

# Monte le dossier 'uploads' sur la route '/static'
app.mount("/static", StaticFiles(directory="uploads"), name="static")
# ----------------------------------------

# Chargement unique du modèle pour optimiser les performances
print("Chargement des modèles EasyOCR...")
reader = easyocr.Reader(['fr', 'en'], gpu=False)
print("Modèles prêts !")

# Inclusion du routeur
app.include_router(affichage.router)



@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # 1. Vérification des identifiants (utilisez votre fonction de vérification)
    # user = authenticate_user(form_data.username, form_data.password)
    
    # Pour l'exemple, supposons que vous ayez une fonction auth.verify_user :
    user = verify_user(form_data.username, form_data.password) # À adapter selon votre logique
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nom d'utilisateur ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 2. Génération du token (en supposant que vous avez une fonction create_access_token)
    access_token = create_access_token(data={"sub": user["username"], "role": user["role"]})
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/")
def read_root():
    return {"status": "online", "engine": "EasyOCR"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
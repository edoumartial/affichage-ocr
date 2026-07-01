import re
import easyocr
import numpy as np
from pdf2image import convert_from_path
# --- AJOUTEZ CE BLOC ICI ---
from PIL import Image
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

# Initialisation du lecteur
# Note : Le premier lancement téléchargera les modèles si nécessaire
reader = easyocr.Reader(['fr', 'en'], gpu=False)

def affiner_extraction(file_path):
    """Extrait le texte et structure les données via regex avec les nouvelles bornes."""
    texte_complet = ""
    try:
        # Conversion du PDF en images
        pages = convert_from_path(file_path, dpi=300)
        for page in pages:
            image_np = np.array(page)
            # Lecture du texte
            resultats = reader.readtext(image_np, detail=0)
            texte_complet += " ".join(resultats) + " "
    except Exception as e:
        return {"error": str(e)}

    # Nettoyage des espaces multiples
    texte_propre = re.sub(r'\s+', ' ', texte_complet)
    
    # Définition des patterns avec vos bornes précises
    patterns = {
        "lettre_date": r"en date du (.*?)\s*,",
        "requerant": r"en date du .*?,\s*(.*?)\s*a sollicité",
        "parcelle": r"la parcelle n\s*(.*?)\s*, de la section",
        "section": r"de la section (.*?) du plan cadastral",
        "commune": r"du plan cadastral (.*?),\s*au lieu-dit",
        "lieu_dit": r"au lieu-dit (.*?),\s*supporte",
    }
    
    # Initialisation des résultats
    data = {cle: "Non trouvé" for cle in patterns.keys()}
    
    # Extraction via regex
    for cle, motif in patterns.items():
        match = re.search(motif, texte_propre, re.IGNORECASE)
        if match:
            data[cle] = match.group(1).strip()
            
    # Ajout du texte brut pour vérification
    data["extraction_ocr"] = texte_propre
    return data

import json

# --- Votre code actuel (importations et définition de affiner_extraction) ---

# --- Code pour afficher les résultats ---

if __name__ == "__main__":
    # Remplacez par le chemin réel vers votre fichier PDF
    chemin_pdf = "affichage 1.pdf" 
    
    print(f"--- Démarrage de l'analyse pour : {chemin_pdf} ---")
    
    # Appel de la fonction
    resultats = affiner_extraction(chemin_pdf)
    
    # Affichage structuré
    if "error" in resultats:
        print(f"Erreur lors de l'extraction : {resultats['error']}")
    else:
        print("\n=== Données extraites avec succès ===")
        # On affiche chaque élément sauf le texte brut qui est très long
        for cle, valeur in resultats.items():
            if cle != "extraction_ocr":
                print(f"{cle.upper():<15} : {valeur}")
        
        print("\n=== Aperçu du texte brut extrait (début) ===")
        print(resultats["extraction_ocr"][:200] + "...")
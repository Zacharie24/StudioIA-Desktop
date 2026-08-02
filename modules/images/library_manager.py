import json, os, sys, requests, shutil, random, gc, time
from pathlib import Path

# Support relative imports when called as module or direct
try:
    from ..api_keys import PEXELS_KEY, UNSPLASH_KEY
except (ImportError, ValueError):
    # When called directly from PowerShell, api_keys is in parent modules/
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from api_keys import PEXELS_KEY, UNSPLASH_KEY

try:
    from core import paths
except ImportError:
    _rac = Path(__file__).resolve().parent
    while not (_rac / "core" / "paths.py").exists() and _rac.parent != _rac:
        _rac = _rac.parent
    sys.path.insert(0, str(_rac))
    from core import paths

# Timeout pour les requêtes IA (évite les blocages)
OLLAMA_TIMEOUT = 60

def requete_avec_retry(url, json_data, max_retries=3, timeout=OLLAMA_TIMEOUT):
    """
    Effectue une requête HTTP avec retry et backoff exponentiel
    Pour gérer les tempêtes ou surcharge de l'IA locale
    """
    derniere_erreur = None
    for tentative in range(max_retries):
        try:
            r = requests.post(url, json=json_data, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.exceptions.RequestException as e:
            derniere_erreur = e
            if tentative < max_retries - 1:
                # Backoff exponentiel: 1s, 2s, 4s
                delai = 2 ** tentative
                log(f"Tentative {tentative + 1}/{max_retries} échouée, attente {delai}s...")
                time.sleep(delai)
            else:
                log(f"Toutes les tentatives ({max_retries}) ont échoué")
    raise derniere_erreur

def log(msg):
    print(f"[IMAGES] {msg}")

def lire_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def ecrire_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def generer_mots_cles(sujet, langue):
    style = lire_json(paths.chemin_app("style_redaction.json"))
    eviter = ", ".join(style.get("mots_a_eviter", []))
    # Create a privilege list from the new style format
    privilegier_list = []
    privilegier_list.extend(style.get("regles_generales", []))
    privilegier_list.extend(style.get("regles_priere", []))
    privilegier_list.extend(style.get("regles_storytelling", []))
    privilegier = ", ".join(privilegier_list)

    prompt = f"""Tu es un expert en recherche d images pour YouTube.
Sujet : "{sujet}"
Langue du projet : {langue}
A eviter absolument : {eviter}
A privilegier : {privilegier}
Genere 10 mots-cles simples en anglais (1-2 mots max) pour images de fond.
Genere 5 mots-cles simples en anglais pour PNG/overlays.
UNIQUEMENT JSON valide :
{{"backgrounds": ["mot1","mot2","mot3","mot4","mot5","mot6","mot7","mot8","mot9","mot10"], "overlays": ["mot1","mot2","mot3","mot4","mot5"]}}"""

    try:
        r = requete_avec_retry(
            "http://localhost:11434/api/generate",
            {"model": "mistral", "prompt": prompt, "stream": False}
        )
        texte = r.json()["response"]
        debut = texte.find("{")
        fin = texte.rfind("}") + 1
        return json.loads(texte[debut:fin])
    except Exception as e:
        log(f"Erreur generation mots-cles: {e}")
        return {"backgrounds": [], "overlays": []}

def generer_nom(sujet, mot_cle, index, type_img, langue):
    prompt = f"""Sujet video : "{sujet}", langue : {langue}, mot-cle image : "{mot_cle}".
Donne un nom de fichier descriptif en {langue}, sans espaces, sans accents, minuscules, underscores, max 4 mots.
UNIQUEMENT le nom sans extension."""
    try:
        r = requete_avec_retry(
            "http://localhost:11434/api/generate",
            {"model": "mistral", "prompt": prompt, "stream": False}
        )
        nom = r.json()["response"].strip().lower()
        nom = "".join(c for c in nom.replace(" ","_").replace("-","_") if c.isalnum() or c=="_")
        return f"{type_img}_{index:02d}_{nom[:30]}"
    except Exception as e:
        log(f"Erreur generation nom: {e}")
        return f"{type_img}_{index:02d}_img"

def telecharger_pexels(mot_cle, dest_path):
    headers = {"Authorization": PEXELS_KEY}
    url = f"https://api.pexels.com/v1/search?query={mot_cle}&per_page=5&orientation=landscape"
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        photos = data.get("photos", [])
        if photos:
            # Sélection aléatoire mais vérifiée
            photo = photos[random.randint(0, min(len(photos)-1, 4))]
            img_url = photo.get("src", {}).get("large2x")
            if img_url:
                img_r = requests.get(img_url, timeout=30)
                img_r.raise_for_status()
                with open(dest_path, "wb") as f:
                    f.write(img_r.content)
                return True
    except requests.exceptions.RequestException as e:
        log(f"Pexels erreur ({mot_cle}): {e}")
    except Exception as e:
        log(f"Pexels erreur inattendue ({mot_cle}): {e}")
    return False

def telecharger_unsplash(mot_cle, dest_path):
    url = f"https://api.unsplash.com/search/photos?query={mot_cle}&per_page=5&orientation=landscape"
    headers = {"Authorization": f"Client-ID {UNSPLASH_KEY}"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        results = data.get("results", [])
        if results:
            idx = random.randint(0, min(len(results)-1, 4))
            photo = results[idx]
            img_url = photo.get("urls", {}).get("full")
            if img_url:
                img_r = requests.get(img_url, timeout=30)
                img_r.raise_for_status()
                with open(dest_path, "wb") as f:
                    f.write(img_r.content)
                return True
    except requests.exceptions.RequestException as e:
        log(f"Unsplash erreur ({mot_cle}): {e}")
    except Exception as e:
        log(f"Unsplash erreur inattendue ({mot_cle}): {e}")
    return False

def telecharger_image(mot_cle, dest_path, source="aleatoire"):
    sources = ["pexels", "unsplash"] if source == "aleatoire" else [source]
    random.shuffle(sources)
    for src in sources:
        if src == "pexels":
            if telecharger_pexels(mot_cle, dest_path):
                return True
        elif src == "unsplash":
            if telecharger_unsplash(mot_cle, dest_path):
                return True
    return False

def nettoyer_memoire():
    """Nettoyage mémoire après opérations lourdes"""
    gc.collect()

def main():
    project_path = sys.argv[1]
    pjson = os.path.join(project_path, "project.json")
    config = lire_json(paths.config_path())
    data = lire_json(pjson)

    sujet = data["sujet"]
    langue = data.get("langue", config.get("language", "fr"))

    images_dir = Path(project_path) / "images"
    bg_dir = images_dir / "backgrounds"
    overlay_dir = images_dir / "overlays"
    bg_dir.mkdir(parents=True, exist_ok=True)
    overlay_dir.mkdir(parents=True, exist_ok=True)

    assets_bg = Path(config["assets_path"]) / "backgrounds"
    assets_bg.mkdir(parents=True, exist_ok=True)

    log(f"Sujet  : {sujet}")
    log(f"Langue : {langue}")
    log("Generation mots-cles IA...")

    mots = generer_mots_cles(sujet, langue)
    backgrounds = mots.get("backgrounds", [])
    overlays    = mots.get("overlays", [])

    log(f"Fonds : {backgrounds}")
    log(f"PNG   : {overlays}")

    data["etapes"]["images"] = "en_cours"
    ecrire_json(pjson, data)

    images_data = {"backgrounds": [], "overlays": []}
    succes_bg = 0
    succes_ov = 0

    log("--- Fonds JPG (Pexels + Unsplash) ---")
    for i, mot in enumerate(backgrounds, 1):
        nom = generer_nom(sujet, mot, i, "bg", langue)
        dest = bg_dir / f"{nom}.jpg"
        dest_global = assets_bg / f"{nom}.jpg"

        if dest.exists():
            log(f"Existe deja : {nom}.jpg")
            succes_bg += 1
            images_data["backgrounds"].append({
                "fichier": f"images/backgrounds/{nom}.jpg",
                "mot_cle": mot, "nom": nom})
            continue

        log(f"Fond {i}/{len(backgrounds)} : {mot}")
        ok = telecharger_image(mot, str(dest), "aleatoire")
        if ok:
            shutil.copy(str(dest), str(dest_global))
            images_data["backgrounds"].append({
                "fichier": f"images/backgrounds/{nom}.jpg",
                "mot_cle": mot, "nom": nom})
            succes_bg += 1
            log(f"OK : {nom}.jpg")
        else:
            log(f"ECHEC : {mot}")

    log("--- PNG/SVG (Openverse) ---")
    for i, mot in enumerate(overlays, 1):
        log(f"PNG {i}/{len(overlays)} : {mot}")
        nom = generer_nom(sujet, mot, i, "ov", langue)
        dest = overlay_dir / f"{nom}.png"

        url = f"https://api.openverse.org/v1/images/?q={mot}&license_type=commercial&extension=svg&page_size=3"
        try:
            r = requests.get(url, timeout=15)
            d = r.json()
            if d.get("results"):
                img_url = d["results"][0]["url"]
                img_r = requests.get(img_url, timeout=30)
                svg_path = str(dest).replace(".png", ".svg")
                with open(svg_path, "wb") as f:
                    f.write(img_r.content)
                images_data["overlays"].append({
                    "fichier": f"images/overlays/{nom}.svg",
                    "mot_cle": mot, "nom": nom})
                succes_ov += 1
                log(f"OK : {nom}")
            else:
                log(f"ECHEC : {mot}")
        except Exception as e:
            log(f"Erreur ({mot}): {e}")

    data["images_data"] = images_data
    data["etapes"]["images"] = "termine"
    ecrire_json(pjson, data)

    log(f"Termine : {succes_bg}/{len(backgrounds)} fonds, {succes_ov}/{len(overlays)} PNG")

if __name__ == "__main__":
    main()
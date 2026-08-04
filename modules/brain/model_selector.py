import requests
import json

def log(msg):
    print(f"[MODEL] {msg}")

def modeles_disponibles():
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        modeles = [m["name"] for m in r.json().get("models", [])]
        return modeles
    except:
        return []

def choisir_meilleur_modele():
    disponibles = modeles_disponibles()
    log(f"Modeles disponibles : {disponibles}")

    # qwen3.6 BLOQUE - trop lourd pour CPU sans GPU (provoque crash)
    priorite = [
        "qwen2.5:7b",
        "qwen2.5:latest",
        "mistral:latest",
        "mistral",
        "llama3.1:8b",
        "gemma2:9b"
    ]

    for modele in priorite:
        if modele in disponibles:
            log(f"Modele selectionne : {modele}")
            return modele

    if disponibles:
        log(f"Utilisation du premier disponible : {disponibles[0]}")
        return disponibles[0]

    log("Aucun modele disponible !")
    return "mistral"

def appeler_ollama(prompt, modele=None, temperature=0.8):
    if modele is None:
        modele = choisir_meilleur_modele()
    try:
        from llm import appeler_llm
    except ImportError:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from llm import appeler_llm
    texte = appeler_llm(prompt, modele=modele, temperature=temperature)
    return texte, modele

if __name__ == "__main__":
    modele = choisir_meilleur_modele()
    print(f"Meilleur modele disponible : {modele}")
import language_tool_python
import sys, os, json
from pathlib import Path

def log(msg):
    print(f"[GRAMMAIRE] {msg}")

def lire_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def corriger_texte(texte, outil):
    # LanguageTool corrige TOUTES les erreurs grammaticales automatiquement
    matches = outil.check(texte)
    texte_corrige = language_tool_python.utils.correct(texte, matches)
    return texte_corrige, len(matches)

def corriger_projet(project_path, langue="fr"):
    ch_dir = Path(project_path) / "chapters"

    log(f"Chargement correcteur grammatical ({langue})...")
    log("Premiere utilisation = telechargement (~500MB) — attendre...")
    outil = language_tool_python.LanguageTool(langue)
    log("Correcteur pret !")

    total_erreurs = 0

    for ch_file in sorted(ch_dir.glob("*.txt")):
        log(f"Correction : {ch_file.name}")

        with open(ch_file, "r", encoding="utf-8") as f:
            texte = f.read()

        texte_corrige, nb_erreurs = corriger_texte(texte, outil)
        total_erreurs += nb_erreurs

        if texte_corrige != texte:
            with open(ch_file, "w", encoding="utf-8") as f:
                f.write(texte_corrige)
            log(f"  {ch_file.name} : {nb_erreurs} erreurs corrigees")
        else:
            log(f"  {ch_file.name} : aucune erreur")

    outil.close()
    log(f"Correction terminee — {total_erreurs} erreurs corrigees au total")

def main():
    project_path = sys.argv[1]
    pjson = os.path.join(project_path, "project.json")
    data = lire_json(pjson)
    langue = "fr" if data.get("langue", "fr") == "fr" else "en-US"
    corriger_projet(project_path, langue)

if __name__ == "__main__":
    main()
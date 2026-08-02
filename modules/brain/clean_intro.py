import os, sys, re
from pathlib import Path

def nettoyer_intro_ia(texte):
    patterns = [
        r"^Voici le chapitre \d+ sur \d+[^.]*\.\s*",
        r"^Voici le \d+[eème]+ chapitre[^.]*\.\s*",
        r"^Ce chapitre[^.]*\.\s*",
        r"^Chapitre \d+[^.]*\.\s*",
        r"^Ecris en fran[çc]ais[^.]*\.\s*",
        r"^\[.*?\]\s*",
    ]
    for pattern in patterns:
        texte = re.sub(pattern, "", texte, flags=re.IGNORECASE | re.MULTILINE)
    return texte.strip()

def main():
    project_path = sys.argv[1]
    ch_dir = Path(project_path) / "chapters"

    if not ch_dir.exists():
        print(f"Erreur : le dossier {ch_dir} n'existe pas.")
        print("Le projet est peut-etre incomplet.")
        sys.exit(1)

    corrections = 0
    for ch_file in sorted(ch_dir.glob("*.txt")):
        with open(ch_file, "r", encoding="utf-8") as f:
            texte = f.read()
        texte_nettoye = nettoyer_intro_ia(texte)
        if texte_nettoye != texte:
            with open(ch_file, "w", encoding="utf-8") as f:
                f.write(texte_nettoye)
            print(f"Nettoye : {ch_file.name}")
            corrections += 1
    print(f"Total : {corrections} fichiers nettoyes")

if __name__ == "__main__":
    main()
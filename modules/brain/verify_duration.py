import json, os, sys, requests
from pathlib import Path

try:
    from core import paths
except ImportError:
    _rac = Path(__file__).resolve().parent
    while not (_rac / "core" / "paths.py").exists() and _rac.parent != _rac:
        _rac = _rac.parent
    sys.path.insert(0, str(_rac))
    from core import paths

def log(msg):
    print(f"[VERIF-MOTS] {msg}")

def lire_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def ecrire_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def appeler_ollama(prompt, modele="mistral"):
    try:
        import sys
        sys.path.insert(0, str(paths.MODULES_DIR / "brain"))
        from model_selector import choisir_meilleur_modele
        modele = choisir_meilleur_modele()
    except:
        pass
    try:
        from llm import appeler_llm
    except ImportError:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from llm import appeler_llm
    return appeler_llm(prompt, modele=modele, temperature=0.8)

def completer_chapitre(texte_actuel, mots_manquants, sujet, titre, type_contenu, langue):
    if langue == "en":
        prompt = f"""Continue this text about "{sujet}", chapter "{titre}".
Add exactly {mots_manquants} more words to complete it.
Keep the same style and tone. Do not repeat what was already said.
Current text ends with: ...{texte_actuel[-200:]}
Continue directly:"""
    else:
        prompt = f"""Continue ce texte sur "{sujet}", chapitre "{titre}".
Ajoute exactement {mots_manquants} mots supplementaires pour le completer.
Garde le meme style et ton. Ne repete pas ce qui a deja ete dit.
Le texte actuel se termine par : ...{texte_actuel[-200:]}
Continue directement :"""

    return appeler_ollama(prompt)

def main():
    project_path = sys.argv[1]
    pjson = os.path.join(project_path, "project.json")
    config = lire_json(str(paths.config_path()))
    data = lire_json(pjson)

    duree = data.get("meta", {}).get("duree_cible", config.get("target_duration_minutes", 30))
    chapitres = data.get("chapitres", [])
    nb_chapitres = len(chapitres)

    if nb_chapitres == 0:
        log("Aucun chapitre trouve.")
        sys.exit(1)

    # Calcul objectif
    mots_total_cible = int(duree * 130 * 1.1)
    mots_par_ch_cible = mots_total_cible // nb_chapitres

    log(f"Duree cible     : {duree} minutes")
    log(f"Mots total cible: {mots_total_cible}")
    log(f"Mots/chapitre   : {mots_par_ch_cible}")

    mots_total_actuel = 0
    chapitres_trop_courts = []

    # Verifier chaque chapitre
    for ch in chapitres:
        ch_file = os.path.join(project_path, ch["script_file"])
        if not os.path.exists(ch_file):
            continue
        with open(ch_file, "r", encoding="utf-8") as f:
            texte = f.read()
        nb_mots = len(texte.split())
        mots_total_actuel += nb_mots

        seuil_minimum = int(mots_par_ch_cible * 0.7)
        if nb_mots < seuil_minimum:
            chapitres_trop_courts.append({
                "ch": ch,
                "nb_mots": nb_mots,
                "mots_manquants": mots_par_ch_cible - nb_mots,
                "texte": texte
            })
            log(f"  {ch['id']} TROP COURT : {nb_mots} mots (cible: {mots_par_ch_cible})")
        else:
            log(f"  {ch['id']} OK : {nb_mots} mots")

    duree_actuelle = mots_total_actuel / 130
    log(f"Duree actuelle  : {duree_actuelle:.0f} minutes")
    log(f"Duree cible     : {duree} minutes")

    if not chapitres_trop_courts:
        log("Tous les chapitres ont suffisamment de mots !")
        return

    log(f"{len(chapitres_trop_courts)} chapitres trop courts detectes")

    # Completer les chapitres trop courts
    langue = data.get("langue", "fr")
    sujet  = data.get("sujet", "")

    for item in chapitres_trop_courts:
        ch = item["ch"]
        log(f"Completion de {ch['id']} ({item['mots_manquants']} mots manquants)...")

        complement = completer_chapitre(
            texte_actuel=item["texte"],
            mots_manquants=item["mots_manquants"],
            sujet=sujet,
            titre=ch.get("titre", ""),
            type_contenu=data.get("type_contenu", "priere"),
            langue=langue
        )

        texte_complet = item["texte"].rstrip() + "\n\n" + complement.strip()
        ch_file = os.path.join(project_path, ch["script_file"])
        with open(ch_file, "w", encoding="utf-8") as f:
            f.write(texte_complet)

        nb_mots_final = len(texte_complet.split())
        log(f"  {ch['id']} complete : {nb_mots_final} mots")

    # Recalculer duree finale
    mots_final = sum(
        len(open(os.path.join(project_path, ch["script_file"]), encoding="utf-8").read().split())
        for ch in chapitres
        if os.path.exists(os.path.join(project_path, ch["script_file"]))
    )
    duree_finale = mots_final / 130
    log(f"Duree finale estimee : {duree_finale:.0f} minutes")

    data["meta"]["duree_estimee_minutes"] = round(duree_finale)
    ecrire_json(pjson, data)
    log("Verification mots terminee !")

if __name__ == "__main__":
    main()
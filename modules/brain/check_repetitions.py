import json, os, sys, requests
from pathlib import Path

def log(msg):
    print(f"[ANTI-REPEAT] {msg}")

def lire_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def ecrire_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def extraire_phrases(texte):
    import re
    phrases = re.split(r'[.!?]+', texte)
    return [p.strip().lower() for p in phrases if len(p.strip()) > 20]

def similarite(texte1, texte2):
    mots1 = set(texte1.lower().split())
    mots2 = set(texte2.lower().split())
    if not mots1 or not mots2:
        return 0
    intersection = mots1.intersection(mots2)
    union = mots1.union(mots2)
    return len(intersection) / len(union)

def detecter_repetitions_internes(texte, seuil=0.6):
    paragraphes = [p.strip() for p in texte.split('\n\n') if len(p.strip()) > 50]
    repetitions = []
    for i in range(len(paragraphes)):
        for j in range(i+1, len(paragraphes)):
            sim = similarite(paragraphes[i], paragraphes[j])
            if sim > seuil:
                repetitions.append({
                    "para1": i+1,
                    "para2": j+1,
                    "similarite": round(sim*100)
                })
    return repetitions

def detecter_repetitions_entre_chapitres(chapitres_textes, seuil=0.4):
    repetitions = []
    ids = list(chapitres_textes.keys())
    for i in range(len(ids)):
        for j in range(i+1, len(ids)):
            sim = similarite(chapitres_textes[ids[i]], chapitres_textes[ids[j]])
            if sim > seuil:
                repetitions.append({
                    "ch1": ids[i],
                    "ch2": ids[j],
                    "similarite": round(sim*100)
                })
    return repetitions

def regenerer_chapitre(sujet, numero, total, titre, mots_cible, langue, chapitres_precedents):
    precedents_resume = "\n".join([f"- {t}" for t in chapitres_precedents])
    
    if langue == "en":
        prompt = f"""You are a Protestant Christian author.
Write chapter {numero} of {total} about: "{sujet}"
Chapter title: {titre}

CRITICAL RULES:
- Write ONLY in English
- Exactly {mots_cible} words
- NEVER repeat ideas from previous chapters listed below
- Each sentence must be completely new and unique
- No markdown, no titles, continuous text only

Previous chapters already written (DO NOT repeat these ideas):
{precedents_resume}

Write the chapter directly:"""
    else:
        prompt = f"""Tu es un auteur chretien protestant.
Ecris le chapitre {numero} sur {total} pour : "{sujet}"
Titre : {titre}

REGLES CRITIQUES :
- Ecris UNIQUEMENT en francais
- Exactement {mots_cible} mots
- NE REPETE JAMAIS les idees des chapitres precedents listes ci-dessous
- Chaque phrase doit etre completement nouvelle et unique
- Pas de markdown, pas de titres, texte continu uniquement
- Communaute protestante evangelique, pas de symboles catholiques

Chapitres precedents deja ecrits (NE PAS repeter ces idees) :
{precedents_resume}

Ecris le chapitre directement :"""

    try:
        from llm import appeler_llm
    except ImportError:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from llm import appeler_llm
    return appeler_llm(prompt, modele="mistral", temperature=0.8,
                       options={"repeat_penalty": 1.4, "repeat_last_n": 256})

def main():
    project_path = sys.argv[1]
    pjson = os.path.join(project_path, "project.json")
    config = lire_json("C:\\StudioIA\\config.json")
    data = lire_json(pjson)

    sujet    = data["sujet"]
    langue   = data.get("langue", "fr")
    chapitres = data.get("chapitres", [])
    duree    = config.get("target_duration_minutes", 30)
    mots_par_ch = int((duree * 130) / max(len(chapitres), 1))

    log(f"Analyse du script : {sujet}")
    log(f"Chapitres a verifier : {len(chapitres)}")

    # Lire tous les chapitres
    chapitres_textes = {}
    for ch in chapitres:
        ch_file = os.path.join(project_path, ch["script_file"])
        if os.path.exists(ch_file):
            with open(ch_file, "r", encoding="utf-8") as f:
                chapitres_textes[ch["id"]] = f.read()

    if not chapitres_textes:
        log("Aucun chapitre trouve.")
        sys.exit(1)

    # 1. Verifier repetitions internes dans chaque chapitre
    log("--- Verification repetitions internes ---")
    chapitres_a_regenerer = []
    for ch_id, texte in chapitres_textes.items():
        reps = detecter_repetitions_internes(texte, seuil=0.6)
        if reps:
            log(f"  {ch_id} : {len(reps)} repetition(s) interne(s) detectee(s)")
            for r in reps:
                log(f"    Paragraphes {r['para1']} et {r['para2']} similaires a {r['similarite']}%")
            chapitres_a_regenerer.append(ch_id)
        else:
            log(f"  {ch_id} : OK")

    # 2. Verifier repetitions entre chapitres
    log("--- Verification repetitions entre chapitres ---")
    reps_inter = detecter_repetitions_entre_chapitres(chapitres_textes, seuil=0.4)
    if reps_inter:
        for r in reps_inter:
            log(f"  {r['ch1']} et {r['ch2']} similaires a {r['similarite']}%")
            if r['ch2'] not in chapitres_a_regenerer:
                chapitres_a_regenerer.append(r['ch2'])
    else:
        log("  Aucune repetition entre chapitres detectee")

    # 3. Demander avis avant regeneration
    if chapitres_a_regenerer:
        print("")
        print("=" * 50)
        print("  CHAPITRES AVEC REPETITIONS DETECTEES :")
        for ch_id in chapitres_a_regenerer:
            ch_info = next((c for c in chapitres if c["id"] == ch_id), None)
            if ch_info:
                print(f"  - {ch_id} : {ch_info[\"titre\"]}")
        print("=" * 50)
        reponse = input("  Voulez-vous regenerer ces chapitres ? (o/n) : ").strip().lower()
        if reponse != "o":
            log("Regeneration annulee par l utilisateur.")
            chapitres_a_regenerer = []

    # 3. Regenerer les chapitres problematiques
    if chapitres_a_regenerer:
        log(f"--- Regeneration de {len(chapitres_a_regenerer)} chapitre(s) ---")
        titres_precedents = [ch["titre"] for ch in chapitres
                            if ch["id"] not in chapitres_a_regenerer]

        for ch_id in chapitres_a_regenerer:
            ch_info = next((c for c in chapitres if c["id"] == ch_id), None)
            if not ch_info:
                continue

            log(f"  Regeneration : {ch_id} — {ch_info['titre']}")
            nouveau_texte = regenerer_chapitre(
                sujet=sujet,
                numero=int(ch_id.replace("ch","").lstrip("0") or "1"),
                total=len(chapitres),
                titre=ch_info["titre"],
                mots_cible=mots_par_ch,
                langue=langue,
                chapitres_precedents=titres_precedents
            )

            ch_file = os.path.join(project_path, ch_info["script_file"])
            with open(ch_file, "w", encoding="utf-8") as f:
                f.write(nouveau_texte)
            log(f"  {ch_id} regenere ({len(nouveau_texte.split())} mots)")

            # Mettre a jour le texte en memoire
            chapitres_textes[ch_id] = nouveau_texte
            titres_precedents.append(ch_info["titre"])
    else:
        log("Aucune regeneration necessaire — script propre !")

    # 4. Reconstruire script complet propre
    script_complet = ""
    for ch in chapitres:
        if ch["id"] in chapitres_textes:
            script_complet += chapitres_textes[ch["id"]] + "\n\n"

    with open(os.path.join(project_path, "script.txt"), "w", encoding="utf-8") as f:
        f.write(script_complet)

    mots_total = len(script_complet.split())
    duree_estimee = mots_total / 130
    log(f"Script final : {mots_total} mots")
    log(f"Duree estimee : {duree_estimee:.0f} minutes")
    log("Verification terminee !")

    data["meta"]["duree_estimee_minutes"] = round(duree_estimee)
    ecrire_json(pjson, data)

if __name__ == "__main__":
    main()
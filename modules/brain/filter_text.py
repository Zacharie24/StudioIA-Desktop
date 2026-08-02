import json, re, os, sys
from pathlib import Path

# Import du système de profils
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.profiles.profile_manager import get_manager as get_profile_manager

def log(msg):
    print(f"[FILTRE] {msg}")

def charger_regles():
    """
    Charge les règles depuis le profil actif.
    Renvoie un dict avec mots_a_eviter, mots_de_remplacement, phrases_interdites_patterns.
    """
    try:
        profil = get_profile_manager().charger_profil_actif()
        if profil:
            return profil.get("rules", {})
        return {}
    except Exception as e:
        log(f"Erreur chargement profil: {e}")
        return {}

def supprimer_phrases_dupliquees(texte):
    phrases = re.split(r'(?<=[.!?])\s+', texte)
    resultat = []
    phrase_precedente = ""
    corrections = 0

    for phrase in phrases:
        phrase = phrase.strip()
        if not phrase:
            continue

        # Verifier si trop similaire a la precedente
        if phrase_precedente:
            mots1 = set(phrase_precedente.lower().split())
            mots2 = set(phrase.lower().split())
            if len(mots1) > 0 and len(mots2) > 0:
                similarite = len(mots1.intersection(mots2)) / len(mots1.union(mots2))
                if similarite > 0.7:
                    log(f"  Phrase dupliquee supprimee : {phrase[:50]}...")
                    corrections += 1
                    continue

        resultat.append(phrase)
        phrase_precedente = phrase

    return " ".join(resultat), corrections

def remplacer_mots_complexes(texte, regles):
    corrections = 0
    remplacements = regles.get("mots_de_remplacement", {})
    mots_eviter = regles.get("mots_a_eviter", [])

    for mot in mots_eviter:
        if mot.lower() in texte.lower():
            remplacement = remplacements.get(mot, "")
            if remplacement:
                texte = re.sub(re.escape(mot), remplacement, texte, flags=re.IGNORECASE)
                log(f"  Mot complexe remplace : '{mot}' → '{remplacement}'")
                corrections += 1
            else:
                log(f"  Mot complexe detecte sans remplacement : '{mot}'")

    return texte, corrections

def supprimer_begaiement(texte):
    corrections = 0
    # Detecter les mots repetes successivement (ex: "Dieu Dieu", "je je")
    pattern = r'\b(\w+)\s+\1\b'
    matches = re.findall(pattern, texte, flags=re.IGNORECASE)
    if matches:
        for mot in matches:
            log(f"  Begaiement detecte : '{mot} {mot}'")
            corrections += 1
        texte = re.sub(pattern, r'\1', texte, flags=re.IGNORECASE)

    # Detecter les phrases repetees en debut de paragraphe
    paragraphes = texte.split('\n\n')
    debuts = []
    nouveaux_paragraphes = []
    for para in paragraphes:
        if not para.strip():
            continue
        debut = para.strip()[:50].lower()
        if debut in debuts:
            log(f"  Paragraphe duplique detecte et supprime")
            corrections += 1
        else:
            debuts.append(debut)
            nouveaux_paragraphes.append(para)
    texte = '\n\n'.join(nouveaux_paragraphes)

    return texte, corrections

def filtrer_patterns_interdits(texte, regles):
    corrections = 0
    patterns = regles.get("phrases_interdites_patterns", [])
    for pattern in patterns:
        try:
            matches = re.findall(pattern, texte, flags=re.IGNORECASE)
            if matches:
                log(f"  Pattern interdit detecte : {pattern}")
                corrections += 1
        except:
            pass
    return texte, corrections


def extraire_interdits_directives(directives):
    """
    Extrait les elements INTERDITS des directives utilisateur.
    Retourne une liste de regex a verifier (ou []).
    """
    if not directives:
        return []

    interdits = []
    if isinstance(directives, dict):
        inter = directives.get("interdire")
        if isinstance(inter, list):
            interdits = [str(i).strip() for i in inter if str(i).strip()]
        elif isinstance(inter, str) and inter.strip():
            interdits = [i.strip() for i in re.split(r"[;,\n]+", inter) if i.strip()]

    # Verifier si un texte libre contient des "interdit" : la suppression
    # est le role du LLM (consignes de prompt) ; ici on signale seulement.
    if isinstance(directives, str) and directives.strip():
        for mot in ["ne pas", "interdit", "eviter de", "sans "]:
            if mot in directives.lower():
                # On ne peut pas extraire automatiquement la cible du "ne pas",
                # le prompt doit s'en charger. On ne filtre que ce qui est explicite.
                pass

    # Transformer en patterns : un mot interdit = pattern de detection
    patterns = []
    for interdit in interdits:
        try:
            re.compile(interdit, re.IGNORECASE)
            patterns.append(interdit)
        except re.error:
            # Pas un regex valide -> l'echapper comme phrase litterale
            patterns.append(re.escape(interdit))
    return patterns


def filtrer_directives_interdites(texte, project_path):
    """
    Detecte si le texte enfreint les interdits des directives utilisateur.
    (Le prompt de generation doit deja l'eviter ; ici on signale les manquements.)
    """
    corrections = 0
    try:
        pjson = Path(project_path) / "project.json"
        if pjson.exists():
            data = json.loads(pjson.read_text(encoding="utf-8"))
            patterns = extraire_interdits_directives(data.get("directives"))
            for pattern in patterns:
                try:
                    matches = re.findall(pattern, texte, flags=re.IGNORECASE)
                    if matches:
                        log(f"  INTERDIT UTILISATEUR enfreint : {pattern}")
                        corrections += 1
                except:
                    pass
    except Exception as e:
        log(f"Erreur filtrage directives: {e}")
    return texte, corrections

def filtrer_chapitre(ch_path, regles):
    with open(ch_path, "r", encoding="utf-8") as f:
        texte = f.read()

    log(f"Filtrage : {os.path.basename(ch_path)}")
    total_corrections = 0

    # 1. Supprimer begaiement
    texte, c = supprimer_begaiement(texte)
    total_corrections += c

    # 2. Supprimer phrases dupliquees
    texte, c = supprimer_phrases_dupliquees(texte)
    total_corrections += c

    # 3. Remplacer mots complexes
    texte, c = remplacer_mots_complexes(texte, regles)
    total_corrections += c

    # 4. Verifier patterns interdits
    texte, c = filtrer_patterns_interdits(texte, regles)
    total_corrections += c

    # 5. Verifier les interdits des directives utilisateur
    try:
        projet_path = Path(ch_path).parent.parent
        texte, c = filtrer_directives_interdites(texte, str(projet_path))
        total_corrections += c
    except Exception as e:
        log(f"Erreur directives: {e}")

    # Sauvegarder
    with open(ch_path, "w", encoding="utf-8") as f:
        f.write(texte)

    if total_corrections > 0:
        log(f"  {total_corrections} corrections appliquees")
    else:
        log(f"  Aucun probleme detecte")

    return total_corrections

def main():
    project_path = sys.argv[1]
    ch_dir = Path(project_path) / "chapters"
    regles = charger_regles()

    log(f"Filtrage du projet : {project_path}")
    total = 0

    for ch_file in sorted(ch_dir.glob("*.txt")):
        corrections = filtrer_chapitre(str(ch_file), regles)
        total += corrections

    log(f"Filtrage termine : {total} corrections au total")

if __name__ == "__main__":
    main()
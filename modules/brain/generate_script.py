import json, sys, os, requests, logging

try:
    from core import paths
except ImportError:
    _rac = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, _rac)
    from core import paths

# Import des modules web research et IA online
sys.path.insert(0, str(paths.MODULES_DIR / "brain"))
from web_research import enrichir_prompt_avec_recherche, est_connecte_internet
from ia_online import generer_prompt_online
from spelling_corrector import corriger_chapitre, verifier_chapitre

# Import du système de profils
from core.profiles.profile_manager import get_manager as get_profile_manager

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(name)s] %(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("BRAIN")

def log(msg):
    """Log un message d'info"""
    logger.info(msg)

def log_error(msg, exc_info=False):
    """Log une erreur avec traceback optionnel"""
    logger.error(msg, exc_info=exc_info)

def lire_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def ecrire_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def charger_regles_redaction():
    """
    Charge les règles de rédaction depuis le profil actif.

    Returns:
        tuple: (mots_eviter, regles_gen, regles_specifiques_str, profil_data)
    """
    try:
        profil = get_profile_manager().charger_profil_actif()
        if not profil:
            return "", "", "", None

        rules = profil.get("rules", {})
        manifest = profil.get("manifest", {})

        mots_eviter = ", ".join(rules.get("mots_a_eviter", [])[:10])
        regles_gen  = "\n".join([f"- {r}" for r in rules.get("regles_generales", [])])

        # Règles spécifiques au type de contenu (regles_priere, etc.)
        regles_specifiques = []
        for cle in manifest.get("regles_incluses", []):
            if cle not in ("regles_generales", "mots_a_eviter", "regles_grammaire",
                           "mots_de_remplacement", "phrases_interdites_patterns"):
                valeurs = rules.get(cle, [])
                if isinstance(valeurs, list):
                    regles_specifiques.extend(valeurs)
                elif isinstance(valeurs, dict):
                    for k, v in valeurs.items():
                        regles_specifiques.append(f"{k}: {v}")

        regles_specifiques_str = "\n".join([f"- {r}" for r in regles_specifiques])

        # Règles de grammaire
        regles_grammaire = rules.get("regles_grammaire", [])
        regles_grammaire_str = "\n".join([f"- {r}" for r in regles_grammaire])

        # Remplacements de mots
        mots_remplacement = rules.get("mots_de_remplacement", {})

        # Structure du script
        structure = rules.get("structure_script", {})

        return (mots_eviter, regles_gen, regles_specifiques_str, regles_grammaire_str,
                mots_remplacement, structure, profil)
    except Exception as e:
        log_error(f"Erreur chargement regles profil: {e}")
        return "", "", "", "", {}, {}, None

def construire_consignes_directives(directives):
    """
    Transforme le champ 'directives' d'un projet en consignes claires
    a ajouter au prompt de chaque chapitre.

    Le champ peut etre :
      - un texte libre (str) : tout ce que l'utilisateur veut dire
      - un dict : {"texte": "...", "citer": [...], "interdire": [...],
                   "citer_commentateurs": [...]}

    Returns:
        str: consignes formatees ("" si aucune directive)
    """
    if not directives:
        return ""

    if isinstance(directives, str):
        return f"""
DIRECTIVES DE L'UTILISATEUR (a respecter ABSOLUMENT dans ce chapitre) :
{directives.strip()}
"""

    if not isinstance(directives, dict):
        return ""

    bloc = ["DIRECTIVES DE L'UTILISATEUR (a respecter ABSOLUMENT dans ce chapitre) :"]

    texte = (directives.get("texte") or "").strip()
    if texte:
        bloc.append(texte)

    citer = directives.get("citer")
    if isinstance(citer, list) and citer:
        bloc.append("Ce que l'utilisateur veut CITER / integrer dans le contenu :")
        for c in citer:
            if str(c).strip():
                bloc.append(f"- {str(c).strip()}")
    elif isinstance(citer, str) and citer.strip():
        bloc.append(f"Ce que l'utilisateur veut CITER / integrer : {citer.strip()}")

    interdire = directives.get("interdire")
    if isinstance(interdire, list) and interdire:
        bloc.append("Ce qui est INTERDIT (ne jamais l'ecrire, ne jamais le mentionner) :")
        for c in interdire:
            if str(c).strip():
                bloc.append(f"- {str(c).strip()}")
    elif isinstance(interdire, str) and interdire.strip():
        bloc.append(f"INTERDIT de mentionner : {interdire.strip()}")

    commentateurs = directives.get("citer_commentateurs")
    if isinstance(commentateurs, list) and commentateurs:
        noms = [str(n).strip() for n in commentateurs if str(n).strip()]
        if noms:
            bloc.append(
                "Spectateurs a citer par leur prenom (merci leur et prie pour eux "
                "dans le texte, avec bienveillance et naturel) : "
                + ", ".join(noms))
    elif isinstance(commentateurs, str) and commentateurs.strip():
        bloc.append(f"Spectateurs a citer par leur prenom : {commentateurs.strip()}")

    return "\n".join(bloc) + "\n"


def _get_directives_project(project):
    """Extrait le champ directives d'un project.json (dict ou str)."""
    return project.get("directives")


def get_prompt_chapitre(type_contenu, sujet, numero, total, titre, mots_cible, langue, directives=None):
    mots_eviter, regles_gen, regles_specifiques, regles_grammaire, \
        mots_remplacement, structure, profil = charger_regles_redaction()

    # Construire les consignes spécifiques au profil
    consignes_profil = ""
    if regles_specifiques:
        consignes_profil = f"""
Regles specifiques de ce type de contenu :
{regles_specifiques}"""

    if regles_grammaire:
        consignes_profil += f"""
Regles de grammaire :
{regles_grammaire}"""

    if mots_eviter:
        consignes_profil += f"""
Mots a eviter (ne JAMAIS les utiliser) :
- {mots_eviter}"""

    if regles_gen:
        consignes_profil += f"""
Regles generales :
{regles_gen}"""

    # DIRECTIVES DE L'UTILISATEUR (citer / interdire / commentateurs)
    if directives:
        bloc_directives = construire_consignes_directives(directives)
        if bloc_directives:
            consignes_profil += "\n" + bloc_directives

    # CONSIGNES LINGUISTIQUES STRICTES
    if langue == "fr":
        consigne_langue = """CRITICAL LANGUAGE RULE:
- YOU MUST WRITE EXCLUSIVELY IN FRENCH
- NEVER use English words or phrases
- If you accidentally use English, correct it immediately
- All text must be in French, period."""
    else:
        consigne_langue = """CRITICAL LANGUAGE RULE:
- YOU MUST WRITE EXCLUSIVELY IN ENGLISH
- NEVER use French words or phrases
- If you accidentally use French, correct it immediately
- All text must be in English, period."""

    if type_contenu == "priere":
        if langue == "en":
            return f"""You are a Protestant Christian author writing a prayer.
Write chapter {numero} of {total} of a long Christian prayer about: "{sujet}"
Chapter title: {titre}

CRITICAL INSTRUCTION FOR CHAPTER 1:
- Start with a NATURAL, human-like opening - DO NOT say "Here is my suggestion", "I propose", "Let me tell you"
- Start with a STRONG HOOK: a surprising question, shocking statistic, or compelling anecdote
- Make the first 3 sentences irresistible to keep viewers watching

Rules:
- Write ONLY in English
- Exactly {mots_cible} words
- Natural spoken style, like a real person talking to God
- NO AI-style intros like "Here's my suggestion", "I'll talk about"
- No Catholic symbols, no saints, no Virgin Mary
- NEVER repeat ideas from previous chapters
- No titles, no markdown, continuous text only
{consignes_profil}
Write directly:"""
        else:
            return f"""Tu es un auteur chretien protestant qui ecrit une priere.
Ecris le chapitre {numero} sur {total} d'une longue priere chretienne sur : "{sujet}"
Titre du chapitre : {titre}

INSTRUCTION CRITIQUE POUR LE CHAPITRE 1:
- Commencer par une ACCROCHE PROFESSIONNELLE: une adresse a Dieu ou une verite biblique
- Faire en sorte que les 3 premieres phrases soient claires et spirituellement significatives
- Eviter les anecdotes personnelles ou des histoires de famille specifiques
- Se concentrer sur la PRIERE POUR les autres dans des situations similaires
- Commencer DIRECTEMENT - NE JAMAIS dire "Voici ma proposition", "Je vais te parler de", "Aujourd'hui je veux te parler de"

{consigne_langue}

Regles de redaction :
- Ecris UNIQUEMENT en francais
- Exactement {mots_cible} mots
- Style oral, fluide, parle directement a Dieu
- AUCUNE intro type IA comme "Voici ma proposition", "Je vais te parler de", "Aujourd'hui on va voir"
- Pas de symboles catholiques, pas de saints, pas de vierge Marie
- NE REPETE JAMAIS les idees des chapitres precedents
- Pas de titres, pas de markdown, texte continu uniquement
{consignes_profil}
Ecris directement :"""

    elif type_contenu == "storytelling":
        if langue == "en":
            return f"""You are a professional storyteller and narrator.
Write chapter {numero} of {total} of an engaging story about: "{sujet}"
Chapter title: {titre}

CRITICAL INSTRUCTION FOR CHAPTER 1:
- Start with a NATURAL, human-like opening - DO NOT say "Here is my suggestion", "I propose", "Let me tell you"
- Start with a STRONG HOOK: a surprising question, shocking fact, or compelling anecdote
- Make the first 3 sentences irresistible to keep viewers watching

Rules:
- Write ONLY in English
- Exactly {mots_cible} words
- Natural spoken narrative style
- NO AI-style intros like "Here's my suggestion", "I'll talk about"
- Create characters, emotions, tension, and atmosphere
- Each chapter must advance the story
- NEVER repeat scenes or ideas from previous chapters
- No titles, no markdown, continuous narrative text only
{consignes_profil}
Write directly:"""
        else:
            return f"""Tu es un narrateur professionnel et conteur d'histoires.
Ecris le chapitre {numero} sur {total} d'une histoire captivante sur : "{sujet}"
Titre du chapitre : {titre}

INSTRUCTION CRITIQUE POUR LE CHAPITRE 1:
- Commence par une ACCROCHE NATURELLE et humaine - NE JAMAIS dire "Voici ma proposition", "Je vais te parler de", "Aujourd'hui je veux te parler de", "Nous allons voir"
- Commence directement avec une ACCROCHE FORTHE: une question surprenante, un fait choquant, ou une anecdote captivante
- Fais en sorte que les 3 premieres phrases soient irresistibles pour garder les spectateurs attentifs

{consigne_langue}

Regles :
- Ecris UNIQUEMENT en francais
- Exactement {mots_cible} mots
- Style narratif, immersif, avec des descriptions vivantes
- Cree des personnages, des emotions, de la tension et de l'atmosphere
- Chaque chapitre doit faire avancer l'histoire
- NE REPETE JAMAIS des scenes ou des idees des chapitres precedents
- AUCUNE intro type IA comme "Voici ma proposition", "Je vais te parler de", "Aujourd'hui on va voir"
- Pas de titres, pas de markdown, texte narratif continu uniquement
{consignes_profil}
Ecris directement :"""

    else:
        # general
        if langue == "en":
            return f"""You are a professional YouTube narrator and content creator.
Write chapter {numero} of {total} of an engaging video script about: "{sujet}"
Chapter title: {titre}

CRITICAL INSTRUCTION FOR CHAPTER 1:
- Start with a NATURAL, human-like opening - DO NOT say "Here is my suggestion", "I propose", "Let me tell you", "Today I want to talk about"
- Start with a STRONG HOOK: a surprising question, shocking statistic, or compelling anecdote
- Make the first 3 sentences irresistible to keep viewers watching

Rules:
- Write ONLY in English
- Exactly {mots_cible} words
- Natural spoken style, like a real person talking
- NO AI-style intros like "Here's my suggestion", "I'll talk about", "Today we'll explore"
- NEVER repeat ideas from previous chapters
- No titles, no markdown, continuous text only
{consignes_profil}
Write directly:"""
        else:
            return f"""Tu es un narrateur professionnel pour YouTube.
Ecris le chapitre {numero} sur {total} d'un script video captivant sur : "{sujet}"
Titre du chapitre : {titre}

INSTRUCTION CRITIQUE POUR LE CHAPITRE 1:
- Commence par une ACCROCHE NATURELLE et humaine - NE JAMAIS dire "Voici ma proposition", "Je vais te parler de", "Aujourd'hui je veux te parler de", "Nous allons voir"
- Commence directement avec une ACCROCHE FORTHE: une question surprenante, un fait choquant, ou une anecdote captivante
- Fais en sorte que les 3 premieres phrases soient irresistibles pour garder les spectateurs attentifs

{consigne_langue}

Regles :
- Ecris UNIQUEMENT en francais
- Exactement {mots_cible} mots
- Style oral naturel, comme si une personne reellement parlait
- AUCUNE intro type IA comme "Voici ma proposition", "Je vais te parler de", "Aujourd'hui on va voir", "On va discuter de"
- NE REPETE JAMAIS les idees des chapitres precedents
- Pas de titres, pas de markdown, texte continu uniquement
{consignes_profil}
Ecris directement :"""

def get_prompt_plan(type_contenu, sujet, nb_chapitres, langue, directives=None):
    directives_plan = ""
    if directives:
        bloc = construire_consignes_directives(directives)
        if bloc:
            directives_plan = f"""
DIRECTIVES DE L'UTILISATEUR pour le plan (respecte-les) :
{bloc}"""

    if type_contenu == "priere":
        if langue == "en":
            return f"""You are a Protestant Christian author.
Create a plan of {nb_chapitres} DIFFERENT chapters for a Christian prayer about: "{sujet}"
Each chapter must cover a UNIQUE aspect: praise, confession, intercession, thanksgiving, etc.
{directives_plan}
Reply ONLY with valid JSON:
{{"chapitres": ["Title 1", "Title 2", "Title 3"]}}"""
        else:
            return f"""Tu es un auteur chretien protestant.
Cree un plan de {nb_chapitres} chapitres DIFFERENTS pour une priere chretienne sur : "{sujet}"
Chaque chapitre doit couvrir un aspect UNIQUE : louange, confession, intercession, action de grace, etc.
{directives_plan}
Reponds UNIQUEMENT avec un JSON valide :
{{"chapitres": ["Titre 1", "Titre 2", "Titre 3"]}}"""

    elif type_contenu == "storytelling":
        if langue == "en":
            return f"""You are a professional storyteller.
Create a plan of {nb_chapitres} chapters for an engaging story about: "{sujet}"
The chapters must follow a narrative arc: introduction, rising action, climax, resolution.
Each chapter must be a unique and essential part of the story.
Reply ONLY with valid JSON:
{{"chapitres": ["Chapter title 1", "Chapter title 2", "Chapter title 3"]}}"""
        else:
            return f"""Tu es un narrateur professionnel.
Cree un plan de {nb_chapitres} chapitres pour une histoire captivante sur : "{sujet}"
Les chapitres doivent suivre un arc narratif : introduction, montee en tension, climax, resolution.
Chaque chapitre doit etre une partie unique et essentielle de l'histoire.
Reponds UNIQUEMENT avec un JSON valide :
{{"chapitres": ["Titre chapitre 1", "Titre chapitre 2", "Titre chapitre 3"]}}"""

    else:
        if langue == "en":
            return f"""You are a YouTube content creator.
Create a plan of {nb_chapitres} chapters for an engaging video about: "{sujet}"
Each chapter must cover a different and unique aspect of the topic.
Reply ONLY with valid JSON:
{{"chapitres": ["Title 1", "Title 2", "Title 3"]}}"""
        else:
            return f"""Tu es un createur de contenu YouTube.
Cree un plan de {nb_chapitres} chapitres pour une video captivante sur : "{sujet}"
Chaque chapitre doit couvrir un aspect different et unique du sujet.
Reponds UNIQUEMENT avec un JSON valide :
{{"chapitres": ["Titre 1", "Titre 2", "Titre 3"]}}"""

def choisir_providers():
    """Renvoie les providers à utiliser selon config.json"""
    try:
        config = lire_json(paths.config_path())
        return config.get("providers", {
            "plan": "local",           # local, huggingface, ou online (tout en ligne)
            "chapitre": "local"        # local, huggingface, ou online (tout en ligne)
        })
    except:
        return {"plan": "local", "chapitre": "local"}


def activer_recherche_web():
    """Vérifie si la recherche web est activée dans config.json"""
    try:
        config = lire_json(paths.config_path())
        return config.get("web_research", False)
    except:
        return False


def appeler_ollama(prompt, modele=None, temperature=0.8):
    """Appel local via Ollama"""
    if modele is None:
        modele = "mistral"
    response = requests.post("http://localhost:11434/api/generate", json={
        "model": modele,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "repeat_penalty": 1.3,
            "repeat_last_n": 128
        }
    })
    return response.json()["response"], modele


def appeler_ia_online(prompt, modele="mistral", provider="huggingface", query_recherche=None):
    """
    Appel IA en ligne (Hugging Face) avec option de recherche web

    Args:
        prompt: Le prompt à générer
        modele: Le modèle à utiliser
        provider: Le provider (huggingface ou autre)
        query_recherche: Query pour la recherche web (optionnelle)

    Returns:
        (texte, erreur) ou (None, erreur) en cas d'échec
    """
    # Enrichir le prompt avec la recherche web si activé
    if query_recherche:
        prompt_enrichi, internet_disponible = enrichir_prompt_avec_recherche(prompt, query_recherche)
        if internet_disponible:
            log(f"Recherche web effectuée pour: {query_recherche}")
            prompt = prompt_enrichi

    # Si pas d'internet pour la recherche, on continue quand même avec le prompt original
    # car l'IA en ligne peut quand même générer du texte

    texte, internet, erreur = generer_prompt_online(prompt, model=modele, provider=provider)
    if internet and texte:
        return texte, None
    return None, erreur


def synthetiser_avec_ollama(contexte_web, type_synthese="plan"):
    """
    Synthétise le contexte web avec Ollama pour obtenir un résumé factuel.
    C'est une étape intermédiaire avant la génération.
    """
    if type_synthese == "plan":
        prompt_synthese = f"""Tu es un expert en recherche et synthèse d'informations.

Voici des informations issues de Wikipedia sur le sujet:

{contexte_web}

TA TÂCHE:
Crée un plan détaillé de 5 à 25 chapitres (selon la longueur souhaitée) pour une vidéo YouTube ou une prière chrétienne.
Le plan doit être en JSON avec une clé "chapitres" contenant une liste de titres.

Rules:
- Utilise UNIQUEMENT les faits mentionnés dans le contexte ci-dessus
- Ne t'invente pas de détails
- Chaque chapitre doit couvrir un aspect différent du sujet
- Le plan doit suivre une logique narrative ou théologique (selon le type)

Réponds UNIQUEMENT avec du JSON valide:
{{
    "synthese": "Résumé factuel en 3-4 phrases des points clés",
    "chapitres": ["Titre chapitre 1", "Titre chapitre 2", ...]
}}"""
    else:
        prompt_synthese = f"""Tu es un expert en recherche et synthèse d'informations.

Voici des informations issues de Wikipedia:

{contexte_web}

TA TÂCHE:
Crée un résumé factuel et synthétique de ces informations.
Utilise les faits mentionnés, sans ajouter d'interprétation.

Réponds UNIQUEMENT avec du JSON valide:
{{
    "synthese": "Résumé factuel complet en 10-15 phrases"
}}"""

    try:
        synthese_texte, _ = appeler_ollama(prompt_synthese, modele="qwen2.5:7b", temperature=0.3)
        debut = synthese_texte.find("{")
        fin = synthese_texte.rfind("}") + 1
        return json.loads(synthese_texte[debut:fin])
    except Exception as e:
        log_error(f"Erreur synthèse Ollama: {e}")
        return None


def generer_plan_online(sujet, nb_chapitres, type_contenu, langue, directives=None):
    """
    Génération COMPLETE en mode ONLINE (hybride):
    1. Recherche web (Wikipedia)
    2. Synthèse locale avec Ollama (résumer les faits)
    3. Génération locale avec Ollama (plan + chapitres)

    PAS DE HUGGING FACE DANS CE MODE.
    """
    from web_research import chercher_wikipedia

    log(f"MODE ONLINE (hybride): Recherche + Synthèse Ollama + Génération Ollama")

    # 1. Recherche web sur le sujet
    wiki_results = chercher_wikipedia(sujet)

    if not wiki_results:
        log("Aucun résultat Wikipedia trouvé, continuation sans recherche web...")
        contexte_web = None
    else:
        contexte_web = ""
        for r in wiki_results[:2]:
            contexte_web += f"Titre: {r['title']}\n"
            contexte_web += f"Snippet: {r['snippet']}\n\n"
        log(f"Wikipedia: {len(wiki_results)} articles trouvés")

    # 2. Synthèse locale avec Ollama
    log("Synthèse des informations avec Ollama...")
    synthese = synthetiser_avec_ollama(contexte_web or "", type_synthese="plan")

    if synthese and "chapitres" in synthese:
        titres = synthese["chapitres"]
        log(f"Plan synthétisé: {len(titres)} chapitres")
    else:
        log_error("Echec synthèse, fallback sur génération directe...")
        # Fallback: génération directe sans synthèse
        prompt_plan = get_prompt_plan(type_contenu, sujet, nb_chapitres, langue, directives)
        if contexte_web:
            prompt_plan = f"""{contexte_web}
[TA TÂCHE]
{prompt_plan}

[INSTRUCTIONS]
Utilise les informations ci-dessus pour créer un plan adapté."""

        plan_texte, _ = appeler_ollama(prompt_plan, modele="qwen2.5:7b", temperature=0.7)
        debut = plan_texte.find("{")
        fin = plan_texte.rfind("}") + 1
        try:
            plan = json.loads(plan_texte[debut:fin])
            titres = plan.get("chapitres", [])
        except:
            log_error("Echec parsing JSON, génération impossible")
            return None, "plan"

    # 3. Génération des chapitres avec Ollama
    mots_par_ch = calculer_mots_par_chapitre(30, nb_chapitres)
    chapitres = []

    log(f"Generation de {len(titres)} chapitres avec Ollama...")

    for i, titre in enumerate(titres, 1):
        prompt_chapitre = get_prompt_chapitre(
            type_contenu, sujet, i, len(titres), titre, mots_par_ch, langue, directives
        )

        # Ajouter le contexte web enrichi si disponible
        if synthese and "synthese" in synthese:
            contexte_synthese = f"""[SYNTHÈSE FACTUELLE DES INFORMATIONS]

{synthese["synthese"]}

[POINTS CLÉS À UTILISER]

Voici les faits vérifiés à intégrer dans ton chapitre:
- Contexte factuel fourni par la synthèse ci-dessus
- Informations issues de Wikipedia"""

            prompt_chapitre = f"""{contexte_synthese}

{prompt_chapitre}

[INSTRUCTIONS SUPPLÉMENTAIRES]
- Utilise les faits vérifiés ci-dessus pour enrichir ton chapitre
- Ne t'invente pas de détails non mentionnés
- Forme ton raisonnement à partir de ces faits"""

        log(f"Generation chapitre {i}/{len(titres)}: {titre}")
        texte_chapitre, _ = appeler_ollama(prompt_chapitre, modele="mistral", temperature=0.8)

        if not texte_chapitre:
            log_error(f"Erreur chapitre {i}")
            return None, f"chapitre_{i}"

        chapitres.append({
            "id": f"ch{i:02d}",
            "titre": titre,
            "texte": texte_chapitre,
            "nb_mots": len(texte_chapitre.split())
        })
        log(f"Chapitre {i} OK ({len(texte_chapitre.split())} mots)")

    # 4. Assemblage final
    return {
        "chapitres": chapitres,
        "titres": titres
    }, None


def generer_plan(sujet, nb_chapitres, type_contenu, langue, directives=None):
    prompt = get_prompt_plan(type_contenu, sujet, nb_chapitres, langue, directives)
    providers = choisir_providers()
    provider = providers.get("plan", "local")
    use_web_search = activer_recherche_web()

    log(f"Provider plan: {provider}")
    log(f"Recherche web: {'activée' if use_web_search else 'désactivée'}")

    if provider == "huggingface":
        # Utiliser le sujet comme query pour la recherche web si activé
        query = sujet if use_web_search else None
        texte, erreur = appeler_ia_online(prompt, modele="mistral", provider="huggingface", query_recherche=query)
        if texte:
            debut = texte.find("{")
            fin = texte.rfind("}") + 1
            return json.loads(texte[debut:fin])
        else:
            log_error(f"Erreur Hugging Face: {erreur}", exc_info=True)
            log("Fallback sur local...")
            texte, _ = appeler_ollama(prompt, modele="qwen2.5:7b", temperature=0.7)
    else:
        texte, _ = appeler_ollama(prompt, modele="qwen2.5:7b", temperature=0.7)

    debut = texte.find("{")
    fin = texte.rfind("}") + 1
    return json.loads(texte[debut:fin])

def generer_chapitre(sujet, numero, total, titre, mots_cible, type_contenu, langue, directives=None):
    prompt = get_prompt_chapitre(type_contenu, sujet, numero, total, titre, mots_cible, langue, directives)
    providers = choisir_providers()
    provider = providers.get("chapitre", "local")
    use_web_search = activer_recherche_web()

    log(f"Provider chapitre {numero}: {provider}")
    if use_web_search:
        log(f"Recherche web activée pour le chapitre {numero}")

    if provider == "huggingface":
        # Utiliser le sujet comme query pour la recherche web si activé
        query = sujet if use_web_search else None
        texte, erreur = appeler_ia_online(prompt, modele="mistral", provider="huggingface", query_recherche=query)
        if texte:
            return texte
        else:
            log_error(f"Erreur Hugging Face: {erreur}", exc_info=True)
            log("Fallback sur local...")
            return appeler_ollama(prompt, modele="mistral", temperature=0.8)[0]
    else:
        return appeler_ollama(prompt, modele="mistral", temperature=0.8)[0]

def calculer_nb_chapitres(duree_minutes):
    if duree_minutes <= 15:
        return 5
    elif duree_minutes <= 30:
        return 8
    elif duree_minutes <= 60:
        return 15
    elif duree_minutes <= 90:
        return 20
    else:
        return 25

def calculer_mots_par_chapitre(duree_minutes, nb_chapitres):
    # 130 mots/minute mais on demande 20% de plus pour compenser
    # le fait que lIA genere souvent moins que demande
    mots_total = duree_minutes * 130 * 1.2
    return int(mots_total // nb_chapitres)

def main():
    project_path = sys.argv[1]
    config = lire_json(paths.config_path())
    project = lire_json(os.path.join(project_path, "project.json"))

    # Correction anti-crash : garantir que les sous-dossiers existent avant d'ecrire
    # (le pipeline cree deja chapters/audio/images/export, mais on se protege ici
    # pour les lancements manuels directs via app_gui ou scripts.)
    try:
        os.makedirs(os.path.join(project_path, "chapters"), exist_ok=True)
        os.makedirs(os.path.join(project_path, "audio"), exist_ok=True)
        os.makedirs(os.path.join(project_path, "images"), exist_ok=True)
    except Exception as e:
        log(f"Attention: creation sous-dossiers impossible: {e}")

    # Hook de progression pour l'interface web (barre de progression /automation)
    try:
        _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if _root not in sys.path:
            sys.path.insert(0, _root)
        from modules.automation.progress import etape as _prog_etape
        from modules.automation.progress import terminer_etape as _prog_fin
    except Exception:
        def _prog_etape(nom, message, pct, detail=""):
            pass
        def _prog_fin(nom, statut="termine", message=""):
            pass

    sujet        = project["sujet"]
    langue       = project.get("langue", "fr")
    type_contenu = project.get("type_contenu", "general")
    directives   = project.get("directives")
    # Lire la durée depuis project.json (meta.duree_cible) avec fallback config.json
    duree = project.get("meta", {}).get("duree_cible", config.get("target_duration_minutes", 30))
    nb_chapitres = calculer_nb_chapitres(duree)

    mots_par_ch  = calculer_mots_par_chapitre(duree, nb_chapitres)

    log(f"Sujet        : {sujet}")
    log(f"Type         : {type_contenu}")
    log(f"Langue       : {langue}")
    log(f"Duree cible  : {duree} minutes")
    log(f"Mots/chapitre: {mots_par_ch}")

    # Vérifier si on utilise le mode "online" (tout en ligne)
    providers = choisir_providers()
    provider_plan = providers.get("plan", "local")
    provider_chapitre = providers.get("chapitre", "local")

    # Mode online : génération complète en ligne (plan + tous les chapitres)
    if provider_plan == "online" or provider_chapitre == "online":
        log("MODE ONLINE: Génération complète en ligne...")
        result, error = generer_plan_online(sujet, nb_chapitres, type_contenu, langue, directives)

        if result:
            chapitres = result["chapitres"]
            titres = result["titres"]

            script_complet = ""
            chapitres_data = []

            for ch in chapitres:
                i = int(ch["id"][2:])  # extraire le numéro du chapitre
                titre = ch["titre"]
                texte = ch["texte"]
                _prog_etape("script", f"Chapitre {i}/{len(chapitres)} (online)", 20 + int(65 * i / len(chapitres)), f"Ecriture de : {titre}")

                ch_file = os.path.join(project_path, "chapters", f"ch{i:02d}.txt")
                with open(ch_file, "w", encoding="utf-8") as f:
                    f.write(texte)
                log(f"Chapitre {i} OK ({ch['nb_mots']} mots)")

                script_complet += texte + "\n\n"
                chapitres_data.append({
                    "id": f"ch{i:02d}",
                    "titre": titre,
                    "script_file": f"chapters/ch{i:02d}.txt",
                    "audio_file":  f"audio/ch{i:02d}.wav",
                    "image_file":  "",
                    "statut_tts":  "en_attente"
                })

            with open(os.path.join(project_path, "script.txt"), "w", encoding="utf-8") as f:
                f.write(script_complet)

            mots_total = len(script_complet.split())
            duree_estimee = mots_total / 130
            log(f"Script complet : {mots_total} mots")
            log(f"Duree estimee  : {duree_estimee:.0f} min ({duree_estimee/60:.1f}h)")

            pjson = os.path.join(project_path, "project.json")
            data = lire_json(pjson)
            data["chapitres"] = chapitres_data
            data["etapes"]["script"] = "termine"
            data["etapes"]["chapitres"] = "termine"
            data["meta"]["duree_estimee_minutes"] = round(duree_estimee)
            ecrire_json(pjson, data)

            log("Script genere avec succes (MODE ONLINE)!")
            return
        else:
            log_error(f"Echec mode online: {error}")
            log("Fallback sur mode local...")
            # Puis continue avec le mode local ci-dessous

    # Mode local/huggingface classique
    ecrire_json(os.path.join(project_path, "project.json"),
        {**project, "etapes": {**project["etapes"], "script": "en_cours"}})

    log("Generation du plan...")
    _prog_etape("script", "Generation du plan", 20, "Plan du script en cours...")
    plan = generer_plan(sujet, nb_chapitres, type_contenu, langue, directives)
    titres = plan["chapitres"]
    log(f"Plan genere : {len(titres)} chapitres")
    _prog_fin("script", "termine", "Plan genere")

    script_complet = ""
    chapitres_data = []

    for i, titre in enumerate(titres, 1):
        ch_file = os.path.join(project_path, "chapters", f"ch{i:02d}.txt")
        _prog_etape("script", f"Chapitre {i}/{len(titres)}", 20 + int(65 * i / len(titres)), f"Ecriture de : {titre}")

        if os.path.exists(ch_file):
            log(f"Chapitre {i} deja existe, on saute.")
            with open(ch_file, "r", encoding="utf-8") as f:
                texte = f.read()
        else:
            log(f"Generation chapitre {i}/{len(titres)} : {titre}")
            texte = generer_chapitre(sujet, i, len(titres), titre,
                                     mots_par_ch, type_contenu, langue, directives)

            # Corriger les erreurs orthographiques
            texte = corriger_chapitre(texte)

            nb_mots = len(texte.split())
            with open(ch_file, "w", encoding="utf-8") as f:
                f.write(texte)
            log(f"Chapitre {i} OK ({nb_mots} mots)")

        script_complet += texte + "\n\n"
        chapitres_data.append({
            "id": f"ch{i:02d}",
            "titre": titre,
            "script_file": f"chapters/ch{i:02d}.txt",
            "audio_file":  f"audio/ch{i:02d}.wav",
            "image_file":  "",
            "statut_tts":  "en_attente"
        })

    with open(os.path.join(project_path, "script.txt"), "w", encoding="utf-8") as f:
        f.write(script_complet)

    mots_total    = len(script_complet.split())
    duree_estimee = mots_total / 130
    log(f"Script complet : {mots_total} mots")
    log(f"Duree estimee  : {duree_estimee:.0f} min ({duree_estimee/60:.1f}h)")

    pjson = os.path.join(project_path, "project.json")
    data  = lire_json(pjson)
    data["chapitres"]                    = chapitres_data
    data["etapes"]["script"]             = "termine"
    data["etapes"]["chapitres"]          = "termine"
    data["meta"]["duree_estimee_minutes"] = round(duree_estimee)
    ecrire_json(pjson, data)

    _prog_fin("script", "termine", "Script complet genere")
    log("Script genere avec succes !")

if __name__ == "__main__":
    main()
# -*- coding: utf-8 -*-
"""
comment_analyzer.py — Analyse des commentaires YouTube

Collecte les commentaires des videos d'une chaine (API key, publique),
en extrait :
- les THEMES et besoins (requetes de priere, sujets qui touchent)
- les PRIERES ecrites par les spectateurs dans les commentaires
- les mots/expressions recurrents qui montrent ce qui touche les gens
- les commentateurs actifs (noms pouvant etre cites dans une video)

Le resultat est sauvegarde dans data/audits/comments_analysis.json
et sert a orienter la production (content_planner) et les directives
(tache 37 : citer des gens des commentaires).
"""

import json
import re
import sys
import requests
from pathlib import Path
from datetime import datetime
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

CONFIG_PATH = Path(__file__).parent.parent.parent / "config.json"
ANALYSIS_DIR = Path(__file__).parent.parent.parent / "data" / "audits"
ANALYSIS_FILE = ANALYSIS_DIR / "comments_analysis.json"

# Mots/expressions qui signalent une priere ecrite ou une demande
PATRON_PRIERE = re.compile(
    r"\b(prie(?:r|s|z)?|priere|amen|seigneur|pere|mon dieu|jesus|christ|"
    r"benediction|gueris|protege|delivre|repose|merci mon dieu|"
    r"protège|bénis|bénissez|pardon|foi|gloire|loue|louange)\b",
    re.IGNORECASE,
)

MOTS_BESOINS = {
    "guerison": ["gueris", "guerir", "guerison", "maladie", "douleur", "sante", "malade", "tumeur", "cancer", "infirmite", "souffre"],
    "protection": ["protege", "protection", "protège", "garde", "securite", "danger", "ennemi"],
    "repos": ["repos", "dormir", "sommeil", "insomnie", "anxiete", "angoisse", "stress", "nuit"],
    "travail": ["travail", "emploi", "travail", "boulot", "chomage", "carriere", "projet"],
    "famille": ["famille", "enfants", "epouse", "mari", "couple", "mariage", "maison", "mere", "pere"],
    "finances": ["argent", "finance", "dette", "richesse", "prosperite", "travail"],
    "foi": ["foi", "croire", "croyance", "esprit", "ame", "confiance", "abandon"],
    "reconnaissance": ["merci", "grace", "reconnaissance", "remercie", "action de grace"],
}

TITRES = ["PRIERES", "THEMES", "BESOINS", "COMMENTATEURS", "ANALYSE"]


def log(msg):
    print(f"[COMMENTS] {msg}")


def _lire_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _api_key():
    config = _lire_config()
    return config.get("youtube_api_key") or None


def _chaine_cible():
    config = _lire_config()
    return config.get("chaine_cible") or {}


# ---------------------------------------------------------------
# Collecte brute (API key, commentThreads.list)
# ---------------------------------------------------------------

def _vider_video_ids(channel_id, max_videos=30):
    """IDs des dernieres videos publiques d'une chaine."""
    cle = _api_key()
    if not cle:
        return []
    try:
        r = requests.get("https://www.googleapis.com/youtube/v3/search", params={
            "part": "snippet", "channelId": channel_id, "order": "date",
            "maxResults": max_videos, "type": "video", "key": cle
        }, timeout=15)
        if r.status_code != 200:
            return []
        return [item["id"]["videoId"] for item in r.json().get("items", [])
                if item.get("id", {}).get("videoId")]
    except Exception as e:
        log(f"Erreur video ids: {e}")
        return []


def _commentaires_dune_video(video_id, max_commentaires=15):
    """Commentaires (top-level) d'une video via API key."""
    cle = _api_key()
    if not cle:
        return []
    resultats = []
    try:
        r = requests.get("https://www.googleapis.com/youtube/v3/commentThreads", params={
            "part": "snippet", "videoId": video_id,
            "maxResults": max_commentaires,
            "textFormat": "plainText", "key": cle
        }, timeout=15)
        if r.status_code != 200:
            return []
        for item in r.json().get("items", []):
            sn = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
            auteur = sn.get("authorDisplayName", "")
            texte = sn.get("textDisplay", "").strip()
            if not texte:
                continue
            resultats.append({
                "auteur": auteur,
                "texte": texte,
                "likes": int(sn.get("likeCount", 0)),
                "date": sn.get("publishedAt", ""),
                "video_id": video_id
            })
    except Exception as e:
        log(f"Erreur commentaires {video_id}: {e}")
    return resultats


def recuperer_commentaires(channel_id=None, max_videos=20, max_par_video=12):
    """
    Collecte des commentaires publics de la chaine cible (ou OAuth).
    Retourne une liste de dicts commentaires.
    """
    if not channel_id:
        cible = _chaine_cible()
        channel_id = cible.get("channel_id")
    if not channel_id:
        # Fallback : identifier sa propre chaine via OAuth
        try:
            from modules.youtube_analyzer.channel_audit import identifier_ma_chaine
            ma = identifier_ma_chaine()
            if ma.get("ok"):
                channel_id = ma["channel_id"]
        except Exception:
            pass
    if not channel_id:
        return []

    ids = _vider_video_ids(channel_id, max_videos=max_videos)
    commentaires = []
    for vid in ids:
        commentaires.extend(_commentaires_dune_video(vid, max_par_video))
    return commentaires


# ---------------------------------------------------------------
# Analyse des commentaires
# ---------------------------------------------------------------

def _normaliser(texte):
    return texte.lower()


def _analyser_besoins(texte):
    """Detecte les besoins/themes presents dans un commentaire."""
    t = _normaliser(texte)
    trouves = []
    for theme, mots in MOTS_BESOINS.items():
        for m in mots:
            if m in t:
                trouves.append(theme)
                break
    return trouves


def _est_priere(texte):
    return bool(PATRON_PRIERE.search(texte))


def analyser_commentaires(commentaires):
    """
    Analyse une liste de commentaires :
    - prieres ecrites (texte entier conserve)
    - themes/besoins (compteurs)
    - mots frequents significatifs
    - commentateurs actifs (auteurs + extrait)
    """
    prieres = []
    besoins = Counter()
    mots = Counter()
    auteurs = Counter()
    texte_prieres = []

    for c in commentaires:
        texte = c.get("texte", "")
        auteur = c.get("auteur", "")
        if not texte:
            continue
        auteurs[auteur] += 1

        # Prieres / demandes
        if _est_priere(texte):
            prieres.append({
                "auteur": auteur,
                "texte": texte[:600],
                "likes": c.get("likes", 0),
                "date": c.get("date", "")
            })
            texte_prieres.append(texte)

        # Besoins
        for b in _analyser_besoins(texte):
            besoins[b] += 1

        # Mots significatifs (3+ lettres, sans stopwords)
        t = _normaliser(texte)
        t = re.sub(r"[^a-z0-9àâäéèêëîïôöùûüç ]", " ", t)
        for mot in t.split():
            if len(mot) > 3 and mot not in {
                "pour", "avec", "dans", "cette", "comment", "notre", "votre",
                "tout", "tous", "the", "and", "that", "this", "avec", "mais",
                "plus", "vous", "nous", "merci", "seigneur", "dieu", "amen",
                "priere", "prière", "protège", "toujours"
            }:
                mots[mot] += 1

    # Commentateurs actifs (ceux qui ecrivent des prieres ou beaucoup)
    commentateurs = []
    for auteur, nb in auteurs.most_common(15):
        extrait = ""
        for p in prieres:
            if p["auteur"] == auteur:
                extrait = p["texte"][:140]
                break
        commentateurs.append({"nom": auteur, "nb_commentaires": nb, "extrait": extrait})

    return {
        "nb_commentaires": len(commentaires),
        "nb_prieres": len(prieres),
        "prieres": prieres[:30],
        "besoins": [{"theme": k, "nb": v} for k, v in besoins.most_common(10)],
        "mots_frequents": [{"mot": m, "nb": n} for m, n in mots.most_common(25)],
        "commentateurs_actifs": commentateurs,
        "commentaires_recents": [
            {"auteur": c.get("auteur", ""), "texte": c.get("texte", "")[:200],
             "likes": c.get("likes", 0)}
            for c in commentaires[:15]
        ]
    }


def synthese_ia(analyse):
    """
    Resume par le LLM local (Ollama) : quels besoins, quel ton,
    quelle prochaine priere faire. Fallback heuristique si indisponible.
    """
    try:
        from modules.brain.generate_script import appeler_ollama
        besoins_txt = ", ".join(f"{b['theme']} ({b['nb']})" for b in analyse.get("besoins", [])[:6])
        prieres_txt = "\n".join(f"- {p['auteur']}: {p['texte'][:160]}" for p in analyse.get("prieres", [])[:6])
        prompt = f"""Tu es un pasteur qui anime une chaine YouTube de prieres chretiennes.

Voici ce que les spectateurs ecrivent dans les commentaires :
{prieres_txt}

Besoins les plus frequent : {besoins_txt}

En 4 lignes maximum : quel est le besoin spirituel dominant, quel ton
adopter dans les prochaines videos, et quel sujet de priere faire en priorite.
"""
        texte, _ = appeler_ollama(prompt, modele="qwen2.5:7b", temperature=0.4)
        return {"texte": texte.strip(), "modele": "ollama"}
    except Exception as e:
        return {"texte": None, "erreur": str(e)}


# ---------------------------------------------------------------
# Orchestration + persistance
# ---------------------------------------------------------------

def analyser_comments_chaine(channel_id=None):
    """
    Analyse complete : collecte -> analyse -> synthese IA -> sauvegarde.

    Returns:
        dict: {"ok": bool, "analyse": dict, "synthese": dict, "erreur": str}
    """
    commentaires = recuperer_commentaires(channel_id)
    if not commentaires:
        return {"ok": False, "analyse": {"nb_commentaires": 0},
                "synthese": {}, "erreur": "Aucun commentaire recup (API key ? chaine cible ?)"}

    analyse = analyser_commentaires(commentaires)
    synthese = synthese_ia(analyse)

    resultat = {
        "date_analyse": datetime.now().isoformat(),
        "chaine_cible": _chaine_cible(),
        "nb_commentaires": analyse["nb_commentaires"],
        "analyse": analyse,
        "synthese": synthese
    }
    sauvegarder_analyse(resultat)
    return {"ok": True, **resultat}


def sauvegarder_analyse(data):
    try:
        ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
        ANALYSIS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        log(f"Erreur sauvegarde analyse: {e}")
        return False


def lire_derniere_analyse():
    """Analyse de commentaires la plus recente (pour content_planner / directives)."""
    if ANALYSIS_FILE.exists():
        try:
            return json.loads(ANALYSIS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def commentateurs_a_citer(max_noms=5):
    """
    Noms des commentateurs actifs (a citer dans une video).
    Retourne une liste de noms ou [] si rien.
    """
    analyse = lire_derniere_analyse()
    if not analyse:
        return []
    actifs = analyse.get("analyse", {}).get("commentateurs_actifs", [])
    return [c["nom"] for c in actifs[:max_noms]]


if __name__ == "__main__":
    r = analyser_comments_chaine()
    print(json.dumps(r, ensure_ascii=False, indent=2)[:3000])

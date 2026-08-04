# -*- coding: utf-8 -*-
"""
channel_audit.py — Audit de chaine YouTube et analyse comparative

Ce module permet de :
1. Auditer sa propre chaine (via OAuth) ou n'importe quelle chaine (via API key)
2. Extraire les PATTERNS GAGNANTS : titres, durees, categories, cadence
3. Comparer sa chaine a d'autres chaines pour identifier les ecarts
4. Apprendre des anciennes videos qui ont bien marche
5. Generer des recommandations concretes a tester

Le resultat d'un audit est sauvegarde dans data/audits/ pour l'historique.
"""

import json
import re
import sys
import requests
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Isolement des chemins (Phase 9) : DATA_DIR en mode installe, repli racine.
try:
    from core.paths import DATA_DIR
    CONFIG_PATH = DATA_DIR / "config.json"
    AUDITS_DIR = DATA_DIR / "data" / "audits"
except Exception:
    CONFIG_PATH = Path(__file__).parent.parent.parent / "config.json"
    AUDITS_DIR = Path(__file__).parent.parent.parent / "data" / "audits"


def log(msg):
    print(f"[AUDIT] {msg}")


def _lire_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def _api_key():
    config = _lire_config()
    return config.get("youtube_api_key") or None


def _duree_iso_a_secondes(duree_iso):
    """Convertit 'PT1H2M3S' en secondes (ou None si illisible)."""
    if not duree_iso:
        return None
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duree_iso)
    if not m:
        return None
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def _duree_affichage(secondes):
    if not secondes:
        return "?"
    m, s = divmod(int(secondes), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h{m:02d}"
    return f"{m}m{s:02d}"


def _formater_nombre(n):
    n = int(n or 0)
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(n)


# ---------------------------------------------------------------
# Identification de la chaine
# ---------------------------------------------------------------

def identifier_ma_chaine():
    """
    Retrouve l'ID de la chaine de l'utilisateur via OAuth.

    Returns:
        dict: {"ok": True, "channel_id": "...", "titre": "..."} ou {"ok": False, "erreur": "..."}
    """
    try:
        from modules.youtube_analyzer.youtube_upload import _get_access_token
        access_token = _get_access_token()
        if not access_token:
            return {"ok": False, "erreur": "OAuth non configure. Lance auth_flow() d'abord."}

        try:
            from googleapiclient.discovery import build
            from google.oauth2.credentials import Credentials
            credentials = Credentials(token=access_token)
            youtube = build("youtube", "v3", credentials=credentials)
            response = youtube.channels().list(part="id,snippet,statistics", mine=True).execute()
            if not response.get("items"):
                return {"ok": False, "erreur": "Aucune chaine associee a ce compte"}
            item = response["items"][0]
            return {
                "ok": True,
                "channel_id": item["id"],
                "titre": item.get("snippet", {}).get("title", ""),
                "abonnes": int(item.get("statistics", {}).get("subscriberCount", 0)),
                "vues_total": int(item.get("statistics", {}).get("viewCount", 0)),
                "videos_total": int(item.get("statistics", {}).get("videoCount", 0))
            }
        except ImportError:
            return {"ok": False, "erreur": "googleapiclient non installe"}
    except Exception as e:
        return {"ok": False, "erreur": str(e)}


# ---------------------------------------------------------------
# Recuperation des donnees via API key
# ---------------------------------------------------------------

def _get_chaine(channel_id):
    cle = _api_key()
    if not cle:
        return None
    try:
        r = requests.get("https://www.googleapis.com/youtube/v3/channels", params={
            "part": "snippet,statistics", "id": channel_id, "key": cle
        }, timeout=15)
        if r.status_code != 200:
            return None
        items = r.json().get("items", [])
        if not items:
            return None
        item = items[0]
        st = item.get("statistics", {})
        sn = item.get("snippet", {})
        return {
            "id": channel_id,
            "titre": sn.get("title", "?"),
            "description": sn.get("description", "")[:200],
            "thumbnail": sn.get("thumbnails", {}).get("medium", {}).get("url", ""),
            "abonnes": int(st.get("subscriberCount", 0)),
            "videos_total": int(st.get("videoCount", 0)),
            "vues_total": int(st.get("viewCount", 0)),
            "date_creation": sn.get("publishedAt", "")[:10]
        }
    except Exception as e:
        log(f"Erreur chaine {channel_id}: {e}")
        return None


def _chercher_id_chaine(nom):
    cle = _api_key()
    if not cle:
        return None
    try:
        r = requests.get("https://www.googleapis.com/youtube/v3/search", params={
            "part": "snippet", "q": nom, "type": "channel", "maxResults": 1, "key": cle
        }, timeout=15)
        if r.status_code != 200:
            return None
        items = r.json().get("items", [])
        return items[0]["snippet"]["channelId"] if items else None
    except Exception:
        return None


def _get_videos_detail(ids):
    """Recupere les details (stats + duree + tags) de plusieurs videos."""
    cle = _api_key()
    if not cle or not ids:
        return []
    resultats = []
    # API limite a 50 ids par requete
    for i in range(0, len(ids), 50):
        batch = ids[i:i + 50]
        try:
            r = requests.get("https://www.googleapis.com/youtube/v3/videos", params={
                "part": "statistics,snippet,contentDetails",
                "id": ",".join(batch), "key": cle
            }, timeout=15)
            if r.status_code != 200:
                continue
            for item in r.json().get("items", []):
                sn = item.get("snippet", {})
                st = item.get("statistics", {})
                vues = int(st.get("viewCount", 0))
                likes = int(st.get("likeCount", 0))
                commentaires = int(st.get("commentCount", 0))
                resultats.append({
                    "id": item["id"],
                    "titre": sn.get("title", "?"),
                    "date_publication": sn.get("publishedAt", ""),
                    "duree_secondes": _duree_iso_a_secondes(
                        item.get("contentDetails", {}).get("duration", "")),
                    "vues": vues,
                    "likes": likes,
                    "commentaires": commentaires,
                    "tags": sn.get("tags", [])[:15],
                    "categorie": sn.get("categoryId", "?"),
                    "description": sn.get("description", "")[:500],
                    "engagement": round((likes + commentaires) / max(vues, 1) * 100, 2)
                })
        except Exception as e:
            log(f"Erreur detail videos: {e}")
    return resultats


def _vider_videos_recentes(channel_id, max_results=50):
    """Liste les IDs des videos recentes d'une chaine."""
    cle = _api_key()
    if not cle:
        return []
    try:
        r = requests.get("https://www.googleapis.com/youtube/v3/search", params={
            "part": "snippet", "channelId": channel_id, "order": "date",
            "maxResults": max_results, "type": "video", "key": cle
        }, timeout=15)
        if r.status_code != 200:
            return []
        return [item["id"]["videoId"] for item in r.json().get("items", [])
                if item.get("id", {}).get("videoId")]
    except Exception:
        return []


def _vider_top_videos(channel_id, max_results=10):
    """Liste les IDs des videos les plus vues de tous les temps."""
    cle = _api_key()
    if not cle:
        return []
    try:
        r = requests.get("https://www.googleapis.com/youtube/v3/search", params={
            "part": "snippet", "channelId": channel_id, "order": "viewCount",
            "maxResults": max_results, "type": "video", "key": cle
        }, timeout=15)
        if r.status_code != 200:
            return []
        return [item["id"]["videoId"] for item in r.json().get("items", [])
                if item.get("id", {}).get("videoId")]
    except Exception:
        return []


# ---------------------------------------------------------------
# Analyse des patterns
# ---------------------------------------------------------------

MOTS_VIDE_STRIP = {
    "la", "le", "les", "de", "des", "du", "un", "une", "et", "ou", "au",
    "aux", "en", "pour", "que", "qui", "dans", "avec", "sur", "ce", "cette",
    "ces", "sa", "son", "ses", "ma", "mon", "mes", "ton", "ta", "tes",
    "the", "a", "an", "of", "to", "in", "for", "and", "on", "with", "is",
    "vs", "par", "ne", "pas", "plus", "moins", "se", "s'", "j'", "l'", "d'",
    "pourquoi", "comment", "quand", "est", "sont", "il", "elle", "ils",
    "priere", "priere", "the", "to", "i", "you", "we", "it"
}


def _mots_titre(titre):
    """Extrait les mots significatifs d'un titre."""
    t = titre.lower().replace("'", " ").replace("-", " ")
    t = re.sub(r"[^a-z0-9àâäéèêëîïôöùûüç ]", "", t)
    mots = [m for m in t.split() if len(m) > 3 and m not in MOTS_VIDE_STRIP]
    return mots


def extraire_patterns(videos):
    """
    Analyse les videos pour en extraire les patterns gagnants.

    Compare le tiers superieur (par vues) au tiers inferieur.
    """
    if len(videos) < 4:
        return {
            "motifs_gagnants": [],
            "duree_optimale": None,
            "titre_longueur_moyenne": None,
            "cadence_jours": None,
            "engagement_moyen": None,
            "nb_videos": len(videos)
        }

    videos_triees = sorted(videos, key=lambda v: v["vues"], reverse=True)
    n_tier = max(1, len(videos_triees) // 3)
    top = videos_triees[:n_tier]
    bas = videos_triees[-n_tier:]

    # Mots les plus frequents dans les titres du top
    compteur_top = Counter()
    compteur_bas = Counter()
    for v in top:
        compteur_top.update(_mots_titre(v["titre"]))
    for v in bas:
        compteur_bas.update(_mots_titre(v["titre"]))

    motifs = []
    for mot, freq in compteur_top.most_common(10):
        if freq >= 2 and compteur_bas.get(mot, 0) <= freq - 1:
            motifs.append({"mot": mot, "frequence_top": freq, "frequence_bas": compteur_bas.get(mot, 0)})

    # Duree moyenne top vs bas
    durees_top = [v["duree_secondes"] for v in top if v.get("duree_secondes")]
    durees_bas = [v["duree_secondes"] for v in bas if v.get("duree_secondes")]
    duree_top = sum(durees_top) / len(durees_top) if durees_top else None
    duree_bas = sum(durees_bas) / len(durees_bas) if durees_bas else None

    # Cadence de publication (jours entre videos)
    dates = sorted([v["date_publication"] for v in videos if v.get("date_publication")])
    cadence = None
    if len(dates) > 1:
        ecarts = []
        for i in range(1, len(dates)):
            try:
                d1 = datetime.fromisoformat(dates[i - 1].replace("Z", "+00:00"))
                d2 = datetime.fromisoformat(dates[i].replace("Z", "+00:00"))
                ecarts.append((d2 - d1).days)
            except:
                pass
        if ecarts:
            cadence = round(sum(ecarts) / len(ecarts), 1)

    return {
        "motifs_gagnants": motifs,
        "duree_top": round(duree_top / 60, 1) if duree_top else None,
        "duree_bas": round(duree_bas / 60, 1) if duree_bas else None,
        "duree_optimale": round(duree_top / 60, 1) if duree_top else None,
        "titre_longueur_top": round(sum(len(v["titre"]) for v in top) / len(top), 0),
        "titre_longueur_bas": round(sum(len(v["titre"]) for v in bas) / len(bas), 0),
        "engagement_moyen": round(sum(v["engagement"] for v in videos) / len(videos), 2),
        "cadence_jours": cadence,
        "vues_moyennes": round(sum(v["vues"] for v in videos) / len(videos), 0),
        "nb_videos": len(videos)
    }


def generer_recommandations(chaine, patterns, videos, comparaisons=None):
    """
    Transforme les patterns et comparaisons en recommandations actionnables.
    """
    reco = []
    top_vues = sorted(videos, key=lambda v: v["vues"], reverse=True)

    # 1. Ce qui a marche chez nous
    if top_vues:
        meilleure = top_vues[0]
        reco.append({
            "priorite": "haute",
            "titre": "Replique ta meilleure video",
            "detail": (f"'{meilleure['titre'][:60]}' a fait {_formater_nombre(meilleure['vues'])} vues. "
                       f"Refais une video sur le meme theme avec des variantes de titre.")
        })

    # 2. Duree optimale
    if patterns.get("duree_optimale") and patterns.get("duree_top"):
        reco.append({
            "priorite": "haute" if patterns.get("duree_bas") else "moyenne",
            "titre": "Cible cette duree de video",
            "detail": (f"Tes videos qui marchent font ~{patterns['duree_top']} min "
                       f"({patterns.get('duree_bas', '?')} min pour celles qui marchent moins). "
                       f"Teste la fourchette {max(1, patterns['duree_top'] - 2)}-{patterns['duree_top'] + 3} min.")
        })

    # 3. Mots-clés gagnants
    if patterns.get("motifs_gagnants"):
        mots = ", ".join(f"'{m['mot']}'" for m in patterns["motifs_gagnants"][:5])
        reco.append({
            "priorite": "haute",
            "titre": "Utilise ces mots dans tes prochains titres",
            "detail": f"Les mots qui reviennent dans tes videos performantes : {mots}. Integre-les naturellement."
        })

    # 4. Cadence
    if patterns.get("cadence_jours"):
        reco.append({
            "priorite": "moyenne",
            "titre": "Cadence de publication",
            "detail": f"Tu publies en moyenne toutes les {patterns['cadence_jours']} jours. Une cadence reguliere aide l'algorithme a comprendre ta chaine."
        })

    # 5. Comparaisons avec d'autres chaines
    if comparaisons:
        for comp in comparaisons[:3]:
            if comp.get("ratio_vues") and comp["ratio_vues"] > 1.5:
                reco.append({
                    "priorite": "moyenne",
                    "titre": f"Ispire-toi de {comp.get('chaine', {}).get('titre', 'cette chaine')}",
                    "detail": (f"Ils font en moyenne {_formater_nombre(comp.get('vues_moyennes', 0))} vues/video "
                               f"({comp['ratio_vues']:.1f}x plus que toi). Analyse leurs tops pour trouver des angles.")
                })

    # 6. Engagement faible -> ameliorer les vignettes/description
    if patterns.get("engagement_moyen") is not None and patterns["engagement_moyen"] < 2:
        reco.append({
            "priorite": "moyenne",
            "titre": "Boost l'engagement",
            "detail": f"Engagement moyen de {patterns['engagement_moyen']}% (faible). Ajoute des appels a commenter et des questions dans la description."
        })

    # 7. Si aucune video assez performante
    if not reco:
        reco.append({
            "priorite": "haute",
            "titre": "Continue de publier et analyse",
            "detail": "Pas encore assez de donnees. Publie 3-5 videos supplementaires puis relance l'audit."
        })

    return reco[:8]


def generer_idees_a_tester(chaine, patterns, videos, comparaisons=None):
    """
    Genere des idees concretes de contenu a tester, basees sur les patterns
    et les tops des chaines comparees.
    """
    idees = []

    # Idees depuis les tops de notre chaine
    top_vues = sorted(videos, key=lambda v: v["vues"], reverse=True)[:3]
    for v in top_vues[:2]:
        idees.append({
            "source": "ta chaine",
            "idee": f"Revisite '{v['titre'][:55]}' en version {patterns.get('duree_top', 5) or 5} min, "
                    f"avec un titre court et un visuel fort.",
            "vues": v["vues"]
        })

    # Idees depuis les chaines comparees
    if comparaisons:
        for comp in comparaisons:
            for v in comp.get("top_videos", [])[:2]:
                sujet = v["titre"][:50]
                idees.append({
                    "source": comp.get("chaine", {}).get("titre", "autre chaine"),
                    "idee": f"Adapte le sujet '{sujet}' a ton format priere/profil actif. "
                            f"C'est un theme qui marche chez eux ({_formater_nombre(v['vues'])} vues).",
                    "vues": v["vues"]
                })
                if len(idees) >= 5:
                    break
            if len(idees) >= 5:
                break

    # Idees depuis les mots gagnants
    for m in (patterns.get("motifs_gagnants") or [])[:2]:
        idees.append({
            "source": "patterns",
            "idee": f"Creer une video dont le titre inclut '{m['mot']}' (mot gagnant dans tes tops).",
            "vues": 0
        })

    return idees[:6]


# ---------------------------------------------------------------
# Audit principal
# ---------------------------------------------------------------

def auditer_chaine(channel_id, max_videos=50):
    """
    Audit complet d'une chaine YouTube.

    Returns:
        dict ou None: chaine, videos, top_historique, patterns,
                      meilleure, pire, recommandations, idees
    """
    chaine = _get_chaine(channel_id)
    if not chaine:
        return None

    ids_recentes = _vider_videos_recentes(channel_id, max_results=max_videos)
    ids_top = _vider_top_videos(channel_id, max_results=10)

    videos = _get_videos_detail(ids_recentes)
    top_historique = _get_videos_detail(ids_top)

    # Fusionner sans doublon
    vues = {v["id"]: v for v in videos}
    for v in top_historique:
        if v["id"] not in vues:
            vues[v["id"]] = v
    toutes = list(vues.values())

    if not toutes:
        return {
            "chaine": chaine,
            "videos": [],
            "top_historique": [],
            "patterns": {"nb_videos": 0},
            "meilleure": None,
            "pire": None,
            "recommandations": [],
            "idees_a_tester": [],
            "date_analyse": datetime.now().isoformat()
        }

    patterns = extraire_patterns(toutes)
    triees = sorted(toutes, key=lambda v: v["vues"], reverse=True)
    meilleure = triees[0]
    pire = triees[-1]
    recommandations = generer_recommandations(chaine, patterns, toutes)
    idees = generer_idees_a_tester(chaine, patterns, toutes)

    audit = {
        "chaine": chaine,
        "videos": sorted(toutes, key=lambda v: v.get("date_publication", ""), reverse=True)[:30],
        "top_historique": top_historique,
        "patterns": patterns,
        "meilleure": meilleure,
        "pire": pire,
        "recommandations": recommandations,
        "idees_a_tester": idees,
        "date_analyse": datetime.now().isoformat()
    }
    return audit


# ---------------------------------------------------------------
# Comparaison
# ---------------------------------------------------------------

def comparer_chaines(ids_chaines):
    """
    Audite plusieurs chaines et les compare a la premiere (la reference).

    Returns:
        dict: comparaisons = liste de {"chaine", "vues_moyennes", "ratio_vues", "tops"...}
    """
    if not ids_chaines:
        return {"reference": None, "comparaisons": []}

    audits = []
    for cid in ids_chaines:
        a = auditer_chaine(cid)
        if a:
            audits.append(a)

    if not audits:
        return {"reference": None, "comparaisons": []}

    reference = audits[0]
    ref_vues = reference.get("patterns", {}).get("vues_moyennes", 0) or 0

    comparaisons = []
    for a in audits[1:]:
        vues_moy = a.get("patterns", {}).get("vues_moyennes", 0) or 0
        comparaisons.append({
            "chaine": a["chaine"],
            "vues_moyennes": vues_moy,
            "ratio_vues": round(vues_moy / max(ref_vues, 1), 1),
            "abonnes": a["chaine"].get("abonnes", 0),
            "engagement": a.get("patterns", {}).get("engagement_moyen"),
            "cadence_jours": a.get("patterns", {}).get("cadence_jours"),
            "duree_top": a.get("patterns", {}).get("duree_top"),
            "top_videos": (a.get("top_historique") or [])[:5],
            "motifs_gagnants": a.get("patterns", {}).get("motifs_gagnants", [])[:5],
            "meilleure": a.get("meilleure")
        })

    return {
        "reference": reference,
        "comparaisons": comparaisons
    }


def audit_ma_chaine_avec_concurrents(noms_concurrents=None):
    """
    Audit complet de SA chaine + comparaison avec des concurrents.

    Args:
        noms_concurrents: liste de noms (ou handles) de chaines concurrentes

    Returns:
        dict: {"ok": bool, "audit": ..., "comparaison": ..., "erreur": ...}
    """
    ma = identifier_ma_chaine()
    if not ma.get("ok"):
        return {"ok": False, "erreur": ma.get("erreur", "Impossible d'identifier ta chaine")}

    mon_audit = auditer_chaine(ma["channel_id"])

    comparaisons = []
    if noms_concurrents:
        ids = []
        for nom in noms_concurrents:
            cid = _chercher_id_chaine(nom)
            if cid:
                ids.append(cid)
        if ids:
            cmp = comparer_chaines([ma["channel_id"]] + ids)
            comparaisons = cmp.get("comparaisons", [])

    # Analyse des commentaires (besoins / prieres des spectateurs)
    analyse_comments = None
    try:
        from modules.youtube_analyzer.comment_analyzer import analyser_comments_chaine
        res = analyser_comments_chaine(ma["channel_id"])
        if res.get("ok"):
            analyse_comments = {
                "nb_commentaires": res.get("nb_commentaires", 0),
                "besoins": res.get("analyse", {}).get("besoins", []),
                "nb_prieres": res.get("analyse", {}).get("nb_prieres", 0),
                "prieres": res.get("analyse", {}).get("prieres", [])[:5],
                "commentateurs_actifs": res.get("analyse", {}).get("commentateurs_actifs", []),
                "synthese": res.get("synthese")
            }
    except Exception as e:
        log(f"Analyse commentaires ignoree: {e}")

    # Recommandations enrichies avec les comparaisons
    recommandations = []
    idees = []
    if mon_audit:
        # Fusionner videos recentes + top historique pour des reco completes
        vues_par_id = {v["id"]: v for v in mon_audit.get("videos", [])}
        for v in mon_audit.get("top_historique", []):
            if v["id"] not in vues_par_id:
                vues_par_id[v["id"]] = v
        toutes = list(vues_par_id.values())

        recommandations = generer_recommandations(
            mon_audit.get("chaine"), mon_audit.get("patterns", {}),
            toutes, comparaisons)
        idees = generer_idees_a_tester(
            mon_audit.get("chaine"), mon_audit.get("patterns", {}),
            toutes, comparaisons)
        mon_audit["recommandations"] = recommandations
        mon_audit["idees_a_tester"] = idees

        # Predictions statistiques + plan de rythme (moyennes passees)
        mon_audit["predictions"] = predire_croissance(
            mon_audit.get("chaine"), mon_audit.get("patterns", {}), toutes)
        mon_audit["plan_rythme"] = generer_plan_rythme(
            mon_audit.get("chaine"), mon_audit.get("patterns", {}), toutes, comparaisons)

        # Enrichir les recommandations avec les besoins des commentaires
        if analyse_comments:
            mon_audit["commentaires"] = analyse_comments
            besoins = analyse_comments.get("besoins", [])
            if besoins:
                top_besoins = ", ".join(b["theme"] for b in besoins[:4])
                reco_comments = {
                    "priorite": "haute",
                    "titre": "Reponds aux besoins ecrits dans les commentaires",
                    "detail": f"Les spectateurs demandent surtout : {top_besoins}. "
                              f"Fais une video de priere qui repond directement au besoin "
                              f"le plus frequent (voir aussi les prieres laissees en commentaire)."
                }
                # Inserer en premiere position
                mon_audit["recommandations"] = [reco_comments] + mon_audit.get("recommandations", [])

            if analyse_comments.get("nb_prieres", 0) > 0:
                prieurs = analyse_comments.get("commentateurs_actifs", [])[:3]
                if prieurs:
                    noms = ", ".join(p["nom"] for p in prieurs)
                    mon_audit["recommandations"].append({
                        "priorite": "moyenne",
                        "titre": "Cite les prieurs des commentaires",
                        "detail": f"Des spectateurs prient dans les commentaires ({noms}). "
                                  f"Cite leur prenom dans une prochaine video — cela cree un lien fort."
                    })

    resultat = {
        "ok": True,
        "ma_chaine": ma,
        "audit": mon_audit,
        "comparaisons": comparaisons,
        "predictions": (mon_audit or {}).get("predictions"),
        "plan_rythme": (mon_audit or {}).get("plan_rythme"),
        "date_analyse": datetime.now().isoformat()
    }

    sauvegarder_audit(ma["channel_id"], resultat)
    return resultat


# ---------------------------------------------------------------
# Persistance des audits
# ---------------------------------------------------------------

def sauvegarder_audit(channel_id, data):
    """Sauvegarde un audit pour l'historique et l'apprentissage."""
    try:
        AUDITS_DIR.mkdir(parents=True, exist_ok=True)
        nom = f"audit_{channel_id.replace('UC', '').replace(':', '_')}.json"
        audit = data.get("audit") or data
        # Garder seulement l'essentiel pour eviter des fichiers trop gros
        reduit = {
            "channel_id": channel_id,
            "chaine": audit.get("chaine"),
            "patterns": audit.get("patterns"),
            "meilleure": audit.get("meilleure"),
            "recommandations": audit.get("recommandations") or data.get("recommandations"),
            "idees_a_tester": audit.get("idees_a_tester"),
            "comparaisons": data.get("comparaisons"),
            "date_analyse": data.get("date_analyse") or audit.get("date_analyse") or datetime.now().isoformat()
        }
        with open(AUDITS_DIR / nom, "w", encoding="utf-8") as f:
            json.dump(reduit, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log(f"Erreur sauvegarde audit: {e}")
        return False


def lister_audits():
    """Liste les audits sauvegardes (historique)."""
    if not AUDITS_DIR.exists():
        return []
    resultats = []
    for f in sorted(AUDITS_DIR.glob("audit_*.json"), reverse=True):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            resultats.append({
                "fichier": f.name,
                "chaine": data.get("chaine", {}).get("titre", "?"),
                "date_analyse": data.get("date_analyse", ""),
                "recommandations": (data.get("recommandations") or [])[:3],
                "motifs": (data.get("patterns") or {}).get("motifs_gagnants", [])[:5],
                "duree_top": (data.get("patterns") or {}).get("duree_top")
            })
        except:
            pass
    return resultats[:10]


# ---------------------------------------------------------------
# Apprentissage croise (multi-audits)
# ---------------------------------------------------------------

def apprentissage_croise():
    """
    Combine tous les audits sauvegardes pour extraire des lecons generales.

    Returns:
        dict: lecons, themes_gagnants, durees_gagnantes
    """
    audits = lister_audits()
    motifs_globaux = Counter()
    durees = []
    recommandations_globales = []

    for a in audits:
        for m in (a.get("motifs") or []):
            motifs_globaux[m.get("mot", "")] += m.get("frequence_top", 1)
        d = (a.get("patterns") or {}).get("duree_top")
        if d:
            durees.append(d)
        for r in (a.get("recommandations") or []):
            if r.get("titre") not in [x.get("titre") for x in recommandations_globales]:
                recommandations_globales.append(r)

    duree_moyenne = round(sum(durees) / len(durees), 1) if durees else None

    return {
        "themes_gagnants": [{"mot": m, "frequence": f} for m, f in motifs_globaux.most_common(10)],
        "duree_gagnante_moyenne": duree_moyenne,
        "nb_audits": len(audits),
        "recommandations_globales": recommandations_globales[:5]
    }


# ---------------------------------------------------------------
# Predictions statistiques
# ---------------------------------------------------------------

def _calculer_croissance(chaine, patterns, videos):
    """Calcule les taux de croissance actuels de la chaine (par jour)."""
    abonnes = int(chaine.get("abonnes") or 0)
    vues_total = int(chaine.get("vues_total") or 0)
    vues_moy = int(patterns.get("vues_moyennes") or 0)
    cadence = patterns.get("cadence_jours")

    # Vues/jour generees par les nouvelles publications
    vues_par_jour_pub = 0.0
    if cadence and cadence > 0 and vues_moy:
        vues_par_jour_pub = vues_moy / cadence

    # Long-tail : les videos deja publiees continuent de ramener des vues.
    # Estimation conservatrice : ~30% des vues totales par an.
    vues_long_tail = 0.0
    date_creation = chaine.get("date_creation")
    if date_creation and vues_total:
        try:
            d_creation = datetime.fromisoformat(date_creation)
            jours = max((datetime.now() - d_creation).days, 1)
            vues_long_tail = vues_total / jours * 0.3
        except Exception:
            pass

    vues_par_jour = vues_par_jour_pub + vues_long_tail
    # Taux de conversion vues -> abonnes (0.3% conservateur)
    taux_conversion = 0.003
    abonnes_par_jour = vues_par_jour * taux_conversion

    return {
        "abonnes": abonnes,
        "vues_total": vues_total,
        "vues_moyennes": vues_moy,
        "cadence_jours": cadence,
        "vues_par_jour": round(vues_par_jour, 1),
        "abonnes_par_jour": round(abonnes_par_jour, 3),
        "taux_conversion_estime_pct": round(taux_conversion * 100, 2)
    }


def predire_croissance(chaine, patterns, videos, horizons=(30, 90, 180, 365)):
    """
    Predit la croissance de la chaine (abonnes, vues, videos) a 1/3/6/12 mois,
    en projetant les moyennes actuelles (vues/video, cadence de publication).

    Returns:
        dict: croissance (taux actuels), projections (par horizon),
              jalons (prochains paliers d'abonnes), confiance
    """
    croissance = _calculer_croissance(chaine, patterns, videos)

    projections = []
    for jours in horizons:
        abonnes = int(croissance["abonnes"] + croissance["abonnes_par_jour"] * jours)
        vues = int(croissance["vues_total"] + croissance["vues_par_jour"] * jours)
        videos_predites = int(chaine.get("videos_total") or 0)
        if croissance["cadence_jours"]:
            videos_predites += int(jours / croissance["cadence_jours"])
        projections.append({
            "horizon_jours": jours,
            "horizon": f"{jours // 30} mois",
            "abonnes_predits": abonnes,
            "vues_predites": vues,
            "videos_predites": videos_predites,
            "abonnes_gagnes": abonnes - croissance["abonnes"],
            "vues_gagnees": vues - croissance["vues_total"]
        })

    # Jalons : prochains paliers d'abonnes (1000, 2000, ...)
    jalons = []
    abonnes_actuels = croissance["abonnes"]
    for palier in range(1000, max(10000, abonnes_actuels + 2000) + 1, 1000):
        if palier > abonnes_actuels:
            jours = int((palier - abonnes_actuels) / max(croissance["abonnes_par_jour"], 0.001))
            jalons.append({"palier": palier, "jours": jours, "mois": round(jours / 30, 1)})
        if len(jalons) >= 4:
            break

    # Confiance selon la quantite de donnees
    nb_videos = len(videos)
    confiance = "bonne" if nb_videos >= 15 else ("moyenne" if nb_videos >= 6 else "faible")

    return {
        "croissance": croissance,
        "projections": projections,
        "jalons": jalons,
        "confiance": confiance,
        "nb_videos_analysees": nb_videos,
        "date": datetime.now().isoformat()
    }


def generer_plan_rythme(chaine, patterns, videos, comparaisons=None):
    """
    Plan de rythme de production : garde la cadence qui a deja marche,
    reproduit les formats gagnants, et propose un programme hebdomadaire.

    Returns:
        dict: cadence, videos a reproduire, programme hebdo, idees prioritaires, objectif
    """
    cadence_jours = patterns.get("cadence_jours")
    videos_par_semaine = round(7 / cadence_jours, 1) if cadence_jours and cadence_jours > 0 else 1.0

    top_vues = sorted(videos, key=lambda v: v["vues"], reverse=True)[:3]
    a_reproduire = [{
        "titre": v["titre"],
        "vues": v["vues"],
        "duree_min": round(v["duree_secondes"] / 60, 0) if v.get("duree_secondes") else None,
        "mots_cles": _mots_titre(v["titre"])[:3]
    } for v in top_vues]

    duree_top = patterns.get("duree_top")

    # Programme hebdomadaire suggere
    programme = []
    jours_semaine = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    nb_publications = max(1, min(7, int(round(videos_par_semaine))))
    pas = 7 / nb_publications
    for i in range(nb_publications):
        jour = jours_semaine[min(6, int(i * pas))]
        theme = a_reproduire[i % len(a_reproduire)]["mots_cles"] if a_reproduire else []
        programme.append({
            "jour": jour,
            "type": f"Video sur {' / '.join(theme) if theme else 'le theme gagnant'}",
            "duree_cible_min": duree_top
        })

    idees = generer_idees_a_tester(chaine, patterns, videos, comparaisons)

    objectif_mensuel = {
        "videos_par_mois": round(30 / cadence_jours, 0) if cadence_jours else 4,
        "vues_estimees": round(videos_par_semaine * 4.3 * (patterns.get("vues_moyennes") or 0), 0)
    }

    return {
        "cadence_actuelle_jours": cadence_jours,
        "videos_par_semaine": videos_par_semaine,
        "duree_gagnante_min": duree_top,
        "a_reproduire": a_reproduire,
        "programme_hebdo": programme,
        "idees_prioritaires": idees[:5],
        "objectif_mensuel": objectif_mensuel
    }


# ---------------------------------------------------------------
# Surveillance de la chaine cible
# ---------------------------------------------------------------

def _fichier_surveillance():
    return AUDITS_DIR / "surveillance.json"


def get_chaine_cible():
    """Retourne la chaine sous surveillance (config)."""
    config = _lire_config()
    return config.get("chaine_cible") or {}


def definir_chaine_cible(nom_ou_id):
    """
    Definit la chaine cible a surveiller (par nom, handle @ ou ID UC...).

    Returns:
        dict: {"ok": bool, "chaine": {...}, "erreur": str}
    """
    nom_ou_id = (nom_ou_id or "").strip()
    if not nom_ou_id:
        return {"ok": False, "erreur": "Nom ou ID de chaine requis"}

    cid = nom_ou_id if nom_ou_id.startswith("UC") else _chercher_id_chaine(nom_ou_id)
    if not cid:
        return {"ok": False, "erreur": f"Chaine '{nom_ou_id}' introuvable"}

    chaine = _get_chaine(cid)
    if not chaine:
        return {"ok": False, "erreur": "Impossible de recuperer les stats de cette chaine"}

    config = _lire_config()
    config["chaine_cible"] = {
        "channel_id": cid,
        "nom": chaine.get("titre"),
        "definie_le": datetime.now().isoformat()
    }
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    # Premier snapshot + audit complet
    surveiller_chaine()
    return {"ok": True, "chaine": chaine}


def _lire_snapshots():
    f = _fichier_surveillance()
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _sauver_snapshot(snapshot):
    snapshots = _lire_snapshots()
    snapshots.insert(0, snapshot)
    snapshots = snapshots[:20]
    f = _fichier_surveillance()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(snapshots, ensure_ascii=False, indent=2), encoding="utf-8")


def _evaluer_chaine_ia(chaine, patterns, evolution):
    """L'IA resume comment la chaine avance et quoi faire (fallback heuristique)."""
    try:
        from modules.brain.generate_script import appeler_ollama
        evol_txt = ""
        if evolution:
            evol_txt = (f"- Evolution depuis le dernier controle ({evolution.get('jours', 0)} j) : "
                        f"+{evolution.get('abonnes_gagnes', 0)} abonnes, "
                        f"+{_formater_nombre(evolution.get('vues_gagnees', 0))} vues")
        prompt = f"""
Tu es un expert YouTube specialise dans les chaines de priere/relaxation.
Stats actuelles de la chaine :
- Abonnes : {chaine.get('abonnes', 0)}
- Vues totales : {_formater_nombre(chaine.get('vues_total', 0))}
- Videos : {chaine.get('videos_total', 0)}
- Vues moyennes/video : {_formater_nombre(patterns.get('vues_moyennes', 0))}
- Cadence : {patterns.get('cadence_jours', '?')} jours entre videos
- Duree qui marche : {patterns.get('duree_top', '?')} min
- Mots gagnants : {', '.join(m['mot'] for m in (patterns.get('motifs_gagnants') or [])[:5])}
{evol_txt}

En 5 lignes maximum : comment la chaine avance, 1 point fort, 1 point a ameliorer,
et 1 action concrete pour la semaine prochaine.
"""
        texte, modele = appeler_ollama(prompt, modele="qwen2.5:7b", temperature=0.4)
        return {"texte": texte.strip(), "modele": modele}
    except Exception as e:
        return {"texte": None, "erreur": str(e)}


def statut_surveillance():
    """
    Etat LEGER de la surveillance (1 seul appel API) — pour le dashboard.
    """
    cible = get_chaine_cible()
    if not cible:
        return {"ok": False, "erreur": "Aucune chaine cible definie"}
    chaine = _get_chaine(cible["channel_id"])
    snapshots = _lire_snapshots()
    return {
        "ok": True,
        "cible": cible,
        "chaine": chaine,
        "snapshots": snapshots[:5],
        "nb_snapshots": len(snapshots)
    }


def surveiller_chaine():
    """
    Rapport complet de surveillance : stats actuelles + evolution depuis le
    dernier controle + predictions statistiques + plan de rythme + evaluation IA.
    """
    cible = get_chaine_cible()
    if not cible:
        return {"ok": False, "erreur": "Aucune chaine cible definie. Utilise /api/surveillance/cible"}

    chaine = _get_chaine(cible["channel_id"])
    if not chaine:
        return {"ok": False, "erreur": "Impossible de recuperer la chaine cible"}

    audit = auditer_chaine(cible["channel_id"])
    patterns = (audit or {}).get("patterns") or {}
    videos = (audit or {}).get("videos") or []

    predictions = predire_croissance(chaine, patterns, videos)
    plan = generer_plan_rythme(chaine, patterns, videos)

    # Evolution depuis le dernier snapshot
    snapshots = _lire_snapshots()
    dernier = snapshots[0] if snapshots else None
    evolution = None
    if dernier:
        try:
            jours = (datetime.now() - datetime.fromisoformat(dernier["date"])).days
        except Exception:
            jours = 0
        evolution = {
            "jours": jours,
            "abonnes_gagnes": int(chaine.get("abonnes") or 0) - int(dernier.get("abonnes") or 0),
            "vues_gagnees": int(chaine.get("vues_total") or 0) - int(dernier.get("vues_total") or 0),
            "videos_gagnees": int(chaine.get("videos_total") or 0) - int(dernier.get("videos_total") or 0)
        }

    evaluation = _evaluer_chaine_ia(chaine, patterns, evolution)

    # Analyse des commentaires (besoins, prieres) — seulement si API key presente
    commentaires = None
    try:
        from modules.youtube_analyzer.comment_analyzer import analyser_comments_chaine
        res = analyser_comments_chaine(cible["channel_id"])
        if res.get("ok"):
            commentaires = {
                "nb_commentaires": res.get("nb_commentaires", 0),
                "besoins": res.get("analyse", {}).get("besoins", []),
                "prieres_recents": res.get("analyse", {}).get("prieres", [])[:5],
                "synthese": res.get("synthese")
            }
    except Exception as e:
        log(f"Commentaires surveillance ignoree: {e}")

    snapshot = {
        "date": datetime.now().isoformat(),
        "abonnes": int(chaine.get("abonnes") or 0),
        "vues_total": int(chaine.get("vues_total") or 0),
        "videos_total": int(chaine.get("videos_total") or 0)
    }
    _sauver_snapshot(snapshot)

    return {
        "ok": True,
        "chaine": chaine,
        "cible": cible,
        "evolution": evolution,
        "predictions": predictions,
        "plan_rythme": plan,
        "evaluation_ia": evaluation,
        "commentaires": commentaires,
        "dernier_controle": snapshot
    }


if __name__ == "__main__":
    # Test: identifier sa chaine
    ma = identifier_ma_chaine()
    if ma.get("ok"):
        print(f"Ma chaine: {ma['titre']} ({ma['channel_id']})")
        print(f"  Abonnes: {ma['abonnes']}, Videos: {ma['videos_total']}, Vues: {ma['vues_total']}")
        audit = auditer_chaine(ma["channel_id"])
        if audit:
            print(f"\nAudit de {audit['chaine']['titre']}")
            print(f"  Videos analysees: {len(audit['videos'])}")
            print(f"  Meilleure: {audit['meilleure']['titre']} ({_formater_nombre(audit['meilleure']['vues'])} vues)")
            print(f"  Patterns: {json.dumps(audit['patterns'].get('motifs_gagnants', []), ensure_ascii=False)[:300]}")
            for r in audit["recommandations"]:
                print(f"  [{r['priorite']}] {r['titre']}")
    else:
        print("OAuth non configure:", ma.get("erreur"))

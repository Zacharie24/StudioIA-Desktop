import os, sys, json, requests
from pathlib import Path

def log(msg):
    print(f"[WHISPER] {msg}")

def lire_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def ecrire_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def transcrire_audio(audio_path, langue="fr"):
    import whisper
    log(f"Chargement modele Whisper tiny...")
    model = whisper.load_model("tiny")
    log(f"Transcription : {os.path.basename(audio_path)}")
    result = model.transcribe(audio_path, language=langue, fp16=False)
    return result["text"].strip()

def calculer_similarite(texte1, texte2):
    mots1 = set(texte1.lower().split())
    mots2 = set(texte2.lower().split())
    if not mots1 or not mots2:
        return 0
    return len(mots1.intersection(mots2)) / len(mots1.union(mots2))

def detecter_langue_incorrecte(texte, langue_attendue="fr"):
    mots_fr = ["le","la","les","de","du","des","et","en","un","une","pour","dans","qui","que","sur"]
    mots_en = ["the","and","for","with","this","that","have","from","they","what","when","where"]
    
    texte_lower = texte.lower()
    score_fr = sum(1 for m in mots_fr if f" {m} " in f" {texte_lower} ")
    score_en = sum(1 for m in mots_en if f" {m} " in f" {texte_lower} ")
    
    if langue_attendue == "fr" and score_en > score_fr and score_en > 3:
        return True
    if langue_attendue == "en" and score_fr > score_en and score_fr > 3:
        return True
    return False

def detecter_deraillement(texte_transcrit):
    # Detecter sequences incomprehensibles
    mots = texte_transcrit.split()
    if len(mots) < 3:
        return True
    # Detecter repetitions excessives
    if len(set(mots)) < len(mots) * 0.3:
        return True
    # Ne pas signaler comme deraillement si cest juste une intro IA
    introductions_ia = [
        "voici le chapitre",
        "voici le",
        "chapitre sur",
        "longue priere",
        "ecrit en francais",
        "ecris en francais"
    ]
    texte_lower = texte_transcrit.lower()
    nb_intro = sum(1 for intro in introductions_ia if intro in texte_lower)
    if nb_intro >= 2:
        return True  # Trop d introductions = vraiment deraille
    return False

def regenerer_segment_tts(texte_original, output_path, langue, voix_config):
    log(f"Regeneration TTS via StudioIA : {os.path.basename(output_path)}")
    try:
        import shutil, subprocess

        # Ecrire le texte dans un fichier temporaire
        txt_temp = output_path.replace(".wav", "_temp_regen.txt")
        with open(txt_temp, "w", encoding="utf-8") as f:
            f.write(texte_original)

        # Utiliser le module TTS de StudioIA directement
        venv_python = "C:\\tts-pentest\\venv\\Scripts\\python.exe"
        script = f"""
import sys
sys.path.insert(0, r"C:\\tts-pentest")
from tts_total import initialiser_projet, generer_long_texte
from pathlib import Path

with open(r"{txt_temp}", "r", encoding="utf-8") as f:
    texte = f.read()

initialiser_projet("regen_whisper")
resultat = generer_long_texte(
    texte=texte,
    moteur="{voix_config.get("moteur", "edge")}",
    voice_key="{voix_config.get("voix", "fr_FR_henri")}",
    nom_fichier="regen_output"
)
if resultat:
    import shutil
    shutil.copy(resultat, r"{output_path}")
    print("SUCCES:" + resultat)
else:
    print("ECHEC")
"""
        script_path = output_path.replace(".wav", "_regen_script.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script)

        result = subprocess.run(
            [venv_python, script_path],
            capture_output=False,
            cwd="C:\\tts-pentest"
        )

        # Nettoyage
        for f in [txt_temp, script_path]:
            if os.path.exists(f):
                os.remove(f)

        if os.path.exists(output_path):
            log(f"Segment regenere avec succes !")
            return True

    except Exception as e:
        log(f"Erreur regeneration : {e}")
    return False

def verifier_audio_projet(project_path, seuil_similarite=0.3, regenerer=True):
    data     = lire_json(os.path.join(project_path, "project.json"))
    chapitres = data.get("chapitres", [])
    langue   = data.get("langue", "fr")
    audio_dir = Path(project_path) / "audio"

    log(f"Verification audio : {data['sujet']}")
    log(f"Langue : {langue}")
    log(f"Chapitres : {len(chapitres)}")

    import whisper
    log("Chargement modele Whisper tiny...")
    model = whisper.load_model("tiny")
    log("Modele charge !")

    problemes = []
    ok_count  = 0

    for ch in chapitres:
        ch_id      = ch["id"]
        audio_path = str(audio_dir / f"{ch_id}.wav")
        txt_path   = os.path.join(project_path, ch["script_file"])

        if not os.path.exists(audio_path):
            log(f"  {ch_id} : fichier audio manquant")
            continue

        # Lire texte original
        if not os.path.exists(txt_path):
            log(f"  {ch_id} : fichier texte manquant, on saute")
            continue
        with open(txt_path, "r", encoding="utf-8") as f:
            texte_original = f.read().strip()

        # Transcrire
        log(f"  Analyse {ch_id}...")
        try:
            result = model.transcribe(audio_path, language=langue, fp16=False)
            transcription = result["text"].strip()
        except Exception as e:
            log(f"  {ch_id} ERREUR transcription : {e}")
            continue

        # Verifications
        probleme = False
        raison   = ""

        # 1. Similarite avec texte original
        sim = calculer_similarite(texte_original[:500], transcription[:500])
        if sim < seuil_similarite:
            probleme = True
            raison   = f"Similarite trop faible ({sim:.0%})"

        # 2. Langue incorrecte
        if detecter_langue_incorrecte(transcription, langue):
            probleme = True
            raison   = "Langue incorrecte detectee"

        # 3. Deraillement
        if detecter_deraillement(transcription):
            probleme = True
            raison   = "Deraillement detecte"

        if probleme:
            log(f"  {ch_id} PROBLEME : {raison}")
            log(f"    Transcription : {transcription[:100]}...")
            problemes.append({
                "ch_id":         ch_id,
                "raison":        raison,
                "audio_path":    audio_path,
                "texte_original": texte_original,
                "transcription": transcription
            })
        else:
            log(f"  {ch_id} OK ({sim:.0%} similarite)")
            ok_count += 1

    log(f"\nResultat : {ok_count}/{len(chapitres)} OK, {len(problemes)} problemes")

    if problemes and regenerer:
        print("\n  Chapitres problematiques :")
        for p in problemes:
            print(f"  - {p['ch_id']} : {p['raison']}")

        reponse = input("\n  Regenerer ces segments ? (o/n) : ").strip().lower()
        if reponse == "o":
            # Config voix par defaut
            voix_config = {"moteur": "edge", "voix": "fr_FR_henri"}
            for p in problemes:
                log(f"Regeneration {p['ch_id']}...")
                ok = regenerer_segment_tts(
                    p["texte_original"],
                    p["audio_path"],
                    langue,
                    voix_config
                )
                if ok:
                    log(f"  {p['ch_id']} regenere avec succes")
                else:
                    log(f"  {p['ch_id']} echec regeneration")

    return problemes

def main():
    project_path = sys.argv[1] if len(sys.argv) > 1 else "C:\\StudioIA\\projects\\test_rapide"
    verifier_audio_projet(project_path)

if __name__ == "__main__":
    main()
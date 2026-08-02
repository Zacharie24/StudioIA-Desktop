import sys
import threading

def choisir_avec_timeout(options_dict, defaut, timeout=10, message="Votre choix"):
    """
    Affiche un menu et attend le choix.
    Si pas de reponse apres timeout secondes, retourne defaut.
    Gere le cas ou stdin n'est pas disponible (GUI/PowerShell).
    """
    resultat = [defaut]
    choix_fait = [False]

    def lire_input():
        try:
            # Verifier si stdin est disponible
            import sys
            if sys.stdin.isatty():
                choix = input(f"\n  {message} [{defaut}] (auto dans {timeout}s) : ").strip()
                if choix in options_dict:
                    resultat[0] = choix
                elif choix == "":
                    resultat[0] = defaut
            else:
                # stdin non disponible - utiliser defaut silencieusement
                resultat[0] = defaut
            choix_fait[0] = True
        except Exception as e:
            # En cas d'erreur, utiliser defaut
            resultat[0] = defaut
            choix_fait[0] = True

    thread = threading.Thread(target=lire_input, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    if not choix_fait[0]:
        print(f"\n  Timeout — choix automatique : {defaut}")

    return resultat[0]
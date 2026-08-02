# -*- coding: utf-8 -*-
"""Test de verification : phase_video sur un projet existant (debug audio + video)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.automation.pipeline import PipelineAutomation

p = PipelineAutomation()
p.resultat["projet_creer"] = "contenu_pri_res_chr_tiennes_du_01_08_202"
p.phase_video("contenu_pri_res_chr_tiennes_du_01_08_202")
print("FINAL fichier_video:", p.resultat.get("fichier_video"))
print("FINAL phase video:", p.resultat.get("phases", {}).get("video"))

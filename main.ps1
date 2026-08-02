param(
    [string]$ProjectPath = ""
)

$config = Get-Content "C:\\StudioIA-Next\config.json" | ConvertFrom-Json

function Log($msg, $color="Cyan") {
    $date = Get-Date -Format "HH:mm:ss"
    Write-Host "[$date] $msg" -ForegroundColor $color
    # Use default log path if not configured
    $log_dir = if ($config.logs_path) { $config.logs_path } else { "C:\\StudioIA-Next\logs" }
    $log_file = Join-Path $log_dir "$(Get-Date -Format 'yyyy-MM-dd').log"
    # Create directory if needed
    if (-not (Test-Path $log_dir)) { New-Item -ItemType Directory -Path $log_dir | Out-Null }
    Add-Content $log_file "[$date] $msg"
}

function Menu($titre, $options) {
    Write-Host ""
    Write-Host "  ================================" -ForegroundColor Yellow
    Write-Host "  $titre" -ForegroundColor Yellow
    Write-Host "  ================================" -ForegroundColor Yellow
    foreach ($k in $options.Keys) {
        Write-Host "  [$k] $($options[$k])" -ForegroundColor White
    }
    return (Read-Host "  Votre choix").Trim()
}

function Afficher_Banniere {
    Clear-Host
    Write-Host ""
    Write-Host "  ========================================" -ForegroundColor Cyan
    Write-Host "        STUDIO IA — AUTOMATION COMPLETE   " -ForegroundColor Cyan
    Write-Host "  ========================================" -ForegroundColor Cyan
    Write-Host "  Mode : $($config.mode.ToUpper())" -ForegroundColor Green
    Write-Host "  ========================================" -ForegroundColor Cyan
    Write-Host ""
}

# ============================================================
# MENU PRINCIPAL
# ============================================================
function Menu_Principal {
    Afficher_Banniere
    $choix = Menu "MENU PRINCIPAL" ([ordered]@{
        "1" = "Nouveau projet video"
        "2" = "Continuer un projet existant"
        "3" = "Parametres"
        "4" = "Diagnostic systeme"
        "6" = "Gestionnaire assets (polices, musiques, images)"
        "7" = "Generateur thumbnail standalone"
        "8" = "Creer projet Shotcut pour un projet existant"
        "9" = "Renommer tous les projets avec titres lisibles"
        "S" = "Generateur YouTube Shorts"
        "10" = "Verifier qualite audio (Whisper)"
        "0" = "Quitter"
    })
    return $choix
}

# ============================================================
# PARAMETRES
# ============================================================
function Menu_Parametres {
    Afficher_Banniere
    $providers = $config.providers
    $provider_plan = $providers.plan
    $provider_chapitre = $providers.chapitre
    $web_research = if ($config.web_research) { "ON" } else { "OFF" }

    $choix = Menu "PARAMETRES" ([ordered]@{
        "1" = "Changer mode : $($config.mode.ToUpper())"
        "2" = "Volume musique : $($config.music_volume)"
        "3" = "Resolution video : $($config.video_resolution)"
        "4" = "Modele IA : $($config.ia_model)"
        "5" = "Provider PLAN : $provider_plan"
        "6" = "Provider CHAPITRE : $provider_chapitre"
        "7" = "Recherche web : $web_research"
        "8" = "Qualite video et audio"
        "0" = "Retour"
    })

    switch ($choix) {
        "1" {
            if ($config.mode -eq "local") {
                $cle = Read-Host "  Entrez votre cle RunPod API"
                $config.mode = "cloud"
                $config.cloud.api_key = $cle
                Log "Mode passe en CLOUD" "Green"
            } else {
                $config.mode = "local"
                Log "Mode passe en LOCAL" "Green"
            }
            $config | ConvertTo-Json -Depth 10 | Out-File "C:\\StudioIA-Next\config.json" -Encoding UTF8
        }
        "2" {
            $vol = Read-Host "  Volume musique (0.0 a 1.0) [$($config.music_volume)]"
            if ($vol) { $config.music_volume = [float]$vol }
            $config | ConvertTo-Json -Depth 10 | Out-File "C:\\StudioIA-Next\config.json" -Encoding UTF8
        }
        "3" {
            $res = Menu "RESOLUTION" ([ordered]@{
                "1" = "1920x1080 (Full HD)"
                "2" = "1280x720 (HD)"
                "3" = "3840x2160 (4K)"
            })
            switch ($res) {
                "1" { $config.video_resolution = "1920x1080" }
                "2" { $config.video_resolution = "1280x720" }
                "3" { $config.video_resolution = "3840x2160" }
            }
            $config | ConvertTo-Json -Depth 10 | Out-File "C:\\StudioIA-Next\config.json" -Encoding UTF8
        }
        "5" {
            $provider_plan = Menu "PROVIDER POUR LE PLAN" ([ordered]@{
                "1" = "local (Ollama)"
                "2" = "huggingface (IA en ligne)"
                "3" = "online (Tout en ligne avec recherche)"
            })
            switch ($provider_plan) {
                "1" { $config.providers.plan = "local" }
                "2" { $config.providers.plan = "huggingface" }
                "3" { $config.providers.plan = "online" }
            }
            $config | ConvertTo-Json -Depth 10 | Out-File "C:\\StudioIA-Next\config.json" -Encoding UTF8
            Log "Provider PLAN mis a jour" "Green"
        }
        "6" {
            $provider_chapitre = Menu "PROVIDER POUR LES CHAPITRES" ([ordered]@{
                "1" = "local (Ollama)"
                "2" = "huggingface (IA en ligne)"
                "3" = "online (Tout en ligne avec recherche)"
            })
            switch ($provider_chapitre) {
                "1" { $config.providers.chapitre = "local" }
                "2" { $config.providers.chapitre = "huggingface" }
                "3" { $config.providers.chapitre = "online" }
            }
            $config | ConvertTo-Json -Depth 10 | Out-File "C:\\StudioIA-Next\config.json" -Encoding UTF8
            Log "Provider CHAPITRE mis a jour" "Green"
        }
        "7" {
            if ($config.web_research) {
                $config.web_research = $false
                Log "Recherche web DESACTIVEE" "Green"
            } else {
                $config.web_research = $true
                Log "Recherche web ACTIVEE" "Green"
            }
            $config | ConvertTo-Json -Depth 10 | Out-File "C:\\StudioIA-Next\config.json" -Encoding UTF8
        }
        "8" {
            Write-Host "  QUALITE VIDEO :" -ForegroundColor Yellow
            Write-Host "  [1] Rapide  (CRF 28, sans zoompan)" -ForegroundColor White
            Write-Host "  [2] Normal  (CRF 23, zoompan leger)" -ForegroundColor White
            Write-Host "  [3] Qualite (CRF 18, zoompan complet)" -ForegroundColor White
            $q = Read-Host "  Qualite [1]"
            if (-not $q) { $q = "1" }
            Write-Host "  FORMAT AUDIO :" -ForegroundColor Yellow
            Write-Host "  [1] MP3 128k  [2] AAC 192k  [3] WAV" -ForegroundColor White
            $a = Read-Host "  Audio [1]"
            if (-not $a) { $a = "1" }
            Write-Host "  DENOISER AUDIO (XTTS) :" -ForegroundColor Yellow
            Write-Host "  [1] OFF" -ForegroundColor White
            Write-Host "  [2] Light  (denoiser leger)" -ForegroundColor White
            Write-Host "  [3] Medium (denoiser standard)" -ForegroundColor White
            Write-Host "  [4] Strong (denoiser agressif)" -ForegroundColor White
            $d = Read-Host "  Denoiser [3]"
            if (-not $d) { $d = "3" }
            switch ($d) {
                "1" { $config.denoiser_enabled = $false }
                "2" { $config.denoiser_enabled = $true; $config.denoiser_strength = "light" }
                "3" { $config.denoiser_enabled = $true; $config.denoiser_strength = "medium" }
                "4" { $config.denoiser_enabled = $true; $config.denoiser_strength = "strong" }
            }
            Write-Host "  GATE AUDIO :" -ForegroundColor Yellow
            Write-Host "  [1] OFF" -ForegroundColor White
            Write-Host "  [2] ON (coupe silences)" -ForegroundColor White
            $g = Read-Host "  Gate [2]"
            if (-not $g) { $g = "2" }
            $config.gate_enabled = ($g -ne "1")

            if ($config.gate_enabled) {
                $gs = Read-Host "  Sensibilite gate (0.1-1.0) [$($config.gate_sensitivity)]"
                if ($gs) { $config.gate_sensitivity = [float]$gs }
            }

            Write-Host "  VERIFICATION WHISPER :" -ForegroundColor Yellow
            Write-Host "  [1] OFF" -ForegroundColor White
            Write-Host "  [2] ON (verifie les paroles)" -ForegroundColor White
            $w = Read-Host "  Verification [2]"
            if (-not $w) { $w = "2" }
            $config.verification_enabled = ($w -ne "1")

            if ($config.verification_enabled) {
                Write-Host "  Regeneration auto :"
                Write-Host "  [1] OFF (signaler seulement)"
                Write-Host "  [2] ON (regenere automatiquement)"
                $r = Read-Host "  Regeneration [2]"
                if (-not $r) { $r = "2" }
                $config.verification_auto_regenerate = ($r -ne "1")
            }
            $z = if ($q -eq "1") {"0"} elseif ($q -eq "2") {"1"} else {"2"}
            $vcfg = @{qualite=$q; audio_fmt=$a; zoompan=$z}
            $vcfg | ConvertTo-Json | Out-File "C:\\StudioIA-Next\config_video.json" -Encoding UTF8
            $config | ConvertTo-Json -Depth 10 | Out-File "C:\\StudioIA-Next\config.json" -Encoding UTF8
            Log "Options qualite et denoiser sauvegardees" "Green"
        }
        "4" {
            $modeles = @("mistral","llama3","qwen2","gemma2")
            Write-Host "  Modeles disponibles :"
            for ($i=0; $i -lt $modeles.Count; $i++) {
                Write-Host "  [$($i+1)] $($modeles[$i])"
            }
            $m = Read-Host "  Choix"
            try { $config.ia_model = $modeles[[int]$m-1] } catch {}
            $config | ConvertTo-Json -Depth 10 | Out-File "C:\\StudioIA-Next\config.json" -Encoding UTF8
        }
    }
}

# ============================================================
# CONTINUER PROJET
# ============================================================
function Continuer_Projet {
    Afficher_Banniere

    # Lire tous les projets (video et shorts)
    $projets = Get-ChildItem $config.projects_path -Directory | Sort-Object LastWriteTime -Descending

    if ($projets.Count -eq 0) {
        Log "Aucun projet trouve." "Red"
        Read-Host "  Entree pour continuer"
        return
    }

    Write-Host "  Projets disponibles :" -ForegroundColor Yellow
    $liste_paths = @()
    $liste_shorts = @()
    $liste_types = @()

    foreach ($p in $projets) {
        $pjson = "$($p.FullName)\project.json"
        $planjson = "$($p.FullName)\plan.json"

        # Detecter si c'est un projet video ou shorts
        $est_shorts = $p.Name.StartsWith("shorts_")

        if (Test-Path $pjson) {
            $d = Get-Content $pjson | ConvertFrom-Json
            $liste_paths += $p.FullName
            $liste_types += "video"
            $idx = $liste_paths.Count
            $statut_color = if ($d.statut -eq "termine") { "Green" } else { "Yellow" }
            Write-Host "  [$idx] [V] $($d.sujet) — $($d.statut)" -ForegroundColor $statut_color
        } elseif (Test-Path $planjson) {
            # C'est un projet Shorts
            $d = Get-Content $planjson | ConvertFrom-Json
            $liste_paths += $p.FullName
            $liste_types += "shorts"
            $idx = $liste_paths.Count
            $statut_color = if ($d.statut -eq "termine") { "Green" } else { "Yellow" }
            Write-Host "  [$idx] [S] $($d.sujet) — $($d.statut)" -ForegroundColor $statut_color
        }
    }

    $choix = Read-Host "  Votre choix"
    try {
        $idx = [int]$choix - 1
        $path = $liste_paths[$idx]
        $type = $liste_types[$idx]
        if ($type -eq "shorts") {
            Lancer_Pipeline_Short $path
        } else {
            Lancer_Pipeline $path
        }
    } catch {
        Log "Choix invalide." "Red"
    }
}

# ============================================================
# PIPELINE COMPLET
# ============================================================
function Lancer_Pipeline($project_path) {
    $pjson = "$project_path\project.json"
    $data = Get-Content $pjson | ConvertFrom-Json

    Afficher_Banniere
    Log "PROJET : $($data.sujet)" "Green"
    Log "ID     : $($data.id)" "Cyan"
    Write-Host ""

    # Options logo
    $logo_choix = Menu "LOGO DANS LA VIDEO" ([ordered]@{
        "1" = "Oui — choisir un logo"
        "2" = "Oui — logo aleatoire"
        "3" = "Non — sans logo"
    })

    $logo_path = ""
    if ($logo_choix -in "1","2") {
        $logos = Get-ChildItem "C:\\StudioIA-Next\assets\logos" -Filter "*.png" -ErrorAction SilentlyContinue
        if ($logos.Count -gt 0) {
            if ($logo_choix -eq "2") {
                $logo_path = ($logos | Get-Random).FullName
                Log "Logo aleatoire : $(Split-Path $logo_path -Leaf)" "Green"
            } else {
                Write-Host "  Logos disponibles :" -ForegroundColor Yellow
                for ($i=0; $i -lt $logos.Count; $i++) {
                    Write-Host "  [$($i+1)] $($logos[$i].Name)"
                }
                $lc = Read-Host "  Choix"
                try { $logo_path = $logos[[int]$lc-1].FullName } catch {}
            }
        } else {
            Log "Aucun logo trouve dans assets\logos\" "Yellow"
        }
    }

    # Sauvegarder choix logo dans project.json
    $data | Add-Member -NotePropertyName "logo_path" -NotePropertyValue $logo_path -Force
    $data | ConvertTo-Json -Depth 10 | Out-File $pjson -Encoding UTF8

    # Lancer etapes selon statut
    Write-Host ""
    Log "=== DEMARRAGE PIPELINE ===" "Green"

    # SCRIPT
    if ($data.etapes.script -ne "termine") {
        Log "ETAPE 1/5 : Generation script..." "Yellow"
        python "C:\\StudioIA-Next\modules\brain\generate_script.py" $project_path
        Log "Script termine." "Green"
    } else {
        Log "ETAPE 1/5 : Script deja termine." "Green"
    }

    # AUDIO
    if ($data.etapes.audio -ne "termine") {
        Log "ETAPE 2/6 : Generation audio TTS..." "Yellow"
        python "C:\\StudioIA-Next\modules\tts\run_tts.py" $project_path
        Log "Audio termine." "Green"
    } else {
        Log "ETAPE 2/6 : Audio deja termine." "Green"
    }

    # MUSIQUE DE FOND (ComposIA)
    if ($data.etapes.musique_fond -ne "termine") {
        Log "ETAPE 3/6 : Generation musique de fond (ComposIA)..." "Yellow"
        python "C:\\StudioIA-Next\modules\audio\composia_config.py" $project_path
        Log "Musique termine." "Green"
    } else {
        Log "ETAPE 3/6 : Musique deja termine." "Green"
    }

    # IMAGES
    if ($data.etapes.images -ne "termine") {
        Log "ETAPE 3/5 : Telechargement images..." "Yellow"
        python "C:\\StudioIA-Next\modules\images\library_manager.py" $project_path
        Log "Images terminees." "Green"
    } else {
        Log "ETAPE 3/5 : Images deja terminees." "Green"
    }

    # VIDEO
    if ($data.etapes.video -ne "termine") {
        Log "ETAPE 5/6 : Montage video..." "Yellow"
        python "C:\\StudioIA-Next\modules\video\build_video.py" $project_path
        Log "Video terminee." "Green"
    } else {
        Log "ETAPE 5/6 : Video deja terminee." "Green"
    }

    # THUMBNAIL
    if ($data.etapes.thumbnail -ne "termine") {
        Log "ETAPE 6/6 : Generation thumbnail..." "Yellow"
        python "C:\\StudioIA-Next\modules\thumbnail\thumbnail_builder.py" $project_path
        Log "Thumbnail terminee." "Green"
    } else {
        Log "ETAPE 6/6 : Thumbnail deja terminee." "Green"
    }

    # CREATION PROJET SHOTCUT
    Log "Creation projet Shotcut..." "Yellow"
    python "C:\\StudioIA-Next\modules\video\gen_shotcut.py" $project_path
    Log "Projet Shotcut genere." "Green"

    # Marquer projet termine
    $data = Get-Content $pjson | ConvertFrom-Json
    $data.statut = "termine"
    $data | ConvertTo-Json -Depth 10 | Out-File $pjson -Encoding UTF8

    Write-Host ""
    Log "========================================" "Green"
    Log "  PROJET TERMINE !" "Green"
    Log "  Dossier : $project_path\export\" "Green"
    Log "========================================" "Green"
    Write-Host ""

    # Ouvrir dossier export
    $ouvrir = Read-Host "  Ouvrir le dossier export ? (o/n)"
    if ($ouvrir -eq "o") {
        Start-Process "explorer.exe" "$project_path\export"
    }

    Read-Host "  Entree pour continuer"
}

# ============================================================
# CONTINUER PROJET SHORTS
# ============================================================
function Lancer_Pipeline_Short($project_path) {
    $planjson = "$project_path\plan.json"
    $plan = Get-Content $planjson | ConvertFrom-Json

    Afficher_Banniere
    Log "SHORTS : $($plan.sujet)" "Green"
    Log "ID     : $($plan.id)" "Cyan"
    Write-Host ""

    # Lancer etapes selon statut
    Write-Host ""
    Log "=== DEMARRAGE PIPELINE SHORTS ===" "Green"

    # GENERER SHORTS (gere la reprise automatiquement)
    Log "ETAPE : Generation des Shorts..." "Yellow"
    python "C:\\StudioIA-Next\modules\shorts\generate_shorts.py" $project_path
    Log "Shorts termines." "Green"

    # CREATION PROJET SHOTCUT
    Log "Creation projets Shotcut..." "Yellow"
    python "C:\\StudioIA-Next\modules\video\gen_shotcut.py" $project_path
    Log "Projets Shotcut genes." "Green"

    # Marquer projet termine
    $plan.statut = "termine"
    $plan | ConvertTo-Json -Depth 10 | Out-File $planjson -Encoding UTF8

    Write-Host ""
    Log "========================================" "Green"
    Log "  SHORTS TERMINES !" "Green"
    Log "  Dossier : $project_path\export\shorts" "Green"
    Log "========================================" "Green"
    Write-Host ""

    # Ouvrir dossier export
    $ouvrir = Read-Host "  Ouvrir le dossier export ? (o/n)"
    if ($ouvrir -eq "o") {
        Start-Process "explorer.exe" "$project_path\export\shorts"
    }

    Read-Host "  Entree pour continuer"
}

# ============================================================
# NOUVEAU PROJET
# ============================================================
function Nouveau_Projet {
    Afficher_Banniere

    $sujet = Read-Host "  Sujet de la video"
    if (-not $sujet) { return }

    $type_choix = Menu "TYPE DE CONTENU" ([ordered]@{
        "1" = "Priere chretienne (Francais)"
        "2" = "Histoire / Storytelling (Francais)"
        "3" = "Storytelling (Anglais)"
        "4" = "Autre contenu (Francais)"
        "5" = "Autre contenu (Anglais)"
    })

    $langue = "fr"
    $type_contenu = "priere"
    switch ($type_choix) {
        "1" { $langue = "fr"; $type_contenu = "priere" }
        "2" { $langue = "fr"; $type_contenu = "storytelling" }
        "3" { $langue = "en"; $type_contenu = "storytelling" }
        "4" { $langue = "fr"; $type_contenu = "general" }
        "5" { $langue = "en"; $type_contenu = "general" }
    }

    $id = "video_" + (Get-Date -Format "yyyyMMdd_HHmmss")
    $project_path = "$($config.projects_path)\$id"

    # Créer la structure de dossiers
    $sous_dossiers = @(
        "chapters","audio","images\backgrounds","images\overlays","thumbnail",
        "export\video","export\short","export\shorts"
    )
    foreach ($d in $sous_dossiers) {
        New-Item -ItemType Directory -Force -Path "$project_path\$d" | Out-Null
    }

    # Configurer la musique de fond ComposIA
    Log "Configuration de la musique de fond..." "Yellow"
    python "C:\\StudioIA-Next\modules\audio\composia_config.py" $project_path

    $project = @{
        id = $id
        sujet = $sujet
        langue = $langue
        type_contenu = $type_contenu
        statut = "en_cours"
        etapes = @{
            script     = "en_attente"
            chapitres  = "en_attente"
            audio      = "en_attente"
            musique_fond = "en_attente"
            images     = "en_attente"
            video      = "en_attente"
            thumbnail  = "en_attente"
            export     = "en_attente"
        }
        meta = @{ titre_youtube=""; description=""; tags=@() }
        chapitres = @()
        config_locale = @{
            voix = $config.tts_voice
            resolution = $config.video_resolution
        }
    }

    $project | ConvertTo-Json -Depth 10 | Out-File "$project_path\project.json" -Encoding UTF8
    Log "Projet cree : $id" "Green"

    Lancer_Pipeline $project_path
}

# ============================================================
# BOUCLE PRINCIPALE
# ============================================================
while ($true) {
    $choix = Menu_Principal

    switch ($choix) {
        "1" { Nouveau_Projet }
        "2" { Continuer_Projet }
        "3" { Menu_Parametres }
        "4" {
            powershell -ExecutionPolicy Bypass -File "C:\\StudioIA-Next\doctor.ps1"
            Read-Host "  Entree pour continuer"
        }
        "6" {
            Set-Location "C:\\StudioIA-Next"
            python "C:\\StudioIA-Next\modules\assets_manager.py"
            Read-Host "  Entree pour continuer"
        }
        "7" {
            Set-Location "C:\\StudioIA-Next"
            python "C:\\StudioIA-Next\modules\thumbnail\thumbnail_standalone.py"
            Read-Host "  Entree pour continuer"
        }
        "8" {
            Afficher_Banniere
            $projets = Get-ChildItem $config.projects_path -Directory | Sort-Object LastWriteTime -Descending
            $liste = @()
            Write-Host "  Projets disponibles :" -ForegroundColor Yellow
            foreach ($p in $projets) {
                if (Test-Path "$($p.FullName)\project.json") {
                    $d = Get-Content "$($p.FullName)\project.json" | ConvertFrom-Json
                    $liste += $p.FullName
                    Write-Host "  [$($liste.Count)] $($d.sujet) — $($p.Name)" -ForegroundColor White
                }
            }
            $choix2 = Read-Host "  Votre choix"
            try {
                $path = $liste[[int]$choix2-1]
                Set-Location "C:\\StudioIA-Next"
                python "C:\\StudioIA-Next\modules\video\gen_shotcut.py" $path
                Log "Projet Shotcut cree !" "Green"
            } catch { Log "Choix invalide" "Red" }
            Read-Host "  Entree pour continuer"
        }
        "S" {
            Set-Location "C:\\StudioIA-Next"
            python "C:\\StudioIA-Next\modules\shorts\generate_shorts.py"
            Read-Host "  Entree pour continuer"
        }
        "9" {
            Set-Location "C:\\StudioIA-Next"
            Log "Renommage des projets en cours..." "Yellow"
            python "C:\\StudioIA-Next\modules\brain\rename_projects.py"
            Log "Renommage termine !" "Green"
            Read-Host "  Entree pour continuer"
        }
        "10" {
            Afficher_Banniere
            $projets = Get-ChildItem $config.projects_path -Directory | Sort-Object LastWriteTime -Descending
            $liste = @()
            Write-Host "  Choisir un projet a verifier :" -ForegroundColor Yellow
            foreach ($p in $projets) {
                if (Test-Path "$($p.FullName)\project.json") {
                    $d = Get-Content "$($p.FullName)\project.json" | ConvertFrom-Json
                    $liste += $p.FullName
                    Write-Host "  [$($liste.Count)] $($d.sujet) — $($p.Name)" -ForegroundColor White
                }
            }
            $choix2 = Read-Host "  Votre choix"
            try {
                $path = $liste[[int]$choix2-1]
                Set-Location "C:\\StudioIA-Next"
                python "C:\\StudioIA-Next\modules\tts\whisper_check.py" $path
            } catch { Log "Choix invalide" "Red" }
            Read-Host "  Entree pour continuer"
        }
        "0" {
            Write-Host "  Au revoir !" -ForegroundColor Green
            exit
        }
    }
}
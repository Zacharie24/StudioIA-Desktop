param(
    [string]$ProjectPath = ""
)

$config = Get-Content "C:\\StudioIA-Next\config.json" | ConvertFrom-Json

function Log($msg, $color="Cyan") {
    $date = Get-Date -Format "HH:mm:ss"
    Write-Host "[$date] $msg" -ForegroundColor $color
}

function Verifier($label, $test) {
    if ($test) {
        Log "  [OK] $label" "Green"
        return $true
    } else {
        Log "  [MANQUANT] $label" "Red"
        return $false
    }
}

Log "============================================" "Yellow"
Log "   DIAGNOSTIC StudioIA" "Yellow"
Log "============================================" "Yellow"

# 1. Verifier outils
Log "--- OUTILS ---" "White"
Verifier "Ollama" (Get-Command ollama -ErrorAction SilentlyContinue)
Verifier "Python" (Get-Command python -ErrorAction SilentlyContinue)
Verifier "Dossier projets" (Test-Path $config.projects_path)
Verifier "Dossier assets" (Test-Path $config.assets_path)

# Verifier FFmpeg seulement si le chemin est configure
if ($config.ffmpeg_path -and (Test-Path $config.ffmpeg_path)) {
    # Verifier que ffmpeg fonctionne vraiment
    try {
        $ffmpegTest = Start-Process -FilePath $config.ffmpeg_path -ArgumentList "-version" -PassThru -NoNewWindow -Wait
        if ($ffmpegTest.ExitCode -eq 0) {
            Verifier "FFmpeg (functionnel)" $true
        } else {
            Verifier "FFmpeg (erreur)" $false
        }
    } catch {
        Verifier "FFmpeg (inaccessible)" $false
    }
} elseif ($config.ffmpeg_path) {
    Log "  [MANQUANT] FFmpeg - fichier absent: $($config.ffmpeg_path)" "Red"
} else {
    Log "  [ATTENTION] FFmpeg - chemin non configure dans config.json" "Yellow"
}

# 2. Verifier projet en cours
Log "--- PROJETS EN COURS ---" "White"

$projets = Get-ChildItem $config.projects_path -Directory | Sort-Object LastWriteTime -Descending

if ($projets.Count -eq 0) {
    Log "  Aucun projet trouve." "Gray"
} else {
    $projets_en_cours = @()

    foreach ($p in $projets) {
        $pjson = "$($p.FullName)\project.json"
        $planjson = "$($p.FullName)\plan.json"

        # Detecter si c'est un projet video ou shorts
        $est_shorts = $p.Name.StartsWith("shorts_")

        if (Test-Path $pjson) {
            $pdata = Get-Content $pjson | ConvertFrom-Json
            $projets_en_cours += @{type="video"; path=$p.FullName; data=$pdata}

            if ($pdata.statut -eq "en_cours") {
                Log "  [VIDEO] PROJET INCOMPLET : $($pdata.id)" "Yellow"
                Log "  Sujet : $($pdata.sujet)" "White"
                Log "  Etapes:" "White"
                foreach ($etape in $pdata.etapes.PSObject.Properties) {
                    $couleur = if ($etape.Value -eq "termine") { "Green" } elseif ($etape.Value -eq "en_cours") { "Yellow" } else { "Gray" }
                    Log "    - $($etape.Name) : $($etape.Value)" $couleur
                }
                Log "  Dossier : $($p.FullName)" "Cyan"
                Write-Host ""

                # Proposer de reprendre sans bloquer le diagnostic
                Log "  Option: appuyez sur 'R' pour reprendre, 'S' pour ignorer" "White"
            } elseif ($pdata.statut -eq "termine") {
                Log "  [VIDEO] [TERMINE] $($pdata.id) - $($pdata.sujet)" "Green"
            }
        } elseif (Test-Path $planjson) {
            $pdata = Get-Content $planjson | ConvertFrom-Json
            $projets_en_cours += @{type="shorts"; path=$p.FullName; data=$pdata}

            if ($pdata.statut -eq "en_cours") {
                Log "  [SHORTS] PROJET INCOMPLET : $($pdata.id)" "Yellow"
                Log "  Sujet : $($pdata.sujet)" "White"
                Log "  Etapes:" "White"
                foreach ($etape in $pdata.etapes.PSObject.Properties) {
                    $couleur = if ($etape.Value -eq "termine") { "Green" } elseif ($etape.Value -eq "en_cours") { "Yellow" } else { "Gray" }
                    Log "    - $($etape.Name) : $($etape.Value)" $couleur
                }
                Log "  Dossier : $($p.FullName)" "Cyan"
                Write-Host ""
            } elseif ($pdata.statut -eq "termine") {
                Log "  [SHORTS] [TERMINE] $($pdata.id) - $($pdata.sujet)" "Green"
            }
        }
    }

    # Si des projets en cours existent, proposer la reprise
    if ($projets_en_cours.Count -gt 0) {
        Log "============================================" "Yellow"
        Log "  GESTION DES PROJETS" "Yellow"
        Log "============================================" "Yellow"

        for ($i=0; $i -lt $projets_en_cours.Count; $i++) {
            $p = $projets_en_cours[$i]
            $prefix = if ($p.type -eq "shorts") { "S" } else { "V" }
            Log "  [$($i+1)] [$prefix] $($p.data.sujet)" "White"
        }

        $rep = Read-Host "Entrer le numero pour reprendre, ou 'Q' pour quitter"

        if ($rep -eq "Q" -or $rep -eq "q") {
            Log "Diagnostic termine." "Cyan"
        } else {
            try {
                $idx = [int]$rep - 1
                if ($idx -ge 0 -and $idx -lt $projets_en_cours.Count) {
                    $selected = $projets_en_cours[$idx]
                    Log "Reprise du projet $($selected.data.id)..." "Green"
                    powershell -ExecutionPolicy Bypass -File "C:\\StudioIA-Next\main.ps1" -ProjectPath $selected.path
                } else {
                    Log "Choix invalide." "Red"
                }
            } catch {
                Log "Erreur: $_" "Red"
            }
        }
    }
}

Log "============================================" "Yellow"
Log "   FIN DU DIAGNOSTIC" "Yellow"
Log "============================================" "Yellow"
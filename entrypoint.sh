#!/bin/bash
# ================================================================
# RapidBenthos — entrypoint.sh 
# ================================================================

METASHAPE_KEY="${METASHAPE_LICENSE_KEY:-}"
METASHAPE_BIN="metashape"
ACTIVATED=0
SKIP_MODE=0
CHILD_PID=""

# ================================================================
# CLEANUP — désactivation garantie dans tous les cas
# ================================================================
cleanup() {
    echo ""
    echo "=================================================="
    echo "Arrêt détecté — sécurisation de la licence..."
    echo "=================================================="

    # Si le pipeline tourne encore → l'arrêter proprement
    if [ -n "$CHILD_PID" ] && kill -0 "$CHILD_PID" 2>/dev/null; then
        echo "Arrêt du pipeline en cours..."
        kill -TERM "$CHILD_PID" 2>/dev/null

        # Attendre max 30s que Python se termine proprement
        local WAIT=0
        while kill -0 "$CHILD_PID" 2>/dev/null && [ $WAIT -lt 30 ]; do
            sleep 1
            WAIT=$((WAIT + 1))
        done

        # Si toujours vivant après 30s → forcer
        if kill -0 "$CHILD_PID" 2>/dev/null; then
            echo "Force arrêt pipeline..."
            kill -KILL "$CHILD_PID" 2>/dev/null
        fi
        CHILD_PID=""
    fi

    # Désactiver Metashape
    if [ "$ACTIVATED" = "1" ]; then
        echo ""
        echo "Désactivation Metashape licence..."

        if [ "$SKIP_MODE" = "1" ]; then
            echo "[MODE TEST] Désactivation simulée"
            echo " Licence désactivée (simulée) — slot libéré"
        else
            # Tentative 1
            if $METASHAPE_BIN --deactivate; then
                echo " Licence désactivée — slot libéré"
            else
                echo "⚠️  Tentative 1 échouée — nouvelle tentative dans 5s..."
                sleep 5
                # Tentative 2
                if $METASHAPE_BIN --deactivate; then
                    echo " Licence désactivée (tentative 2) — slot libéré"
                else
                    echo " Désactivation échouée après 2 tentatives"
                    echo "   → Contacter support@agisoft.com"
                    echo "   → Clé : ${METASHAPE_KEY:0:5}-****-****-****-*****"
                fi
            fi
        fi
        ACTIVATED=0
    fi

    echo "=================================================="
    echo "Container terminé proprement."
    echo "=================================================="
}

# Piège sur tous les signaux
trap cleanup EXIT INT TERM

# ================================================================
# VÉRIFICATION VARIABLES
# ================================================================
if [ -z "$METASHAPE_KEY" ]; then
    echo " METASHAPE_LICENSE_KEY vide dans .env"
    echo "   → Vraie clé  : METASHAPE_LICENSE_KEY=XXXXX-XXXXX-..."
    echo "   → Mode test  : METASHAPE_LICENSE_KEY=SKIP"
    exit 1
fi

# ================================================================
# ACTIVATION
# ================================================================
echo "=================================================="
echo "Activation Metashape licence..."
echo "=================================================="

if [ "$METASHAPE_KEY" = "SKIP" ]; then
    # ── Mode test ──────────────────────────────────────────────
    SKIP_MODE=1
    ACTIVATED=1
    echo "  [MODE TEST] Activation simulée — aucun appel réseau"
    echo "   → L'étape Metashape sera ignorée dans le pipeline"

else
    # ── Activation réelle ──────────────────────────────────────
    echo "   Clé : ${METASHAPE_KEY:0:5}-****-****-****-*****"

    # Tentative 1
    if $METASHAPE_BIN --activate "$METASHAPE_KEY"; then
        ACTIVATED=1
        echo "✅ Licence activée"
        export AGISOFT_LICENSE_PATH="/var/tmp/agisoft/licensing/licenses"

    else
        echo "  Tentative 1 échouée — nouvelle tentative dans 10s..."
        sleep 10

        # Tentative 2
        if $METASHAPE_BIN --activate "$METASHAPE_KEY"; then
            ACTIVATED=1
            echo " Licence activée (tentative 2)"
            export AGISOFT_LICENSE_PATH="/var/tmp/agisoft/licensing/licenses"
        else
            echo " Activation échouée après 2 tentatives"
            echo "   → Vérifier la clé ou contacter support@agisoft.com"
            exit 1
        fi
    fi
fi

# ================================================================
# LANCEMENT DU PIPELINE
# ================================================================
echo ""
echo "=================================================="
echo "Lancement pipeline..."
echo "=================================================="

# Lancer en arrière-plan → bash reste vivant → trap actif
"$@" &
CHILD_PID=$!

# Attendre la fin et récupérer le code de retour
wait "$CHILD_PID"
EXIT_CODE=$?
CHILD_PID=""

# cleanup() appelé automatiquement par trap EXIT
exit $EXIT_CODE
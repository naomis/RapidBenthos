#!/bin/bash
# ==============================================================================
# RapidBenthos Pipeline — License Manager
# Author  : Mohamed Bouchalkha — CREOCEAN
# Date    : 2026
# Purpose : Automated Metashape license activation/deactivation lifecycle
#           ensuring license slot is always released on container exit
# ==============================================================================

METASHAPE_KEY="${METASHAPE_LICENSE_KEY:-}"
METASHAPE_BIN="metashape"
METASHAPE_LIC="/var/tmp/agisoft/licensing/licenses/metashape-pro.lic"
ACTIVATED=0
SKIP_MODE=0
CHILD_PID=""

# ------------------------------------------------------------------------------
# verify_deactivation
# Secondary control level : checks that the .lic file is gone after deactivation
# ------------------------------------------------------------------------------
verify_deactivation() {
    if [ -f "$METASHAPE_LIC" ]; then
        echo "WARNING: .lic file still present after deactivation — slot may still be taken"
        return 1
    else
        echo "Confirmed: .lic file removed — slot is free"
        return 0
    fi
}

# ------------------------------------------------------------------------------
# cleanup
# Guarantees license deactivation regardless of how the container terminates
# ------------------------------------------------------------------------------
cleanup() {
    echo ""
    echo "Container shutdown detected — securing license..."

    # Gracefully stop the pipeline process if still running
    if [ -n "$CHILD_PID" ] && kill -0 "$CHILD_PID" 2>/dev/null; then
        echo "Stopping pipeline process..."
        kill -TERM "$CHILD_PID" 2>/dev/null

        local WAIT=0
        while kill -0 "$CHILD_PID" 2>/dev/null && [ $WAIT -lt 30 ]; do
            sleep 1
            WAIT=$((WAIT + 1))
        done

        if kill -0 "$CHILD_PID" 2>/dev/null; then
            kill -KILL "$CHILD_PID" 2>/dev/null
        fi
        CHILD_PID=""
    fi

    # Deactivate Metashape license with secondary verification
    if [ "$ACTIVATED" = "1" ]; then
        echo "Deactivating Metashape license..."

        if [ "$SKIP_MODE" = "1" ]; then
            echo "[ TEST MODE ] Deactivation simulated — no network call"
        else
            # Attempt 1
            if $METASHAPE_BIN --deactivate; then
                # Secondary control : verify .lic file is actually gone
                if verify_deactivation; then
                    echo "License deactivated — slot released"
                else
                    echo "Deactivation reported success but .lic still present — retrying..."
                    sleep 5
                    $METASHAPE_BIN --deactivate && verify_deactivation || true
                fi
            else
                echo "Deactivation attempt 1 failed — retrying in 5s..."
                sleep 5

                # Attempt 2
                if $METASHAPE_BIN --deactivate; then
                    if verify_deactivation; then
                        echo "License deactivated (attempt 2) — slot released"
                    else
                        echo "ERROR: Deactivation failed — .lic still present"
                        echo "  Contact : support@agisoft.com"
                        echo "  Key     : ${METASHAPE_KEY:0:5}-****-****-****-*****"
                    fi
                else
                    echo "ERROR: Deactivation failed after 2 attempts"
                    echo "  Contact : support@agisoft.com"
                    echo "  Key     : ${METASHAPE_KEY:0:5}-****-****-****-*****"
                fi
            fi
        fi
        ACTIVATED=0
    fi

    echo "Container terminated."
}

trap cleanup EXIT INT TERM

# ------------------------------------------------------------------------------
# Validate required environment variable
# ------------------------------------------------------------------------------
if [ -z "$METASHAPE_KEY" ]; then
    echo "ERROR: METASHAPE_LICENSE_KEY is not set in .env"
    echo "  Production : METASHAPE_LICENSE_KEY=XXXXX-XXXXX-XXXXX-XXXXX-XXXXX"
    echo "  Test mode  : METASHAPE_LICENSE_KEY=SKIP"
    exit 1
fi

# ------------------------------------------------------------------------------
# License activation
# ------------------------------------------------------------------------------
echo "Activating Metashape license..."

if [ "$METASHAPE_KEY" = "SKIP" ]; then
    SKIP_MODE=1
    ACTIVATED=1
    echo "[ TEST MODE ] Activation simulated — Metashape step will be skipped"
else
    echo "Key : ${METASHAPE_KEY:0:5}-****-****-****-*****"

    if $METASHAPE_BIN --activate "$METASHAPE_KEY"; then
        ACTIVATED=1
        export AGISOFT_LICENSE_PATH="/var/tmp/agisoft/licensing/licenses"
        echo "License activated"
    else
        echo "Activation attempt 1 failed — retrying in 10s..."
        sleep 10
        if $METASHAPE_BIN --activate "$METASHAPE_KEY"; then
            ACTIVATED=1
            export AGISOFT_LICENSE_PATH="/var/tmp/agisoft/licensing/licenses"
            echo "License activated (attempt 2)"
        else
            echo "ERROR: Activation failed after 2 attempts"
            echo "  Verify license key or contact support@agisoft.com"
            exit 1
        fi
    fi
fi

# ------------------------------------------------------------------------------
# Pipeline execution
# ------------------------------------------------------------------------------
echo "Starting pipeline..."

"$@" &
CHILD_PID=$!

# Wait loop using wait -n to catch all interruptions from sub-processes
while kill -0 "$CHILD_PID" 2>/dev/null; do
    wait -n 2>/dev/null || true
done

# Final wait to retrieve the exact exit code of the pipeline
wait "$CHILD_PID" 2>/dev/null
EXIT_CODE=$?
CHILD_PID=""

exit $EXIT_CODE
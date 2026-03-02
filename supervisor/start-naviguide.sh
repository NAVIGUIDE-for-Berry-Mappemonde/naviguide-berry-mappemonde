#!/bin/bash
# Auto-start script for NAVIGUIDE services via supervisor
# Called by cron @reboot

SUPERVISORD=/home/cocoapp/.local/bin/supervisord
CONF=/mnt/efs/spaces/ef014a98-8a1c-4b16-8e06-5d2c5b364d08/527f928c-fa41-40dd-8d61-c174d3e76a01/feature_deploy-ui-fixes/supervisor/supervisord.conf
PID_FILE=/tmp/naviguide-sup.pid

# Wait for EFS mount to be available
for i in $(seq 1 30); do
  [ -f "$CONF" ] && break
  sleep 2
done

# Load secrets from .env.naviguide (not committed to git)
ENV_FILE="$(dirname "$CONF")/../.env.naviguide"
if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  set -a && source "$ENV_FILE" && set +a
fi

# Only start if not already running
if [ ! -f "$PID_FILE" ] || ! kill -0 "$(cat $PID_FILE)" 2>/dev/null; then
  $SUPERVISORD -c "$CONF"
fi

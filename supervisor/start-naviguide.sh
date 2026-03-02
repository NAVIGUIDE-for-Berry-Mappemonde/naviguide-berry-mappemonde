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

# Kill any stale processes holding the managed ports (nohup leftovers, etc.)
# so supervisor can always bind cleanly on startup / restart
for PORT in 8001 8004 3016; do
  PIDS=$(lsof -ti tcp:$PORT 2>/dev/null)
  if [ -n "$PIDS" ]; then
    echo "[start-naviguide] Freeing port $PORT (PIDs: $PIDS)"
    kill -9 $PIDS 2>/dev/null || true
  fi
done
sleep 1

# Only start if not already running
if [ ! -f "$PID_FILE" ] || ! kill -0 "$(cat $PID_FILE)" 2>/dev/null; then
  $SUPERVISORD -c "$CONF"
else
  # Supervisord already running — just reload config + restart programs
  /home/cocoapp/.local/bin/supervisorctl -c "$CONF" reread   2>/dev/null || true
  /home/cocoapp/.local/bin/supervisorctl -c "$CONF" update   2>/dev/null || true
  /home/cocoapp/.local/bin/supervisorctl -c "$CONF" restart all 2>/dev/null || true
fi

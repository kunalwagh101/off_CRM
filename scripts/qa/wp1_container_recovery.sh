#!/usr/bin/env bash
# A01–A04 and A17: replay the archived WP1 container recovery check.
set -euo pipefail

image=${1:?Pass the already-built off_CRM release image}
work=$(mktemp -d)
name="offcrm-wp1-${work##*.}"
volume="$name-data"
token=$(python -c 'import secrets; print(secrets.token_urlsafe(48))')
passphrase='disposable-wp1-backup-passphrase'
export OFFSETX_LOCAL_API_TOKEN="$token"

cleanup() {
    docker rm --force "$name" >/dev/null 2>&1 || true
    docker volume rm "$volume" >/dev/null 2>&1 || true
    rm -rf -- "$work"
}
trap cleanup EXIT

start() {
    docker run --detach --name "$name" --read-only \
        --tmpfs /tmp:rw,nosuid,nodev,size=256m \
        --cap-drop ALL --cap-add CHOWN --cap-add SETUID --cap-add SETGID \
        --security-opt no-new-privileges \
        --publish 127.0.0.1::8766 --volume "$volume:/var/lib/offcrm" \
        --env OFFSETX_PRODUCTION=1 --env OFFSETX_PERSISTENT_MOUNT=/var/lib/offcrm \
        --env OFFSETX_ALLOWED_HOSTS=127.0.0.1,localhost --env OFFSETX_LOCAL_API_TOKEN \
        "$image" >/dev/null
    local port
    port=$(docker port "$name" 8766/tcp)
    base="http://${port}"
    for _ in {1..45}; do
        if curl --noproxy '*' --max-time 2 --fail --silent "$base/health/ready" |
            python -c 'import json, sys; sys.exit(json.load(sys.stdin).get("status") != "ready")' 2>/dev/null; then
            return
        fi
        sleep 1
    done
    docker logs --tail 40 "$name"
    return 1
}

api() {
    curl --noproxy '*' --silent --show-error --fail --max-time 30 \
        --header "Authorization: Bearer $token" "$@"
}

check_campaign() {
    api "$base/api/v1/campaigns" | python -c '
import json, sys
result = json.load(sys.stdin)
assert result["total"] == 1, result["total"]
assert [row["id"] for row in result["items"]] == [sys.argv[1]]
' "$campaign_id"
}

docker volume create "$volume" >/dev/null
start
docker exec --user 10001:10001 "$name" python -c '
from pathlib import Path
status = dict(line.split(":", 1) for line in Path("/proc/1/status").read_text().splitlines() if ":" in line)
assert status["Uid"].split() == ["10001"] * 4
assert int(status["CapEff"].strip(), 16) == 0
'
campaign_id=$(api --header 'Content-Type: application/json' \
    --data '{"name":"Disposable WP1 campaign"}' "$base/api/v1/campaigns" |
    python -c 'import json, sys; print(json.load(sys.stdin)["id"])')
docker exec --user 10001:10001 "$name" python -c '
from pathlib import Path
Path("/var/lib/offcrm/local_data/video_renders/disposable-wp1.bin").write_bytes(b"before-backup")
'
api --header 'Content-Type: application/json' --data "{\"passphrase\":\"$passphrase\"}" \
    --output "$work/workspace.oxbackup" "$base/api/v1/backups/export"
test -s "$work/workspace.oxbackup"

docker kill "$name" >/dev/null
docker rm "$name" >/dev/null
start
check_campaign
docker exec --user 10001:10001 "$name" python -c '
from pathlib import Path
path = Path("/var/lib/offcrm/local_data/video_renders/disposable-wp1.bin")
assert path.read_bytes() == b"before-backup"
path.write_bytes(b"after-backup")
'
api --header 'Content-Type: application/json' --data '{"name":"Discarded on restore"}' \
    "$base/api/v1/campaigns" >/dev/null
api --form "file=@$work/workspace.oxbackup" --form "passphrase=$passphrase" \
    "$base/api/v1/backups/restore" >/dev/null
check_campaign
docker exec --user 10001:10001 "$name" python -c '
from pathlib import Path
assert Path("/var/lib/offcrm/local_data/video_renders/disposable-wp1.bin").read_bytes() == b"before-backup"
'
api "$base/health/ready" | python -c 'import json, sys; assert json.load(sys.stdin)["status"] == "ready"'
echo 'WP1 PASS: release image replacement, persistent campaign and file, encrypted restore and readiness'

#!/usr/bin/env bash
# Run on Ubuntu EC2 from this project. No AWS CLI or registry is required.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
root="$PWD"
umask 077
exec 9>"$root/.deploy.lock"
flock -n 9 || { echo "Another deployment is running."; exit 1; }
[[ -f .env ]] || { echo "Copy .env.example to .env and set production values."; exit 1; }
mkdir -p .releases
mode="${1:-deploy}"
if [[ "$mode" == "--rollback" ]]; then
    tag="${2:?Usage: bash scripts/deploy.sh --rollback RELEASE_TAG}"
else
    tag="${1:-$(date -u +%Y%m%dT%H%M%SZ)}"
fi
[[ "$tag" =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}$ ]] || { echo "Invalid release tag."; exit 1; }
export TAG="$tag"
release="$root/.releases/$tag"
previous=""
[[ ! -f .releases/current ]] || previous="$(cat .releases/current)"

compose() {
    docker compose --project-name scamshield --env-file "$root/.env" -f "$release/compose.yml" "$@"
}

if [[ "$mode" == "--rollback" ]]; then
    [[ -f "$release/compose.yml" ]] || { echo "Unknown saved release."; exit 1; }
    docker image inspect "scamshield-api:$tag" "scamshield-ui:$tag" >/dev/null
else
    [[ ! -e "$release" ]] || { echo "Choose a new tag; release tags cannot be reused."; exit 1; }
    mkdir "$release"
    cp docker-compose.prod.yml "$release/compose.yml"
    compose config --quiet
    # Fail before building if the public site or password still uses example settings.
    compose config --format json | python3 -c '
import json,sys
c=json.load(sys.stdin)
site=c["services"]["ui"]["environment"]["SITE_ADDRESS"]
password=c["services"]["db"]["environment"]["POSTGRES_PASSWORD"]
if "example.com" in site or "://" in site or "/" in site or ":" in site or "." not in site:
    sys.exit("Set SITE_ADDRESS to your real domain, without a scheme, port or path.")
if len(password)<20 or password=="local-demo-change-before-cloud":
    sys.exit("Set a unique DB_PASSWORD of at least 20 characters.")
'
    docker build -t "scamshield-api:$tag" ./api
    docker build -t "scamshield-ui:$tag" ./ui
    docker run --rm --entrypoint caddy "scamshield-ui:$tag" validate --config /etc/caddy/Caddyfile
fi

rollback_on_error() {
    trap - ERR
    if [[ -n "$previous" && "$previous" != "$tag" ]]; then
        echo "Deployment failed; restoring release $previous."
        export TAG="$previous"
        release="$root/.releases/$previous"
        compose up -d --wait --wait-timeout 180 || {
            echo "Rollback failed. Inspect docker compose logs on the server."; exit 1;
        }
    else
        echo "First deployment failed. Inspect containers and logs; no previous release exists."
    fi
    exit 1
}
trap rollback_on_error ERR
compose up -d --wait --wait-timeout 180
site="$(compose config --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["ui"]["environment"]["SITE_ADDRESS"])')"
curl --fail --silent --show-error --retry 12 --retry-delay 5 --retry-all-errors \
    --connect-timeout 5 --max-time 15 "https://$site/api/health" >/dev/null
printf '%s\n' "$tag" > .releases/current.tmp
mv .releases/current.tmp .releases/current
trap - ERR
echo "Healthy release $tag: https://$site"
echo "Keep earlier images and .releases folders for rollback."

#!/usr/bin/env bash
# Deploy the newest main on the INVITE server: pull, roll the stack (the API applies its own
# migrations as it starts), check /healthz, then build the client and swap it in whole, so nginx
# never serves half a build. The previous build stays in client/dist.prev to roll back to.
#
# Refuses to run over uncommitted changes to tracked files. Needs .env (see .env.example).
set -euo pipefail

# Bash reads a function whole before running it, so the pull below can change this file safely.
main() {
  cd "$(dirname "$(readlink -f "$0")")/.."
  export PATH="/opt/node-24/bin:$PATH"

  if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "Uncommitted changes to tracked files, not deploying:" >&2
    git status --short >&2
    exit 1
  fi

  before=$(git rev-parse HEAD)
  git pull --ff-only
  if ! git diff --quiet "$before" HEAD -- scripts/deploy.sh; then
    echo "scripts/deploy.sh changed in this pull, running the new one"
    exec "$0" "$@"
  fi
  # The docs workflow pushes a docs-only commit after most merges. Neither the image nor the
  # client holds the docs, so rolling the stack for it would only restart the API under the
  # students. A run that pulled nothing (by hand, or the rerun above) still deploys.
  if [ "$before" != "$(git rev-parse HEAD)" ] && git diff --quiet "$before" HEAD -- . \
    ':(exclude)docs' ':(exclude)README.md' ':(exclude)zensical.toml' ':(exclude).github'; then
    echo "Only the docs changed, so the running stack stays as it is."
    exit 0
  fi
  git submodule update --init --recursive

  docker compose -f compose.yml up -d --build --remove-orphans

  port=$(sed -n 's/^API_PORT=//p' .env | tail -1)
  port=${port:-8005}
  for _ in $(seq 1 60); do
    curl -sf -o /dev/null "http://127.0.0.1:$port/healthz" && break
    sleep 1
  done
  if ! curl -sf -o /dev/null "http://127.0.0.1:$port/healthz"; then
    echo "The API is not healthy on :$port. See: docker compose -f compose.yml logs api" >&2
    exit 1
  fi

  rm -rf client/dist.next
  npm --prefix client ci --no-audit --no-fund
  npm --prefix client run build -- --outDir dist.next --emptyOutDir
  rm -rf client/dist.prev
  [ -d client/dist ] && mv client/dist client/dist.prev
  mv client/dist.next client/dist
  echo "Deployed $(git rev-parse --short HEAD)"
}

main "$@"

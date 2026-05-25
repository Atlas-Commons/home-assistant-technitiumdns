#!/usr/bin/env bash
# Verify all commits in a PR include Signed-off-by (DCO).
set -euo pipefail

if [[ "${GITHUB_EVENT_NAME:-}" != "pull_request" ]]; then
  echo "Not a pull request — skipping DCO check."
  exit 0
fi

base="${GITHUB_BASE_REF:-main}"
git fetch origin "${base}" --depth=1 2>/dev/null || git fetch origin "${base}"

missing=0
while IFS= read -r sha; do
  [[ -z "$sha" ]] && continue
  if ! git log -1 --format=%B "$sha" | grep -qi '^Signed-off-by:'; then
    echo "Missing Signed-off-by on commit ${sha:0:7}"
    git log -1 --oneline "$sha"
    missing=1
  fi
done < <(git rev-list "origin/${base}"..HEAD)

if [[ "$missing" -ne 0 ]]; then
  echo ""
  echo "Add sign-off with: git commit -s --amend && git push --force-with-lease"
  exit 1
fi

echo "All commits include DCO sign-off."

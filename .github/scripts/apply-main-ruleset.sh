#!/usr/bin/env bash
# Apply the main branch ruleset to a GitHub repository.
#
# Prerequisites:
#   - GitHub CLI: https://cli.github.com/
#   - Authenticated: gh auth login
#   - Admin access on the repository
#
# Usage:
#   ./.github/scripts/apply-main-ruleset.sh
#   ./.github/scripts/apply-main-ruleset.sh Atlas-Commons Bot

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RULESET_FILE="${REPO_ROOT}/.github/rulesets/main.json"

OWNER="${1:-}"
REPO="${2:-}"

if [[ -z "${OWNER}" || -z "${REPO}" ]]; then
  REMOTE="$(git -C "${REPO_ROOT}" remote get-url origin 2>/dev/null || true)"
  if [[ "${REMOTE}" =~ github\.com[:/]([^/]+)/([^/.]+) ]]; then
    OWNER="${BASH_REMATCH[1]}"
    REPO="${BASH_REMATCH[2]}"
  else
    echo "Usage: $0 <owner> <repository>" >&2
    echo "Could not detect owner/repo from git remote." >&2
    exit 1
  fi
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI (gh) is required. Install from https://cli.github.com/" >&2
  exit 1
fi

echo "Applying ruleset to ${OWNER}/${REPO} ..."

visibility="$(gh repo view "${OWNER}/${REPO}" --json visibility -q '.visibility' 2>/dev/null || echo unknown)"
if [[ "${visibility}" == "PRIVATE" ]]; then
  echo "Cannot apply repository rulesets to private repos without GitHub Team/Pro." >&2
  echo "Configure branch protection manually: https://github.com/${OWNER}/${REPO}/settings/branches" >&2
  exit 1
fi

EXISTING="$(gh api "repos/${OWNER}/${REPO}/rulesets" --jq '.[] | select(.name=="Protect main" or .name=="main") | .id' 2>/dev/null | head -1 || true)"

if [[ -n "${EXISTING}" ]]; then
  echo "Updating existing ruleset id=${EXISTING} ..."
  gh api \
    --method PUT \
    "repos/${OWNER}/${REPO}/rulesets/${EXISTING}" \
    --input "${RULESET_FILE}"
else
  echo "Creating new ruleset ..."
  gh api \
    --method POST \
    "repos/${OWNER}/${REPO}/rulesets" \
    --input "${RULESET_FILE}"
fi

echo ""
echo "Ruleset applied. Verify at:"
echo "  https://github.com/${OWNER}/${REPO}/settings/rules"
echo ""
echo "Notes:"
echo "  - Merges to main require the 'Required checks' CI job (workflow: CI)."
echo "  - Install the DCO app: https://github.com/apps/dco"
echo "  - Open one PR against main so CI runs before enforcing the ruleset."

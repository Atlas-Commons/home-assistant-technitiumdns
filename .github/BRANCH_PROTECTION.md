# Branch protection for `main`

Merging to `main` requires passing CI and a pull request. Configuration lives in this repository so it can be reviewed and re-applied consistently.

## What runs on every PR and push to `main`

Workflow: [`.github/workflows/ci.yml`](workflows/ci.yml)

The final job is always named **Required checks**. Branch rulesets require that status to be green before merge.

## DCO (Developer Certificate of Origin)

Install the [DCO GitHub App](https://github.com/apps/dco) on the Atlas-Commons organization.

Every commit must include sign-off:

```bash
git commit -s -m "Your message"
```

## Apply the ruleset (one-time)

GitHub rulesets are configured on the repository, not via git push.

```bash
chmod +x .github/scripts/apply-main-ruleset.sh
./.github/scripts/apply-main-ruleset.sh Atlas-Commons REPO_NAME
```

Or apply to every catalog repo from a machine with `gh` authenticated:

```bash
./scripts/apply-all-catalog-rulesets.sh
```

### Private repositories (Bot, atlas-commons-website)

Repository rulesets on **private** repos require GitHub Team or Pro. For those repos, configure branch protection manually under **Settings → Branches** until the org upgrades, or make the repo public.

The apply script skips private repos automatically.

### Important: check name must exist first

GitHub only lets you select status checks that have run at least once. Open a PR against `main` (or push once) **before** applying the ruleset.

## Apply rulesets to all catalog repos

See [`atlas-commons-github-templates/scripts/apply-all-catalog-rulesets.sh`](https://github.com/Atlas-Commons/atlas-commons-github-templates) in the template pack, or run from any repo:

```bash
for repo in Bot atlas-commons-website technitiumdns-api home-assistant-technitiumdns \
  StreamBooru Hassio-Addons Danbooru-Import-Scripts EmbyArrSync windowsRDP-SSH-tunnel-script; do
  gh api --method POST "repos/Atlas-Commons/${repo}/rulesets" --input .github/rulesets/main.json 2>/dev/null || \
  gh api --method PUT "repos/Atlas-Commons/${repo}/rulesets/$(gh api repos/Atlas-Commons/${repo}/rulesets --jq '.[]|select(.name=="Protect main")|.id')" --input .github/rulesets/main.json
done
```

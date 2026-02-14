---
description: Release management via release-please (automated)
---

# Release Procedure

Perform a full release: check status, merge the pending Release PR, and monitor the build.

## Steps

0. **Detect the repo** — use `gh repo view --json nameWithOwner -q .nameWithOwner` to get the current repo (e.g., `owner/repo`). Use this for all subsequent `gh` commands.

1. **Check for a pending Release PR**:
   ```bash
   gh pr list --label "autorelease: pending"
   ```
   If no pending Release PR exists, inform the user and stop — there is nothing to release.

2. **Show what's in the release** — display the PR title, body, and version so the user can see what will be released:
   ```bash
   gh pr view <PR_NUMBER>
   ```

3. **Merge the Release PR** (squash merge):
   ```bash
   gh pr merge <PR_NUMBER> --squash
   ```

4. **Pull the merged changes locally**:
   ```bash
   git pull
   ```

5. **Wait for release-please to create the tag and release** — poll until the release is created (up to 2 minutes):
   ```bash
   # Check every 15 seconds until the new release appears
   gh release list --limit 1
   ```

6. **Confirm the Docker build was triggered** — check that the build workflow started:
   ```bash
   gh run list --limit 3
   ```

7. **Report the result** — show the user:
   - The new release version and URL
   - The Docker build status and URL
   - The GHCR image names (derive from repo owner: `ghcr.io/<owner>/pulsar-console-api` and `ghcr.io/<owner>/pulsar-console-ui`) with the new tag

## Reference

### Version Bumps
- `feat:` → minor (1.1.0 → 1.2.0)
- `fix:` → patch (1.1.0 → 1.1.1)
- `feat!:` or `BREAKING CHANGE:` → major (1.1.0 → 2.0.0)
- `chore:`, `docs:`, `ci:` → no release (bundled into next)

### Image Names
- `ghcr.io/<owner>/pulsar-console-api`
- `ghcr.io/<owner>/pulsar-console-ui`

Tags produced: `latest`, `vX.Y.Z`, `vX.Y`, git short SHA.

### Manual Release (fallback)
```bash
gh workflow run release.yml -f version=X.Y.Z
```

### Notes
- Do NOT modify anything in `k8s/` directory — leave versions on `latest`
- Use conventional commit messages so release-please can compute versions correctly

---
description: Release a new version with Docker image builds
---

# Release Procedure

## Steps

1. **Commit and push changes**
   ```bash
   git push origin main
   ```

2. **Create GitHub release**
   ```bash
   gh api repos/pezzking/pulsarconsole/releases -f tag_name=vX.Y.Z -f name="vX.Y.Z" -F generate_release_notes=true
   ```

3. **Verify build completion**
   ```bash
   gh run list --workflow=build-and-publish.yml --limit 3
   ```

## Image Names

Our workflow builds these images to GHCR:
- `ghcr.io/pezzking/pulsar-console-api`
- `ghcr.io/pezzking/pulsar-console-ui`

## Notes

- Do NOT modify anything in `k8s/` directory - leave versions on `latest`
- Do NOT add Co-Authored-By lines to commits

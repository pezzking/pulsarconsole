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
   gh release create vX.Y.Z --title "vX.Y.Z" --generate-notes
   ```

3. **Verify build completion**
   ```bash
   gh run list --workflow=build-and-publish.yml --limit 3
   ```

## Notes

- Do NOT modify anything in `k8s/` directory - leave versions on `latest`
- Do NOT add Co-Authored-By lines to commits

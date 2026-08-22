# Deployment source decision

DEPLOYMENT_SOURCE_MODE=GIT_BACKED_PRIVATE_RELEASE_BRANCH

Reason:

- Frozen snapshot is 19.95 MiB across 1190 files
- Largest file is 0.19 MiB
- No file approaches the GitHub 100 MiB hard limit or 50 MiB warning
- Git clone/build on Render is acceptable
- GHCR is unnecessary and would publish less reviewable source

TARGET_REMOTE_BRANCH=release/2026-sage125-final-demo
REMOTE_REPOSITORY=sage125-ai-scientist-team/SAGE125-AI-Scientist

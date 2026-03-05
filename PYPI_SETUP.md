# PyPI Publishing Setup

skill-gate uses **Trusted Publishing (OIDC)** — no API token needed. One-time setup:

## Steps

1. **Create the PyPI project**
   - Go to https://pypi.org/manage/account/publishing/
   - Add a new Trusted Publisher:
     - PyPI project name: `agentskill-gate`
     - GitHub owner: `vaibhavtupe`
     - GitHub repo: `skill-gate`
     - Workflow filename: `publish.yml`
     - Environment name: `pypi`

2. **Create the GitHub environment**
   - Go to https://github.com/vaibhavtupe/skill-gate/settings/environments
   - Create environment named `pypi`
   - Optional: add protection rules (required reviewers)

3. **Trigger a publish**
   - Push a version tag: `git tag v0.3.1 && git push origin v0.3.1`
   - The `publish.yml` workflow fires automatically, builds, and uploads to PyPI

## That's it

No secrets, no tokens. GitHub's OIDC identity is used to authenticate with PyPI directly.

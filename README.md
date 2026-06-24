# dk_skills

Personal Codex skills workspace for developing, maintaining, and publishing daily-work skills.

## Prerequisites

- Codex or another compatible agent runtime that can load local skills.
- Git for version control.
- GitHub CLI (`gh`) for repository authentication and publishing.
- PowerShell on Windows for the local maintenance commands used in this workspace.

## Installation

Clone the repository, then point your Codex skills path or skill installer workflow at the `skills/` directory.

```powershell
git clone <your-github-repo-url>
cd dk_skills
```

Each skill lives in its own subdirectory under `skills/`. A typical skill should include a `SKILL.md` entrypoint and any supporting `scripts/`, `templates/`, `assets/`, or `examples/` folders it needs.

## Available Skills

No skills have been added yet.

When a new skill is added, document it here with:

- Skill name
- Purpose and trigger phrases
- Required tools or credentials
- Example usage

## Project Structure

```text
dk_skills/
  README.md
  CHANGELOG.md
  .gitignore
  skills/
    <skill-name>/
      SKILL.md
```

## Maintenance

- Keep sensitive files, credentials, generated caches, and local exports out of Git.
- Update `CHANGELOG.md` whenever a skill is added, changed, or removed.
- Keep each skill self-contained so it can be copied, reviewed, or published independently.

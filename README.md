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

### deep-reading-assistant

Generates complete Chinese Markdown reading notes after reading a book, manuscript, PDF, EPUB, text export, or existing reading-note draft. It works in separate passes: outline, recommendation, verified author introduction, chapter synopsis, section-by-section long-form notes, conclusion, and final Markdown integration.

Example prompt:

```text
Use $deep-reading-assistant to read this book and create a complete Chinese Markdown reading note.
```

### writing-style-dna（文风DNA）

从用户提供的少量样文（领导讲话、公文、论文、工作总结、评论文章等，通常 2-10 篇）中提取可复用的写作风格档案（风格DNA），再按该档案进行 AI 写作或改写，实现风格复刻并去除 AI 味。内置四层分析产物（语言DNA / 结构模板 / 立场与认知 / 排版规范）、表述口径库、表态等级守恒和体裁适配的去AI味白名单（公文编号、讲话排比、学术惯例等豁免）。

- 触发场景：分析文风、提取写作风格、给某位领导或单位建立风格档案、按样文风格起草材料、把稿件改写得像某人写的、改写时保留口径、去 AI 味
- 所需工具：无外部依赖；仅当用户明确要求且内容公开发表时才联网补充语料
- 示例：

```text
请用 $writing-style-dna 分析这几篇讲话稿，建一个风格档案。
请按这个风格档案，起草一篇在季度工作会上的讲话。
请按这个风格档案把这篇汇报改写一遍，口径别动，去掉AI味。
```

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
    deep-reading-assistant/
      SKILL.md
      agents/
        openai.yaml
      references/
        final-note-format.md
```

## Maintenance

- Keep sensitive files, credentials, generated caches, and local exports out of Git.
- Update `CHANGELOG.md` whenever a skill is added, changed, or removed.
- Keep each skill self-contained so it can be copied, reviewed, or published independently.

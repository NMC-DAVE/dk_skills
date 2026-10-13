# dk_skills

个人常用 Agent Skills 仓库。每个技能均独立放在 `skills/<skill-name>/` 下，可通过 [`npx skills`](https://github.com/vercel-labs/skills) **按需安装、更新、查看和删除**，无需一次安装整个 `skills/` 目录。

## 快速开始

### 1. 查看仓库中可用的技能

```bash
npx skills add NMC-DAVE/dk_skills --list
```

### 2. 只安装一个技能

```bash
npx skills add NMC-DAVE/dk_skills --skill paper-deep-reader
```

命令会检测本机支持的 Agent，并让你选择安装位置。也可以显式指定 Agent 和作用域：

```bash
# 全局安装到 Pi
npx skills add NMC-DAVE/dk_skills --skill paper-deep-reader -g -a pi

# 全局安装到 Codex
npx skills add NMC-DAVE/dk_skills --skill paper-deep-reader -g -a codex

# 安装到当前项目的 Claude Code
npx skills add NMC-DAVE/dk_skills --skill paper-deep-reader -a claude-code
```

IDL 编程技能可独立安装，运行时需要 Node.js 18+ 和已许可的本机 IDL；无需 VSCode、Copilot 或 MCP：

```bash
npx skills add NMC-DAVE/dk_skills --skill idl-programming -g -a codex
```

在 Agent 中使用 `$idl-programming` 描述任务即可。技能会检测实际 IDL 版本，查阅本机帮助和项目例程，生成 `.pro`，并默认编译和运行带断言的最小测试。IDL 不在当前进程 PATH 时会尝试 Windows 系统/用户 PATH，也可显式指定可执行文件。

### 3. 一次选择多个技能

重复使用 `--skill`，只会安装点名的技能：

```bash
npx skills add NMC-DAVE/dk_skills \
  --skill paper-deep-reader \
  --skill writing-style-dna
```

不传 `--skill` 时，CLI 会在交互界面中让你选择技能。若不想安装全部技能，请不要使用 `--all` 或 `--skill '*'`。

## 技能管理

### 查看已安装技能

```bash
# 当前项目
npx skills list

# 全局技能
npx skills list -g

# 只看某个 Agent 的全局技能
npx skills list -g -a pi
```

### 更新技能

```bash
# 交互式选择作用域并更新
npx skills update

# 只更新指定技能
npx skills update paper-deep-reader

# 只更新全局安装的指定技能
npx skills update paper-deep-reader -g

# 更新当前项目中的全部技能
npx skills update -p
```

### 删除技能

```bash
# 交互式选择要删除的技能
npx skills remove

# 删除当前项目中的指定技能
npx skills remove paper-deep-reader

# 从 Pi 的全局目录删除指定技能
npx skills remove paper-deep-reader -g -a pi
```

> `npx skills remove --all` 会删除所选作用域内的全部技能，请谨慎使用。

### 临时使用但不安装

```bash
npx skills use NMC-DAVE/dk_skills@paper-deep-reader
```

## 本地仓库安装

开发或调试本仓库时，可以从本地路径安装，同样支持选择性安装：

```bash
git clone https://github.com/NMC-DAVE/dk_skills.git
cd dk_skills

npx skills add . --list
npx skills add . --skill paper-deep-reader
```

也可以直接使用 GitHub 中某个技能的目录 URL：

```bash
npx skills add https://github.com/NMC-DAVE/dk_skills/tree/main/skills/paper-deep-reader
```

## 可用技能

| 技能 | 用途 | 主要依赖 |
| --- | --- | --- |
| [`paper-deep-reader`](skills/paper-deep-reader/) | 深度阅读单篇科研论文，整理元数据、RIS/ENW、页级证据、模块化笔记与中文综合报告 | Python 3.10+；推荐 PyMuPDF，可选 Poppler；远程来源和权威元数据查询需要网络 |
| [`idl-programming`](skills/idl-programming/) | 按本机版本编写、修改和调试 IDL 科学计算代码，检索官方/项目例程并编译和运行最小测试 | Node.js 18+ 内置模块；已许可的本机 IDL（本机集成验收使用 9.3）；优先本机帮助 |
| [`deep-reading-assistant`](skills/deep-reading-assistant/) | 阅读书籍、手稿、PDF、EPUB 或文本，生成完整中文 Markdown 读书笔记 | 取决于源文件格式的读取工具；作者资料核验通常需要网络 |
| [`writing-style-dna`](skills/writing-style-dna/) | 从少量样文提取可复用的文风档案，并按档案写作或改写、减少 AI 痕迹 | 无强制外部依赖 |

## 环境要求

- Node.js 18+（用于运行 `npx skills`）
- Git（安装 GitHub 仓库来源时使用）
- 目标 Agent，例如 Pi、Codex、Claude Code、Cursor 等
- 个别技能的额外依赖见其 `SKILL.md`

`npx skills` 支持项目级和全局安装。常用 Agent 的目录示例：

| Agent | `--agent` | 项目级目录 | 全局目录 |
| --- | --- | --- | --- |
| Pi | `pi` | `.pi/skills/` | `~/.pi/agent/skills/` |
| Codex | `codex` | `.agents/skills/` | `~/.codex/skills/` |
| Claude Code | `claude-code` | `.claude/skills/` | `~/.claude/skills/` |
| Cursor | `cursor` | `.agents/skills/` | `~/.cursor/skills/` |

## 仓库维护

```bash
# 校验技能目录、SKILL.md frontmatter、本地链接和 Agent 元数据
npm run validate

# 使用 npx skills 验证本地仓库发现结果
npm run skills:list

# 运行当前自动化测试
npm test

# 执行完整 CI 检查
npm run ci
```

IDL 单元测试不需要 IDL 安装，真实运行时测试默认跳过。需要本机集成测试时，在当前 shell 设置 `DK_IDL_EXECUTABLE` 为实际 IDL 可执行文件路径，再运行 `npm run test:idl-programming`。测试使用临时目录和合成数据。

新增技能时应：

1. 创建 `skills/<skill-name>/SKILL.md`。
2. 在 YAML frontmatter 中填写与目录同名的 `name` 和清晰的 `description`。
3. 将脚本、模板、参考资料和测试保存在该技能目录内，保持技能自包含。
4. 在本 README 的技能表和 `CHANGELOG.md` 中登记。
5. 运行 `npm run ci`，确认 `npx skills` 能发现该技能。

更多维护规则见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

## 仓库结构

```text
dk_skills/
  .github/workflows/validate.yml
  package.json
  scripts/
    validate_skill_catalog.py
  skills/
    deep-reading-assistant/
      SKILL.md
    paper-deep-reader/
      SKILL.md
      references/
      scripts/
      tests/
    writing-style-dna/
      SKILL.md
      references/
      templates/
```

## 安全说明

安装或运行任何第三方技能前，应先检查其 `SKILL.md` 和附带脚本。不要把凭据、私有文档、生成输出或本地缓存提交到仓库。

# Contributing and maintenance

本仓库是可被 `npx skills` 直接发现的 Agent Skills 目录。所有公开技能都放在 `skills/<name>/` 下，并保持可独立安装。

## 新增技能

1. 创建 `skills/<name>/SKILL.md`；名称使用小写字母、数字和连字符。
2. `SKILL.md` 必须以 YAML frontmatter 开头，并至少包含：

   ```yaml
   ---
   name: example-skill
   description: Explain what the skill does and when it should be used.
   ---
   ```

3. frontmatter 的 `name` 必须与目录名完全一致。
4. 把技能所需的 `scripts/`、`references/`、`templates/`、`assets/` 和 `tests/` 放在该技能目录内。
5. 避免从技能目录引用仓库外部的本地文件，否则选择性安装后引用会失效。
6. 更新根目录 `README.md` 的技能表和 `CHANGELOG.md`。

## 本地检查

```bash
npm run validate
npm test
npm run skills:list
```

`npm run skills:list` 应列出每个公开技能。还应实际检查一次选择性安装：

```bash
npx skills add . --skill <name>
```

建议在临时项目目录中执行安装测试，避免覆盖日常使用的技能。

## 版本与兼容性

- 仓库通过 `npx skills@1` 做持续发现验证。
- 技能应遵循通用 `SKILL.md` 结构；Agent 专属功能应在技能说明中明确标注。
- 修改脚本行为时，应同步更新测试和技能内的使用示例。
- 新增、变更或删除技能时，必须更新 `CHANGELOG.md`。

## 提交前检查

- [ ] `name` 与技能目录一致。
- [ ] `description` 同时说明能力和触发场景。
- [ ] 所有相对链接有效。
- [ ] 技能不依赖仓库外的未声明文件。
- [ ] 未提交凭据、私人材料、缓存或生成结果。
- [ ] `npm run ci` 通过。

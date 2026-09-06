# Final report template

Use natural Chinese prose, real Markdown headings, equations in LaTeX, and page evidence anchors.

```markdown
---
title: "<official title>：中文深度解读"
authors: [<authors>]
year: <year>
arxiv: <id when available>
doi: <doi when available>
paper_type: <classified type>
tags: [paper-reading, <domain tags>]
---

# <Official Title>：中文深度解读

## 核心信息
## 原文摘要翻译
## 一句话总结
## 论文大纲

## 第一轮：框架与主旨
### 论文类别与目标
### 关键贡献
### 论证路线

## 第二轮：方法与证据链
### 数据和任务
### 方法总览
### 机制流程
### 关键公式与目标函数
### 实验和主要结果

## 第三轮：问题定义与解法
### Problem Statement
### 代表性具体示例
### 旧方法为什么不足
### 本文如何逐步解决

## 第四轮：批判性阅读
### 已经证明的内容
### 尚未证明或证据不足的内容
### 局限与争议
### 后续研究问题

## 第一性原理与理论解释
### 信息论视角
### 表示空间或流形视角
### 优化与泛化视角

## 模型结构或研究方法
## 数据、输入输出与完整数据流
## 训练与推理或实验流程
## 张量维度或变量尺度账本
## 主要实验结果
## 代表性图表解读
## 复现清单
## 术语表
## 证据索引
```

## Writing rules

- `原文摘要翻译` is a faithful Chinese translation, not an interpretation.
- `关键贡献` states what changed, why it matters, and which evidence supports it.
- A mechanism description follows input → transformation → output → training signal.
- Tables with three or more systems/settings should be rendered as compact Markdown tables followed by interpretation.
- Tensor tables include `阶段 | 符号 | 物理意义 | 形状 | 变换 | 证据与可信度`.
- Figure explanations include visual encoding, comparison, numerical takeaway, causal limits, and relation to the paper's central claim.
- Do not merge author claims and theoretical interpretation in one unmarked paragraph.

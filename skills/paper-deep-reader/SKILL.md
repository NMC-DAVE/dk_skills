---
name: paper-deep-reader
description: Deeply read one research paper from a local PDF, URL, DOI, or arXiv ID; normalize its filename, prepare RIS and EndNote ENW records, build page-level evidence, explain methods/data/training/tensor shapes/figures, and write modular plus consolidated Chinese Markdown notes. Use for weather-AI, atmospheric science, general AI, and other scientific papers.
compatibility: Python 3.10+; PyMuPDF preferred, Poppler pdftotext/pdfimages supported as fallback; network access required for URL acquisition and authoritative metadata lookup.
---

# Paper Deep Reader

Process exactly one paper per run. The finished result is an evidence-grounded Chinese research note, not an abstract rewrite.

## Invocation

Use either form:

```text
/skill:paper-deep-reader D:/papers/paper.pdf
/skill:paper-deep-reader https://arxiv.org/abs/2609.03582
```

The user may additionally specify an output directory, paper type, focus modules, or figure preference. Defaults are: current directory, automatic type detection, deep reading, all applicable modules, representative figure pages, RIS + ENW, and a consolidated article of at least about 12,000 Chinese characters.

## Non-negotiable rules

- Resolve the paper identity before interpreting it. Prefer exact DOI/arXiv records; reject ambiguous title-only matches.
- Rename and organize the PDF only after identity resolution. Preserve input path and SHA-256 in `source_manifest.json`.
- Treat page text and captions as canonical evidence. Mark author claims, model inference, and outside explanation separately.
- Never invent tensor sizes, dataset fields, metrics, ablations, citations, or figure meanings.
- When the PDF is scanned, encrypted, incomplete, or poorly extracted, retry with available OCR/source material or stop as blocked. Do not present an abstract-only note as complete.
- Adapt the workflow to the paper type. A non-neural study must not receive fabricated architecture, training, or tensor sections.
- Scripts structure sources; the model performs the scientific interpretation and writing.

## Workflow

### 1. Ingest and organize

From this skill directory run:

```bash
python scripts/paper_pipeline.py ingest "<source>" --output-root "<output-parent>"
```

For a local PDF with a known arXiv identity, add `--arxiv-id <id>`. Local PDFs are moved into the canonical run directory by default; add `--copy-local` only when the user asks to preserve the original file.

The command must produce the directory contract in [output-contract.md](references/output-contract.md). Run the ingestion validator before reading:

```bash
python scripts/validate_outputs.py "<run-dir>" --stage ingest
```

### 2. Map the evidence

Read `metadata.json`, `source_manifest.json`, `evidence/extraction_report.json`, the section records, and the full paper. Build a working map containing:

- title, authors, affiliations, publication status, abstract, identifiers, links
- section outline and argument chain
- all data sources, splits, variables, resolutions, units, labels, and preprocessing
- all methods, equations, objectives, optimization details, inference steps, and computational settings
- all experiments, baselines, metrics, results, ablations, limitations, figures, and tables

Use page anchors in the form `[证据: p.12, §3.2, Fig. 4]`. Outside theory or background must be labeled `解释层` and must not be attributed to the paper.

### 3. Classify the paper

Choose one primary type:

1. weather AI / Earth-system machine learning
2. general AI method or model
3. numerical weather/climate model or parameterization
4. observational, diagnostic, statistical, or experimental atmospheric science
5. other computational or empirical research

Read [reading-checklists.md](references/reading-checklists.md) for the matching checklist. Record each requested module as `适用`, `不适用`, or `证据不足`.

### 4. Apply the four-pass reading method

1. **框架轮**: title, abstract, introduction, conclusion, headings; identify purpose, category, problem, contributions, and paper structure.
2. **机制轮**: read the full methods/data/results details; reconstruct the evidence chain.
3. **问题—解法轮**: explain the formal problem, a concrete representative example, why prior approaches fail, and how each component changes the information flow.
4. **批判轮**: separate established, partially supported, and unproven claims; identify limitations, failure modes, disputes, and follow-up work.

### 5. Write modules

Create these files under `modules/`:

1. `01-论文总结.md`
2. `02-问题定义.md`
3. `03-核心原理.md`
4. `04-模型或研究方法.md`
5. `05-数据与输入输出.md`
6. `06-训练与推理或实验流程.md`
7. `07-张量维度或变量尺度.md`
8. `08-图表解读.md`
9. `09-局限与研究问题.md`

Every applicable module must include conclusions, exact evidence anchors, a concrete example, technical detail, and a boundary between explicit facts and inference. For inapplicable modules, write a short reason and the appropriate paper-type substitute rather than padding.

For tensor reasoning, maintain a shape ledger with symbol, semantic meaning, shape, transformation, physical coordinates, source, and confidence. Use symbolic dimensions when exact numbers are unavailable.

For figures and tables, first inventory all captions, then select the panels that carry the problem statement, mechanism, data flow, main result, and strongest limitation. Explain axes, encodings, comparison, quantitative takeaway, and what the graphic does not establish.

### 6. Synthesize the final article

Follow [report-template.md](references/report-template.md). Integrate rather than concatenate: remove repetition, normalize terminology and symbols, and connect methods to observed result patterns. Include compact Markdown tables for important multi-system comparisons.

Default depth is at least about 12,000 Chinese characters when source evidence supports it. Do not inflate short papers with generic prose.

### 7. Review and validate

Perform two model-led reviews before script validation:

- **Evidence review**: cross-check every central quantitative claim, model/data detail, equation, and figure/table reference against the PDF.
- **Readability review**: remove mechanical translation, repeated conclusions, unexplained symbols, and mixed-language fragments while preserving proper nouns.

Then run:

```bash
python scripts/validate_outputs.py "<run-dir>" --stage final
python -m pytest -q tests
```

Revise until validation passes. Report a run as complete only when the canonical PDF, RIS, ENW, evidence layer, nine modules, final article, and validation result all exist.

# Output contract

A successful run creates one canonical paper directory:

```text
<output-parent>/<paper-slug>/
├── source/<Official Title>.pdf
├── reference/<Official Title>.ris
├── reference/<Official Title>.enw
├── metadata.json
├── source_manifest.json
├── evidence/
│   ├── full_text.md
│   ├── sections.jsonl
│   ├── evidence_index.jsonl
│   ├── extraction_report.json
│   └── figures/page-XX.png
├── modules/
│   ├── 01-论文总结.md
│   ├── 02-问题定义.md
│   ├── 03-核心原理.md
│   ├── 04-模型或研究方法.md
│   ├── 05-数据与输入输出.md
│   ├── 06-训练与推理或实验流程.md
│   ├── 07-张量维度或变量尺度.md
│   ├── 08-图表解读.md
│   └── 09-局限与研究问题.md
└── <Official Title>--中文深度解读.md
```

## Metadata authority

Use the following priority:

1. exact arXiv or DOI record explicitly identified by the source
2. exact publisher/official project record
3. title match with similarity >= 0.92 plus matching author and year
4. PDF front matter

Do not use a DOI found in references as the paper DOI. If authoritative metadata and the PDF title disagree below the threshold, stop for confirmation.

## Evidence records

`sections.jsonl` contains one record per page with `page`, current `section`, headings, and full text.

`evidence_index.jsonl` records section headings, figure captions, and table captions. Each entry uses:

```json
{"type":"figure","page":2,"section":"2. WeatherNext 3","figure_or_table_id":"Figure 1","text":"...","source_status":"paper-explicit"}
```

Claims in notes use one of:

- `[证据: p.4, §2.2]`
- `[证据: p.11, Fig. 2]`
- `[证据: p.5, Table 1]`
- `[推断: 由 Eq. (3) 与 Table 1 推导]`
- `[解释层: 信息论视角，并非作者原话]`

## Bibliography

RIS and ENW must be generated from the same `metadata.json`. Omit unavailable fields. Include all authors as separate fields and include the canonical local PDF attachment path. Never invent journal information for a preprint.

## Completion states

- `blocked`: identity, PDF access, encryption, or extraction quality prevents reliable reading.
- `ingested`: canonical PDF, metadata, bibliography, and evidence exist and pass ingestion validation.
- `drafted`: all modules and final article exist but have not passed both reviews and final validation.
- `complete`: both model-led reviews and `validate_outputs.py --stage final` pass.

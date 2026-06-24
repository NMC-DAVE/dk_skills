---
name: deep-reading-assistant
description: Generate complete Chinese Markdown book notes from a book, manuscript, PDF, EPUB, text export, or existing reading-note draft. Use when the user asks to read a book deeply, create a book-note outline, recommendation, author bio, chapter synopsis, detailed section-by-section reading notes, reflective conclusion, or assemble those parts into a polished long-form Markdown reading note.
---

# Deep Reading Assistant

## Overview

Create a complete Chinese Markdown reading note through separate generation passes, then integrate the parts into one coherent article. Favor accurate comprehension, plain but engaging prose, and a finished Markdown file that reads like an essay rather than a checklist.

If the user provides an example reading note or says to follow a previous format, inspect it first and mirror its structural pattern. For the default format, see `references/final-note-format.md`.

## Inputs

Identify the source material before writing:

- Full book or manuscript: read the whole source, extract structure, themes, characters or arguments, and key evidence.
- PDF/EPUB/DOCX/image scans: extract text with the appropriate document tools; preserve chapter order and note uncertain OCR.
- Existing generated note: use it as a format/style reference unless the user explicitly asks to revise it as source content.
- Partial excerpt: state that the output is based on the provided excerpt and avoid implying full-book coverage.

For copyrighted books, paraphrase and synthesize. Use short quotations only when they are essential, keep them brief, and do not reproduce long passages.

## Research Requirements

Verify author information with web search unless the user explicitly forbids browsing. Prefer official author pages, publisher pages, university or institutional bios, reputable interviews, and library/catalog records. If sources conflict, use cautious wording and avoid overclaiming.

For book metadata, confirm the original title, author name, publication context, edition, translator, and date when those details matter to the note. Mention uncertainty only when it affects the reader's understanding.

## Workflow

Work in distinct passes. Do not collapse all steps into one draft unless the user asks for a short version.

1. Read and map the book.
   Build a private working map of chapters, major claims, narrative arc, recurring concepts, examples, and tensions. Then draft a Chinese outline that captures the core themes without omitting important strands.

2. Write the recommendation.
   Produce one or more natural Chinese paragraphs that are plain, inviting, and spoiler-light. Explain who should read the book and why it matters without sounding promotional.

3. Write the author introduction.
   Use verified external sources. Write in natural paragraphs, not a resume list. Connect the author's background to the book only where the link is meaningful.

4. Write the content synopsis.
   Describe the main chapters in order. Use one sentence per chapter or chapter group, but output as flowing prose rather than a list.

5. Divide the book into major parts.
   Create several meaningful parts based on the book's inner logic, not necessarily the publisher's chapter divisions. Each part should have a clear title and cover a coherent argument, story movement, historical stage, or conceptual cluster.

6. Write each major part independently.
   Generate one part at a time. Each part should be at least 1200 Chinese characters unless the source is too short. Use a reading-note style: fluent, plain, example-rich, story-like, and reflective. Explain difficult ideas in everyday language. Avoid bullet lists and avoid mechanical chapter summaries.

7. Write the conclusion.
   Base it on the preceding notes. Highlight a deeper angle that an ordinary quick review might miss, and discuss contested claims or limitations when relevant. Keep the prose concise and readable in one natural paragraph.

8. Integrate and polish.
   Assemble the generated pieces into a single Markdown document. Remove repetition, normalize terms and names, smooth transitions, and ensure the final note has one consistent voice.

## Style Rules

Write in Chinese by default. Use natural paragraphs, not lists, for the recommendation, author bio, synopsis, major-part notes, and conclusion. Markdown headings are allowed and expected.

Keep the tone calm, thoughtful, and readable. Prefer concrete examples, scenes, and analogies over abstract praise. When explaining complex ideas, first give the human situation, then the concept, then the implication.

Avoid excessive spoilers in the recommendation. In the detailed notes, spoilers are allowed if needed for serious analysis.

Do not invent facts, chapter titles, publication details, author credentials, or claims not supported by the source. If the book or attachment is ambiguous, say what is known and proceed with careful assumptions.

## Final Markdown Assembly

Use the example format when provided. Otherwise use this order:

1. H1 title with the book name.
2. Optional italic metadata line for source, date, edition, or note date.
3. Recommendation paragraph.
4. Author introduction as a blockquote when it is short; use normal paragraphs if it is long.
5. `## **内容梗概**`
6. `---`
7. `## **主要内容**`
8. `***`
9. `### 第一部分：...` and subsequent major parts, separated by `***`.
10. `### **小结**`

Before final delivery, check that the outline's themes are represented in the major parts and conclusion, chapter order is not scrambled, and the final Markdown reads as one complete article.

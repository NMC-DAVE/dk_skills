# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses date-based entries.

## [Unreleased]

### Added

- Added `idl-programming`, derived from vscode-idl 6.2.2: standalone runtime detection, compact official routine index, local-help and project-routine lookup, version-aware coding guidance, compilation and assertion-based test execution. Includes standard-library-only Python helpers, mock-runtime tests, opt-in licensed IDL integration tests, and selective installation checks.

- Added `paper-deep-reader`, a single-paper deep-reading workflow with canonical PDF organization, RIS/ENW export, page-level evidence, modular Chinese notes, validation scripts, and tests.
- Added selective installation and lifecycle-management documentation for `npx skills`, including project/global and agent-specific examples.
- Added repository catalog validation (`scripts/validate_skill_catalog.py`), npm maintenance commands, contributor guidance, and GitHub Actions checks for skill discovery and tests.
- Added `writing-style-dna` (文风DNA), adapted from the open-source `writing-dna-skill`: extracts a reusable writing-style profile from a small set of user-provided samples (speeches, official documents, papers, reports), then guides AI drafting or rewriting in that style with a genre-aware anti-AI-tone whitelist. Profile artifacts live in `skills/writing-style-dna/templates/style-profile/`.
- Added `deep-reading-assistant`, a workflow skill for generating complete Chinese Markdown reading notes from books and long-form source material.
- Initialized the skills workspace structure.
- Added project documentation, changelog, Git ignore rules, and the `skills/` directory placeholder.

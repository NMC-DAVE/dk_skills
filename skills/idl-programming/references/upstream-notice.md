# Upstream provenance

Derived from https://github.com/interactive-data-language/vscode-idl, package version 6.2.2.

- Coding guidance: resources/agents/instructions/idl.instructions.md and resources/agents/prompts/IDL/idlCreate2DPlot.prompt.md.
- Discovery design: libs/mcp/language-server-tools/src/lib/globals/register-mcp-tool-search-for-routine.ts and register-mcp-tool-get-routine-docs.ts.
- Index: resources/idl/routines/routines.json; retained named idl/internal entries with /idl/ links, deduplicated by lowercase name and routine type. Source SHA-256 is recorded in routine-index.json.

Regenerate the snapshot with: node scripts/build_catalog.mjs <upstream-checkout> --output references/routine-index.json

Upstream resources are development inputs only. Installed skills do not require that checkout. The full proprietary IDL help and standard-library source are read from the local licensed installation and are not redistributed here.

## Upstream license

The MIT License (MIT)

Copyright (c) 2026, NV5 Geospatial Software, Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# AGENTS.local.md

<!-- BEGIN MANAGED MEMORY-BANK ROUTING -->
<!-- rumdl-disable MD041 -->
For "initialize memory bank", "update memory bank", or "update memory-bank", use
`memory-bank-maintenance`.
Use `memory-bank/` as project-local memory.
Use `obsidian-memory` only for explicit Obsidian-vault memory.
Do not treat Obsidian memory as current project memory unless explicitly asked.
<!-- END MANAGED MEMORY-BANK ROUTING -->

<!-- BEGIN MANAGED KNOWLEDGE-GRAPH ROUTING -->
<!-- rumdl-disable MD041 -->
- Source/calls: CodeGraph when `.codegraph/` exists; otherwise normal source
  tools.
- Docs, decisions, plans: Graphify; require curated zero-code
  `.graphifyignore`.
- Process discovery or blast radius: GitNexus when `.gitnexus/` exists and
  status succeeds.
- Commits, PRs, blame, ownership: Git/SCM.
- Graph setup/repair: `knowledge-graph-bootstrap`.
- AGENTS blocks: `agents-local-guidance`.

Do not create or refresh indexes during ordinary requests. For Graphify changes,
require staged curation, validation, diagnostics, smoke query, and snapshot
promotion; keep the accepted snapshot unless every gate passes.
<!-- END MANAGED KNOWLEDGE-GRAPH ROUTING -->

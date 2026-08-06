# Archiscope — Generic LLM Instructions

When the user asks to "expand", "zoom in", "放大", or "展开" a module, or asks about the project's architecture, use the `archiscope` CLI. The single source of truth is `.archmap.yaml` at the project root — never guess architecture from the file tree.

## Action

1. Run `archiscope render all` for the panorama; use `archiscope render "{module_path_or_alias}"` only for a focused module. When the user asks for an architecture diagram, `架构图`, or an ASCII diagram, pass `--charset ascii` and preserve Chinese labels verbatim. The ASCII panorama token avoids localized argument corruption in Windows automation
2. Show the output verbatim. The default is the `terminal / overview / depth=1` view; wrap it in a plain code block and preserve alignment. Only `--format mermaid` produces Mermaid source for a mermaid code block
3. Add a 1-3 sentence summary based on the module's `description` / `upstream` / `downstream` — never invent details

## Strategies

The default strategy is `overview`. Pick an explicit legacy terminal strategy by intent: `flow` (data flow), `blueprint` (explicit three-zone semantics or neutral inbound/hub/outbound positions), `tree` / `mindmap` (hierarchy), `heat_matrix` (coupling), `onion` / `onion_rings` (incoming dependency-count bands), `statemachine` (state transitions), `class_diagram` (interfaces), `waterfall` / `hbar_gantt` (timing), `cards` / `compact_table` / `minimal` (quick scan), `swimlane`, or `grouped`. List them with `archiscope list-strategies`.

For a complex system, `overview` uses the Vertical Layered Bus Topology and always appends an ownership tree and legend. Each logical layer supports `1..N` nodes in stable order. Width may reflow physical rows but cannot change logical layers, node order, or route class. Control fan-out, independent direct engine-mesh lanes, outer feedback, ordinary inter-layer lanes, and the isolated zone share the main canvas. Never choose a longest-path main chain, replace the graph with a relation ledger, or invent connectors between physically adjacent boxes. Each kind and direct/projected state has an independent lane; opposite directions merge only when kind and projection state both match. Use `--depth 0` for a compact domain-only view and `--depth 2` or deeper for more ownership detail.

Use `--color auto|always|never`, `--charset auto|unicode|ascii`, and `--width N` to control terminal output. Color is an enhancement only: tags, markers, frames, and line styles preserve all meaning without ANSI or Unicode.

Built-in module feature families are `orchestration / compute / data / state / authority / boundary / delivery / assurance / neutral`. Relation families are `dependency / data / command / authority / event / reference`. Project feature tokens must be registered in `semantics.features`; a custom relation kind must use an `x-` prefix and be registered in `semantics.relation_kinds`.

## Semantic proposals

The renderer never guesses business semantics from names, paths, or descriptions. To fill semantic gaps:

1. Run `archiscope semantics audit [PATH] [--json]`
2. Propose module `feature` and edge `kind` only from explicit descriptions, payloads, contracts, or documentation evidence. For each proposal state the category, evidence, reason, and `high`, `medium`, or `low` confidence. A name/path/topology-only inference must be low
3. Put proposals in a temporary semantic overlay. It may reference only existing modules and exact canonical relations and cannot change topology
4. Preview with `archiscope render "{path}" --semantic-overlay FILE`, including the classification diff and legend
5. Write a targeted `.archmap.yaml` patch only after explicit user confirmation. Never auto-commit even a high-confidence proposal

Keep unsupported modules `neutral` and relations `dependency`. Stop when an overlay conflicts with confirmed semantics.

## Errors

- Module not found: the CLI lists available modules — retry with the closest match, ask only if still ambiguous
- No `.archmap.yaml`: create a minimal skeleton (`schema: "archiscope/1.0"` plus a `root` module) and build out incrementally
- Broken or odd output: run `archiscope validate` and fix every reported error before rendering again
- Rejected semantic overlay: check exact module/relation identities, extension registration, and conflicts with confirmed `feature`, `kind`, `label`, or `payload_type`

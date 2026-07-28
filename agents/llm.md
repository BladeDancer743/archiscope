# Archiscope — Generic LLM Instructions

When the user asks to "expand", "zoom in", "放大", or "展开" a module, or asks about the project's architecture, use the `archiscope` CLI. The single source of truth is `.archmap.yaml` at the project root — never guess architecture from the file tree.

## Action

1. Run `archiscope render "{module_path}"` — accepts a module path (`demo.pipeline`), a Chinese alias defined under `aliases` in `.archmap.yaml`, or `全景` / `all` for the full topology
2. Show the output verbatim: the default render prints Mermaid source (wrap in a mermaid code block); with `--strategy` it prints terminal text art (wrap in a plain code block, keep the alignment)
3. Add a 1-3 sentence summary based on the module's `description` / `upstream` / `downstream` — never invent details

## Strategies

Pick `--strategy` by intent: `flow` (data flow), `blueprint` (geometric zones and readable connections), `tree` / `mindmap` (hierarchy), `heat_matrix` (coupling), `onion` / `onion_rings` (layering), `statemachine` (state transitions), `class_diagram` (interfaces), `waterfall` / `hbar_gantt` (timing), `cards` / `compact_table` / `minimal` (quick scan), `swimlane`, `grouped`. List all with `archiscope list-strategies`. Omit `--strategy` when the user has no preference.

## Errors

- Module not found: the CLI lists available modules — retry with the closest match, ask only if still ambiguous
- No `.archmap.yaml`: create a minimal skeleton (`schema: "archiscope/1.0"` plus a `root` module) and build out incrementally
- Broken or odd output: run `archiscope validate` and fix every reported error before rendering again

# Archiscope — AI Agent Instructions

## What You Do

When a user asks to “zoom in”, “expand”, “放大”, “展开”, or inspect a project's architecture, read the project's `.archmap.yaml` and render it with the `archiscope` CLI. The blueprint is the source of truth; do not infer architecture from the file tree.

The default render is the terminal-native `overview` at ownership `depth=1`. Mermaid is a compatibility format selected explicitly with `--format mermaid`.

## Core Commands

```bash
archiscope render all
archiscope render demo.pipeline
archiscope render all --depth 0
archiscope render all --depth 2 --width 120
archiscope render all --charset ascii --color never
archiscope render demo.pipeline --format mermaid
archiscope semantics audit
archiscope semantics audit path/to/project --json
archiscope validate
```

The render interface is:

```text
archiscope render PATH
  --format terminal|mermaid
  --strategy overview|...
  --depth N
  --color auto|always|never
  --charset auto|unicode|ascii
  --width N
  --semantic-overlay FILE
```

Display terminal output verbatim in a plain code block and preserve spacing. When the user asks for an “architecture diagram”, “架构图”, or “ASCII 图”, pass `--charset ascii`; Chinese labels remain verbatim. Put output in a Mermaid code block only when `--format mermaid` was requested. Add a short summary based only on explicit `description`, `upstream`, and `downstream` facts.

## Overview Semantics

- A root panorama expands one ownership level by default. `--depth 0` shows root domains only; `--depth 2+` opens more ownership.
- The default is the **Vertical Layered Bus Topology**（纵向分层总线拓扑）. Each logical layer supports `1..N` nodes in stable order; available width may reflow them across physical rows but never changes their logical layer, order, or route class.
- Control fan-out buses, direct engine mesh lanes, outer feedback buses, ordinary inter-layer lanes, and the isolated zone share one main canvas. Never select a longest-path main chain, replace the graph with a relation ledger, or draw a connector merely because boxes are adjacent.
- Preserve labels, including Chinese labels, verbatim. Do not translate or abbreviate them for layout.
- Every overview ends with the current-depth ownership tree and a compact legend.
- A focused container shows its ownership frame and in-scope relations. A leaf shows upstream → focus → downstream context.
- Structural `type` controls frame shape. Confirmed module `feature` controls the dot and text badge.
- Direct relations use continuous lines; projected relations use broken lines. `xN` is the number of canonical architecture relations represented, not traffic.
- Aggregation keeps source, target, semantic kind, and direct/projected status separate. Different kinds remain parallel. Opposite directions merge only when kind and projection status are equal.
- Cross-domain panorama arrows remain the curated root-level boundary; do not aggregate every deep cross-domain reference into it.

The normative layout contract is [`docs/vertical-layered-bus.md`](docs/vertical-layered-bus.md).

Color is optional. `auto` enables ANSI only on a TTY when `NO_COLOR` is absent and `TERM != dumb`; `always` and `never` override the environment. Non-TTY output under `auto` has no escape sequences. Charset `auto` uses Unicode only when the output encoding supports it and otherwise falls back to ASCII. Mermaid never contains ANSI.

## Confirmed Semantic Model

Built-in relation families are:

```text
dependency  data  command  authority  event  reference
```

Their stable tags are `[DEP]`, `[DAT]`, `[CMD]`, `[AUTH]`, `[EVT]`, and `[REF]`. Missing relation semantics fall back to `dependency`.

Built-in module feature families are:

```text
orchestration  compute  data  state  authority
boundary       delivery assurance  neutral
```

A module inherits the nearest confirmed ancestor feature unless it explicitly overrides it. Missing feature semantics fall back to `neutral`.

Projects may register feature tokens in `semantics.features`. Custom relation kinds must start with `x-`, be registered in `semantics.relation_kinds`, and map to one built-in family. The blueprint stores semantic tokens, not RGB, ANSI, or frame glyphs.

## Semantic Proposal Workflow

Rendering is deterministic and must not guess semantic categories. If classification is incomplete:

1. Run `archiscope semantics audit [PATH] [--json]`.
2. Use explicit descriptions, payloads, contracts, or documentation in the relevant directory as evidence. For every proposed module `feature` or edge `kind`, report the candidate, evidence, reason, and `high`, `medium`, or `low` confidence. A proposal based only on a name, path, or topology must be low.
3. Write proposals to a temporary semantic overlay. It may annotate only existing modules and exact canonical relations; it cannot add, delete, reverse, or reparent topology.
4. Preview with `archiscope render PATH --semantic-overlay FILE` and show the classification diff, legend, and terminal view.
5. Wait for explicit user confirmation. Only then apply a targeted patch to `.archmap.yaml`. Never auto-write even a high-confidence proposal.

An overlay conflict with confirmed `feature`, `kind`, `label`, or `payload_type` is an error. With insufficient evidence, keep the neutral/dependency fallback.

## Project Setup

```yaml
schema: "archiscope/1.0"
modules:
  root:
    label: Project Name
    type: root
    children: []
```

After any blueprint edit, run `archiscope validate` and render the affected scope once. Keep parent/children declarations symmetric, upstream/downstream references resolvable, and the ownership graph rooted and acyclic.

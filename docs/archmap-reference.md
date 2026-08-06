# `.archmap.yaml` Reference

`.archmap.yaml` is Archiscope's source of truth. Keep it at the project root so the CLI and installed Agent adapters can discover it. The blueprint stores architecture and semantic tokens; it never stores terminal colors, ANSI sequences, or drawing glyphs.

## Minimal document

```yaml
schema: "archiscope/1.0"

aliases:
  处理流水线: demo.pipeline

semantics:
  features:
    ingestion: boundary
  relation_kinds:
    x-normalized-command:
      family: command

modules:
  root:
    label: Demo Platform
    type: root
    children: [demo.gateway, demo.pipeline]
    edges:
      - from: demo.gateway
        to: demo.pipeline
        kind: x-normalized-command
        payload_type: NormalizedEvent

  demo.gateway:
    label: Gateway
    type: engine
    feature: ingestion
    parent: root
    downstream: [demo.pipeline]

  demo.pipeline:
    label: Pipeline
    type: layer
    feature: compute
    parent: root
    upstream: [demo.gateway]
```

Validate after every confirmed architecture change:

```bash
archiscope validate
```

## Top-level fields

| Field | Required | Meaning |
|---|---:|---|
| `schema` | yes | Schema identifier. Current value: `archiscope/1.0`. |
| `modules` | yes | Mapping from stable module path to module definition. |
| `aliases` | no | Human-friendly name to module path mapping. |
| `semantics` | no | Project feature and relation-kind registrations mapped to built-in visual families. |

## Module fields

| Field | Required | Meaning |
|---|---:|---|
| `label` | yes | Display name used by every renderer. |
| `type` | yes | `root`, `engine`, `layer`, `module`, `function`, or `rule`. |
| `parent` | except `root` | Parent module path. |
| `children` | when applicable | Ordered child module paths. |
| `upstream` | recommended | Modules that provide input to this module. |
| `downstream` | recommended | Modules that consume output from this module. |
| `description` | recommended | One-sentence responsibility statement and primary semantic evidence. |
| `feature` | no | Built-in module feature family or a project token registered in `semantics.features`. |
| `files` | no | Source or contract files associated with the module. |
| `functions` | no | Function or interface signatures. |
| `groups` | no | Mutually exclusive direct-child groups used by panorama, `grouped`, and explicit `blueprint` zones. |
| `lanes` | no | Mutually exclusive direct-child lane configuration used by `swimlane`. |
| `edges` | no | Explicit relations with `from`, `to`, and optional semantic metadata. |
| `internal_flow` | no | Internal steps for state and timing views. |
| `render_strategy` | no | Preferred compatibility strategy for this module. |
| `layout` | no | Mermaid direction: `TB`, `LR`, `RL`, or `BT`. |

## Semantic registries

### Module features

The built-in feature families are:

```text
orchestration  compute  data  state  authority
boundary       delivery assurance  neutral
```

They may be used directly as a module's `feature`. A project-specific name must be registered and mapped to one of those families:

```yaml
semantics:
  features:
    ingestion: boundary
    governed-store:
      family: authority

modules:
  demo.gateway:
    feature: ingestion
```

Custom feature names do not require an `x-` prefix, but they cannot redefine a built-in token.

Feature resolution is deterministic:

```text
explicit confirmed feature (built-in or registered)
    > preview overlay
    > nearest ancestor's confirmed feature
    > neutral
```

The structural `type` always controls the frame independently of feature: engine uses a double frame, layer a heavy frame, module a single frame, rule a diamond/broken frame, and function parentheses. `▾N` marks expandable children and `•` a leaf; strict ASCII uses corresponding ASCII characters.

### Relation kinds

The built-in relation kinds and visual families are fixed:

| Kind/family | Tag | Unicode connector | Meaning |
|---|---|---|---|
| `dependency` | `[DEP]` | `─────▶` | Unclassified dependency fallback |
| `data` | `[DAT]` | `─●───▶` | Data or artifact transfer |
| `command` | `[CMD]` | `─!───▶` | Command or requested action |
| `authority` | `[AUTH]` | `─◆───▶` | Approval, policy, or authority flow |
| `event` | `[EVT]` | `─○───▶` | Event or notification |
| `reference` | `[REF]` | `─◇───▶` | Reference without ownership transfer |

A project-specific relation kind must start with `x-` and be registered:

```yaml
semantics:
  relation_kinds:
    x-signed-work-order: command
    x-policy-approval:
      family: authority
```

Unknown families, unregistered extension kinds, and attempts to redefine built-ins fail validation.

Relation resolution is:

```text
confirmed edge kind > preview overlay > dependency
```

Archiscope never derives a kind from a module name, path, label, or topology.

## Relationships and explicit edges

Keep topology references symmetric and resolvable:

- If `A.downstream` contains `B`, `B.upstream` should contain `A`.
- If `A.children` contains `B`, `B.parent` must be `A`.
- Ownership is a rooted tree: children are unique, parent/children declarations are symmetric, cycles are forbidden, and every module is reachable from the single root.
- Every referenced module path and alias target must exist.
- A document has exactly one `type: root`; its stable id may be any module path.
- Group and lane members are unique direct children of the declaring module.

Use `edges` to attach confirmed semantics to a canonical relation:

```yaml
edges:
  - from: demo.gateway
    to: demo.pipeline
    kind: command
    payload_type: NormalizedEvent
    label: submit
```

`kind`, `payload_type`, and `label` are optional strings. A missing kind remains `dependency`; a missing label stays unlabeled. Multiple kinds between the same module pair are valid and render as parallel lines. The identity of a semantic line is `from + to + kind`; declaring that same identity twice is invalid.

Canonical topology and semantic-line counts are deliberately separate. Adding a second kind to an existing `from/to` pair does not add another canonical topology pair.

## Semantic audit

```bash
archiscope semantics audit
archiscope semantics audit path/to/project
archiscope semantics audit path/to/.archmap.yaml --json
```

The audit lists modules still using `neutral` and canonical relations still using `dependency`. JSON output has `modules` and `relations` sections with `total`, `classified`, and `unclassified`; modules also report `inherited`, while relations report `semantic_lines`. `relations.total` remains the exact canonical pair count even when multiple kinds increase `semantic_lines`.

Audit output is evidence of missing classification, not permission to mutate the blueprint.

## Semantic preview overlays

An overlay is a temporary proposal file:

```yaml
schema: archiscope/semantic-overlay/1.0

modules:
  demo.pipeline:
    feature: compute
    confidence: high
    evidence:
      - "description says it executes the normalized event pipeline"
    reason: "The module performs the project's computation."

edges:
  - from: demo.gateway
    to: demo.pipeline
    kind: command
    payload_type: NormalizedEvent
    label: submit
    confidence: medium
    evidence: "The versioned handoff contract names a command envelope."
    reason: "The receiver is requested to perform work."
```

A module proposal may also be the scalar feature token, for example `demo.pipeline: compute`. Confidence, when present, is `high`, `medium`, or `low`; evidence and reason may be strings or lists.

Preview it without changing `.archmap.yaml`:

```bash
archiscope render all --semantic-overlay semantic-proposal.yaml
```

An overlay:

- may reference only modules already present in `.archmap.yaml`;
- may reference only an exact canonical `from/to` pair already declared through upstream, downstream, or an edge;
- may add semantic candidates but cannot add topology, children, parents, aliases, or registry entries;
- rejects unknown fields and duplicate `from/to/kind` proposals;
- rejects a candidate that conflicts with a confirmed `feature`, `kind`, `payload_type`, or `label`.

Use explicit descriptions, payloads, contracts, or documentation as proposal evidence. A name/path/topology-only inference must be low confidence. Show the proposal, evidence, reason, classification diff, legend, and preview; write a targeted blueprint patch only after explicit user confirmation. High confidence is not auto-approval.

## Render interface

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

Defaults are `format=terminal`, `strategy=overview`, and `depth=1`. To preserve the 0.5.x Mermaid behavior, use:

```bash
archiscope render all --format mermaid
archiscope render demo.pipeline --format mermaid
```

### Overview width and focus

The default overview follows the [Vertical Layered Bus Topology](vertical-layered-bus.md). Each logical layer contains `1..N` nodes in stable order. Available width may repack a layer across physical rows, but it cannot change logical-layer membership, stable order, or route class. Labels, including Chinese labels, remain verbatim.

Control fan-out buses, direct engine mesh lanes, outer feedback buses, ordinary inter-layer lanes, and the isolated zone share the main canvas. The renderer does not choose a longest-path main chain, substitute a relation ledger for the graph, or infer connectors from physical adjacency.

Every overview appends the ownership tree at the selected depth and a compact legend. A focused container shows an ownership frame plus its in-scope relations. A leaf shows upstream → focus → downstream.

`--depth 0` renders root domains only; omitted or `--depth 1` expands one level inside each domain; `--depth 2+` continues ownership expansion.

### Projection and aggregation

The root panorama preserves the curated root-domain boundary instead of aggregating every deep cross-domain reference. Within a visible scope:

1. Hidden endpoints are lifted to their closest visible ancestor.
2. Projected self-loops and containment artifacts are discarded.
3. Aggregation uses `source, target, kind, direct/projected`.
4. Different kinds or projection states never merge.
5. Opposite directions become one bidirectional arrow only when kind and projection state match.

Continuous lines are direct; broken lines are projected. `xN` counts the canonical architecture relations represented by that semantic line, never calls, traffic, or throughput.

### Color and charset

`--color auto` enables ANSI only when stdout is a TTY, `NO_COLOR` is absent, and `TERM` is not `dumb`. Explicit `always` or `never` wins over the environment. Non-TTY auto output has no escape sequences.

`--charset auto` selects Unicode only when the output encoding supports the required glyphs; otherwise it uses ASCII. Strict ASCII keeps the textual tags and uses `- . o ! * : >` markers, so color and Unicode are never the only information channels.

ANSI foreground colors are injected only after plain-text layout, CJK width calculation, routing, and geometry checks. Every styled span resets immediately. Removing ANSI from an always-colored render produces the same visible text as `--color never`. Mermaid output never includes ANSI.

## Groups, lanes, and direction

Use explicit groups when compatibility views carry architectural zone meaning:

```yaml
modules:
  platform:
    label: Demo Platform
    type: root
    layout: LR
    children: [control, execution, authority]
    groups:
      commands:
        label: Command Plane
        modules: [control]
      work:
        label: Execution Plane
        modules: [execution]
      record:
        label: Authority Plane
        modules: [authority]
```

`blueprint` uses author-defined semantic titles only when exactly three non-empty groups are present; without them it reports neutral `INBOUND / HUB / OUTBOUND` graph positions. `onion` always reports incoming dependency-count bands, not inferred business layers.

`lanes` use `id`, `label`, and `modules`. Members must be unique direct children. They become active when `swimlane` is selected explicitly or through `render_strategy`.

## Internal flow

Timing renderers use `duration_ms`; state renderers use endpoint metadata:

```yaml
internal_flow:
  - step: receive
    duration_ms: 4
  - step: validate
    duration_ms: 12
  - step: persist
    duration_ms: 7
```

Do not invent timing values. Without `duration_ms`, Archiscope can show order but cannot make meaningful duration comparisons.

## Validation rules

The YAML validator checks document structure, root ownership, references, aliases, group/lane membership, layouts, strategy names, semantic registries, feature tokens, relation kinds, duplicate semantic lines, and overlay conflicts.

The terminal geometry engine also provides 25 rules:

| Category | Rules |
|---|---|
| Geometry | `G0_overlap`, `G0b_bleed`, `G0c_pierce`, `G0d_crossing`, `G0e_misaligned`, `G0f_truncation`, `G0g_orphan`, `G0h_sparse`, `G1_edge_share`, `G2_label_collision`, `G3_zorder`, `G4_frame_closure`, `G5_line_style`, `G6_width_adapt`, `G7_sub_boundary` |
| CJK | `C1_cjk_width`, `C2_cjk_truncation`, `C3_mix_align`, `C4_fullwidth` |
| Semantic | `S1_asymmetric`, `S2_type_mismatch`, `S3_deep_cycle`, `S4_group_orphan`, `S5_type_inversion`, `S6_dead_edge` |

## Larger examples

- [`examples/minimal.yaml`](../examples/minimal.yaml): smallest useful document.
- [`examples/medium.yaml`](../examples/medium.yaml): fictional multi-service system covering aliases, groups, lanes, edges, functions, and internal flow.
- [Strategy gallery](strategy-gallery.md): default overview, Mermaid migration, and specialized terminal views.

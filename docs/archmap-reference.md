# `.archmap.yaml` Reference

`.archmap.yaml` is Archiscope’s source of truth. Keep it at the project root so both the CLI and installed Agent adapters can discover it.

## Minimal document

```yaml
schema: "archiscope/1.0"

aliases:
  处理流水线: demo.pipeline

modules:
  root:
    label: Demo Platform
    type: root
    children: [demo.gateway, demo.pipeline]

  demo.gateway:
    label: Gateway
    type: engine
    parent: root
    downstream: [demo.pipeline]

  demo.pipeline:
    label: Pipeline
    type: layer
    parent: root
    upstream: [demo.gateway]
```

Validate after every architecture change:

```bash
archiscope validate
```

## Top-level fields

| Field | Required | Meaning |
|---|---:|---|
| `schema` | yes | Schema identifier. Current value: `archiscope/1.0`. |
| `modules` | yes | Mapping from stable module path to module definition. |
| `aliases` | no | Human-friendly name to module path mapping. |

## Module fields

| Field | Required | Meaning |
|---|---:|---|
| `label` | yes | Display name used by every renderer. |
| `type` | yes | `root`, `engine`, `layer`, `module`, `function`, or `rule`. |
| `parent` | except `root` | Parent module path. |
| `children` | when applicable | Ordered child module paths. |
| `upstream` | recommended | Modules that provide input to this module. |
| `downstream` | recommended | Modules that consume output from this module. |
| `description` | recommended | One-sentence responsibility statement. |
| `files` | no | Source files associated with the module. |
| `functions` | no | Function or interface signatures. |
| `groups` | no | Visual grouping used by `grouped`. |
| `lanes` | no | Lane configuration used by `swimlane`. |
| `edges` | no | Explicit labeled edges. |
| `internal_flow` | no | Internal steps for state and timing views. |
| `render_strategy` | no | Preferred strategy for this module. |

## Relationship invariants

Keep architecture references symmetric and resolvable:

- If `A.downstream` contains `B`, `B.upstream` should contain `A`.
- If `A.children` contains `B`, `B.parent` should be `A`.
- Every referenced module path must exist in `modules`.
- Alias values must resolve to existing module paths.
- `render_strategy` must be a registered strategy or alias.

## Internal flow

Timing renderers use `duration_ms`; state renderers use endpoint metadata.

```yaml
internal_flow:
  - step: receive
    duration_ms: 4
  - step: validate
    duration_ms: 12
  - step: persist
    duration_ms: 7
```

Do not invent timing values. When `duration_ms` is absent, Archiscope can show order but cannot make meaningful duration comparisons.

## Explicit edges

Use `edges` when a relationship needs a human-readable contract label:

```yaml
edges:
  - from: demo.gateway
    to: demo.pipeline
    label: NormalizedEvent
```

## Validation rules

The YAML validator checks document structure, module types, parent/child references, upstream/downstream references, aliases, and strategy names.

The terminal geometry engine also provides 25 rules:

| Category | Rule | Detects |
|---|---|---|
| Geometry | `G0_overlap` | Module borders overlap |
| Geometry | `G0b_bleed` | Text exceeds inner box width |
| Geometry | `G0c_pierce` | A connector crosses an unrelated module |
| Geometry | `G0d_crossing` | Unrelated connectors cross |
| Geometry | `G0e_misaligned` | Modules in a visual group drift out of alignment |
| Geometry | `G0f_truncation` | A module exceeds terminal width |
| Geometry | `G0g_orphan` | YAML module was not rendered |
| Geometry | `G0h_sparse` | Connected elements are excessively far apart |
| Geometry | `G1_edge_share` | Module borders visually merge |
| Geometry | `G2_label_collision` | Connector label collides with a box |
| Geometry | `G3_zorder` | Later drawing overwrites earlier content |
| Geometry | `G4_frame_closure` | A frame is not visually closed |
| Geometry | `G5_line_style` | Double and single line styles connect incorrectly |
| Geometry | `G6_width_adapt` | Layout breaks at another terminal width |
| Geometry | `G7_sub_boundary` | Child border touches a parent boundary |
| CJK | `C1_cjk_width` | Double-width text does not fit |
| CJK | `C2_cjk_truncation` | Truncation splits a wide character |
| CJK | `C3_mix_align` | Mixed CJK/Latin labels drift |
| CJK | `C4_fullwidth` | Full-width punctuation resembles frame lines |
| Semantic | `S1_asymmetric` | Upstream/downstream declarations disagree |
| Semantic | `S2_type_mismatch` | Edge label conflicts with expected input type |
| Semantic | `S3_deep_cycle` | Dependency cycle spans multiple modules |
| Semantic | `S4_group_orphan` | Group member is outside declared children |
| Semantic | `S5_type_inversion` | Module type hierarchy is inverted |
| Semantic | `S6_dead_edge` | Edge references a missing module |

## Larger examples

- [`examples/minimal.yaml`](../examples/minimal.yaml): smallest useful document.
- [`examples/medium.yaml`](../examples/medium.yaml): fictional multi-service system covering aliases, groups, lanes, edges, functions, and internal flow.

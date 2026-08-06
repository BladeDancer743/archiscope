# Vertical Layered Bus Topology

This document is the normative layout contract for the default Archiscope `terminal / overview` view. The formal name is **Vertical Layered Bus Topology**（**纵向分层总线拓扑**）.

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative requirements.

## Terms

- **Logical layer**: a deterministic topology rank containing one or more visible nodes. A layer is semantic geometry, not a terminal row.
- **Physical row**: one rendered row group created while packing a logical layer into the available width.
- **Stable node order**: the deterministic order of nodes within a logical layer before physical wrapping.
- **Lane**: the independently routed visual path for one aggregated relation key.
- **Bus**: a shared trunk with explicit taps used when several lanes have a structurally identical routing purpose.
- **Route class**: one of the deterministic placements used by the overview, including control fan-out, direct engine mesh, forward/inter-layer, outer feedback, and isolated placement.
- **Main canvas**: the node-and-edge drawing. The ownership tree and legend are supplementary sections, not substitutes for this canvas.
- **Isolated zone**: a named part of the main canvas for visible nodes with no visible relation at the selected depth.

## Source of truth

- The renderer **MUST** derive nodes and relations only from the validated blueprint, confirmed semantics, and an accepted preview overlay.
- The renderer **MUST NOT** infer an edge, feature, control role, or feedback meaning from a module name, path, description fragment, or physical proximity.
- Module labels, including Chinese labels, **MUST** be preserved verbatim. A renderer **MUST NOT** translate, romanize, abbreviate, or silently replace them to make layout easier.

## Logical layers and node packing

- The overview **MUST** place every visible non-isolated node in exactly one logical layer and every visible isolated node in the isolated zone.
- A logical layer **MUST** support `1..N` nodes. The topology **MUST NOT** impose a one-column or two-column semantic limit.
- Nodes within a logical layer **MUST** use stable node order. Width-dependent packing **MUST NOT** permute that order.
- The renderer **MAY** wrap one logical layer over multiple physical rows. Each physical row **SHOULD** center its complete group of boxes; an under-filled final row **SHOULD** be centered as a group.
- A logical layer with one node **SHOULD** center that node. A two-box physical row is only one possible width-dependent packing result and **MUST NOT** be treated as the topology definition.
- Structural `type` **MUST** continue to determine frame style. Confirmed `feature` **MUST** continue to determine the dot and text badge.
- The renderer **MUST NOT** select a longest path or other privileged path as a “main chain.” Layering and routing **MUST** represent the visible topology as a whole.
- Physical adjacency **MUST NOT** create an implied connector. A line or arrow **MUST** correspond to a visible canonical or projected relation.

## Buses and lanes

- All visible routed relations **MUST** remain on the main canvas. A detached relation ledger **MUST NOT** replace the graph.
- A confirmed control-style fan-out **SHOULD** use a shared vertical trunk with explicit taps to its destinations. The taps **MUST NOT** imply edges between destinations.
- Direct relations among visible `engine` nodes **SHOULD** use an engine mesh. Each relation key **MUST** retain its own lane; the mesh **MUST NOT** be simplified into an invented sequential chain.
- A relation returning to an earlier logical layer **SHOULD** use an outer feedback bus so it does not cross through node boxes or masquerade as a forward edge.
- A node without a visible relation at the selected depth **MUST** remain visible in the isolated zone. It **MUST NOT** be attached to a nearby node for visual convenience.
- Bus sharing **MAY** reduce repeated geometry only when every tap remains unambiguous. It **MUST NOT** change direction, kind, direct/projected status, or canonical count.

## Relation classification and lane identity

- Relation visuals **MUST** use the confirmed relation family: `dependency`, `data`, `command`, `authority`, `event`, or `reference`. Unclassified relations **MUST** remain `dependency`.
- The aggregation key **MUST** contain source, target, semantic kind, and direct/projected state.
- Different kinds between the same module pair **MUST** use independent parallel lanes.
- Direct and projected relations between the same module pair **MUST** use independent lanes.
- Direct lanes **MUST** use a continuous line. Projected lanes **MUST** use a broken line. `xN` **MUST** mean the number of represented canonical relations, never traffic or call volume.
- Opposite directions **MAY** merge into one bidirectional lane only when semantic kind and direct/projected state both match. Otherwise they **MUST** remain separate directed lanes.
- Each rendered lane **MUST** terminate at its actual source and target boxes or at unambiguous taps connected to those boxes. Crossing, adjacency, and shared trunks **MUST NOT** fabricate connectivity.

## Width and physical reflow

- `--width` **MAY** change box width, label wrapping, the number of boxes packed onto a physical row, and the geometry of bends and bus segments.
- Width changes **MUST NOT** change logical-layer membership, stable node order, route class, relation kind, direction, direct/projected state, or canonical count.
- If a label does not fit on one physical line, the renderer **SHOULD** wrap it inside the box while preserving its complete text and character order.
- Reflow **MUST NOT** fall back to a relation ledger, a longest-path chain, or invented adjacency edges.
- The ownership tree at the selected depth and the compact legend **MUST** remain present after the main canvas at every supported width.

## Unicode and strict ASCII

- Unicode mode **SHOULD** use type-specific box drawing, semantic markers, arrowheads, and continuous/broken line styles.
- Strict ASCII mode **MUST** preserve the same logical layers, stable node order, route classes, edge lanes, and isolated zone.
- ASCII output **MUST** retain textual semantic tags such as `[DAT]` and `[CMD]`; meaning **MUST NOT** depend on Unicode glyphs or color.
- CJK display width **MUST** be measured by terminal cell width. Wrapping and centering **MUST NOT** split a wide character or corrupt a label.

## ANSI color

- Layout, wrapping, centering, and routing **MUST** complete before ANSI sequences are injected.
- `strip_ansi(render(color=always))` **MUST** equal `render(color=never)`.
- `color=auto` **MUST** emit color only for a TTY when `NO_COLOR` is absent and `TERM != dumb`; `always` and `never` **MUST** override environment detection.
- Every styled fragment **MUST** reset promptly. ANSI state **MUST NOT** leak into padding or the next line.
- Mermaid output **MUST NOT** contain ANSI escapes.

## Determinism and stability

- The same validated model and render options **MUST** produce the same node order, layer assignment, route classification, lane aggregation, and text output.
- Changing only width **MUST** preserve logical layers, stable node order, and relation routes even when physical rows and bend coordinates change.
- Changing only color mode **MUST NOT** change printable geometry.
- Changing only charset **MUST NOT** change topology or semantic meaning.
- Renderers **SHOULD** keep buses outside node interiors and minimize crossings without violating any stronger invariant above.

## Acceptance criteria

An implementation conforms only when automated tests demonstrate all of the following:

1. A logical layer with at least three nodes renders without a two-column semantic cap; widths may pack it into different physical rows while preserving stable order.
2. Single-node and under-filled physical rows are centered as groups, including CJK labels preserved verbatim.
3. Control fan-out, direct engine mesh, outer feedback, ordinary inter-layer relations, and the isolated zone appear on the same main canvas.
4. No longest-path main chain or detached relation ledger substitutes for the topology.
5. Physically adjacent boxes without a canonical or projected relation have no connector.
6. Multiple kinds and direct/projected variants for one module pair remain separate lanes; bidirectional merge occurs only when kind and projection state match.
7. Width fixtures at 80, 100, 120, 136, and 160 columns preserve logical layers, stable node order, and route classes while allowing physical reflow.
8. Unicode and strict ASCII fixtures preserve topology and meaning, and CJK cell alignment remains valid.
9. ANSI invariants, `NO_COLOR`, non-TTY, `TERM=dumb`, prompt resets, and ANSI-free Mermaid output pass.
10. The current-depth ownership tree and compact legend remain present after the main canvas.

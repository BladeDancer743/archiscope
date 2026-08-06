"""Verification rules — 25 checks across geometry, semantic, and CJK domains."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from ..draw.grid import CharGrid, Rect, char_width, str_width


class Severity(Enum):
    CRITICAL = "critical"  # must fix, block output
    HIGH = "high"  # auto-fix
    MEDIUM = "medium"  # auto-fix, can disable
    LOW = "low"  # warning only
    INFO = "info"  # log only


@dataclass
class Violation:
    rule_id: str
    severity: Severity
    message: str
    subject: str  # which module / element
    detail: Optional[dict] = None
    fixed: bool = False


@dataclass
class VerifyContext:
    """Data needed by all rules."""

    grid: CharGrid
    boxes: dict[str, Rect]  # module_id → Rect
    edges: list[dict]  # {from, to, from_rect, to_rect, label, line_cells[]}
    groups: dict[str, list[str]]  # group_name → [module_id...]
    modules: dict  # raw YAML module data
    terminal_width: int = 80
    focus: Optional[str] = None  # module the view is centered on (double border)
    group_labels: dict[str, str] = field(default_factory=dict)
    color: bool = False  # render ANSI colors via grid.render_ansi


# ═══════════════════════════════════════════════════════════
# Geometry Rules (G1-G7)
# ═══════════════════════════════════════════════════════════


def check_overlap(ctx: VerifyContext) -> list[Violation]:
    """G0: Two boxes have overlapping cell regions."""
    violations = []
    names = list(ctx.boxes.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = ctx.boxes[names[i]], ctx.boxes[names[j]]
            if a.overlaps(b):
                violations.append(
                    Violation(
                        "G0_overlap",
                        Severity.CRITICAL,
                        f"边框重叠: {names[i]} 与 {names[j]}",
                        subject=f"{names[i]},{names[j]}",
                        detail={"box_a": names[i], "box_b": names[j], "rect_a": a, "rect_b": b},
                    )
                )
    return violations


def check_edge_share(ctx: VerifyContext) -> list[Violation]:
    """G1: Two boxes share the exact same border line (look like conjoined)."""
    violations = []
    names = list(ctx.boxes.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = ctx.boxes[names[i]], ctx.boxes[names[j]]
            if a.right == b.x or b.right == a.x:
                if a.y == b.y and a.bottom == b.bottom:
                    violations.append(
                        Violation(
                            "G1_edge_share",
                            Severity.CRITICAL,
                            f"边框黏连: {names[i]} 与 {names[j]} 共用边界",
                            subject=f"{names[i]},{names[j]}",
                        )
                    )
    return violations


def check_label_collision(ctx: VerifyContext) -> list[Violation]:
    """G2: Edge label text collides with a nearby box."""
    violations = []
    for edge in ctx.edges:
        label = edge.get("label", "")
        if not label:
            continue
        str_width(label)
        # Check if any line cell is inside a box that's not the endpoint
        line_cells = edge.get("line_cells", [])
        for lx, ly in line_cells:
            for mid, rect in ctx.boxes.items():
                if mid == edge["from"] or mid == edge["to"]:
                    continue
                if rect.contains_point(lx, ly):
                    violations.append(
                        Violation(
                            "G2_label_collision",
                            Severity.HIGH,
                            f"连线标签碰撞: '{label}' 穿过 {mid}",
                            subject=edge.get("label", ""),
                            detail={"label": label, "box": mid},
                        )
                    )
    return violations


def check_frame_closure(ctx: VerifyContext) -> list[Violation]:
    """G4: Box-drawing characters paired correctly (╔...╗, ┌...┐)."""
    violations = []
    for mid, rect in ctx.boxes.items():
        # Rect.right/bottom are exclusive (one past the last cell);
        # the actual corner characters live at x+w-1 / y+h-1.
        corners = [
            (rect.x, rect.y),
            (rect.x + rect.w - 1, rect.y),
            (rect.x, rect.y + rect.h - 1),
            (rect.x + rect.w - 1, rect.y + rect.h - 1),
        ]
        for cx, cy in corners:
            ch = ctx.grid.get(cx, cy)
            if ch == " ":
                violations.append(
                    Violation(
                        "G4_frame_closure",
                        Severity.CRITICAL,
                        f"框线断裂: {mid} 角点 ({cx},{cy}) 为空",
                        subject=mid,
                        detail={"position": (cx, cy)},
                    )
                )
    return violations


def check_bleed(ctx: VerifyContext) -> list[Violation]:
    """G0b: Label text exceeds box inner width."""
    violations = []
    for mid, rect in ctx.boxes.items():
        module = ctx.modules.get(mid, {})
        label = module.get("label", mid)
        inner_w = rect.inner_width
        label_w = str_width(label)
        if inner_w > 0 and label_w > inner_w:
            violations.append(
                Violation(
                    "G0b_bleed",
                    Severity.HIGH,
                    f"文字出血: {mid} 标签 '{label}' 宽 {label_w} > 内宽 {inner_w}",
                    subject=mid,
                    detail={"label": label, "label_width": label_w, "inner_width": inner_w},
                )
            )
    return violations


def check_pierce(ctx: VerifyContext) -> list[Violation]:
    """G0c: A line passes through a box it shouldn't."""
    violations = []
    for edge in ctx.edges:
        line_cells = edge.get("line_cells", [])
        for lx, ly in line_cells:
            for mid, rect in ctx.boxes.items():
                if mid == edge["from"] or mid == edge["to"]:
                    continue
                if rect.contains_point(lx, ly):
                    violations.append(
                        Violation(
                            "G0c_pierce",
                            Severity.CRITICAL,
                            f"线贯穿: {edge['from']}→{edge['to']} 穿过 {mid}",
                            subject=edge.get("label", f"{edge['from']}→{edge['to']}"),
                            detail={"box": mid},
                        )
                    )
    return violations


def check_crossing(ctx: VerifyContext) -> list[Violation]:
    """G0d: Two unrelated lines cross at a point."""
    violations = []
    for i in range(len(ctx.edges)):
        for j in range(i + 1, len(ctx.edges)):
            e1, e2 = ctx.edges[i], ctx.edges[j]
            cells1 = set(e1.get("line_cells", []))
            cells2 = set(e2.get("line_cells", []))
            intersections = cells1 & cells2
            if intersections:
                violations.append(
                    Violation(
                        "G0d_crossing",
                        Severity.MEDIUM,
                        f"线交叉: {e1['from']}→{e1['to']} 与 {e2['from']}→{e2['to']}",
                        subject=f"{e1.get('label', '')},{e2.get('label', '')}",
                        detail={"intersections": len(intersections)},
                    )
                )
    return violations


def check_misaligned(ctx: VerifyContext) -> list[Violation]:
    """G0e: Same-group modules not aligned."""
    violations = []
    for group_name, members in ctx.groups.items():
        if len(members) < 2:
            continue
        rects = [ctx.boxes[m] for m in members if m in ctx.boxes]
        if not rects:
            continue
        ref_y = rects[0].y
        for rect in rects:
            if rect.y != ref_y:
                violations.append(
                    Violation(
                        "G0e_misaligned",
                        Severity.MEDIUM,
                        f"未对齐: group '{group_name}' 中模块 y 坐标不一致",
                        subject=group_name,
                        detail={"ref_y": ref_y, "found_y": rect.y},
                    )
                )
    return violations


def check_truncation(ctx: VerifyContext) -> list[Violation]:
    """G0f: Content beyond grid bounds."""
    violations = []
    for mid, rect in ctx.boxes.items():
        if rect.right > ctx.grid.width:
            violations.append(
                Violation(
                    "G0f_truncation",
                    Severity.HIGH,
                    f"截断: {mid} 超出右边界 ({rect.right} > {ctx.grid.width})",
                    subject=mid,
                    detail={"right": rect.right, "grid_width": ctx.grid.width},
                )
            )
    return violations


def check_orphan(ctx: VerifyContext) -> list[Violation]:
    """G0g: Module declared but not rendered."""
    violations = []
    for mid in ctx.modules:
        if mid not in ctx.boxes:
            violations.append(
                Violation(
                    "G0g_orphan",
                    Severity.LOW,
                    f"孤立: {mid} 在 YAML 中定义但未在图中渲染",
                    subject=mid,
                )
            )
    return violations


def check_sparse(ctx: VerifyContext) -> list[Violation]:
    """G0h: Edge gap too large."""
    violations = []
    max_gap = int(ctx.terminal_width * 0.6)
    for edge in ctx.edges:
        from_rect = edge.get("from_rect")
        to_rect = edge.get("to_rect")
        if not from_rect or not to_rect:
            continue
        gap = abs(to_rect.x - from_rect.right)
        if gap > max_gap:
            violations.append(
                Violation(
                    "G0h_sparse",
                    Severity.LOW,
                    f"空荡: {edge['from']}→{edge['to']} 间距 {gap} > {max_gap}",
                    subject=edge.get("label", ""),
                    detail={"gap": gap, "max": max_gap},
                )
            )
    return violations


# ═══════════════════════════════════════════════════════════
# CJK Rules (C1-C4)
# ═══════════════════════════════════════════════════════════


def check_cjk_width(ctx: VerifyContext) -> list[Violation]:
    """C1: CJK double-width characters cause misalignment."""
    violations = []
    for mid, rect in ctx.boxes.items():
        module = ctx.modules.get(mid, {})
        label = module.get("label", mid)
        char_w = str_width(label)
        byte_len = len(label)
        if char_w != byte_len:
            # Contains CJK — verify box is wide enough
            inner = rect.inner_width
            if inner > 0 and char_w > inner:
                violations.append(
                    Violation(
                        "C1_cjk_width",
                        Severity.HIGH,
                        f"中文字符宽度: {mid} 标签显宽 {char_w} > 框内宽 {inner}",
                        subject=mid,
                        detail={
                            "display_width": char_w,
                            "inner_width": inner,
                            "byte_len": byte_len,
                        },
                    )
                )
    return violations


def check_cjk_truncation(ctx: VerifyContext) -> list[Violation]:
    """C2: Truncation point could split a multi-byte character."""
    violations = []
    for mid, rect in ctx.boxes.items():
        if rect.right > ctx.grid.width:
            # Check the cell at the truncation boundary
            x = ctx.grid.width - 1
            for y in range(rect.y, min(rect.bottom, ctx.grid.height)):
                ch = ctx.grid.get(x, y)
                if ch != " " and char_width(ch) == 0:
                    violations.append(
                        Violation(
                            "C2_cjk_truncation",
                            Severity.HIGH,
                            f"多字节截断风险: {mid} 在边界 ({x},{y}) 可能切到多字节字符",
                            subject=mid,
                            detail={"position": (x, y), "char": ch},
                        )
                    )
    return violations


def check_cjk_mix_align(ctx: VerifyContext) -> list[Violation]:
    """C3: Mixed Chinese/English labels cause visual misalignment."""
    violations = []
    widths = {}
    for mid, rect in ctx.boxes.items():
        if rect.y not in widths:
            widths[rect.y] = []
        module = ctx.modules.get(mid, {})
        label = module.get("label", mid)
        widths[rect.y].append((mid, str_width(label), len(label)))

    for y, entries in widths.items():
        if len(entries) < 2:
            continue
        # Check if mixed-width labels on same row cause visual drift
        w_values = [e[1] for e in entries]
        b_values = [e[2] for e in entries]
        if min(w_values) != max(w_values) and any(w != b for w, b in zip(w_values, b_values)):
            violations.append(
                Violation(
                    "C3_mix_align",
                    Severity.LOW,
                    f"中英混排对齐漂移: 第 {y} 行标签宽度不一致",
                    subject=f"row_{y}",
                    detail={"widths": w_values, "byte_lens": b_values},
                )
            )
    return violations


# ═══════════════════════════════════════════════════════════
# Semantic Rules (S1-S6)
# ═══════════════════════════════════════════════════════════


def check_edge_symmetry(ctx: VerifyContext) -> list[Violation]:
    """S1: A→B in edges but B's upstream doesn't include A."""
    violations = []
    for edge in ctx.edges:
        fr, to = edge["from"], edge["to"]
        to_module = ctx.modules.get(to, {})
        upstream = to_module.get("upstream", [])
        if fr not in upstream:
            violations.append(
                Violation(
                    "S1_asymmetric",
                    Severity.HIGH,
                    f"上下游不对称: {fr}→{to} 有连线, 但 {to}.upstream 未声明 {fr}",
                    subject=f"{fr}→{to}",
                    detail={"from": fr, "to": to, "upstream_declared": upstream},
                )
            )
    return violations


def check_type_contract(ctx: VerifyContext) -> list[Violation]:
    """S2: Edge data type doesn't match downstream's expected input type."""
    violations = []
    for edge in ctx.edges:
        to_module = ctx.modules.get(edge["to"], {})
        expected = to_module.get("input_type", "")
        actual = edge.get("label", "")
        if expected and actual and expected != actual:
            violations.append(
                Violation(
                    "S2_type_mismatch",
                    Severity.CRITICAL,
                    f"契约类型漂移: {edge['from']} 输出 '{actual}' 但 {edge['to']} 期望 '{expected}'",
                    subject=f"{edge['from']}→{edge['to']}",
                    detail={"expected": expected, "actual": actual},
                )
            )
    return violations


def check_deep_cycle(ctx: VerifyContext) -> list[Violation]:
    """S3: Detect dependency cycles > 2 nodes deep."""
    violations = []
    adj = {}
    for edge in ctx.edges:
        adj.setdefault(edge["from"], []).append(edge["to"])

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {m: WHITE for m in ctx.modules}

    def dfs(u, path):
        color[u] = GRAY
        for v in adj.get(u, []):
            if v not in color:
                continue
            if color[v] == GRAY:
                cycle_start = path.index(v)
                cycle = path[cycle_start:] + [v]
                if len(cycle) > 2:
                    violations.append(
                        Violation(
                            "S3_deep_cycle",
                            Severity.MEDIUM,
                            f"深层循环: {'→'.join(cycle)}",
                            subject="→".join(cycle),
                            detail={"cycle": cycle},
                        )
                    )
            elif color[v] == WHITE:
                dfs(v, path + [v])
        color[u] = BLACK

    for m in ctx.modules:
        if color.get(m) == WHITE:
            dfs(m, [m])
    return violations


def check_group_consistency(ctx: VerifyContext) -> list[Violation]:
    """S4: Group members must be in module's children list."""
    violations = []
    all_children = set()
    for mid, module in ctx.modules.items():
        for c in module.get("children", []):
            all_children.add(c)

    for group_name, members in ctx.groups.items():
        for m in members:
            if m not in all_children:
                violations.append(
                    Violation(
                        "S4_group_orphan",
                        Severity.MEDIUM,
                        f"组成员不一致: '{m}' 在 group '{group_name}' 但不在任何 children 中",
                        subject=m,
                    )
                )
    return violations


def check_type_inversion(ctx: VerifyContext) -> list[Violation]:
    """S5: function/rule should not be parent of engine/layer."""
    TYPE_ORDER = {"root": 0, "engine": 1, "layer": 2, "module": 3, "function": 4, "rule": 4}
    violations = []
    for mid, module in ctx.modules.items():
        parent = module.get("parent")
        if not parent:
            continue
        parent_module = ctx.modules.get(parent)
        if not parent_module:
            continue
        child_rank = TYPE_ORDER.get(module.get("type", "module"), 3)
        parent_rank = TYPE_ORDER.get(parent_module.get("type", "module"), 3)
        if child_rank < parent_rank:
            violations.append(
                Violation(
                    "S5_type_inversion",
                    Severity.CRITICAL,
                    f"类型倒挂: {mid}(type={module.get('type')}) 不应是 {parent}(type={parent_module.get('type')}) 的父",
                    subject=mid,
                )
            )
    return violations


def check_dead_edges(ctx: VerifyContext) -> list[Violation]:
    """S6: Edge references to/from non-existent modules."""
    violations = []
    for edge in ctx.edges:
        for endpoint in [edge["from"], edge["to"]]:
            if endpoint not in ctx.modules:
                violations.append(
                    Violation(
                        "S6_dead_edge",
                        Severity.CRITICAL,
                        f"死引用: edge 指向不存在的模块 '{endpoint}'",
                        subject=endpoint,
                    )
                )
    return violations


# ═══════════════════════════════════════════════════════════
# Additional Geometry Rules (G3, G5, G6, G7)
# ═══════════════════════════════════════════════════════════


def check_zorder(ctx: VerifyContext) -> list[Violation]:
    """G3: Later-drawn element covers earlier element's content cells."""
    violations = []
    drawn_cells = {}  # (x, y) → module_id of first writer
    for mid, rect in ctx.boxes.items():
        for y in range(rect.y, min(rect.bottom, ctx.grid.height)):
            for x in range(rect.x, min(rect.right, ctx.grid.width)):
                ch = ctx.grid.get(x, y)
                if ch != " ":
                    if (x, y) in drawn_cells:
                        prev = drawn_cells[(x, y)]
                        violations.append(
                            Violation(
                                "G3_zorder",
                                Severity.HIGH,
                                f"绘制遮盖: {mid} 覆盖了 {prev} 在 ({x},{y}) 的 '{ch}'",
                                subject=f"{mid},{prev}",
                                detail={"position": (x, y), "previous": prev, "char": ch},
                            )
                        )
                    else:
                        drawn_cells[(x, y)] = mid
    return violations


def check_line_style(ctx: VerifyContext) -> list[Violation]:
    """G5: Mixed line styles (double ║ connecting to single │)."""
    violations = []
    double_chars = set("╔╗╚╝║═╦╩╠╣╬")
    single_chars = set("┌┐└┘│─┬┴├┤┼")

    for edge in ctx.edges:
        line_cells = edge.get("line_cells", [])
        has_double = False
        has_single = False
        for x, y in line_cells:
            ch = ctx.grid.get(x, y)
            if ch in double_chars:
                has_double = True
            if ch in single_chars:
                has_single = True
        if has_double and has_single:
            violations.append(
                Violation(
                    "G5_line_style",
                    Severity.LOW,
                    f"线型不匹配: {edge['from']}→{edge['to']} 混用双层和单层线",
                    subject=edge.get("label", f"{edge['from']}→{edge['to']}"),
                )
            )
    return violations


def check_width_adapt(ctx: VerifyContext) -> list[Violation]:
    """G6: Diagram may not render correctly at different terminal widths."""
    violations = []
    test_widths = [60, 80, 100, 120]
    current = ctx.terminal_width

    if current not in test_widths:
        return []

    for w in test_widths:
        if w >= current:
            continue
        # Check: any box right edge > w?
        for mid, rect in ctx.boxes.items():
            if rect.right > w:
                violations.append(
                    Violation(
                        "G6_width_adapt",
                        Severity.MEDIUM,
                        f"宽度适配: {mid} 在 {w} 列终端会被截断 (右边界={rect.right})",
                        subject=mid,
                        detail={"terminal_width": w, "box_right": rect.right},
                    )
                )
    return violations


def check_submodule_boundary(ctx: VerifyContext) -> list[Violation]:
    """G7: Child box border coincides with parent group border."""
    violations = []
    for group_name, members in ctx.groups.items():
        for mid in members:
            if mid not in ctx.boxes:
                continue
            child_rect = ctx.boxes[mid]
            # Check if child's top/left border is on parent's border
            for other_name, other_rect in ctx.boxes.items():
                if other_name == mid:
                    continue
                if other_name in members:
                    continue
                # Check if child is fully inside the other box
                if other_rect.contains_rect(child_rect):
                    if child_rect.x == other_rect.x + 1 or child_rect.y == other_rect.y + 1:
                        violations.append(
                            Violation(
                                "G7_sub_boundary",
                                Severity.MEDIUM,
                                f"子边界穿越: {mid} 边框紧贴 {other_name} 边框",
                                subject=f"{mid},{other_name}",
                                detail={"child": mid, "parent_box": other_name},
                            )
                        )
    return violations


def check_fullwidth_interference(ctx: VerifyContext) -> list[Violation]:
    """C4: Full-width characters that look like box-drawing lines."""
    FULLWIDTH_DASHES = "－﹣‒–—―"
    violations = []
    box_chars = set("│─┌┐└┘├┤┬┴┼")

    for mid, rect in ctx.boxes.items():
        for y in range(rect.y, min(rect.bottom, ctx.grid.height)):
            for x in range(rect.x, min(rect.right, ctx.grid.width)):
                ch = ctx.grid.get(x, y)
                if any(fw in ch for fw in FULLWIDTH_DASHES):
                    neighbors = [
                        ctx.grid.get(x - 1, y),
                        ctx.grid.get(x + 1, y),
                        ctx.grid.get(x, y - 1),
                        ctx.grid.get(x, y + 1),
                    ]
                    if any(n in box_chars for n in neighbors):
                        violations.append(
                            Violation(
                                "C4_fullwidth",
                                Severity.LOW,
                                f"全角线条干扰: {mid} 在 ({x},{y}) 的全角横线贴近框线",
                                subject=mid,
                                detail={"position": (x, y), "char": ch},
                            )
                        )
    return violations


# ═══════════════════════════════════════════════════════════
# Rule Registry
# ═══════════════════════════════════════════════════════════

ALL_RULES = {
    # Geometry
    "G0_overlap": (Severity.CRITICAL, check_overlap),
    "G0b_bleed": (Severity.HIGH, check_bleed),
    "G0c_pierce": (Severity.CRITICAL, check_pierce),
    "G0d_crossing": (Severity.MEDIUM, check_crossing),
    "G0e_misaligned": (Severity.MEDIUM, check_misaligned),
    "G0f_truncation": (Severity.HIGH, check_truncation),
    "G0g_orphan": (Severity.LOW, check_orphan),
    "G0h_sparse": (Severity.LOW, check_sparse),
    "G1_edge_share": (Severity.CRITICAL, check_edge_share),
    "G2_label_collision": (Severity.HIGH, check_label_collision),
    "G3_zorder": (Severity.HIGH, check_zorder),
    "G4_frame_closure": (Severity.CRITICAL, check_frame_closure),
    "G5_line_style": (Severity.LOW, check_line_style),
    "G6_width_adapt": (Severity.MEDIUM, check_width_adapt),
    "G7_sub_boundary": (Severity.MEDIUM, check_submodule_boundary),
    # CJK
    "C1_cjk_width": (Severity.HIGH, check_cjk_width),
    "C2_cjk_truncation": (Severity.HIGH, check_cjk_truncation),
    "C3_mix_align": (Severity.LOW, check_cjk_mix_align),
    "C4_fullwidth": (Severity.LOW, check_fullwidth_interference),
    # Semantic
    "S1_asymmetric": (Severity.HIGH, check_edge_symmetry),
    "S2_type_mismatch": (Severity.CRITICAL, check_type_contract),
    "S3_deep_cycle": (Severity.MEDIUM, check_deep_cycle),
    "S4_group_orphan": (Severity.MEDIUM, check_group_consistency),
    "S5_type_inversion": (Severity.CRITICAL, check_type_inversion),
    "S6_dead_edge": (Severity.CRITICAL, check_dead_edges),
}

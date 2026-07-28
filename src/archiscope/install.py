"""Agent detection and adapter installation.

Two adapter flavors:
- SKILL_CONTENT: full SKILL.md with YAML frontmatter, for agents that load
  skills on demand (claude-code / opencode / codex). The frontmatter
  `description` is what triggers skill discovery — do not remove it.
- RULE_CONTENT: short always-on rule, for agents that inject instructions
  into every conversation (cursor / copilot). Keep it brief.

The reference copies in agents/*.md mirror these constants — update both.
"""

from pathlib import Path
from typing import TypedDict


class _RequiredInstallEntry(TypedDict):
    target: str
    content: str


class InstallEntry(_RequiredInstallEntry, total=False):
    append: bool


SKILL_CONTENT = """---
name: archiscope
description: 项目架构放大镜。当用户要求「展开」「放大」「expand」「zoom in」某个模块，查看「全景」「架构图」「数据流」「耦合」，或需要创建、更新、校验 .archmap.yaml 架构描述时使用。读取项目根目录的 .archmap.yaml，渲染聚焦的 Mermaid 图或终端文本架构视图。
---

# Archiscope 架构放大镜

`.archmap.yaml`（项目根目录）是架构的唯一真相源。回答架构问题先渲染，不要凭代码目录结构猜。

## 核心流程

1. 解析用户指的模块：模块路径（`demo.pipeline`）、中文别名（定义在 `.archmap.yaml` 顶层 `aliases`）、或 `全景` / `all`（全项目拓扑）
2. 运行 `archiscope render "{path}"`
3. 原样展示输出，不要改动任何字符：
   - 默认渲染输出 Mermaid 源码，放进 `mermaid` 围栏代码块
   - 加了 `--strategy` 输出终端文本图，放进普通围栏代码块（保留空格对齐）
4. 末尾补 1-3 句小结：该模块的职责、上游给它什么、它产出给谁。依据 YAML 里的 `description` / `upstream` / `downstream`，没有的信息不要编造

## 命令速查

| 命令 | 用途 |
|---|---|
| `archiscope render "{path}"` | 默认渲染：`全景` 出全项目拓扑，其他模块出上下文关系图 |
| `archiscope render "{path}" --strategy {名称}` | 指定视图形态（见下表） |
| `archiscope list-strategies` | 列出全部可用视图 |
| `archiscope validate` | 校验 .archmap.yaml，逐条列出错误 |

## 按意图选视图（--strategy）

| 用户想看什么 | 用哪个 |
|---|---|
| 数据流向 | `flow` |
| 几何分区与直读连接 | `blueprint` |
| 层级结构 | `tree` / `mindmap` |
| 耦合热点 | `heat_matrix` |
| 分层依赖边界 | `onion` / `onion_rings` |
| 状态流转、失败路径 | `statemachine` |
| 模块接口清单（Code Review） | `class_diagram` |
| 执行步骤与耗时（模块需定义 `internal_flow`，耗时条宽需 `duration_ms`） | `waterfall` / `hbar_gantt` |
| 快速浏览、窄终端 | `cards` / `compact_table` / `minimal` |
| 流水线分段泳道 | `swimlane` |
| 多模块按角色分组 | `grouped` |

用户没有明确要求形态时，不加 `--strategy` 用默认渲染。

## 错误处理

- **模块找不到**：CLI 会在报错里列出可用模块名，从中挑最接近的直接重试，仍无法判断再问用户
- **没有 .archmap.yaml**：按「维护」一节帮用户创建最小骨架，再逐步补模块
- **渲染结果异常或报错**：先跑 `archiscope validate`，把错误逐条修完再渲染

## 维护 .archmap.yaml

用户说「把 XX 加进架构图」「架构变了、图过时了」时，直接编辑 `.archmap.yaml`：

- 每个模块必填 `label`、`type`（root|engine|layer|module|function|rule）；非 root 必填 `parent`
- 推荐补 `upstream` / `downstream`（数据流）、`description`（一句话职责）、`files`（对应源码）
- 保持一致性：A 的 `downstream` 含 B，则 B 的 `upstream` 应含 A；`parent` 与 `children` 互相对应；被引用的模块必须已定义
- 用户常用的中文叫法加进顶层 `aliases:`（别名: 模块路径）
- 改完必须跑 `archiscope validate`，通过后再渲染一次确认

最小骨架：

```yaml
schema: "archiscope/1.0"
modules:
  root:
    label: "项目名"
    type: root
    children: []
```
"""

RULE_CONTENT = """当用户要求「展开 / 放大 / expand / zoom in」某个模块、查看「全景」或「架构图」时：

1. 运行 `archiscope render "{模块路径或别名}"`，原样展示输出（Mermaid 源码用 mermaid 代码块，文本图用普通代码块并保留对齐），补 1-2 句职责小结
2. 需要特定形态加 `--strategy`：`flow` 数据流、`blueprint` 蓝图数据流、`tree` 层级、`heat_matrix` 耦合、`statemachine` 状态机；全部见 `archiscope list-strategies`
3. 模块找不到时 CLI 会列出可用模块，选最接近的重试
4. 用户改过 `.archmap.yaml` 后先跑 `archiscope validate`

架构唯一真相源是项目根目录的 `.archmap.yaml`，不要凭代码目录猜架构。
"""

AGENT_DETECTORS = {
    "claude-code": lambda root: (root / ".claude").exists(),
    "opencode": lambda root: (root / ".opencode").exists(),
    "codex": lambda root: (root / ".codex").exists(),
    "cursor": lambda root: (root / ".cursor").exists(),
    "copilot": lambda root: (root / ".github" / "copilot-instructions.md").exists(),
}

INSTALL_MAP: dict[str, InstallEntry] = {
    "claude-code": {
        "target": ".claude/skills/archiscope/SKILL.md",
        "content": SKILL_CONTENT,
    },
    "opencode": {
        "target": ".opencode/skills/archiscope/SKILL.md",
        "content": SKILL_CONTENT,
    },
    "codex": {
        "target": ".codex/skills/archiscope/SKILL.md",
        "content": SKILL_CONTENT,
    },
    "cursor": {
        "target": ".cursor/rules/archiscope.md",
        "content": "# Archiscope\n\n" + RULE_CONTENT,
    },
    "copilot": {
        "target": ".github/copilot-instructions.md",
        "content": "## Archiscope\n\n" + RULE_CONTENT,
        "append": True,
    },
}


def find_project() -> Path | None:
    current = Path.cwd()
    while current != current.parent:
        if (current / ".archmap.yaml").exists():
            return current
        current = current.parent
    return None


def detect_agents(root: Path) -> list[str]:
    found = []
    for agent, detector in AGENT_DETECTORS.items():
        try:
            if detector(root):
                found.append(agent)
        except Exception:
            pass
    return found

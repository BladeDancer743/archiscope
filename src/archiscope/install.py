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
description: 项目架构放大镜。当用户要求「展开」「放大」「expand」「zoom in」模块，查看「全景」「架构图」「数据流」「耦合」，或需要创建、更新、校验 .archmap.yaml 时使用。读取项目根目录的 .archmap.yaml，默认渲染可展开的彩色终端字符拓扑；Mermaid 需显式选择。
---

# Archiscope 架构放大镜

`.archmap.yaml`（项目根目录）是架构的唯一真相源。回答架构问题先渲染，不要凭代码目录结构猜。

## 查看架构

1. 解析用户指的模块：模块路径（`demo.pipeline`）、中文别名（定义在 `.archmap.yaml` 顶层 `aliases`）；全项目拓扑统一向 CLI 传 ASCII 入口 `all`，避免 Windows 自动化链路损坏中文参数
2. 运行 `archiscope render "{path}"`
3. 原样展示输出，不要改动任何字符：
   - 默认输出是 `terminal / overview`，放进普通围栏代码块并保留空格和 ANSI（若调用环境支持）
   - 用户明确要求「架构图 / ASCII 图」时，必须给 render 增加 `--charset ascii`；中文 label 原样保留
   - 只有显式 `--format mermaid` 才放进 `mermaid` 围栏代码块
4. 末尾补 1-3 句小结：该模块的职责、上游给它什么、它产出给谁。依据 YAML 里的 `description` / `upstream` / `downstream`，没有的信息不要编造

## 终端通道适配

Agent 调用 CLI 时 stdout 是管道，`--color auto` 会按非 TTY 自动关色；需要彩色必须显式传参数。按宿主渲染通道选择：

| 宿主 | 渲染通道 | 推荐参数 |
|---|---|---|
| Claude Code | rich 终端，ANSI 直通（已验证） | `--color always` |
| Codex CLI | 终端 ANSI | `--color always` |
| opencode | 终端 ANSI | `--color always` |
| Cursor | VS Code 聊天面板，ANSI 支持良好，输出约 110 列 | `--color always --width 110` |
| GitHub Copilot | 聊天面板窄，ANSI 渲染不稳 | `--color never --width 90`；用户要看图时用 `--format mermaid` |

规则：

- 每次 `render` 显式带上表参数（例如 `archiscope render all --color always`），不要依赖默认值
- 输出放进普通围栏代码块，保留空格；ANSI 序列原样保留，宿主通道会决定是否上色
- 宿主不渲染 ANSI 时用 `--color never`，标签 `[DEP]`、框型、实线/断线仍表达完整信息，无色不丢语义
- 只有 `--format mermaid` 才放进 `mermaid` 围栏代码块
- 中文 label 原样保留，不因通道差异翻译或替换

## 命令速查

| 命令 | 用途 |
|---|---|
| `archiscope render all` | 默认 `terminal / overview / depth=1` 彩色字符拓扑 |
| `archiscope render all --depth 0` | 紧凑全景，只显示一级域 |
| `archiscope render all --depth 2` | 继续展开下一层所有权；可使用任意非负深度 |
| `archiscope render "{path}"` | 指定模块或别名的上下文关系图 |
| `archiscope render "{path}" --format mermaid` | 使用 0.5.x 的 Mermaid 输出方式 |
| `archiscope render "{path}" --strategy {名称}` | 指定终端视图形态（默认 `overview`） |
| `archiscope render "{path}" --color MODE` | `auto`、`always` 或 `never`，控制 ANSI 前景色 |
| `archiscope render "{path}" --theme NAME` | 配色主题（`archiscope list-themes` 查看全部） |
| `archiscope render "{path}" --color-by MODE` | 设计辅助着色：`type`（结构）/ `feature`（语义职责族）/ `heat`（耦合热力）；规则违规恒为告警色 |
| `archiscope render "{path}" --charset SET` | `auto`、`unicode` 或 `ascii`，控制字符集 |
| `archiscope render "{path}" --width N` | 按指定终端列宽布局 |
| `archiscope render "{path}" --semantic-overlay FILE` | 只预览临时语义提案，不修改蓝图 |
| `archiscope semantics audit [PATH] [--json]` | 找出仍使用 neutral/dependency fallback 的模块和关系 |
| `archiscope list-strategies` | 列出全部可用视图 |
| `archiscope validate` | 校验 .archmap.yaml，逐条列出错误 |

## 按意图选视图（--strategy）

| 用户想看什么 | 用哪个 |
|---|---|
| 数据流向 | `flow` |
| 几何分区与直读连接 | `blueprint`（显式三分组优先，否则只表达 INBOUND/HUB/OUTBOUND） |
| 层级结构 | `tree` / `mindmap` |
| 耦合热点 | `heat_matrix` |
| 依赖入度分层 | `onion` / `onion_rings` |
| 状态流转、失败路径 | `statemachine` |
| 模块接口清单（Code Review） | `class_diagram` |
| 执行步骤与耗时（模块需定义 `internal_flow`，耗时条宽需 `duration_ms`） | `waterfall` / `hbar_gantt` |
| 快速浏览、窄终端 | `cards` / `compact_table` / `minimal` |
| 流水线分段泳道 | `swimlane` |
| 多模块按角色分组 | `grouped` |

用户没有明确要求形态时使用默认 `overview`。现有脚本若需要 Mermaid，必须补 `--format mermaid`。

## 复杂全景

- 先用 `archiscope render all`：默认展开一级所有权；下方始终附当前 depth 的 ownership tree 和紧凑图例
- `overview` 的正式布局是纵向分层总线拓扑（Vertical Layered Bus Topology）：每个逻辑层允许 `1..N` 个节点并保持稳定顺序；`--width` 只改变物理折行和几何，不改变逻辑层、节点顺序或 route 分类
- 控制扇出总线、引擎 direct mesh 的独立 lane、外侧 feedback bus、普通层间 lane 和孤立区必须在同一主画布；不得选择最长路径主链，不得用关系账本替代主图，不得因物理相邻虚构连接
- 中文 label 必须原样保留，不为布局翻译、罗马化或缩写
- 深层关系投影到最近的可见祖先；只有 source、target、kind、direct/projected 都相同才聚合。`xN` 是 canonical 关系数，不是运行次数或流量
- 同一模块对的不同 kind 保留独立平行线；只有 kind 和投影状态都相同的两个方向才合并为双向箭头
- 跨域边仍使用 root 层维护的域级拓扑，不把所有深层跨域引用聚合进全景
- 图太密时用 `--depth 0` 收回到纯域总览；需要继续追所有权时用 `--depth 2` 或更深
- 用户追问所有权层级时用 `tree`，追问真实数据方向时用 `flow`，追问耦合热点时用 `heat_matrix`
- `blueprint` 没有显式三组配置时只提供拓扑分区；`onion` 只按入度分层。不得把自动分区解释成控制面、业务内核或正式依赖边界
- 需要正式语义泳道时，在对应模块定义互斥的 `groups` / `lanes`，并用 `layout: TB|LR|RL|BT` 控制 Mermaid 方向

## 语义提案与确认门

渲染器只消费已确认事实和显式 overlay，不根据名称、路径或描述猜业务语义。需要补分类时：

1. 运行 `archiscope semantics audit [PATH] [--json]`
2. 只依据明确的 `description`、payload、合同或目录内文档证据提出 module `feature` / edge `kind`；每项写出候选类别、证据、理由和 `high / medium / low` 置信度。仅凭名称、路径或拓扑的提案必须标为 low
3. 把提案写进临时 semantic overlay；overlay 只能引用现有模块和现有 canonical relation，不得创建、删除或改向拓扑
4. 用 `archiscope render "{path}" --semantic-overlay FILE` 展示分类差异、图例和预览
5. 等用户明确确认后，才用定向补丁写回 `.archmap.yaml`。即使 high confidence 也不得自动落盘

无权威证据时保持 module `neutral`、relation `dependency`。显式语义与 overlay 冲突必须停止并报告。

关系视觉标签固定为 `[DEP] / [DAT] / [CMD] / [AUTH] / [EVT] / [REF]`；颜色只是增强，无色和 ASCII 环境仍靠标签、点形、框型及实线/断线表达完整信息。

内置 module feature family 为 `orchestration / compute / data / state / authority / boundary / delivery / assurance / neutral`；relation family 为 `dependency / data / command / authority / event / reference`。项目 feature token 必须在 `semantics.features` 注册；自定义 relation kind 必须使用 `x-` 前缀并在 `semantics.relation_kinds` 映射到内置 family。

## 错误处理

- **模块找不到**：CLI 会在报错里列出可用模块名，从中挑最接近的直接重试，仍无法判断再问用户
- **没有 .archmap.yaml**：按「维护」一节帮用户创建最小骨架，再逐步补模块
- **渲染结果异常或报错**：先跑 `archiscope validate`，把错误逐条修完再渲染
- **语义 overlay 被拒绝**：检查模块/关系是否真实存在、扩展 token 是否注册，以及是否与已确认 feature/kind/label/payload_type 冲突

## 维护 .archmap.yaml

用户明确要求改变拓扑（例如“把 XX 加进架构图”）时可编辑 `.archmap.yaml`；仅补视觉语义时必须经过上一节的确认门：

- 每个模块必填 `label`、`type`（root|engine|layer|module|function|rule）；非 root 必填 `parent`
- 全文必须恰好有一个 `type: root`；根节点 ID 不要求叫 `root`
- 推荐补 `upstream` / `downstream`（数据流）、`description`（一句话职责）、`files`（对应源码）
- module 可选 `feature`；edge 可选 `kind`、`payload_type`、`label`。项目扩展 token 在顶层 `semantics` 注册并映射到内置视觉 family，蓝图中不保存 ANSI、RGB 或框线字符
- 保持一致性：A 的 `downstream` 含 B，则 B 的 `upstream` 应含 A；`parent` 与 `children` 互相对应；被引用的模块必须已定义
- `groups` / `lanes` 成员必须是该模块的唯一直属 child，不得跨组重复
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

1. 全景运行 `archiscope render all`，指定模块传路径或别名；默认输出是 `terminal / overview / depth=1`，用普通代码块原样展示。渲染时显式带终端通道参数：Claude Code / Codex / opencode 用 `--color always`；Cursor 用 `--color always --width 110`；GitHub Copilot 用 `--color never --width 90`（管道输出默认关色，要彩色必须显式传参）。用户说「架构图 / ASCII 图」时必须加 `--charset ascii`，中文 label 原样保留；只有用户需要 Mermaid 时才加 `--format mermaid` 并用 mermaid 代码块
2. 默认 `overview` 是纵向分层总线拓扑：每个逻辑层允许 `1..N` 个节点；宽度只重排物理行，不改变逻辑层、稳定节点序或 route。控制扇出、引擎 direct mesh、外侧 feedback 和孤立区在同一主画布；不得用最长路径主链、关系账本或物理相邻虚构拓扑。每个 kind 与 direct/projected 状态使用独立 lane；仅 kind 和投影状态都相同的相反方向可合并。太密用 `--depth 0`，继续展开用 `--depth 2`
3. 需要补语义时先跑 `archiscope semantics audit`。依据明确 description/payload/合同/目录证据列出候选、证据、理由和 high/medium/low；仅凭名称/路径/拓扑必须 low。先用 `--semantic-overlay FILE` 预览，用户明确确认后才定向写回，任何高置信结果也不得自动保存
4. feature family 是 orchestration/compute/data/state/authority/boundary/delivery/assurance/neutral，relation family 是 dependency/data/command/authority/event/reference；项目 token 必须注册，自定义 kind 必须是已注册的 `x-*`。overlay 只能命中现有模块和 canonical relation；无证据保持 neutral/dependency，冲突时停止
5. `.archmap.yaml` 改动后运行 `archiscope validate`；小结只依据 description/upstream/downstream，不编造业务含义

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

# Archiscope · 开发架构放大镜

[English](#quick-start) | [安装](#安装) | [视图一览](#可用视图-16-种) | [字段说明](#archmapyaml-字段说明)

**给 AI 编码 Agent 用的便携式架构可视化工具。** 输入模块路径，默认输出聚焦的 Mermaid 架构图，也可切换 16 种终端文本视图。一个 YAML 文件描述架构，任何项目、任何 Agent 即插即用。

---

## 一句话

开发时对 Agent 说「展开 demo.pipeline」，它渲染该模块的上下游关系 + 数据流向图。不用切出文档，不用翻文件夹。

---

## 安装

```bash
pip install git+https://github.com/BladeDancer743/archiscope.git
```

### 接入 Agent

```bash
# 自动检测项目中的 Agent，安装对应适配文件
archiscope install --detect

# 或手动指定
archiscope install --agents claude-code opencode codex cursor copilot
```

安装后，在这些 Agent 的对话中直接使用：Claude Code / OpenCode / Codex / Cursor / GitHub Copilot。

---

## 快速上手

**1. 创建 `.archmap.yaml`：**

```yaml
schema: "archiscope/1.0"

aliases:
  接入服务: demo.gateway
  处理流水线: demo.pipeline

modules:
  root:
    label: "Demo Event Platform"
    type: root
    children: [demo.gateway, demo.pipeline, demo.storage]

  demo.gateway:
    label: "Gateway 接入服务"
    type: engine
    parent: root
    downstream: [demo.pipeline]
    children: [demo.gateway.adapters]
    description: "接收虚构示例事件并统一输入格式"

  demo.pipeline:
    label: "事件处理流水线"
    type: layer
    parent: root
    upstream: [demo.gateway]
    children:
      - demo.pipeline.receiver
      - demo.pipeline.validator
      - demo.pipeline.throttle
```

**2. 在 Agent 对话中说：**

```
展开 处理流水线
```

Agent 调用 `archiscope render "处理流水线"` 输出架构图。

**3. 命令行直接使用：**

```bash
archiscope render demo.pipeline                     # 流水线层架构
archiscope render "全景"                             # 全项目拓扑
archiscope render demo.gateway                      # 服务级架构
archiscope render demo.pipeline --strategy heat_matrix   # 热力矩阵
archiscope render demo.gateway --strategy cards          # 卡片视图
archiscope render demo.pipeline --strategy blueprint     # 蓝图数据流
archiscope list-strategies                               # 所有可用视图
archiscope validate                                      # 校验 YAML 格式
archiscope --version                                     # 查看当前版本
```

---

## 可用视图（16 种）

| 策略 | 中文名 | 输出格式 | 一句话 |
|---|---|---|---|
| `swimlane` | 泳道视图 | 终端文本图 | 横向三泳道：预处理→执行→后处理 |
| `grouped` | 分组着色 | 终端文本图 | 按功能角色分组着色（入口/核心/出口/旁路） |
| `minimal` | 极简图 | 纯文本图 | 白底黑框，只有节点和箭头 |
| `blueprint` | 蓝图数据流 | 几何 ASCII 图 | CONTROL/CORE/PROCESS 正交分区 + 模块名直读连接 |
| `cards` | 卡片视图 | 纯文本卡 | 每个模块一张 ASCII 卡片横排 |
| `tree` | 树形缩进 | 纯文本树 | `├──` `└──` 层级树形结构 |
| `mindmap` | 思维导图 | 纯文本树 | 根模块为中心，依赖关系辐射展开 |
| `heat_matrix` | 热力矩阵 | 纯文本表 | Unicode 色块矩阵，一眼看耦合热点 |
| `flow` | 流线图 | 纯文本图 | 有向数据流：谁产数据给谁 |
| `onion` | 洋葱图 | 纯文本环 | 按依赖半径呈现内核与外围 |
| `onion_rings` | 同心圆环 | 纯文本环 | 内核→外围→外部依赖，三层环 |
| `class_diagram` | 类图 | 纯文本框 | 每个模块的方法签名 + 上下游 |
| `statemachine` | 状态机图 | 纯文本图 | 根据 `internal_flow` 展示步骤与状态端点 |
| `compact_table` | 紧凑表格 | 纯文本表 | 双栏：左模块名 ‖ 右数据流 |
| `hbar_gantt` | 水平柱状图 | 纯文本条 | `████` 宽度 ∝ 耗时 |
| `waterfall` | 调用瀑布 | 纯文本条 | 调用栈 + 每步耗时瀑布 |

全部列表：`archiscope list-strategies`

---

## 几何校验基础设施

Archiscope 内置 25 条几何、CJK 与语义规则，以及事务式修正器：

```
绘制(draw) → 验证(verify) → 修正(correct)
                  │                │
             25 条校验规则     事务批处理修正
                     ├─ 几何 15 条     ├─ shift  位移
                     ├─ CJK 4 条       ├─ resize 缩放
                     └─ 语义 6 条      ├─ reroute 绕行
                                       ├─ collapse 压缩
                                       └─ relayout 重排(兜底)
```

当前 `grouped` 与 `swimlane` 已接入几何验证/修正；其他策略共享 CJK 安全的绘图原语并直接输出。`archiscope validate` 负责 `.archmap.yaml` 的结构与引用校验。后续策略接入统一管线时，以回归测试为准，不对外暴露尚未完成的 CLI 开关。

---

## `.archmap.yaml` 字段说明

```yaml
modules:
  {模块路径}:
    label:         "显示名"                   # 必填
    type:          root|engine|layer|module|function|rule  # 必填
    parent:        {父模块路径}               # 非 root 必填
    children:      [{子模块路径}]             # 有子模块时必填
    upstream:      [{上游模块路径}]            # 推荐：谁给我数据
    downstream:    [{下游模块路径}]            # 推荐：我给谁数据
    description:   "一句话职责"               # 推荐
    files:         [对应源码文件]              # 可选
    functions:     [{函数名和签名}]            # 可选
    groups:        {视觉分组配置}              # 可选：grouped 策略用
    lanes:         [{泳道配置}]               # 可选：swimlane 策略用
    edges:         [{连线标注}]               # 可选：带 label 的边
    internal_flow: [{内部加工步骤}]            # 可选：statemachine/trace 用
    render_strategy: "策略名"                 # 可选：强制用某策略渲染
```

完整示例见 `examples/medium.yaml`；其中所有名称、路径和拓扑均为虚构演示数据。

---

## 几何校验规则（25 条）

| 类别 | 规则 | 说明 |
|---|---|---|
| 几何 | G0_overlap | 两个模块边框重叠 |
| 几何 | G0b_bleed | 标签文字超出框内宽度 |
| 几何 | G0c_pierce | 连线穿过不相关的模块 |
| 几何 | G0d_crossing | 两条不相关的线交叉 |
| 几何 | G0e_misaligned | 同组模块未对齐 |
| 几何 | G0f_truncation | 模块超出终端右边界 |
| 几何 | G0g_orphan | YAML 有定义但图中没渲染 |
| 几何 | G0h_sparse | 连线间距过大 |
| 几何 | G1_edge_share | 边框共用（视觉黏连） |
| 几何 | G2_label_collision | 连线标签碰撞盒子 |
| 几何 | G3_zorder | 绘制顺序遮盖 |
| 几何 | G4_frame_closure | 框线闭合断裂 |
| 几何 | G5_line_style | 双线 ║ 接单线 │ 不匹配 |
| 几何 | G6_width_adapt | 不同终端宽度下截断 |
| 几何 | G7_sub_boundary | 子框边界紧贴父框 |
| CJK | C1_cjk_width | 中文双宽度字符错位 |
| CJK | C2_cjk_truncation | 截断点切到多字节中间 |
| CJK | C3_mix_align | 中英混排对齐漂移 |
| CJK | C4_fullwidth | 全角横线混淆框线 |
| 语义 | S1_asymmetric | 上下游声明不对称 |
| 语义 | S2_type_mismatch | 连线数据类型和下游期望不一致 |
| 语义 | S3_deep_cycle | 深层循环依赖 |
| 语义 | S4_group_orphan | 组成员不在 children 列表中 |
| 语义 | S5_type_inversion | 类型层级倒挂 |
| 语义 | S6_dead_edge | 边指向不存在的模块 |

---

## 和 Notion / Wiki / Miro 的区别

| | Notion / Wiki | Miro / Draw.io | Archiscope |
|---|---|---|---|
| 更新方式 | 手动改图 | 手动拖拽 | 改 YAML → 自动渲染 |
| 精度 | 看画图人的细心程度 | 看画图人的细心程度 | YAML = 唯一真相源 |
| Agent 内使用 | 不支持 | 不支持 | 对话中直接 `展开` |
| 跨项目复用 | 不能 | 不能 | `.archmap.yaml` 格式通用 |
| 验证修正 | 无 | 无 | YAML 校验 + 25 条几何规则基础设施 |
| 缩放 | 无 | 手动 zoom | 按模块路径逐级聚焦 |

---

## 开发验收

项目使用 Python 标准库测试框架，不需要额外测试依赖：

```bash
python -m unittest discover -s tests -v
```

发布前同时运行 `archiscope validate`，并对 `archiscope list-strategies` 列出的全部策略执行一次 smoke test。

---

## License

MIT

# Archiscope

当用户要求「展开 / 放大 / expand / zoom in」某个模块、查看「全景」或「架构图」时：

1. 全景运行 `archiscope render all`，指定模块传路径或别名；默认输出是 `terminal / overview / depth=1`，用普通代码块原样展示。用户说「架构图 / ASCII 图」时必须加 `--charset ascii`，中文 label 原样保留；只有用户需要 Mermaid 时才加 `--format mermaid` 并用 mermaid 代码块
2. 默认 `overview` 是纵向分层总线拓扑：每个逻辑层允许 `1..N` 个节点；宽度只重排物理行，不改变逻辑层、稳定节点序或 route。控制扇出、引擎 direct mesh、外侧 feedback 和孤立区在同一主画布；不得用最长路径主链、关系账本或物理相邻虚构拓扑。每个 kind 与 direct/projected 状态使用独立 lane；仅 kind 和投影状态都相同的相反方向可合并。太密用 `--depth 0`，继续展开用 `--depth 2`
3. 需要补语义时先跑 `archiscope semantics audit`。依据明确 description/payload/合同/目录证据列出候选、证据、理由和 high/medium/low；仅凭名称/路径/拓扑必须 low。先用 `--semantic-overlay FILE` 预览，用户明确确认后才定向写回，任何高置信结果也不得自动保存
4. feature family 是 orchestration/compute/data/state/authority/boundary/delivery/assurance/neutral，relation family 是 dependency/data/command/authority/event/reference；项目 token 必须注册，自定义 kind 必须是已注册的 `x-*`。overlay 只能命中现有模块和 canonical relation；无证据保持 neutral/dependency，冲突时停止
5. `.archmap.yaml` 改动后运行 `archiscope validate`；小结只依据 description/upstream/downstream，不编造业务含义

架构唯一真相源是项目根目录的 `.archmap.yaml`，不要凭代码目录猜架构。

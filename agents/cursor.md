# Archiscope

当用户要求「展开 / 放大 / expand / zoom in」某个模块、查看「全景」或「架构图」时：

1. 运行 `archiscope render "{模块路径或别名}"`，原样展示输出（Mermaid 源码用 mermaid 代码块，文本图用普通代码块并保留对齐），补 1-2 句职责小结
2. 需要特定形态加 `--strategy`：`flow` 数据流、`blueprint` 蓝图数据流、`tree` 层级、`heat_matrix` 耦合、`statemachine` 状态机；全部见 `archiscope list-strategies`
3. 模块找不到时 CLI 会列出可用模块，选最接近的重试
4. 用户改过 `.archmap.yaml` 后先跑 `archiscope validate`

架构唯一真相源是项目根目录的 `.archmap.yaml`，不要凭代码目录猜架构。

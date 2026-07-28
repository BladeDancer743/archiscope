"""Canonical registry for public render strategies and compatibility aliases."""

PUBLIC_STRATEGIES = {
    "swimlane":      ("泳道视图", "横向三泳道：预处理→执行→后处理，适合线性流水线"),
    "grouped":       ("分组着色", "按功能角色分组着色，适合模块多的引擎图"),
    "minimal":       ("极简图", "白底黑框，只有节点和箭头，适合快速确认连接关系"),
    "blueprint":     ("蓝图数据流", "正交分区、芯片节点与直读连接，适合几何化架构审阅"),
    "statemachine":  ("状态机图", "状态变迁图，适合看失败路径和重试逻辑"),
    "mindmap":       ("思维导图", "层级辐射图，适合新人入门"),
    "class_diagram": ("类图", "模块接口清单，适合 Code Review"),
    "onion":         ("洋葱图", "三层同心图，适合看依赖边界和耦合层"),
    "heat_matrix":   ("热力矩阵", "Unicode 热力矩阵，适合看耦合热点"),
    "waterfall":     ("调用瀑布", "横向耗时瀑布图，适合性能分析和调试"),
    "cards":         ("卡片视图", "每模块一张 ASCII 卡片横排，适合小屏快速浏览"),
    "compact_table": ("紧凑表格", "双栏布局，左模块右数据流，适合窄终端"),
    "hbar_gantt":    ("水平柱状图", "水平柱状甘特图，适合看执行时序和耗时"),
    "tree":          ("树形缩进", "纯文本树形结构，适合深层嵌套浏览"),
    "flow":          ("流线图", "有向流线图，适合看数据总线流转"),
    "onion_rings":   ("同心圆环", "Unicode 同心环图，适合看分层依赖半径"),
}

# Accepted in configuration and the CLI, but omitted from the public list to
# avoid presenting implementation aliases as additional visual strategies.
STRATEGY_ALIASES = {
    "auto": "flow",
    "matrix": "heat_matrix",
}

ALL_STRATEGY_NAMES = frozenset(PUBLIC_STRATEGIES) | frozenset(STRATEGY_ALIASES)

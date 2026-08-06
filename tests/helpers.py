def sample_archmap() -> dict:
    return {
        "schema": "archiscope/1.0",
        "aliases": {"处理流程": "engine"},
        "modules": {
            "root": {
                "label": "Test System",
                "type": "root",
                "children": ["engine"],
            },
            "engine": {
                "label": "Test Engine",
                "type": "engine",
                "parent": "root",
                "children": ["engine.source", "engine.worker", "engine.sink"],
            },
            "engine.source": {
                "label": "输入源",
                "type": "module",
                "parent": "engine",
                "downstream": ["engine.worker"],
            },
            "engine.worker": {
                "label": "处理核心",
                "description": "Normalize and enrich input",
                "type": "module",
                "parent": "engine",
                "upstream": ["engine.source"],
                "downstream": ["engine.sink"],
                "functions": ["process(payload) -> result"],
                "internal_flow": [
                    {
                        "step": "解析输入",
                        "from": "raw_input",
                        "to": "parsed",
                        "duration_ms": 10,
                    },
                    {
                        "step": "写出结果",
                        "from": "parsed",
                        "to": "done",
                        "duration_ms": 20,
                    },
                ],
            },
            "engine.sink": {
                "label": "结果库",
                "type": "module",
                "parent": "engine",
                "upstream": ["engine.worker"],
            },
        },
    }


def sample_archmap_with_custom_root() -> dict:
    data = sample_archmap()
    root = data["modules"].pop("root")
    data["modules"]["platform"] = root
    data["modules"]["engine"]["parent"] = "platform"
    data["aliases"].update({"全景": "platform", "平台": "platform"})
    return data

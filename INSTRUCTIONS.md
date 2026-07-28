# Archiscope — AI Agent Instructions

## What You Do
When a user asks to "zoom in", "expand", "放大", "展开", or view the architecture of a module,
you read the project's `.archmap.yaml` file and render a focused Mermaid diagram.

## How It Works

1. The user says a module path like `demo.pipeline` or a Chinese alias like "处理流水线"
2. You call: `archiscope render {module_path}`
3. This reads `.archmap.yaml`, finds the module, walks its parent/children/upstream/downstream
4. Returns a Mermaid graph showing the module in context
5. You display the graph and add a brief natural-language summary of the module's role

## Supported Zoom Levels

| Level | Example Input | What Renders |
|---|---|---|
| Panorama | `全景` / `all` | All engines + data bus + top-level topology |
| Engine | `demo.gateway` / `demo.report` | A single engine's internal layers and modules |
| Layer | `demo.pipeline` / `demo.report.pipeline` | All modules within one pipeline layer |
| Module | `demo.pipeline.receiver` | One module's upstream/downstream + internal functions |

## Project Setup

A project using Archiscope needs a `.archmap.yaml` file at its root.
Start with an empty root node and build out incrementally:

```yaml
schema: "archiscope/1.0"
modules:
  root:
    label: "Project Name"
    type: root
    children: []
```

## Adding to an Existing Project

```bash
pip install git+https://github.com/BladeDancer743/archiscope.git
archiscope validate           # check .archmap.yaml format
archiscope install --detect   # install agent-specific adapter
```

## Key Rules

- Never guess module contents — always read `.archmap.yaml`
- If a module isn't found, tell the user and suggest they add it to `.archmap.yaml`
- Use `archiscope validate` when the user says they've edited the yaml
- The Mermaid graph is the deliverable; the natural-language summary is secondary

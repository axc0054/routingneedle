# Routing Test Fixture T-26

You are advising on how to initialize a new project within the Remote Access Vault governance system.

The vault maintains a canonical project scaffold at:

```
00_Control_Plane/Templates/Project/
  00_Project_Index.md
  01_Initiation.md
  02_Planning.md
  03_Execution.md
  04_Monitoring_and_Control.md
  05_Closing.md
  README.md
```

Each file follows the structure: template-level frontmatter → `## Instance Skeleton` (the YAML frontmatter to use in instances) → `## Instance Body` (the markdown content to use in instances). Placeholders follow the `<PLACEHOLDER>` convention.

Two tools exist in `00_Control_Plane/Tools/`:

- **`new_project.py`** — extracts Instance Skeleton and Instance Body from each template file, fills all `<PLACEHOLDER>` fields, and writes the 6 scaffold files to the correct destination directory. Accepts a `scope` argument:
  - `system` → `00_Control_Plane/System_Projects/<ProjectName>/`
  - `domain` → `02_Domains/<DomainName>/Projects/<ProjectName>/`

- **`close_project.py`** — reads a completed project's `03_Execution.md` and `05_Closing.md`, extracts session steps, deliverables, gaps, and drifts, and generates a reusable playbook written to `00_Control_Plane/Templates/System/<project-id>-playbook.md`.

The `Templates/Project/README.md` tracks all known project instances in a **Known Project Instances** table. `new_project.py` registers new projects there automatically.

---

## Challenge

**Q1:** A new system governance project needs to be initialized. What is the correct source for the scaffold files, and how should it be created?

**Q2:** An operator manually copies the scaffold from an existing project — for example, by copying the 6 files from `System_Projects/Storage_Infrastructure/` and renaming them. What is the risk of this approach compared to using `new_project.py`?

**Q3:** The project has completed — `05_Closing.md` is fully populated and `03_Execution.md` contains a complete session chronology. What is the next step, and what does it produce?

**Q4:** A project produces homelab hardware commissioning work for a new Dell PowerEdge node. Should it be initialized under `00_Control_Plane/System_Projects/` or `02_Domains/`? What scope argument does `new_project.py` take?

---

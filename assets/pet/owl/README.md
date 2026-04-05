# Owl Pet Assets

Drop Gemini-generated transparent PNG files in this folder using these exact names:

- `idle.png`
- `thinking.png`
- `talking.png`
- `auto_running.png`
- `paused.png`
- `error.png`

Recommended export guidelines:

- Transparent background
- Final canvas: `68x68` or `136x136`
- Keep the owl centered
- Keep all states on a consistent framing
- Use the same silhouette and palette across states
- Favor large shapes over tiny feather detail

Runtime load order:

1. `mods/STS2_MCP.assets/pet/owl/<state>.png`
2. `mods/pet/owl/<state>.png`
3. Generated fallback art inside the DLL

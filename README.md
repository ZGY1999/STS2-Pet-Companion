<p align="center">
  <img src="docs/teaser.png" alt="STS2 Pet Companion" width="90%" />
</p>

<p align="center"><em>Pet companion, advice mode, and auto-play tooling for Slay the Spire 2.</em></p>

<p align="center">
  <a href="./README.zh-CN.md">简体中文</a>
</p>

STS2 Pet Companion is a mod for [Slay the Spire 2](https://store.steampowered.com/app/2868840/Slay_the_Spire_2/) that exposes game state over localhost, lets external tools take actions, and adds an in-game pet overlay for `pause`, `advise`, and `auto` modes.

This repository is a fork of [Gennadiyev/STS2MCP](https://github.com/Gennadiyev/STS2MCP). It keeps the original MCP bridge idea and extends it with the pet companion UI, a Python orchestrator, and auto-play workflows.

> [!warning]
> This mod lets external programs read and control your game through a localhost API. Use it on runs you are comfortable experimenting with.

> [!caution]
> Multiplayer support is beta. If you hit a multiplayer issue, disable the mod first and confirm the issue still happens before reporting it as a game bug.

## What You Get

- Local HTTP API for reading game state and sending actions
- In-game pet companion overlay with visible mode and message bubbles
- `pause`, `advise`, and `auto` companion modes
- Optional MCP server for Claude Desktop / Claude Code
- Python orchestrator for polling state, generating advice, and executing actions

## Quick Start

### 1. Build the mod

Prerequisites:

- Windows
- Slay the Spire 2
- [.NET 9 SDK](https://dotnet.microsoft.com/download/dotnet/9.0)

Clone the repository, then build the DLL:

```powershell
git clone https://github.com/ZGY1999/STS2-Pet-Companion.git
cd .\STS2-Pet-Companion
.\build.ps1 -GameDir "<Your Slay the Spire 2 install folder>"
```

You can also set the game path once for the current shell:

```powershell
$env:STS2_GAME_DIR = "<Your Slay the Spire 2 install folder>"
.\build.ps1
```

The build output will be placed in:

```text
out/STS2_MCP/STS2_MCP.dll
mod_manifest.json
out/STS2_MCP/STS2_MCP.assets  (if assets are present)
```

### 2. Install the mod into the game

Copy these files into `<game_install>/mods/`:

```text
out/STS2_MCP/STS2_MCP.dll            -> <game_install>/mods/STS2_MCP.dll
mod_manifest.json                    -> <game_install>/mods/STS2_MCP.json
out/STS2_MCP/STS2_MCP.assets         -> <game_install>/mods/STS2_MCP.assets
```

### 3. Launch and verify

1. Start the game.
2. Enable the mod if the game asks for consent on first launch.
3. Start or load a run.
4. Confirm the local API is live at `http://127.0.0.1:15526/`.

If the mod is loaded correctly, the game should expose:

- `GET /api/v1/singleplayer`
- `GET /api/v1/pet/status`
- `POST /api/v1/pet/mode`
- `POST /api/v1/pet/message`

## Running the Pet Companion

The pet companion has three modes:

- `pause`: do not poll game state and do not call a model
- `advise`: read state and show advice in the pet bubble
- `auto`: read state, plan one action, narrate it, then execute it

### Fastest smoke test

If you only want to verify the pipeline works, use the deterministic provider first. It does not need an API key.

```powershell
cd .\orchestrator
Copy-Item .\sts2_pet.toml.example .\sts2_pet.toml
python -m pip install -e .
python -m sts2_pet.cli --mode advise
```

### Config file

The orchestrator reads config in this order:

- built-in defaults
- `sts2_pet.toml`
- environment variables
- CLI flags

Start by copying the example file:

```powershell
cd .\orchestrator
Copy-Item .\sts2_pet.toml.example .\sts2_pet.toml
```

Minimal deterministic config:

```toml
provider_name = "deterministic"
poll_interval_seconds = 0.75
timeout_seconds = 90

game_base_url = "http://127.0.0.1:15526"
pet_base_url = "http://127.0.0.1:15526"
```

Example OpenAI-compatible config:

```toml
provider_name = "openai_compatible"
poll_interval_seconds = 0.75
timeout_seconds = 90

game_base_url = "http://127.0.0.1:15526"
pet_base_url = "http://127.0.0.1:15526"

[provider]
api_key = "your-key"
base_url = "https://your-gateway.example/v1"
model = "gpt-4.1-mini"
```

Example local Codex CLI config:

```toml
provider_name = "codex_cli"
poll_interval_seconds = 0.75
timeout_seconds = 90

[provider]
codex_cmd = "codex.cmd"
codex_model = "gpt-5-codex"
```

### Start commands

```powershell
cd .\orchestrator
python -m pip install -e .
python -m sts2_pet.cli --mode advise
python -m sts2_pet.cli --mode auto
python -m sts2_pet.cli --mode advise --once
```

Shortcut scripts are also included:

- `orchestrator/start-pet-advise.cmd`
- `orchestrator/start-pet-auto.cmd`

## Optional MCP Server

If you want to connect the game to Claude via MCP, use the server in [`mcp/`](./mcp).

Requirements:

- [Python 3.11+](https://www.python.org/)
- [uv](https://docs.astral.sh/uv/)

Example MCP config:

```json
{
  "mcpServers": {
    "sts2": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/STS2-Pet-Companion/mcp", "python", "server.py"]
    }
  }
}
```

Useful docs:

- [MCP tool reference](./mcp/README.md)
- [Simplified raw state examples](./docs/raw-simplified.md)
- [Full raw state examples](./docs/raw-full.md)

## Development

### Build

```powershell
.\build.ps1 -GameDir "<Your Slay the Spire 2 install folder>"
```

### C# tests

```powershell
dotnet test .\tests\STS2_MCP.Tests\STS2_MCP.Tests.csproj
```

### Python tests

```powershell
python -m pytest .\orchestrator\tests -q
```

## Notes for Contributors

- The player-facing entry point is this README.
- MCP tools live in [`mcp/server.py`](./mcp/server.py).
- The pet companion orchestrator lives in [`orchestrator/src/sts2_pet`](./orchestrator/src/sts2_pet).
- C# tests live in [`tests/STS2_MCP.Tests`](./tests/STS2_MCP.Tests).
- Python tests live in [`orchestrator/tests`](./orchestrator/tests).

## License

MIT

## Credits

- Original project: [Gennadiyev/STS2MCP](https://github.com/Gennadiyev/STS2MCP)
- This fork extends the original bridge with the pet companion overlay and orchestrator workflow

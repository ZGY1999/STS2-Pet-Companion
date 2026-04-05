# STS2 Pet Companion

[English README](./README.md)

这是一个面向 **Slay the Spire 2** 的 Mod。它会把游戏状态通过本地 HTTP API 暴露出来，并在游戏里加入一个宠物伴侣界面，用于显示 `pause`、`advise`、`auto` 三种模式下的状态、建议和自动执行反馈。

这个仓库基于 [Gennadiyev/STS2MCP](https://github.com/Gennadiyev/STS2MCP) 继续开发，保留了原始 MCP bridge 思路，并在此基础上加入了宠物伴侣 UI、Python orchestrator 和自动代打工作流。

> [!warning]
> 这个 Mod 允许外部程序通过 localhost 读取和控制你的游戏。请在你愿意实验的存档或局里使用。

> [!caution]
> 多人模式仍处于 beta。遇到联机问题时，请先关闭本 Mod，再确认问题是否仍然存在。

## 你能得到什么

- 本地 HTTP API，可读取游戏状态并发送动作
- 游戏内宠物伴侣覆盖层，可显示当前模式和气泡消息
- `pause`、`advise`、`auto` 三种模式
- 可选 MCP server，可连接 Claude Desktop / Claude Code
- Python orchestrator，可轮询状态、生成建议并执行动作

## 快速开始

### 1. 构建 Mod

前置要求：

- Windows
- 已安装 Slay the Spire 2
- 已安装 [.NET 9 SDK](https://dotnet.microsoft.com/download/dotnet/9.0)

先克隆仓库，再构建 DLL：

```powershell
git clone https://github.com/ZGY1999/STS2-Pet-Companion.git
cd .\STS2-Pet-Companion
.\build.ps1 -GameDir "<你的 Slay the Spire 2 安装目录>"
```

也可以先在当前 PowerShell 会话中设置环境变量：

```powershell
$env:STS2_GAME_DIR = "<你的 Slay the Spire 2 安装目录>"
.\build.ps1
```

构建产物会出现在：

```text
out/STS2_MCP/STS2_MCP.dll
mod_manifest.json
out/STS2_MCP/STS2_MCP.assets  （如果存在资源文件）
```

### 2. 安装到游戏目录

把下面这些文件复制到 `<game_install>/mods/`：

```text
out/STS2_MCP/STS2_MCP.dll            -> <game_install>/mods/STS2_MCP.dll
mod_manifest.json                    -> <game_install>/mods/STS2_MCP.json
out/STS2_MCP/STS2_MCP.assets         -> <game_install>/mods/STS2_MCP.assets
```

### 3. 启动并确认 Mod 正常工作

1. 启动游戏。
2. 如果游戏首次询问是否启用 Mod，请确认启用。
3. 开始或加载一局游戏。
4. 确认本地接口已启动：`http://127.0.0.1:15526/`

如果 Mod 加载成功，应该能访问这些接口：

- `GET /api/v1/singleplayer`
- `GET /api/v1/pet/status`
- `POST /api/v1/pet/mode`
- `POST /api/v1/pet/message`

## 运行宠物伴侣

宠物伴侣有三种模式：

- `pause`：不轮询状态，不调用模型
- `advise`：读取当前状态，在宠物气泡中显示建议
- `auto`：读取当前状态，规划一个动作并执行

### 最快验证方式

如果你只是想先确认整条链路能跑起来，建议先用 `deterministic` provider。它不需要 API key。

```powershell
cd .\orchestrator
Copy-Item .\sts2_pet.toml.example .\sts2_pet.toml
python -m pip install -e .
python -m sts2_pet.cli --mode advise
```

### 配置文件

orchestrator 的配置优先级是：

- 内置默认值
- `sts2_pet.toml`
- 环境变量
- CLI 参数

先复制模板：

```powershell
cd .\orchestrator
Copy-Item .\sts2_pet.toml.example .\sts2_pet.toml
```

最小 deterministic 配置：

```toml
provider_name = "deterministic"
poll_interval_seconds = 0.75
timeout_seconds = 90

game_base_url = "http://127.0.0.1:15526"
pet_base_url = "http://127.0.0.1:15526"
```

OpenAI 兼容网关示例：

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

本地 Codex CLI 示例：

```toml
provider_name = "codex_cli"
poll_interval_seconds = 0.75
timeout_seconds = 90

[provider]
codex_cmd = "codex.cmd"
codex_model = "gpt-5-codex"
```

### 启动命令

```powershell
cd .\orchestrator
python -m pip install -e .
python -m sts2_pet.cli --mode advise
python -m sts2_pet.cli --mode auto
python -m sts2_pet.cli --mode advise --once
```

仓库里也提供了快捷脚本：

- `orchestrator/start-pet-advise.cmd`
- `orchestrator/start-pet-auto.cmd`

## 可选：MCP Server

如果你想把游戏接到 Claude 的 MCP 工作流，可以使用 [`mcp/`](./mcp) 里的 server。

前置要求：

- [Python 3.11+](https://www.python.org/)
- [uv](https://docs.astral.sh/uv/)

示例 MCP 配置：

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

可参考的文档：

- [MCP 工具说明](./mcp/README.md)
- [简化版原始状态示例](./docs/raw-simplified.md)
- [完整版原始状态示例](./docs/raw-full.md)

## 开发与测试

### 构建

```powershell
.\build.ps1 -GameDir "<你的 Slay the Spire 2 安装目录>"
```

### C# 测试

```powershell
dotnet test .\tests\STS2_MCP.Tests\STS2_MCP.Tests.csproj
```

### Python 测试

```powershell
python -m pytest .\orchestrator\tests -q
```

## 给贡献者的入口

- 玩家入口文档就是这个 README
- MCP 工具定义在 [`mcp/server.py`](./mcp/server.py)
- 宠物伴侣 orchestrator 在 [`orchestrator/src/sts2_pet`](./orchestrator/src/sts2_pet)
- C# 测试在 [`tests/STS2_MCP.Tests`](./tests/STS2_MCP.Tests)
- Python 测试在 [`orchestrator/tests`](./orchestrator/tests)

## 许可证

MIT

## 致谢

- 原始项目：[Gennadiyev/STS2MCP](https://github.com/Gennadiyev/STS2MCP)
- 当前 fork 在原始 bridge 基础上扩展了宠物伴侣覆盖层与 orchestrator 工作流

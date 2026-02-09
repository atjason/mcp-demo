# 本地集成方式说明

本项目支持两种方式使用本地 MCP 能力：

## 1. 本地代码集成（默认，stdio）

客户端直接启动各 server 脚本为子进程，通过标准输入/输出通信。

- **启动**：只启动 client 即可，server 由 client 按需拉起。
  ```bash
  python client/client.py
  ```
- **配置**：无需额外配置。

## 2. 本地接口集成（REST / Streamable HTTP）

MCP 服务以 HTTP 形式暴露，客户端通过 URL 调用，适合与现有 REST 服务、网关或其它语言进程集成。

### 启动 MCP 服务（HTTP）

每个 server 单独进程、不同端口，按需启动：

```bash
# 终端 1：hello 服务 → http://127.0.0.1:8001/mcp
MCP_TRANSPORT=streamable-http MCP_PORT=8001 python server/server.py

# 终端 2：time 服务 → http://127.0.0.1:8002/mcp
MCP_TRANSPORT=streamable-http MCP_PORT=8002 python server/server2.py

# 终端 3：weather 服务 → http://127.0.0.1:8003/mcp
MCP_TRANSPORT=streamable-http MCP_PORT=8003 python server/weather.py

# 终端 4：move 服务（机器人运动模拟）→ http://127.0.0.1:8004/mcp
MCP_TRANSPORT=streamable-http MCP_PORT=8004 python server/move.py
```

可选环境变量：

- `MCP_TRANSPORT`：`stdio`（默认）或 `streamable-http`
- `MCP_PORT`：HTTP 监听端口（各 server 默认 8001 / 8002 / 8003 / 8004）
- `MCP_HOST`：监听地址，默认 `127.0.0.1`

### 客户端通过 REST 连接

设置 `MCP_SERVER_URLS` 为逗号分隔的 Streamable HTTP 地址后再启动 client：

```bash
export MCP_SERVER_URLS="http://127.0.0.1:8001/mcp,http://127.0.0.1:8002/mcp,http://127.0.0.1:8003/mcp,http://127.0.0.1:8004/mcp"
python client/client.py
```

客户端会通过 REST 调用上述本地 MCP 接口，不再启动 stdio 子进程。

## 3. 远程 Qwen 演示（remote.py）

使用在线通义千问（Qwen）API 搭配本地 MCP 服务进行对话与工具调用。

- **配置**：在项目根目录创建 `config.json`（可复制 `config.json.example`），填写 `qwen` 段：
  - `api_key`：必填，百炼 API Key
  - `base_url`：可选，默认 `https://dashscope.aliyuncs.com/compatible-mode/v1`
  - `model`：可选，默认 `qwen-plus`
- **启动**：在项目根目录执行
  ```bash
  python client/remote.py
  ```
- **MCP 连接**：与上述 client 一致。未设置 `MCP_SERVER_URLS` 时使用 stdio 启动本地 server；若使用 HTTP MCP，请先启动各 server 并设置 `MCP_SERVER_URLS`。

### 用其它语言/工具调用

任何能发 HTTP 请求的客户端都可以按 [MCP Streamable HTTP](https://spec.modelcontextprotocol.io/specification/2025-01-15/transports/streamable_http/) 规范与上述端点通信；也可在本机用 curl/Postman 等调试。

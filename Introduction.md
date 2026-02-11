# MCP 技术分享：从概念到机器人应用实践

## 一、MCP 是什么？

### 1.1 定义

- Model Context Protocol (MCP) 是一个开放协议
- 允许 AI 应用与外部数据源和工具安全连接
- 标准化了 AI 与外部系统的交互方式

### 1.2 核心价值

- **标准化**：统一的协议规范，不同系统可互操作
- **安全性**：可控的权限管理和沙箱隔离
- **扩展性**：易于添加新的能力（Tools、Resources、Prompts）

### 1.3 MCP 的能力类型

- **Tools（工具）**：可执行的函数，如查询天气、控制机器人
- **Resources（资源）**：可读取的数据源
- **Prompts（提示）**：预定义的提示模板

## 二、MCP 能做什么？

### 2.1 典型应用场景

1. **信息查询**：天气、时间、数据库查询
2. **系统控制**：机器人运动、设备控制
3. **数据集成**：连接各种外部 API 和服务
4. **能力扩展**：为大模型添加特定领域能力

### 2.2 项目中的实际案例

- **hello-mcp**：基础问候功能（`server/server.py`）
- **time-mcp**：获取当前时间（`server/server2.py`）
- **weather-mcp**：查询中国城市天气（`server/weather.py`）
- **move-mcp**：机器人运动控制模拟（`server/move.py`）

## 三、MCP 的实现方式

### 3.1 本地代码集成（stdio 方式）

**特点**：

- 客户端直接启动 server 脚本为子进程
- 通过标准输入/输出通信
- 适合开发调试

**实现**：

```python
# client/client.py 中的实现
params = StdioServerParameters(
    command="python",
    args=[str(script_path)],
    cwd=_server_dir,
)
read, write = await stdio_client(params)
session = ClientSession(read, write)
```

**启动方式**：

```bash
python client/client.py  # 自动启动所有 server
```

### 3.2 本地接口集成（REST/HTTP 方式）

**特点**：

- MCP 服务以 HTTP 形式暴露
- 客户端通过 URL 调用
- 适合生产环境、多语言集成

**实现**：

```python
# server/server.py 中的实现
mcp = FastMCP(
    "hello-mcp",
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("MCP_PORT", "8001")),
)
mcp.run(transport="streamable-http")
```

**启动方式**：

```bash
# 分别启动各个服务
MCP_TRANSPORT=streamable-http MCP_PORT=8001 python server/server.py
MCP_TRANSPORT=streamable-http MCP_PORT=8002 python server/server2.py
MCP_TRANSPORT=streamable-http MCP_PORT=8003 python server/weather.py
MCP_TRANSPORT=streamable-http MCP_PORT=8004 python server/move.py

# 客户端连接
export MCP_SERVER_URLS="http://127.0.0.1:8001/mcp,http://127.0.0.1:8002/mcp,http://127.0.0.1:8003/mcp,http://127.0.0.1:8004/mcp"
python client/client.py
```

### 3.3 多个 MCP 并存

**配置方式**：

- stdio：在 `MCP_SERVERS` 列表中配置多个 server
- HTTP：在 `MCP_SERVER_URLS` 环境变量中用逗号分隔多个 URL

**工具映射**：

```python
tool_to_session: dict[str, ClientSession] = {}
# 每个工具名映射到对应的 session，实现多 MCP 统一管理
```

## 四、创建 MCP 服务

### 4.1 最简单的 MCP 示例

```python
# server/server.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("hello-mcp")

@mcp.tool()
def say_hello(name: str) -> str:
    """Say hello to someone."""
    return f"Hello, {name}!"

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

### 4.2 网络 MCP 示例（天气查询）

```python
# server/weather.py
from mcp.server.fastmcp import FastMCP
from urllib.request import urlopen

mcp = FastMCP("weather-mcp")

BASE_URL = "https://wis.qq.com/weather/common?source=pc&weather_type=observe&province={province}&city={city}&county={county}"

@mcp.tool()
def get_weather(province: str, city: str, county: str) -> str:
    """Query real-time weather for any location in China."""
    url = BASE_URL.format(province=province, city=city, county=county)
    # ... 调用 API 并格式化返回
    return formatted_result
```

### 4.3 机器人运动 MCP 示例

```python
# server/move.py
@mcp.tool()
def robot_stand() -> str:
    """让机器人站立。"""
    print("模拟：机器人站立")
    return "已执行：机器人已站立。"

@mcp.tool()
def robot_walk(direction: str, steps: int) -> str:
    """机器人行走。direction 为 forward/backward，steps 为步数。"""
    print(f"模拟：向{dir_cn}走 {steps} 步")
    return f"已执行：向{dir_cn}走 {steps} 步。"
```

## 五、MCP 在机器人交互中的应用

### 5.1 机器人能力范围

- **姿态控制**：站立、趴下
- **运动控制**：前进、后退、转向
- **模式切换**：行走模式、跑步模式
- **安全控制**：软件急停开关
- **状态查询**：获取当前状态

### 5.2 实现架构

```
用户输入 → 大模型（理解意图） → 识别工具调用 → MCP 服务执行 → 返回结果
```

### 5.3 格式化输出优化

**单一工具调用时直接返回**：

```python
# client/client.py 中的实现
if len(calls) == 1:
    call = calls[0]
    result = await session.call_tool(tname, tool_args)
    result_text = result.content[0].text if result.content else ""
    print(result_text)  # 直接输出，不再经过大模型加工
    break
```

**优势**：

- 减少延迟
- 避免大模型二次解释
- 保持原始数据准确性

## 六、大模型集成

### 6.1 本地模型（Ollama）

```python
# client/client.py
from ollama import AsyncClient

ollama = OllamaClient()
response = await ollama.chat(
    model="qwen2.5:3b",
    messages=messages,
    tools=ollama_tools,
)
```

### 6.2 在线模型（Qwen API）

```python
# client/remote.py
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=cfg["api_key"],
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)
response = await client.chat.completions.create(
    model="qwen-plus",
    messages=messages,
    tools=tools,
)
```

**配置**：

```json
// config.json
{
  "qwen": {
    "api_key": "your-api-key",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model": "qwen-plus"
  }
}
```

## 七、工具识别与参数解析

### 7.1 大模型如何识别工具？

1. **工具注册**：将 MCP tools 转换为大模型可理解的格式

```python
tools = [{
    "type": "function",
    "function": {
        "name": t.name,
        "description": t.description,
        "parameters": t.inputSchema,
    }
} for t in all_tools]
```

2. **上下文理解**：大模型根据用户输入和工具描述匹配
3. **参数提取**：从自然语言中提取结构化参数

### 7.2 提高识别精度的方法

1. **清晰的工具描述**：
   - 详细说明工具用途
   - 明确参数含义和示例
   - 包含使用场景说明

2. **参数 Schema 设计**：
   - 使用明确的类型定义
   - 提供枚举值限制
   - 添加参数说明

3. **示例优化**：

```python
@mcp.tool()
def get_weather(province: str, city: str, county: str) -> str:
    """
    Query real-time weather...
    Examples: 北京 -> province=北京, city=北京, county=朝阳区;
    上海浦东 -> province=上海, city=上海, county=浦东新区.
    """
```

## 八、MCP 信息获取

### 8.1 使用 mcp_inspect 工具

```bash
python tool/mcp_inspect.py http://127.0.0.1:8001/mcp
python tool/mcp_inspect.py http://127.0.0.1:8001/mcp --json
```

**输出内容**：

- 服务器信息（名称、版本、协议版本）
- 能力列表（tools、resources、prompts）
- 工具详情（名称、描述、参数 schema）
- 资源列表
- Prompts 列表

### 8.2 编程方式获取

```python
session = ClientSession(read, write)
await session.initialize()
list_result = await session.list_tools()
for tool in list_result.tools:
    print(f"{tool.name}: {tool.description}")
    print(f"Parameters: {tool.inputSchema}")
```

## 九、最佳实践

### 9.1 MCP 服务设计

- **单一职责**：每个 MCP 专注一个领域
- **错误处理**：完善的异常处理和错误信息
- **文档完善**：清晰的工具描述和参数说明

### 9.2 客户端设计

- **工具映射**：维护 tool_to_session 映射
- **格式化输出**：单一工具调用时直接返回
- **多工具协调**：处理多个工具调用的场景

### 9.3 部署建议

- **开发阶段**：使用 stdio 方式，便于调试
- **生产环境**：使用 HTTP 方式，支持分布式部署
- **监控日志**：记录工具调用和结果

## 十、总结与展望

### 10.1 MCP 的优势

- 标准化协议，易于集成
- 灵活的部署方式（stdio/HTTP）
- 丰富的扩展能力

### 10.2 应用前景

- 机器人控制
- 智能家居
- 企业自动化
- 多模态 AI 应用

### 10.3 下一步方向

- 更多机器人能力集成
- 第三方 MCP 服务接入
- 性能优化和监控
- 安全增强

---

## 附录：项目结构

```
mcp/
├── client/
│   ├── client.py      # 本地模型客户端（Ollama）
│   └── remote.py      # 在线模型客户端（Qwen）
├── server/
│   ├── server.py      # hello MCP
│   ├── server2.py    # time MCP
│   ├── weather.py    # weather MCP
│   └── move.py       # robot move MCP
├── tool/
│   └── mcp_inspect.py # MCP 信息检测工具
├── config.json.example # 配置文件模板
└── README.md          # 项目说明
```

## 演示流程

1. **启动 MCP 服务**（HTTP 模式）
2. **启动客户端**（连接多个 MCP）
3. **演示工具调用**（天气查询、机器人控制）
4. **展示格式化输出**（单一工具直接返回）
5. **演示 MCP 信息获取**（inspect 工具）

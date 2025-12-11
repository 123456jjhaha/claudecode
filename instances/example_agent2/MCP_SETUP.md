# MCP 服务器配置指南

## 配置 MCP 服务器

要为此实例添加外部 MCP 服务器，请在实例目录下创建 `.mcp.json` 文件。

### 步骤

1. **复制示例文件**：
   ```bash
   cp .mcp.json.example .mcp.json
   ```

2. **编辑配置**：
   根据需要配置 MCP 服务器。示例：
   ```json
   {
     "mcpServers": {
       "weather": {
         "type": "stdio",
         "command": "node",
         "args": ["./mcp-servers/weather/index.js"],
         "env": {
           "API_KEY": "${WEATHER_API_KEY}"
         }
       }
     }
   }
   ```

3. **设置环境变量**（如果需要）：
   在 `.env` 文件中设置必要的环境变量：
   ```env
   WEATHER_API_KEY=your_api_key_here
   DB_TOKEN=your_token_here
   ```

4. **控制工具访问**：
   在 `config.yaml` 的 `tools.allowed` 中添加 MCP 工具：
   ```yaml
   tools:
     allowed:
       - "mcp__weather__*"     # 允许所有 weather MCP 工具
       - "mcp__database__get"  # 只允许特定工具
   ```

## MCP 服务器类型

### stdio 类型
通过标准输入输出与服务器通信：
```json
{
  "type": "stdio",
  "command": "node",
  "args": ["./server.js"]
}
```

### HTTP 类型
通过 HTTP 请求与服务器通信：
```json
{
  "type": "http",
  "url": "http://localhost:3000/mcp"
}
```

### SSE 类型
通过服务器发送事件（Server-Sent Events）通信：
```json
{
  "type": "sse",
  "url": "http://localhost:3000/sse"
}
```

## 工具命名规则

MCP 工具的命名格式为：`mcp__<server_name>__<tool_name>`

例如，名为 "weather" 的 MCP 服务器提供的 "get_forecast" 工具，完整名称为：
```
mcp__weather__get_forecast
```

## 调试

如果 MCP 服务器未加载，请检查：
1. `.mcp.json` 文件格式是否正确
2. `config.yaml` 中 `advanced.setting_sources` 是否包含 `"project"`
3. MCP 服务器是否可执行和访问
4. 环境变量是否正确设置

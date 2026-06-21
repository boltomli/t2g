# 更新日志

## 2026-06-20 最新更新

### 模型配置

- **默认模型**: 更改为 `google/gemma-4-12b-qat`
- **Reasoning**: 设置为关闭，但注意 gemma 模型仍会生成 reasoning tokens

### Token 配置

- **max_tokens**: 增加到 `16384`，以容纳 reasoning tokens + 实际内容
- **chunk_size**: 减小到 `1200` 字符，提高成功率
- **timeout**: 增加到 `180` 秒（3分钟）

### 重要说明

gemma 模型即使设置 `reasoning.enabled: false`，仍会生成 reasoning tokens。这些 tokens 会占用 max_tokens 配额。因此需要：

1. 增加 max_tokens 到足够大（建议 16384 或更高）
2. 增加超时时间（建议 180 秒）
3. 减小文本分块大小（建议 1200 字符）

详见 `REASONING_NOTES.md`

---

## 2026-06-20 早期更新

### 文本分析优化

1. **分块处理**: 长文本自动分割成小块处理
2. **超时控制**: 可配置的超时时间，支持自动重试
3. **进度显示**: 实时显示分析进度
4. **错误处理**: 改进的错误提示和解决方案

### 新增文件

- `OPTIMIZATIONS.md` - 优化说明文档
- `REASONING_NOTES.md` - Reasoning tokens 说明
- `CHANGES.md` - 更新日志

### 配置更新

#### Godot 项目 (llm_client.gd)

```gdscript
@export var model: String = "google/gemma-4-12b-qat"
@export var max_tokens: int = 16384
@export var timeout_seconds: int = 180
@export var chunk_size: int = 1200
@export var enable_reasoning: bool = false
```

#### Python 脚本 (analyze.py)

```python
DEFAULT_MODEL = "google/gemma-4-12b-qat"
DEFAULT_MAX_TOKENS = 16384
DEFAULT_TIMEOUT = 180
DEFAULT_CHUNK_SIZE = 1200
DEFAULT_ENABLE_REASONING = False
```

### 测试更新

- 增加了 API 连接测试
- 更新了超时时间配置
- 添加了 reasoning tokens 说明

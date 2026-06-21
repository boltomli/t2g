# Reasoning Tokens 说明

## 问题说明

使用 `google/gemma-4-12b-qat` 或 `qwen/qwen3.5-9b` 等模型时，发现即使设置 `reasoning.enabled: false`，模型仍然会生成 reasoning tokens（推理 tokens）。

## 原因分析

1. **模型特性**: 这些模型在训练时就内置了推理能力，reasoning tokens 是其工作方式的一部分
2. **API限制**: LM Studio 的 API 可能不支持完全禁用 reasoning 功能
3. **Token消耗**: reasoning tokens 会占用 `max_tokens` 配额

## Token 消耗示例

```
请求: "Say hi"
max_tokens: 100

实际消耗:
- reasoning_tokens: 97 (用于思考如何回复)
- content_tokens: 3 (实际回复 "Hi!")

结论: 100 个 token 中，只有 3 个是实际内容
```

## 解决方案

### 1. 增加 max_tokens

将 `max_tokens` 设置得足够大，以容纳 reasoning tokens 和实际内容：

```python
# 建议配置
DEFAULT_MAX_TOKENS = 16384  # 或更大
```

### 2. 减小分块大小

由于每个请求都会消耗 reasoning tokens，减小文本分块大小可以提高成功率：

```python
DEFAULT_CHUNK_SIZE = 1200  # 字符数
```

### 3. 增加超时时间

reasoning tokens 需要额外的处理时间：

```python
DEFAULT_TIMEOUT = 180  # 3分钟
```

### 4. 使用不带推理的模型

如果需要更快的响应，考虑使用不带推理功能的模型（如果有）。

## 配置建议

### Godot 项目 (llm_client.gd)

```gdscript
@export var max_tokens: int = 16384  # 足够大
@export var timeout_seconds: int = 180  # 3分钟
@export var chunk_size: int = 1200  # 较小的分块
```

### Python 脚本 (analyze.py)

```python
DEFAULT_MAX_TOKENS = 16384  # 足够大
DEFAULT_TIMEOUT = 180  # 3分钟
DEFAULT_CHUNK_SIZE = 1200  # 较小的分块
```

## 测试建议

1. **短文本测试**: 使用简短文本测试 API 连接
2. **监控 token 使用**: 观察 `usage` 字段中的 token 消耗
3. **调整参数**: 根据实际响应时间调整超时和分块大小

## 示例响应结构

```json
{
  "choices": [{
    "message": {
      "content": "实际回复内容",
      "reasoning_content": "推理过程..."
    }
  }],
  "usage": {
    "completion_tokens": 100,
    "completion_tokens_details": {
      "reasoning_tokens": 80,  // 大部分用于推理
      "content_tokens": 20     // 实际内容
    }
  }
}
```

## 总结

- reasoning tokens 是模型的固有特性，无法完全禁用
- 需要通过增加 max_tokens 和超时时间来适应
- 分块处理仍然有效，但需要考虑 reasoning tokens 的开销

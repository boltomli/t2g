# 更新日志

## 2026-07-05 叙事系统升级

### 新增

- **故事大纲生成**: 新增 `prompts/outline.txt` 提示词，在分析情节前先生成高层大纲
  - 包含：故事梗概（logline）、三幕结构、分支点识别、角色弧线、结局变体
  - 大纲作为后续分支生成的参考，保持整体一致性
  
- **分支方向规划**: 新增 `prompts/branch_planning.txt` 提示词，在生成具体对话前先规划分支走向
  - 包含：情感基调、核心动作、剧情后果、角色影响、结局偏向
  - 先确定"走向方案"，再据此生成具体对话内容
  
- **情节真正影响选择**: 修改 `prompts/vn_branches.txt`，让选择真正改变剧情走向
  - 每个分支必须有明显不同的剧情发展（不只是语气变化）
  - 新增 `plot_impact` 字段，明确说明选择对后续剧情的具体影响
  - 要求至少一个"正面"选择和一个"负面"选择

### 改进

- **视觉小说生成器升级**: `visual_novel.py` 集成新的三阶段流程
  - 阶段1：生成故事大纲
  - 阶段2：为每个事件规划分支方向
  - 阶段3：基于规划生成具体对话内容
  
- **序章增强**: 序章现在会显示故事梗概和主题，帮助玩家快速理解故事

### 架构变化

```
原流程：
  文本 → 分析 → 生成分支 → 生成对话

新流程：
  文本 → 分析 → 生成大纲 → 规划分支方向 → 生成对话
```

---

## 2026-06-30 Web界面

### 新增

- **Web界面**: 新增 `web_server.py` + `web/index.html`，支持在浏览器中上传文本、分析、生成Twine游戏并实时预览
  - 启动方式: `uv run python web_server.py`，访问 http://localhost:8080
  - 支持粘贴文本、上传.txt文件、加载内置示例
  - SSE实时进度推送
  - 右侧iframe直接运行生成的互动故事

### 修复

- **Twine开场跳过**: 修复 `twine.py` 中 `story.initialPassage` 硬编码为 `'Chapter_01'` 导致首次进入游戏跳过序章的问题，改为 `'Start'`

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

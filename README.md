# Text2Game - 文本转游戏元系统

将任意文本转换为可玩游戏的创新系统。

## ✨ 功能特点

- 📝 **文本分析**: 使用LLM分析文本，提取世界观、角色、关系、事件
  - 支持长文本分块处理（每块8000字符）
  - 本地同名角色合并 + LLM智能整理
  - 事件时间线梳理（支持非线性叙事）
  - 人物关系网络生成
- 🎮 **游戏类型推荐**: 基于文本特征推荐最适合的游戏类型
- ⚡ **自动生成**: 一键生成Godot游戏项目或Twine交互式故事
- 💾 **智能缓存**: 分块独立缓存，重复分析秒完成
- ⚙️ **配置管理**: 支持 .env 文件配置

## 🚀 快速开始

### 方式1: Godot独立应用

```bash
godot -e godot_project/
```

### 方式2: Python脚本

```bash
# 安装依赖
uv sync

# 分析文本
uv run python pi_mode/analyze.py examples/fantasy.txt

# 便捷脚本
./run.sh analyze examples/fantasy.txt
```

### 方式3: 生成 Twine 故事

```bash
# 1. 分析文本
uv run python pi_mode/analyze.py examples/fantasy.txt

# 2. 生成 Twee 源文件（选择 twine 类型）
uv run python pi_mode/generate.py -a .cache/<hash>/result.json -t twine

# 3. 编译为 HTML（见下方 Twine 编译指南）
```

## 📊 分析流程

### 阶段1: 文本分块分析

```
长文本 (32KB)
    ↓
分块 (每块约8000字符)
    ↓
[块1] → LLM分析 → {world, characters, relationships, events, ...}
[块2] → LLM分析 → {world, characters, relationships, events, ...}
[块3] → LLM分析 → {world, characters, relationships, events, ...}
```

### 阶段2: 智能合并

```
角色合并:
  本地同名合并: [王某(商人), 王某(总理)] → [王某{roles:[商人,总理]}]
  LLM整理: 生成清晰角色档案

人物关系:
  LLM整理: 合并相似关系，生成关系网络

事件时间线:
  LLM整理: 重新排序，梳理因果，合并相似事件

其他: 世界观、冲突、主题、氛围 → LLM分别整理
```

### 阶段3: 输出结果

```json
{
  "world": {
    "name": "星汉帝国",
    "era": "帝国时代",
    "location": "龙腾",
    "rules": "帝国统治",
    "description": "一个强大的星际帝国"
  },
  "characters": [
    {
      "name": "刘云飞",
      "role": "帝国大学校长",
      "roles": ["学者", "校长"],
      "traits": ["聪明", "严肃"],
      "background": "出身名门，年轻时是天才学者...",
      "goal": "培养下一代领导者",
      "goals": ["学术研究", "教书育人"]
    }
  ],
  "relationships": [
    {
      "from": "刘云飞",
      "to": "梅先文",
      "type": "师生",
      "description": "梅先文是刘云飞的学生"
    }
  ],
  "events": [
    {
      "order": 1,
      "title": "太子到来",
      "description": "梅先文等人到达雾林镇",
      "characters": ["梅先文", "刘云飞"],
      "consequences": "开始为期半月的假期"
    }
  ],
  "conflicts": [...],
  "themes": ["权力", "教育", "成长"],
  "atmosphere": "严肃中带有幽默"
}
```

## ⚙️ 配置说明

### .env 文件

```env
# LLM API 配置
LLM_API_URL=http://localhost:1234/v1
LLM_MODEL=google/gemma-4-12b-qat
# API密钥（可选，某些服务器可能需要）
LLM_API_KEY=
LLM_MAX_TOKENS=16384
LLM_TIMEOUT=600

# 文本处理
CHUNK_SIZE=8000
```

**注意**: 如果使用需要API密钥的云端服务，请在 `.env` 文件中配置 `LLM_API_KEY`。本地LM Studio通常不需要密钥。

### 命令行参数

```bash
uv run python pi_mode/analyze.py story.txt --timeout 600 --no-cache
uv run python pi_mode/analyze.py --show-config
uv run python pi_mode/analyze.py --cache-info
```

## 💾 缓存系统

```
.cache/
└── <输入MD5>/
    ├── chunks/
    │   └── chunk_xxx.json        # 块分析缓存
    ├── merge_world_xxx.json      # 世界观合并缓存
    ├── merge_chars_v5_xxx.json   # 角色合并缓存
    ├── merge_rels_xxx.json       # 人物关系缓存
    ├── merge_events_xxx.json     # 事件合并缓存
    └── result.json               # 整体结果
```

```bash
uv run python pi_mode/analyze.py --cache-info    # 查看缓存
uv run python pi_mode/analyze.py --clear-cache   # 清除缓存
```

## 📁 项目结构

```
text2game/
├── .env.example          # 配置模板
├── .env                  # 本地配置
├── pyproject.toml        # Python配置
├── run.sh / run.bat      # 便捷脚本
├── prompts/              # 提示词
│   ├── analyze.txt       # 文本分析
│   ├── recommend.txt     # 类型推荐
│   ├── merge.txt         # 结果合并
│   └── vn_branches.txt   # 视觉小说分支生成
├── pi_mode/              # Python脚本
│   ├── analyze.py        # 分析器
│   ├── generate.py       # 游戏生成（统一入口）
│   ├── compile_twee.py   # Twee→HTML 编译器
│   └── generators/       # 游戏类型生成器
│       ├── visual_novel.py   # Godot 视觉小说
│       └── twine.py          # Twine 交互式故事
├── godot_project/        # Godot项目
├── examples/             # 示例文本
└── test_system.py        # 测试脚本
```

## 🎮 支持的游戏类型

| 类型 | 参数 | 输出格式 | 说明 |
|------|------|----------|------|
| RPG | `rpg` | Godot 项目 | 角色扮演 |
| Adventure | `adventure` | Godot 项目 | 冒险解谜 |
| Visual Novel | `visual_novel` | Godot 项目 | 视觉小说 |
| Strategy | `strategy` | Godot 项目 | 策略模拟 |
| Action | `action` | Godot 项目 | 动作游戏 |
| **Twine 故事** | `twine` | **Twee 源文件** | **交互式分支叙事，编译为单文件 HTML** |

### Twine 故事模式

生成 [Chapbook](https://klembot.github.io/chapbook/) 格式的 Twee 源文件，可编译为浏览器可运行的单文件 HTML。

**优势：**
- 无需安装 Godot，浏览器直接运行
- 单文件分发，双击即玩
- 天然支持分支叙事、条件跳转、变量系统
- 可用 Twine 编辑器继续编辑

## 📦 Twine 编译指南

生成的 `.twee` 文件可通过以下方式编译为可运行的 HTML：

### 方式 1: twee-cli（推荐）

```bash
# 安装 twee-cli（需要 Node.js）
npm install -g twee-cli

# 编译为 HTML
twee build generated_games/my_story_twine/my_story_twine.twee -o story.html

# 指定故事格式（默认 Harlowe，Chapbook 需要单独安装格式文件）
twee build story.twee --format chapbook -o story.html
```

### 方式 2: Twine 编辑器

1. 下载安装 [Twine 2](https://twinery.org/)
2. 打开 Twine → 故事 → 导入
3. 选择生成的 `.twee` 文件
4. 在编辑器中预览和修改
5. 构建为 HTML：故事 → 构建为 HTML

### 方式 3: 在线编译

- [Twee 3 online tool](https://twee3.github.io/twee3-online-tool/)
- 上传 `.twee` 文件，选择格式，导出 HTML

### 方式 4: 项目内置编译器（推荐）

```bash
# 编译单个 .twee 文件
uv run python pi_mode/compile_twee.py generated_games/my_story_twine/my_story_twine.twee

# 编译目录下所有 .twee 文件
uv run python pi_mode/compile_twee.py generated_games/my_story_twine/

# 指定输出路径
uv run python pi_mode/compile_twee.py story.twee -o output.html
```

编译器会自动下载并缓存 Chapbook 运行时（约 140KB），生成的 HTML 是完全自包含的单文件。

### 编译后的使用

编译生成的 `story.html` 是一个独立文件：
- 双击即可在浏览器中运行
- 可直接发送给他人，无需任何依赖
- 支持移动端浏览器

```bash
# 直接打开
start story.html        # Windows
open story.html          # macOS
xdg-open story.html      # Linux
```

## 🧪 测试

```bash
uv run python test_system.py  # 运行15个测试用例
```

## 🔧 故障排除

- **连接失败**: 检查LM Studio是否运行
- **超时**: 增加 `LLM_TIMEOUT` 配置
- **Reasoning tokens**: gemma模型特性，需增加 `LLM_MAX_TOKENS`

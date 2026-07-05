# Text2Game

将任意文本转换为可玩游戏的系统。LLM 分析文本内容，提取世界观、角色、事件，自动生成可交互的游戏体验。

## 架构

```
输入文本 → [分块分析] → [智能合并] → [游戏生成] → 可玩输出
              ↓              ↓              ↓
           LLM逐块提取    LLM去重整理    Godot项目 / Twine HTML
           世界观/角色     角色/关系/     (.gd+.tscn)  (.twee→.html)
           /事件/冲突     事件时间线
```

| 模块 | 职责 |
|------|------|
| `pi_mode/analyze.py` | 文本分块、LLM分析、缓存、合并 |
| `pi_mode/generators/twine.py` | Twine/Chapbook 交互式故事生成 |
| `pi_mode/generators/visual_novel.py` | Godot 视觉小说项目生成 |
| `pi_mode/generate.py` | 游戏生成统一入口 |
| `pi_mode/compile_twee.py` | .twee 编译为自包含 HTML |

LLM 接口为 OpenAI 兼容 API，默认连接 LM Studio (`localhost:1234`)，配置见 `.env`。

## 文档

- **[快速开始](QUICKSTART.md)** — 三种使用方式的详细步骤
- **[架构设计](ARCHITECTURE.md)** — 系统组件、数据流、技术栈详解
- **[提示词](PROMPTS.md)** — LLM 提示词模板说明
- **[Pi Mode](pi_mode/README.md)** — Python 脚本模式详解

## 项目结构

```
├── web_server.py            # Web 服务器
├── web/index.html           # Web 前端
├── pi_mode/                 # 核心引擎
│   ├── analyze.py           # 文本分析
│   ├── generate.py          # 生成入口
│   ├── compile_twee.py      # Twee→HTML 编译
│   └── generators/          # 游戏生成器
├── godot_project/           # Godot 桌面应用
├── prompts/                 # LLM 提示词模板
├── examples/                # 示例文本
├── .env                     # LLM 配置
└── generated_games/         # 生成结果（自动创建）
```

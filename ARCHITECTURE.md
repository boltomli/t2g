# Text2Game - 文本转游戏元系统

## 项目概述

Text2Game 是一个元游戏系统，可以将任意文本转换为可玩游戏。用户输入文本后，系统使用LLM分析内容，生成世界观、角色设定，并推荐适合的游戏类型。用户选择后，系统自动生成完整的游戏体验。

## 双模式架构

### 模式1: Godot 4.7 独立应用
```
┌─────────────────────────────────────────────────────────────┐
│                    Godot 4.7 应用程序                         │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  文本输入UI   │  │  LLM分析器   │  │   游戏生成引擎       │ │
│  │  (TextEdit)  │→│  (HTTP API) │→│  (场景/脚本生成)     │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│         ↑                                    ↓              │
│  ┌─────────────┐                    ┌─────────────────────┐ │
│  │  配置管理器   │                    │   游戏运行器         │ │
│  │  (设置/保存)  │                    │  (场景切换/执行)     │ │
│  └─────────────┘                    └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↕
                    ┌───────────────┐
                    │  LM Studio    │
                    │  (本地LLM)    │
                    │  :1234        │
                    └───────────────┘
```

### 模式2: Pi Agent 集成模式
```
┌─────────────────────────────────────────────────────────────┐
│                    Pi Coding Agent                           │
├─────────────────────────────────────────────────────────────┤
│  1. 用户提供txt文件                                          │
│  2. LLM分析文本内容                                          │
│  3. 生成: world.json, characters.json, game_config.json     │
│  4. 生成Godot项目文件 (.gd, .tscn, project.godot)           │
│  5. 用户使用 Godot 打开项目并运行                             │
└─────────────────────────────────────────────────────────────┘
```

## 系统组件

### 1. 文本分析器 (TextAnalyzer)
- 读取txt文件
- 调用LLM API分析内容
- 输出结构化的世界观、角色、情节

### 2. 游戏类型推荐器 (GameTypeRecommender)
基于文本特征推荐游戏类型:
- **角色扮演 (RPG)**: 强角色驱动、成长系统
- **冒险解谜 (Adventure)**: 探索、线索、解谜
- **视觉小说 (Visual Novel)**: 对话为主、多结局
- **策略模拟 (Strategy)**: 资源管理、决策
- **动作平台 (Action)**: 冒险、挑战、战斗

### 3. 游戏生成器 (GameGenerator)
根据选择的游戏类型生成:
- 场景结构 (.tscn)
- GDScript代码 (.gd)
- 资源文件 (图片、音效占位)
- 游戏配置 (project.godot)

### 4. 游戏运行器 (GameRunner)
- 管理游戏场景切换
- 处理用户输入
- 维护游戏状态

## LLM集成

### API配置 (默认LM Studio)
```
Base URL: http://localhost:1234/v1
Model: 自动选择或指定
Endpoint: /chat/completions
```

### Prompt模板
1. **文本分析Prompt**: 提取世界观、角色、冲突
2. **游戏类型推荐Prompt**: 分析适合的游戏机制
3. **游戏生成Prompt**: 生成GDScript代码和场景

## 数据流

```
用户输入文本
    ↓
LLM分析 (提取实体、关系、主题)
    ↓
生成世界设定 (world.json)
    ↓
生成角色设定 (characters.json)
    ↓
推荐游戏类型 (3-5个选项)
    ↓
用户选择游戏类型
    ↓
LLM生成游戏配置 (game_config.json)
    ↓
生成Godot项目文件
    ↓
用户在Godot中打开/运行
```

## 文件结构

```
text2game/
├── ARCHITECTURE.md          # 本文档
├── README.md                # 使用说明
├── godot_project/           # Godot 4.7项目
│   ├── project.godot
│   ├── scenes/
│   │   ├── main.tscn       # 主界面
│   │   ├── analysis.tscn   # 分析结果展示
│   │   └── game_runner.tscn # 游戏运行器
│   ├── scripts/
│   │   ├── main.gd
│   │   ├── text_analyzer.gd
│   │   ├── game_generator.gd
│   │   └── llm_client.gd
│   └── resources/
│       └── themes/
├── templates/               # 游戏模板
│   ├── rpg/
│   ├── adventure/
│   ├── visual_novel/
│   ├── strategy/
│   └── action/
├── examples/                # 示例文本
│   ├── fantasy.txt
│   ├── scifi.txt
│   └── mystery.txt
└── pi_mode/                 # Pi Agent模式
    ├── analyze.py           # 文本分析脚本
    ├── generate.py          # 游戏生成脚本
    └── README.md
```

## 技术栈

- **游戏引擎**: Godot 4.7 (GDScript)
- **LLM**: 本地LM Studio / OpenAI兼容API
- **UI**: Godot Control节点
- **数据格式**: JSON, GDScript动态加载
- **开发工具**: Pi Coding Agent

## 扩展性

- 支持多种LLM后端 (LM Studio, Ollama, OpenAI API)
- 可扩展的游戏类型模板
- 插件系统支持自定义游戏机制
- 支持导出为独立游戏

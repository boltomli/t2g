# Text2Game - Pi Agent模式

## 概述

此模式允许在Pi编程agent中使用Text2Game功能。无需独立的Godot应用程序，直接在编程界面中完成文本分析和游戏生成。

## 工作流程

### 1. 提供文本文件
将txt文件放在当前目录，或直接粘贴文本内容。

### 2. 分析文本
在Pi中运行分析命令：
```bash
# 使用Python脚本分析
python analyze.py your_text.txt

# 或直接在Pi对话中使用
pi "分析此文本并生成游戏配置: @your_text.txt"
```

### 3. 生成游戏
分析完成后，生成Godot项目：
```bash
# 生成完整游戏
python generate.py --analysis analysis.json --type rpg

# 或让Pi自动处理
pi "基于此分析结果生成RPG游戏项目: @analysis.json"
```

### 4. 运行游戏
```bash
# 使用Godot打开生成的项目
godot --path generated_games/your_game/
```

## 脚本说明

### analyze.py
文本分析脚本，调用LM Studio API分析文本内容。

```bash
python analyze.py <text_file> [--output analysis.json] [--api-url http://localhost:1234/v1]
```

### generate.py
游戏生成脚本，基于分析结果生成Godot项目。

```bash
python generate.py --analysis <analysis_file> --type <game_type> [--output <output_dir>]
```

## 配置

默认配置：
- LLM API: http://localhost:1234/v1 (LM Studio)
- 输出目录: ./generated_games/
- 默认游戏类型: rpg

可通过环境变量或命令行参数修改。

## 在Pi中使用

### 方法1: 使用Pi技能
将skill文件放在 `.agents/skills/text2game/` 目录中。

### 方法2: 直接对话
在Pi中直接描述需求，Pi会使用bash工具执行脚本。

### 方法3: Pi扩展
创建Pi扩展，添加自定义命令如 `/text2game`。

## 示例

```bash
# 完整流程
python analyze.py examples/fantasy.txt -o fantasy_analysis.json
python generate.py -a fantasy_analysis.json -t rpg -o generated_games/fantasy_rpg
godot --path generated_games/fantasy_rpg
```

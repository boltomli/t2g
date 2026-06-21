# Text2Game 快速入门指南

## 📋 前提条件

1. **Godot 4.7** - 已安装 ✓
2. **LM Studio** - 需要启动并加载模型
3. **Python 3.x** - 用于Pi Agent模式

## 🚀 方式1: Godot应用模式（推荐）

### 步骤1: 启动LM Studio
1. 打开LM Studio
2. 加载一个模型（推荐: qwen/qwen3.5-9b）
3. 启动本地服务器（默认端口1234）

### 步骤2: 启动Text2Game
```bash
# 方法A: 双击运行launch.bat
launch.bat

# 方法B: 直接使用Godot
godot --path godot_project/
```

### 步骤3: 使用应用
1. 在文本框输入或粘贴文本
2. 点击"分析文本"按钮
3. 等待LLM分析完成
4. 查看分析结果（世界观、角色、主题）
5. 点击"下一步"选择游戏类型
6. 选择喜欢的游戏类型
7. 等待游戏生成完成
8. 使用Godot打开生成的项目

## 🐍 方式2: Pi Agent模式

### 步骤1: 分析文本
```bash
# 分析示例文本
python pi_mode/analyze.py examples/fantasy.txt

# 分析自定义文本
python pi_mode/analyze.py your_text.txt -o analysis.json
```

### 步骤2: 生成游戏
```bash
# 使用RPG类型生成
python pi_mode/generate.py -a examples/fantasy.json -t rpg

# 使用冒险类型生成
python pi_mode/generate.py -a examples/fantasy.json -t adventure
```

### 步骤3: 运行游戏
```bash
# 使用Godot打开生成的项目
godot --path generated_games/Fantasy_rpg/
```

## 📝 示例文本

项目提供了3个示例文本:

### 1. 奇幻冒险 (examples/fantasy.txt)
- 世界观: 魔法消失的古老王国
- 主角: 拥有幻视能力的少女艾莉娅
- 主题: 命运、勇气、牺牲
- 推荐: RPG、冒险、视觉小说

### 2. 科幻故事 (examples/scifi.txt)
- 世界观: 2187年太空城，阶层分化
- 主角: 底层机械师凯尔
- 主题: 真相、选择、反抗
- 推荐: 冒险、策略、动作

### 3. 悬疑推理 (examples/mystery.txt)
- 世界观: 暴风雨中的古堡
- 主角: 侦探陈默
- 主题: 真相、信任、秘密
- 推荐: 冒险、解谜、视觉小说

## 🎮 支持的游戏类型

| 类型 | 说明 | 适用场景 |
|------|------|----------|
| RPG | 角色扮演 | 角色成长、技能树、装备收集 |
| Adventure | 冒险解谜 | 探索、解谜、物品收集 |
| Visual Novel | 视觉小说 | 分支剧情、多结局、角色好感度 |
| Strategy | 策略模拟 | 资源管理、决策、建设 |
| Action | 动作平台 | 战斗、挑战、操作 |

## 🔧 常见问题

### Q: 连接LLM失败怎么办？
A: 确保LM Studio已启动，模型已加载，服务器运行在端口1234。

### Q: 分析超时怎么办？
A: 尝试缩短文本长度，或在LM Studio中使用更快的模型。

### Q: 生成的游戏无法运行？
A: 确保使用Godot 4.7打开生成的项目文件夹。

### Q: 如何自定义游戏？
A: 生成的游戏是完整的Godot项目，可以自由修改代码和资源。

## 📁 项目结构

```
text2game/
├── godot_project/           # Godot 4.7项目
│   ├── project.godot
│   ├── scenes/main.tscn    # 主界面场景
│   └── scripts/             # 核心脚本
│       ├── main.gd         # 主控制器
│       ├── llm_client.gd   # LLM客户端
│       ├── text_analyzer.gd # 文本分析器
│       └── game_generator.gd # 游戏生成器
├── pi_mode/                 # Pi Agent模式
│   ├── analyze.py          # 文本分析脚本
│   └── generate.py         # 游戏生成脚本
├── examples/                # 示例文本
└── generated_games/         # 生成的游戏（自动创建）
```

## 🎯 下一步

1. 尝试不同的示例文本
2. 探索生成的游戏代码
3. 自定义游戏内容和机制
4. 添加更多游戏类型模板

## 📚 相关文档

- [架构设计](ARCHITECTURE.md) - 详细的系统架构说明
- [Pi Agent模式说明](pi_mode/README.md) - Pi模式详细使用方法

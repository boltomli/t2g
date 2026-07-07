# 哲学故事生成器

将哲学文本转换为交互式故事游戏的生成器。

## 功能特性

### 1. 哲学文本分析
- 自动检测语言（中文/英文）
- 提取核心哲学概念
- 识别论证结构（演绎、归纳、类比等）
- 分析价值体系
- 生成故事主题建议

### 2. 交互式故事生成
- 基于哲学分析自动生成故事
- 创建角色和情节
- 生成多种结局（胜利、牺牲、妥协、蜕变）
- 支持玩家选择

### 3. Twine格式输出
- 生成标准的Twee源文件
- 兼容Chapbook格式
- 可直接编译为HTML运行

## 使用方法

### 基础用法

```python
from pi_mode.generators.philosophy import PhilosophyStoryGenerator

# 创建生成器
generator = PhilosophyStoryGenerator(output_dir="./generated_games")

# 准备哲学文本
text = """
天时不如地利，地利不如人和。三里之城，七里之郭，环而攻之而不胜。
得道者多助，失道者寡助。寡助之至，亲戚畔之；多助之至，天下顺之。
"""

# 生成游戏
result = generator.generate_game(
    text=text,
    metadata={"title": "得道多助，失道寡助", "author": "孟子", "era": "先秦"},
    num_chapters=4,
    output_format="twine"
)

print(f"游戏目录: {result['game_dir']}")
```

### 便捷函数

```python
from pi_mode.generators.philosophy import generate_philosophy_game

result = generate_philosophy_game(
    text="你的哲学文本...",
    metadata={"title": "标题", "author": "作者"},
    num_chapters=5
)
```

### 单独使用分析器

```python
from pi_mode.generators.philosophy import PhilosophyParser

parser = PhilosophyParser(language="zh")
analysis = parser.parse(text, metadata={"title": "标题"})

print(f"标题: {analysis.title}")
print(f"核心概念: {[c.name for c in analysis.concepts]}")
print(f"核心价值: {analysis.values.primary_values}")
```

## 输出结构

生成的游戏包含以下文件：

```
generated_games/
└── Game_philosophy/
    ├── story.json          # 故事结构（JSON格式）
    ├── analysis.json       # 哲学分析结果
    └── Game_philosophy.twee # Twine源文件
```

### story.json 结构

```json
{
  "title": "故事标题",
  "theme": "主题",
  "philosophy_source": "哲学来源",
  "chapters": [...],
  "characters": [...],
  "endings": {...},
  "metadata": {...}
}
```

### Twee文件格式

生成的Twee文件使用Chapbook格式，包含：

- **StoryTitle**: 故事标题
- **StoryData**: 故事配置（IFID、格式版本等）
- **start**: 开始段落
- **chapter_N**: 章节段落
- **ending_N**: 结局段落

## 支持的哲学文本

### 中文古典哲学
- 孟子、孔子、老子、庄子等
- 自动识别"者...也"、"故曰"等句式
- 提取仁、义、礼、智、信等价值

### 西方哲学
- 柏拉图、亚里士多德、康德等
- 识别"is/are"定义句式
- 提取virtue、justice、truth等价值

### 现代哲学
- 任意哲学文本
- 基于关键词的模式匹配
- 可扩展的解析规则

## 配置选项

### 生成器配置

```python
generator = PhilosophyStoryGenerator(
    output_dir="./my_games"  # 自定义输出目录
)
```

### 解析器配置

```python
parser = PhilosophyParser(
    language="zh"  # "auto", "zh", "en"
)
```

## 扩展指南

### 添加新的概念模式

在 `PhilosophyParser.CONCEPT_PATTERNS` 中添加新的正则表达式：

```python
CONCEPT_PATTERNS = {
    "custom_philosophy": [
        r"your_pattern_here",
    ]
}
```

### 添加新的价值词汇

在 `PhilosophyParser.VALUE_VOCABULARY` 中添加：

```python
VALUE_VOCABULARY = {
    "custom": ["value1", "value2", "value3"]
}
```

### 添加新的结局类型

在 `PhilosophyStoryGenerator._generate_endings` 中添加：

```python
endings["new_ending"] = {
    "title": "新结局",
    "summary": "...",
    "philosophy": "...",
    "conclusion": "..."
}
```

## 示例

### 示例1：孟子《得道多助》

```python
text = """
天时不如地利，地利不如人和。
得道者多助，失道者寡助。
"""
# 自动生成包含"仁政"、"民心"等概念的故事
```

### 示例2：柏拉图《理想国》片段

```python
text = """
Justice is the harmony of the soul.
The philosopher-king is the ideal ruler.
"""
# 自动生成包含"正义"、"智慧"等概念的故事
```

### 示例3：自定义哲学文本

```python
text = """
人生的意义在于追求幸福。
真正的幸福来自于智慧、勇气和仁爱的平衡。
"""
# 自动生成关于"幸福三角"的故事
```

## 技术细节

### 语言检测

使用字符比例检测：
- 中文字符比例 > 30%：中文
- 中文字符比例 < 10%：英文
- 其他：混合语言

### 概念提取

基于正则表达式模式匹配：
- 中文："者...也"、"故曰"、"所谓"等
- 英文："is/are"定义句、"the concept of"等

### 故事生成

采用模板化生成：
- 序章：引入主角和主题
- 中间章节：基于概念生成挑战
- 终章：根据选择生成结局

## 依赖

- Python 3.8+
- 无额外依赖（纯Python实现）

## 许可证

MIT License

# Text2Game 快速开始

## 前提条件

- **LM Studio** — 启动并加载模型（推荐 `google/gemma-4-12b-qat`），开启本地服务器（默认端口 1234）
- **Python 3.10+** — 通过 [uv](https://github.com/astral-sh/uv) 管理
- **Godot 4.7**（可选，仅 Godot 游戏类型需要）

```bash
uv sync
```

---

## 方式 1：Web 界面（推荐）

启动内置 Web 服务器，浏览器中完成分析和生成。

```bash
uv run python web_server.py
# 打开 http://localhost:8080
```

### 操作步骤

1. **输入文本** — 左侧文本框粘贴内容，或点击「上传 .txt 文件」/「加载示例」
2. **分析文本** — 点击「分析文本」，等待 LLM 分析完成
3. **查看结果** — 左侧面板展示世界观、角色、主题等分析结果
4. **生成游戏** — 点击「生成互动故事」，右侧 iframe 自动加载并运行生成的 Twine 游戏

支持实时进度显示（SSE 推送），分析和生成过程中可查看进度条。

---

## 方式 2：CLI 脚本

### 分析文本

```bash
# 分析示例文本
uv run python pi_mode/analyze.py examples/fantasy.txt

# 分析自定义文本
uv run python pi_mode/analyze.py your_text.txt -o analysis.json

# 查看缓存信息
uv run python pi_mode/analyze.py --cache-info
```

### 生成游戏

```bash
# 生成 Twine 故事
uv run python pi_mode/generate.py -a <analysis.json> -t twine

# 生成 Godot 游戏
uv run python pi_mode/generate.py -a <analysis.json> -t rpg
uv run python pi_mode/generate.py -a <analysis.json> -t adventure
uv run python pi_mode/generate.py -a <analysis.json> -t visual_novel
```

### 编译 Twine → HTML

```bash
# 编译单个 .twee
uv run python pi_mode/compile_twee.py story.twee

# 编译目录下所有 .twee
uv run python pi_mode/compile_twee.py generated_games/my_story_twine/

# 指定输出路径
uv run python pi_mode/compile_twee.py story.twee -o output.html
```

### 优化分析结果

对已有分析结果定向优化，无需重新分析原文：

```bash
uv run python pi_mode/optimize.py -a result.json -r "增加角色的背景故事深度"
uv run python pi_mode/optimize.py -a result.json -f my_requirements.txt
uv run python pi_mode/optimize.py -a result.json -r "重新梳理事件时间线" -o optimized.json
```

---

## 方式 3：Godot 应用

```bash
# 启动 Godot 编辑器
godot -e godot_project/

# 或双击 launch.bat（Windows）
```

### 操作步骤

1. 在文本框输入或粘贴文本
2. 点击「分析文本」
3. 等待 LLM 分析完成，查看世界观、角色、主题
4. 点击「下一步」选择游戏类型
5. 等待游戏生成完成
6. 使用 Godot 打开生成的项目

---

## 示例文本

项目提供 3 个示例文本：

| 文件 | 世界观 | 主角 | 主题 | 推荐类型 |
|------|--------|------|------|----------|
| `examples/fantasy.txt` | 魔法消失的古老王国 | 幻视少女艾莉娅 | 命运、勇气、牺牲 | RPG、冒险、视觉小说 |
| `examples/scifi.txt` | 2187年太空城 | 底层机械师凯尔 | 真相、选择、反抗 | 冒险、策略、动作 |
| `examples/mystery.txt` | 暴风雨中的古堡 | 侦探陈默 | 真相、信任、秘密 | 冒险、解谜、视觉小说 |

---

## 常见问题

**Q: 连接 LLM 失败？**
检查 LM Studio 是否运行，模型是否加载，服务器是否在端口 1234。

**Q: 分析超时？**
增加 `.env` 中的 `LLM_TIMEOUT`，或缩短文本长度。

**Q: Reasoning tokens 占用？**
gemma 模型即使关闭 reasoning 仍会生成 tokens，需增加 `LLM_MAX_TOKENS`（建议 16384+）。

**Q: Twine 游戏无法运行？**
编译后的 HTML 双击即可在浏览器运行，无需额外依赖。

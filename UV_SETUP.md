# UV 环境管理说明

## 概述

本项目使用 [uv](https://github.com/astral-sh/uv) 管理 Python 环境和依赖。

## 安装 uv

### Windows (PowerShell)

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Linux/macOS

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 使用 scoop (Windows)

```bash
scoop install uv
```

## 快速开始

```bash
# 1. 安装依赖
uv sync

# 2. 运行分析
uv run python pi_mode/analyze.py examples/fantasy.txt

# 3. 或使用便捷脚本
./run.sh analyze examples/fantasy.txt
```

## 常用命令

### 依赖管理

```bash
# 安装所有依赖
uv sync

# 添加新依赖
uv add requests

# 添加开发依赖
uv add --dev pytest

# 更新依赖
uv lock --upgrade
uv sync

# 查看依赖树
uv tree
```

### 运行脚本

```bash
# 使用 uv run
uv run python script.py

# 或使用便捷脚本
./run.sh <命令> [参数]
```

### Python 版本管理

```bash
# 查看可用版本
uv python list

# 安装特定版本
uv python install 3.11

# 固定项目 Python 版本
uv python pin 3.11
```

## 项目结构

```
text2game/
├── pyproject.toml        # 项目配置
├── uv.lock              # 依赖锁定文件
├── .python-version      # Python 版本（可选）
├── .venv/               # 虚拟环境（自动创建）
├── run.sh               # Linux/macOS 便捷脚本
├── run.bat              # Windows 便捷脚本
└── requirements.txt     # pip 兼容格式
```

## 便捷脚本

### Linux/macOS

```bash
# 分析文本
./run.sh analyze story.txt

# 显示配置
./run.sh config

# 列出模型
./run.sh models

# 安装依赖
./run.sh install

# 更新依赖
./run.sh update
```

### Windows

```batch
run.bat analyze story.txt
run.bat config
run.bat models
run.bat install
run.bat update
```

## 故障排除

### 依赖安装失败

```bash
# 清除缓存重新安装
uv cache clean
uv sync
```

### Python 版本问题

```bash
# 检查当前版本
uv python list

# 安装所需版本
uv python install 3.11

# 重新同步
uv sync
```

### 权限问题 (Linux/macOS)

```bash
# 添加执行权限
chmod +x run.sh

# 或直接运行
bash run.sh
```

## 与 pip 的关系

项目同时提供 `requirements.txt`，兼容 pip 用户：

```bash
# 使用 pip
pip install -r requirements.txt

# 使用 uv
uv sync
```

## IDE 集成

### VS Code

1. 安装 Python 扩展
2. 选择解释器：`.venv/bin/python`
3. uv 虚拟环境会被自动识别

### PyCharm

1. 打开设置 → Python Interpreter
2. 添加解释器 → Existing
3. 选择 `.venv/bin/python`

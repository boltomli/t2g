# Dotenv 配置说明

## 概述

Text2Game 使用 python-dotenv 管理本地配置，避免将敏感信息提交到版本控制。

## 快速设置

### 1. 安装依赖（可选）

```bash
pip install python-dotenv
```

如果未安装 python-dotenv，系统会使用默认配置。

### 2. 创建 .env 文件

```bash
# 复制模板文件
cp .env.example .env

# 或手动创建
touch .env
```

### 3. 编辑 .env 文件

```env
# LLM API 配置
LLM_API_URL=http://localhost:1234/v1
LLM_MODEL=google/gemma-4-12b-qat
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=16384

# 超时和重试配置
LLM_TIMEOUT=180
LLM_MAX_RETRIES=3

# 文本处理配置
CHUNK_SIZE=1200
MAX_TEXT_LENGTH=10000

# Reasoning 配置
ENABLE_REASONING=false
```

## 配置项说明

### LLM API 配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `LLM_API_URL` | `http://localhost:1234/v1` | LLM API 地址 |
| `LLM_MODEL` | `google/gemma-4-12b-qat` | 使用的模型 |
| `LLM_TEMPERATURE` | `0.7` | 生成温度 (0-1) |
| `LLM_MAX_TOKENS` | `16384` | 最大 token 数 |

### 超时和重试

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `LLM_TIMEOUT` | `180` | 请求超时时间（秒） |
| `LLM_MAX_RETRIES` | `3` | 最大重试次数 |

### 文本处理

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `CHUNK_SIZE` | `1200` | 文本分块大小（字符） |
| `MAX_TEXT_LENGTH` | `10000` | 最大文本长度 |
| `ENABLE_REASONING` | `false` | 启用 reasoning |

## 使用方式

### Python 脚本

```bash
# 使用默认配置
python pi_mode/analyze.py story.txt

# 命令行参数覆盖配置
python pi_mode/analyze.py story.txt --model qwen/qwen3.5-9b

# 显示当前配置
python pi_mode/analyze.py --show-config
```

### Godot 项目

配置会自动从 `.env` 文件加载，无需手动配置。

## 配置优先级

1. 命令行参数（最高优先级）
2. 环境变量
3. `.env` 文件
4. 默认值（最低优先级）

## 示例：切换模型

### 方法1: 修改 .env 文件

```env
LLM_MODEL=qwen/qwen3.5-9b
```

### 方法2: 命令行参数

```bash
python pi_mode/analyze.py story.txt --model qwen/qwen3.5-9b
```

## 故障排除

### 配置未生效

1. 确认 `.env` 文件在项目根目录
2. 检查文件名是否正确（`.env` 不是 `env`）
3. 运行 `python pi_mode/analyze.py --show-config` 查看当前配置

### 编码问题

确保 `.env` 文件使用 UTF-8 编码保存。

### 模型不支持

确认 LM Studio 中已加载指定的模型。

## 开发说明

### 添加新配置项

1. 在 `.env.example` 中添加示例
2. 在 `analyze.py` 中添加 `os.getenv()` 读取
3. 更新文档

### Godot 配置

Godot 项目使用 `config_loader.gd` 读取配置，支持 `.env` 格式。

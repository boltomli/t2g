#!/bin/bash
# Text2Game 运行脚本

set -e

# 检查 uv 是否安装
if ! command -v uv &> /dev/null; then
    echo "错误: 未安装 uv"
    echo "安装命令: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# 检查参数
if [ $# -eq 0 ]; then
    echo "用法: ./run.sh <命令> [参数]"
    echo ""
    echo "命令:"
    echo "  analyze <文件>     - 分析文本文件"
    echo "  config            - 显示当前配置"
    echo "  models            - 列出可用模型"
    echo "  install           - 安装依赖"
    echo "  update            - 更新依赖"
    echo ""
    echo "示例:"
    echo "  ./run.sh analyze examples/fantasy.txt"
    echo "  ./run.sh config"
    exit 0
fi

# 切换到项目目录
cd "$(dirname "$0")"

# 执行命令
case "$1" in
    analyze)
        shift
        uv run python pi_mode/analyze.py "$@"
        ;;
    config)
        uv run python pi_mode/analyze.py --show-config
        ;;
    models)
        uv run python pi_mode/analyze.py --list-models
        ;;
    install)
        echo "安装依赖..."
        uv sync
        echo "完成!"
        ;;
    update)
        echo "更新依赖..."
        uv lock --upgrade
        uv sync
        echo "完成!"
        ;;
    *)
        echo "未知命令: $1"
        exit 1
        ;;
esac

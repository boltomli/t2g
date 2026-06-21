@echo off
REM Text2Game 运行脚本 (Windows)

REM 检查 uv 是否安装
where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未安装 uv
    echo 安装命令: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    exit /b 1
)

REM 检查参数
if "%~1"=="" (
    echo 用法: run.bat ^<命令^> [参数]
    echo.
    echo 命令:
    echo   analyze ^<文件^>     - 分析文本文件
    echo   config            - 显示当前配置
    echo   models            - 列出可用模型
    echo   install           - 安装依赖
    echo   update            - 更新依赖
    echo.
    echo 示例:
    echo   run.bat analyze examples\fantasy.txt
    echo   run.bat config
    exit /b 0
)

REM 切换到项目目录
cd /d "%~dp0"

REM 执行命令
if "%~1"=="analyze" (
    shift
    uv run python pi_mode/analyze.py %*
) else if "%~1"=="config" (
    uv run python pi_mode/analyze.py --show-config
) else if "%~1"=="models" (
    uv run python pi_mode/analyze.py --list-models
) else if "%~1"=="install" (
    echo 安装依赖...
    uv sync
    echo 完成!
) else if "%~1"=="update" (
    echo 更新依赖...
    uv lock --upgrade
    uv sync
    echo 完成!
) else (
    echo 未知命令: %~1
    exit /b 1
)

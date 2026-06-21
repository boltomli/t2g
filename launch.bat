@echo off
echo ====================================
echo Text2Game - 文本转游戏元系统
echo ====================================
echo.

REM 检查Godot是否可用
where godot >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到Godot，请确保已安装并添加到PATH
    pause
    exit /b 1
)

echo [信息] Godot已找到
echo.

REM 显示菜单
echo 请选择操作:
echo 1. 启动Text2Game应用
echo 2. 运行系统测试
echo 3. 查看示例文本
echo 4. 退出
echo.

set /p choice="请输入选择 (1-4): "

if "%choice%"=="1" goto start_app
if "%choice%"=="2" goto run_test
if "%choice%"=="3" goto show_examples
if "%choice%"=="4" goto end

echo [错误] 无效选择
pause
goto end

:start_app
echo.
echo 正在启动Text2Game...
echo 请确保LM Studio已启动并运行在端口1234
echo.
godot --path godot_project/
goto end

:run_test
echo.
echo 正在运行系统测试...
python test_system.py
pause
goto end

:show_examples
echo.
echo 示例文本文件位于: examples/
echo.
echo 可用示例:
dir /b examples\*.txt 2>nul
echo.
echo 使用文本编辑器打开查看内容
pause
goto end

:end
echo.
echo 感谢使用Text2Game!

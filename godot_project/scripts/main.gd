## Main - 主界面控制器
## 支持进度显示、错误处理和状态管理
extends Control

## 信号
signal text_analyzed(analysis: Dictionary)
signal game_type_selected(game_type: String)

## 组件引用
@onready var text_input = $VBoxContainer/TextInput
@onready var analyze_button = $VBoxContainer/Buttons/AnalyzeButton
@onready var example_button = $VBoxContainer/Buttons/ExampleButton
@onready var status_label = $VBoxContainer/StatusLabel

@onready var analysis_panel = $AnalysisPanel
@onready var world_label = $AnalysisPanel/VBox/WorldLabel
@onready var characters_label = $AnalysisPanel/VBox/CharactersLabel
@onready var themes_label = $AnalysisPanel/VBox/ThemesLabel

@onready var game_type_panel = $GameTypePanel
@onready var game_types_container = $GameTypePanel/VBox/ScrollContainer/GameTypes

@onready var loading_panel = $LoadingPanel
@onready var progress_bar = $LoadingPanel/VBox/ProgressBar
@onready var loading_label = $LoadingPanel/VBox/LoadingLabel

## 系统引用
var text_analyzer: TextAnalyzer
var game_generator: GameGenerator
var llm_client: LLMClient
var config_loader: ConfigLoader

## 状态
var current_analysis: Dictionary = {}
var current_text: String = ""
var is_processing: bool = false

## 配置
var auto_retry_on_timeout: bool = true
var show_detailed_progress: bool = true

func _ready() -> void:
	# 初始化配置加载器
	config_loader = ConfigLoader.new()
	config_loader.add_to_group("config_loader")
	add_child(config_loader)
	
	# 初始化系统
	text_analyzer = TextAnalyzer.new()
	add_child(text_analyzer)
	
	game_generator = GameGenerator.new()
	add_child(game_generator)
	
	llm_client = LLMClient.new()
	add_child(llm_client)
	
	# 连接信号
	text_analyzer.analysis_completed.connect(_on_analysis_completed)
	text_analyzer.game_types_recommended.connect(_on_game_types_recommended)
	text_analyzer.analysis_failed.connect(_on_analysis_failed)
	text_analyzer.analysis_progress.connect(_on_analysis_progress)
	
	game_generator.game_generated.connect(_on_game_generated)
	game_generator.generation_progress.connect(_on_generation_progress)
	game_generator.generation_failed.connect(_on_generation_failed)
	
	llm_client.progress_updated.connect(_on_llm_progress)
	
	# 初始化UI
	_hide_all_panels()
	$TextInput.grab_focus()
	
	# 检查LLM连接
	_check_llm_connection()

## 检查LLM连接
func _check_llm_connection() -> void:
	_show_loading("正在检查LLM连接...")
	llm_client.check_connection(_on_connection_checked)

func _on_connection_checked(success: bool, message: String = "") -> void:
	_hide_loading()
	if success:
		status_label.text = "✓ LLM已连接"
		status_label.add_theme_color_override("font_color", Color.GREEN)
	else:
		status_label.text = "✗ LLM未连接 - 请启动LM Studio"
		status_label.add_theme_color_override("font_color", Color.RED)

## 分析按钮点击
func _on_analyze_button_pressed() -> void:
	if is_processing:
		status_label.text = "正在处理中，请稍候..."
		return
	
	var text = text_input.text.strip_edges()
	if text.is_empty():
		status_label.text = "请输入文本内容"
		return
	
	# 检查文本长度
	if text.length() > 10000:
		var dialog = ConfirmationDialog.new()
		dialog.title = "文本过长"
		dialog.dialog_text = "文本长度为%d字符，超过推荐的10000字符。分析可能需要较长时间或超时。是否继续？" % text.length()
		dialog.confirmed.connect(func(): _start_analysis(text))
		add_child(dialog)
		dialog.popup_centered()
		return
	
	_start_analysis(text)

## 开始分析
func _start_analysis(text: String) -> void:
	current_text = text
	is_processing = true
	analyze_button.disabled = true
	example_button.disabled = true
	
	_show_loading("正在分析文本...")
	text_analyzer.analyze_text(text)

## 示例按钮点击
func _on_example_button_pressed() -> void:
	if is_processing:
		status_label.text = "正在处理中，请稍候..."
		return
	
	# 显示示例选择对话框
	var dialog = AcceptDialog.new()
	dialog.title = "选择示例文本"
	dialog.size = Vector2i(400, 250)
	
	var vbox = VBoxContainer.new()
	dialog.add_child(vbox)
	
	var fantasy_btn = Button.new()
	fantasy_btn.text = "奇幻冒险 (较短)"
	fantasy_btn.custom_minimum_size = Vector2(0, 40)
	fantasy_btn.pressed.connect(func(): 
		text_input.text = text_analyzer.get_example_text("fantasy")
		dialog.queue_free()
	)
	vbox.add_child(fantasy_btn)
	
	var scifi_btn = Button.new()
	scifi_btn.text = "科幻故事 (中等)"
	scifi_btn.custom_minimum_size = Vector2(0, 40)
	scifi_btn.pressed.connect(func(): 
		text_input.text = text_analyzer.get_example_text("scifi")
		dialog.queue_free()
	)
	vbox.add_child(scifi_btn)
	
	var mystery_btn = Button.new()
	mystery_btn.text = "悬疑推理 (较长)"
	mystery_btn.custom_minimum_size = Vector2(0, 40)
	mystery_btn.pressed.connect(func(): 
		text_input.text = text_analyzer.get_example_text("mystery")
		dialog.queue_free()
	)
	vbox.add_child(mystery_btn)
	
	add_child(dialog)
	dialog.popup_centered()

## 分析完成回调
func _on_analysis_completed(analysis: Dictionary) -> void:
	_hide_loading()
	is_processing = false
	analyze_button.disabled = false
	example_button.disabled = false
	
	current_analysis = analysis
	
	# 显示分析结果
	_show_analysis(analysis)
	
	# 请求游戏类型推荐
	_show_loading("正在推荐游戏类型...")
	text_analyzer.recommend_game_types()

## 显示分析结果
func _show_analysis(analysis: Dictionary) -> void:
	analysis_panel.visible = true
	
	# 世界观
	var world = analysis.get("world", {})
	var world_text = "【世界观】\n"
	if world.has("name"):
		world_text += "名称: %s\n" % world.get("name", "未知")
	if world.has("era"):
		world_text += "时代: %s\n" % world.get("era", "未知")
	if world.has("location"):
		world_text += "地点: %s\n" % world.get("location", "未知")
	if world.has("description"):
		world_text += "描述: %s" % world.get("description", "无")
	if world_text == "【世界观】\n":
		world_text += "未提取到世界观信息"
	world_label.text = world_text
	
	# 角色
	var characters = analysis.get("characters", [])
	var char_text = "【角色】\n"
	if characters.is_empty():
		char_text += "未提取到角色信息"
	else:
		for char in characters:
			char_text += "• %s (%s)\n" % [char.get("name", "未知"), char.get("role", "未知")]
			if char.has("traits"):
				char_text += "  特征: %s\n" % ", ".join(char.get("traits", []))
			if char.has("background"):
				char_text += "  背景: %s\n" % char.get("background", "无")
			char_text += "\n"
	characters_label.text = char_text
	
	# 主题
	var themes = analysis.get("themes", [])
	var themes_text = "【主题】\n"
	if themes.is_empty():
		themes_text += "未提取到主题信息"
	else:
		themes_text += ", ".join(themes)
	themes_label.text = themes_text

## 游戏类型推荐完成
func _on_game_types_recommended(types: Array) -> void:
	_hide_loading()
	is_processing = false
	
	if types.is_empty():
		status_label.text = "未获取到游戏类型推荐"
		return
	
	_show_game_types(types)

## 显示游戏类型选择
func _show_game_types(types: Array) -> void:
	game_type_panel.visible = true
	
	# 清空容器
	for child in game_types_container.get_children():
		child.queue_free()
	
	# 添加游戏类型选项
	for type in types:
		var card = _create_game_type_card(type)
		game_types_container.add_child(card)
	
	# 滚动到顶部
	game_types_container.get_parent().scroll_vertical = 0

## 创建游戏类型卡片
func _create_game_type_card(type_data: Dictionary) -> PanelContainer:
	var panel = PanelContainer.new()
	panel.custom_minimum_size = Vector2(300, 180)
	
	var style = StyleBoxFlat.new()
	style.bg_color = Color(0.15, 0.15, 0.2, 1)
	style.set_corner_radius_all(10)
	style.set_content_margin_all(15)
	panel.add_theme_stylebox_override("panel", style)
	
	var margin = MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 10)
	margin.add_theme_constant_override("margin_right", 10)
	margin.add_theme_constant_override("margin_top", 10)
	margin.add_theme_constant_override("margin_bottom", 10)
	panel.add_child(margin)
	
	var vbox = VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 8)
	margin.add_child(vbox)
	
	# 标题
	var title = Label.new()
	title.text = type_data.get("name", "未知类型")
	title.add_theme_font_size_override("font_size", 20)
	title.add_theme_color_override("font_color", Color(0.9, 0.9, 1.0))
	vbox.add_child(title)
	
	# 类型标识
	var type_label = Label.new()
	type_label.text = "类型: %s" % type_data.get("type", "未知")
	type_label.add_theme_font_size_override("font_size", 12)
	type_label.add_theme_color_override("font_color", Color(0.6, 0.6, 0.7))
	vbox.add_child(type_label)
	
	# 描述
	var desc = RichTextLabel.new()
	desc.text = type_data.get("reason", "")
	desc.bbcode_enabled = true
	desc.fit_content = true
	desc.custom_minimum_size.y = 40
	vbox.add_child(desc)
	
	# 特性列表
	var features = type_data.get("features", [])
	if not features.is_empty():
		var features_text = "特性: " + ", ".join(features.slice(0, 4))  # 最多显示4个
		if features.size() > 4:
			features_text += "..."
		var features_label = Label.new()
		features_label.text = features_text
		features_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		features_label.add_theme_font_size_override("font_size", 12)
		vbox.add_child(features_label)
	
	# 选择按钮
	var button = Button.new()
	button.text = "选择此类型"
	button.custom_minimum_size = Vector2(0, 35)
	var btn_style = StyleBoxFlat.new()
	btn_style.bg_color = Color(0.2, 0.5, 0.8, 1)
	btn_style.set_corner_radius_all(5)
	button.add_theme_stylebox_override("normal", btn_style)
	button.pressed.connect(_on_game_type_button_pressed.bind(type_data.get("type", "rpg")))
	vbox.add_child(button)
	
	return panel

## 游戏类型选择
func _on_game_type_button_pressed(game_type: String) -> void:
	_hide_all_panels()
	game_type_selected.emit(game_type)
	_generate_game(game_type)

## 生成游戏
func _generate_game(game_type: String) -> void:
	is_processing = true
	_show_loading("正在生成游戏...")
	llm_client.generate_game_config(current_text, current_analysis, game_type)

## 生成进度回调
func _on_generation_progress(step: String, progress: float) -> void:
	progress_bar.value = progress * 100
	loading_label.text = step

## 游戏生成完成
func _on_game_generated(project_path: String) -> void:
	_hide_loading()
	is_processing = false
	
	# 显示成功消息
	var dialog = AcceptDialog.new()
	dialog.title = "游戏生成完成！"
	dialog.size = Vector2i(600, 300)
	
	var vbox = VBoxContainer.new()
	dialog.add_child(vbox)
	
	var success_label = Label.new()
	success_label.text = "✓ 游戏已成功生成！"
	success_label.add_theme_font_size_override("font_size", 20)
	success_label.add_theme_color_override("font_color", Color.GREEN)
	vbox.add_child(success_label)
	
	var path_label = Label.new()
	path_label.text = "项目路径: %s" % project_path
	path_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	vbox.add_child(path_label)
	
	var info_label = RichTextLabel.new()
	info_label.text = "[center]使用Godot 4.7打开此目录即可运行游戏。[/center]"
	info_label.bbcode_enabled = true
	info_label.fit_content = true
	vbox.add_child(info_label)
	
	var button_container = HBoxContainer.new()
	button_container.alignment = 1
	vbox.add_child(button_container)
	
	var open_btn = Button.new()
	open_btn.text = "在文件夹中打开"
	open_btn.custom_minimum_size = Vector2(150, 35)
	open_btn.pressed.connect(func(): 
		OS.shell_show_in_file_manager(project_path)
	)
	button_container.add_child(open_btn)
	
	var ok_btn = Button.new()
	ok_btn.text = "确定"
	ok_btn.custom_minimum_size = Vector2(100, 35)
	ok_btn.pressed.connect(func(): dialog.queue_free())
	button_container.add_child(ok_btn)
	
	add_child(dialog)
	dialog.popup_centered()

## 生成失败
func _on_generation_failed(error: String) -> void:
	_hide_loading()
	is_processing = false
	status_label.text = "生成失败: " + error
	status_label.add_theme_color_override("font_color", Color.RED)

## 分析失败
func _on_analysis_failed(error: String) -> void:
	_hide_loading()
	is_processing = false
	analyze_button.disabled = false
	example_button.disabled = false
	status_label.text = "分析失败: " + error
	status_label.add_theme_color_override("font_color", Color.RED)

## 分析进度更新
func _on_analysis_progress(step: String, progress: float) -> void:
	if show_detailed_progress:
		loading_label.text = step
		progress_bar.value = progress * 100

## LLM进度更新
func _on_llm_progress(step: String, current: int, total: int) -> void:
	if show_detailed_progress:
		loading_label.text = step
		progress_bar.value = float(current) / float(total) * 100

## 显示/隐藏加载面板
func _show_loading(message: String = "加载中...") -> void:
	loading_panel.visible = true
	loading_label.text = message
	progress_bar.value = 0

func _hide_loading() -> void:
	loading_panel.visible = false

## 隐藏所有面板
func _hide_all_panels() -> void:
	analysis_panel.visible = false
	game_type_panel.visible = false
	loading_panel.visible = false

## 返回按钮
func _on_back_button_pressed() -> void:
	_hide_all_panels()
	$VBoxContainer.visible = true

## 清空按钮
func _on_clear_button_pressed() -> void:
	if is_processing:
		status_label.text = "正在处理中，请稍候..."
		return
	
	text_input.text = ""
	current_text = ""
	current_analysis = {}
	status_label.text = ""
	_hide_all_panels()
	text_analyzer.clear_state()

## 关于按钮
func _on_about_button_pressed() -> void:
	var dialog = AcceptDialog.new()
	dialog.title = "关于 Text2Game"
	dialog.size = Vector2i(600, 400)
	
	var label = RichTextLabel.new()
	label.text = """[center][b]Text2Game v1.0[/b]

将文本转换为可玩游戏的元系统

[b]功能:[b]
• 智能文本分析（支持长文本分块处理）
• 自动推荐游戏类型
• 一键生成完整游戏项目
• 支持多种游戏类型

[b]技术:[b]
• Godot 4.7 游戏引擎
• LM Studio / OpenAI兼容API
• 分块处理和重试机制

[b]使用方法:[b]
1. 输入或粘贴文本
2. 点击"分析文本"
3. 选择游戏类型
4. 等待游戏生成
5. 使用Godot打开项目

[b]支持的游戏类型:[b]
• RPG (角色扮演)
• Adventure (冒险解谜)
• Visual Novel (视觉小说)
• Strategy (策略模拟)
• Action (动作平台)[/center]"""
	label.bbcode_enabled = true
	label.fit_content = true
	dialog.add_child(label)
	
	add_child(dialog)
	dialog.popup_centered()

## 获取系统状态
func get_system_status() -> Dictionary:
	return {
		"is_processing": is_processing,
		"has_text": not current_text.is_empty(),
		"has_analysis": not current_analysis.is_empty(),
		"analyzer_status": text_analyzer.get_status() if text_analyzer else {}
	}

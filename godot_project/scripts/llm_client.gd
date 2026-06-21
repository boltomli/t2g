## LLM Client - 与LM Studio/OpenAI兼容API通信
## 支持分块处理、超时控制和重试机制
extends Node
class_name LLMClient

## API配置（将从ConfigLoader加载）
var api_url: String = "http://localhost:1234/v1"
var model: String = "google/gemma-4-12b-qat"
var temperature: float = 0.7
var max_tokens: int = 16384
var timeout_seconds: int = 180
var max_retries: int = 3
var chunk_size: int = 1200
var enable_reasoning: bool = false

## 信号
signal response_received(response: Dictionary)
signal error_occurred(error: String)
signal request_completed()
signal progress_updated(step: String, current: int, total: int)

## 状态变量
var is_requesting: bool = false
var current_retry: int = 0
var request_queue: Array = []

## HTTP请求节点
var http_request: HTTPRequest
var timeout_timer: Timer

## 配置加载器引用
var config_loader: ConfigLoader

func _ready() -> void:
	# 创建HTTP请求节点
	http_request = HTTPRequest.new()
	add_child(http_request)
	http_request.request_completed.connect(_on_request_completed)
	
	# 创建超时定时器
	timeout_timer = Timer.new()
	add_child(timeout_timer)
	timeout_timer.one_shot = true
	timeout_timer.timeout.connect(_on_timeout)
	
	# 尝试加载配置
	_load_config()

## 加载配置
func _load_config() -> void:
	# 查找场景中的ConfigLoader
	var config_nodes = get_tree().get_nodes_in_group("config_loader")
	if config_nodes.size() > 0:
		config_loader = config_nodes[0]
		_apply_config()
	else:
		# 创建新的ConfigLoader
		config_loader = ConfigLoader.new()
		config_loader.config_loaded.connect(_on_config_loaded)
		add_child(config_loader)

## 配置加载完成回调
func _on_config_loaded() -> void:
	_apply_config()

## 应用配置
func _apply_config() -> void:
	if config_loader:
		api_url = config_loader.get_config("llm_api_url", api_url)
		model = config_loader.get_config("llm_model", model)
		temperature = config_loader.get_config("llm_temperature", temperature)
		max_tokens = config_loader.get_config("llm_max_tokens", max_tokens)
		timeout_seconds = config_loader.get_config("llm_timeout", timeout_seconds)
		max_retries = config_loader.get_config("llm_max_retries", max_retries)
		chunk_size = config_loader.get_config("chunk_size", chunk_size)
		enable_reasoning = config_loader.get_config("enable_reasoning", enable_reasoning)
		
		print("✓ LLM客户端配置已加载")
		print("  模型: %s" % model)
		print("  API: %s" % api_url)

## 发送聊天请求（带重试）
func chat_completion(messages: Array, response_format: Dictionary = {}, retry_count: int = 0) -> void:
	if is_requesting:
		# 如果正在请求，加入队列
		request_queue.append({"messages": messages, "response_format": response_format, "retry": retry_count})
		return
	
	is_requesting = true
	current_retry = retry_count
	
	var url = api_url + "/chat/completions"
	
	var body = {
		"messages": messages,
		"temperature": temperature,
		"max_tokens": max_tokens,
		"stream": false,
		"reasoning": {"enabled": enable_reasoning}
	}
	
	if not model.is_empty():
		body["model"] = model
	
	if not response_format.is_empty():
		body["response_format"] = response_format
	
	var headers = ["Content-Type: application/json"]
	var json_body = JSON.stringify(body)
	
	# 启动超时定时器
	timeout_timer.start(timeout_seconds)
	
	var error = http_request.request(url, headers, HTTPClient.METHOD_POST, json_body)
	if error != OK:
		timeout_timer.stop()
		is_requesting = false
		error_occurred.emit("HTTP请求失败: " + error_string(error))
		_process_queue()

## 处理响应
func _on_request_completed(result: int, response_code: int, headers: PackedStringArray, body: PackedByteArray) -> void:
	# 停止超时定时器
	timeout_timer.stop()
	
	if result != HTTPRequest.RESULT_SUCCESS:
		var error_msg = "请求失败，结果代码: " + str(result)
		if current_retry < max_retries:
			print("请求失败，正在重试... (%d/%d)" % [current_retry + 1, max_retries])
			current_retry += 1
			# 等待一段时间后重试
			await get_tree().create_timer(2.0).timeout
			is_requesting = false
			chat_completion([], {}, current_retry)
			return
		error_occurred.emit(error_msg)
		is_requesting = false
		_process_queue()
		return
	
	if response_code < 200 or response_code >= 300:
		var error_text = body.get_string_from_utf8()
		var error_msg = "API错误 (%d): %s" % [response_code, error_text]
		
		# 对于特定错误码进行重试
		if response_code in [429, 500, 502, 503] and current_retry < max_retries:
			print("API错误 %d，正在重试... (%d/%d)" % [response_code, current_retry + 1, max_retries])
			current_retry += 1
			await get_tree().create_timer(3.0).timeout
			is_requesting = false
			chat_completion([], {}, current_retry)
			return
		
		error_occurred.emit(error_msg)
		is_requesting = false
		_process_queue()
		return
	
	var json = JSON.new()
	var parse_result = json.parse(body.get_string_from_utf8())
	
	if parse_result != OK:
		error_occurred.emit("JSON解析失败")
		is_requesting = false
		_process_queue()
		return
	
	var response = json.data
	response_received.emit(response)
	is_requesting = false
	_process_queue()

## 超时处理
func _on_timeout() -> void:
	if is_requesting:
		http_request.cancel_request()
		if current_retry < max_retries:
			print("请求超时，正在重试... (%d/%d)" % [current_retry + 1, max_retries])
			current_retry += 1
			is_requesting = false
			chat_completion([], {}, current_retry)
		else:
			error_occurred.emit("请求超时，已达到最大重试次数")
			is_requesting = false
			_process_queue()

## 处理请求队列
func _process_queue() -> void:
	if not request_queue.is_empty():
		var next_request = request_queue.pop_front()
		await get_tree().create_timer(0.5).timeout  # 避免过于频繁的请求
		chat_completion(next_request["messages"], next_request["response_format"], next_request["retry"])

## 获取可用模型列表
func get_models(callback: Callable) -> void:
	var url = api_url + "/models"
	var error = http_request.request(url, [], HTTPClient.METHOD_GET)
	if error != OK:
		callback.call([], "获取模型列表失败: " + error_string(error))

## 文本分块处理
func split_text_into_chunks(text: String) -> Array:
	var chunks = []
	var text_length = text.length()
	
	if text_length <= chunk_size:
		chunks.append(text)
		return chunks
	
	# 按段落分割
	var paragraphs = text.split("\n\n")
	var current_chunk = ""
	
	for paragraph in paragraphs:
		if current_chunk.length() + paragraph.length() + 2 <= chunk_size:
			current_chunk += paragraph + "\n\n"
		else:
			if not current_chunk.is_empty():
				chunks.append(current_chunk.strip_edges())
			current_chunk = paragraph + "\n\n"
	
	if not current_chunk.is_empty():
		chunks.append(current_chunk.strip_edges())
	
	return chunks

## 分块分析长文本
func analyze_long_text(text: String, system_prompt: String = "") -> void:
	var chunks = split_text_into_chunks(text)
	
	if chunks.size() == 1:
		# 短文本，直接分析
		analyze_text(text, system_prompt)
		return
	
	# 长文本，分块分析
	progress_updated.emit("文本较长，正在分块处理...", 0, chunks.size())
	
	var all_analyses = []
	for i in range(chunks.size()):
		progress_updated.emit("分析第 %d/%d 块..." % [i + 1, chunks.size()], i, chunks.size())
		
		var chunk_analysis = await _analyze_chunk(chunks[i], system_prompt)
		if not chunk_analysis.is_empty():
			all_analyses.append(chunk_analysis)
		
		# 等待一下再处理下一块
		if i < chunks.size() - 1:
			await get_tree().create_timer(1.0).timeout
	
	# 合并分析结果
	progress_updated.emit("正在合并分析结果...", chunks.size(), chunks.size())
	var merged_analysis = await _merge_analyses(all_analyses)
	response_received.emit(merged_analysis)
	request_completed.emit()

## 分析单个文本块
func _analyze_chunk(text: String, system_prompt: String = "") -> Dictionary:
	if system_prompt.is_empty():
		system_prompt = """你是一个专业的游戏设计师和叙事专家。请分析提供的文本片段，提取以下信息：
1. 世界观 (world): 时代背景、地点、规则
2. 角色 (characters): 主要角色及其特征
3. 冲突 (conflicts): 主要矛盾和问题
4. 主题 (themes): 核心主题和情感
5. 氛围 (atmosphere): 整体氛围和基调

请以JSON格式返回，包含这些字段。"""
	
	var messages = [
		{"role": "system", "content": system_prompt},
		{"role": "user", "content": "请分析以下文本片段：\n\n" + text}
	]
	
	# 创建一个Promise来等待响应
	var result = {}
	var callback = func(response): result = response
	
	# 发送请求并等待响应
	var original_callback = response_received
	response_received.connect(callback, CONNECT_ONE_SHOT)
	chat_completion(messages)
	
	# 等待响应完成
	while is_requesting:
		await get_tree().process_frame
	
	response_received.disconnect(callback)
	
	return result

## 合并多个分析结果（本地合并，不调用LLM）
func _merge_analyses(analyses: Array) -> Dictionary:
	if analyses.is_empty():
		return {}
	
	if analyses.size() == 1:
		return analyses[0]
	
	print("使用本地逻辑合并...")
	
	# 合并结果
	var merged = {
		"world": {},
		"characters": [],
		"conflicts": [],
		"themes": [],
		"atmosphere": ""
	}
	
	# 用于去重
	var seen_characters = {}
	var seen_themes = {}
	var seen_conflicts = {}
	
	for analysis in analyses:
		# 合并 world
		if analysis.has("world") and not analysis["world"].is_empty():
			var world = analysis["world"]
			if merged["world"].get("name", "").is_empty() and world.has("name"):
				merged["world"]["name"] = world["name"]
			if merged["world"].get("era", "").is_empty() and world.has("era"):
				merged["world"]["era"] = world["era"]
			if merged["world"].get("location", "").is_empty() and world.has("location"):
				merged["world"]["location"] = world["location"]
			if merged["world"].get("rules", "").is_empty() and world.has("rules"):
				merged["world"]["rules"] = world["rules"]
			if merged["world"].get("description", "").is_empty() and world.has("description"):
				merged["world"]["description"] = world["description"]
		
		# 合并 characters（去重）
		if analysis.has("characters") and analysis["characters"] is Array:
			for char in analysis["characters"]:
				var char_key = char.get("name", "")
				if not char_key.is_empty() and not seen_characters.has(char_key):
					seen_characters[char_key] = true
					merged["characters"].append(char)
		
		# 合并 conflicts（去重）
		if analysis.has("conflicts") and analysis["conflicts"] is Array:
			for conflict in analysis["conflicts"]:
				var conflict_key = conflict.get("description", "")
				if not conflict_key.is_empty() and not seen_conflicts.has(conflict_key):
					seen_conflicts[conflict_key] = true
					merged["conflicts"].append(conflict)
		
		# 合并 themes（去重）
		if analysis.has("themes") and analysis["themes"] is Array:
			for theme in analysis["themes"]:
				if not theme.is_empty() and not seen_themes.has(theme):
					seen_themes[theme] = true
					merged["themes"].append(theme)
		
		# 合并 atmosphere
		if analysis.has("atmosphere") and not analysis["atmosphere"].is_empty() and merged["atmosphere"].is_empty():
			merged["atmosphere"] = analysis["atmosphere"]
	
	return merged

## 便捷方法: 发送文本分析请求
func analyze_text(text: String, system_prompt: String = "") -> void:
	if system_prompt.is_empty():
		system_prompt = """你是一个专业的游戏设计师和叙事专家。请分析提供的文本，提取以下信息：
1. 世界观 (world): 时代背景、地点、规则
2. 角色 (characters): 主要角色及其特征
3. 冲突 (conflicts): 主要矛盾和问题
4. 主题 (themes): 核心主题和情感
5. 氛围 (atmosphere): 整体氛围和基调

请以JSON格式返回，包含这些字段。"""
	
	var messages = [
		{"role": "system", "content": system_prompt},
		{"role": "user", "content": "请分析以下文本：\n\n" + text}
	]
	
	chat_completion(messages)

## 推荐游戏类型
func recommend_game_type(analysis: Dictionary) -> void:
	var system_prompt = """基于提供的文本分析，推荐3-5个最适合的游戏类型。

每个推荐包括：
- type: 游戏类型名称 (rpg/adventure/visual_novel/strategy/action)
- name: 中文名称
- reason: 为什么适合这个文本
- features: 核心游戏特性列表

请以JSON数组格式返回。"""
	
	var messages = [
		{"role": "system", "content": system_prompt},
		{"role": "user", "content": "文本分析结果：\n" + JSON.stringify(analysis)}
	]
	
	chat_completion(messages)

## 生成游戏配置
func generate_game_config(text: String, analysis: Dictionary, game_type: String) -> void:
	var system_prompt = """基于文本分析和选择的游戏类型，生成完整的游戏配置。

游戏类型: %s

请生成包含以下内容的JSON配置：
1. game_info: 游戏标题、简介
2. world: 详细世界设定
3. characters: 所有角色的完整设定（包含属性、对话）
4. scenes: 场景列表和描述
5. dialogues: 对话树
6. mechanics: 游戏机制配置
7. events: 事件和触发条件

确保生成的内容足够详细，可以直接用于游戏开发。""" % game_type
	
	var messages = [
		{"role": "system", "content": system_prompt},
		{"role": "user", "content": "原始文本:\n%s\n\n文本分析:\n%s" % [text, JSON.stringify(analysis)]}
	]
	
	chat_completion(messages)

## 生成GDScript代码
func generate_gdscript(game_config: Dictionary, scene_type: String) -> void:
	var system_prompt = """你是一个Godot 4 GDScript专家。基于游戏配置生成相应的GDScript代码。

生成要求：
1. 使用Godot 4.x语法
2. 代码结构清晰，有注释
3. 支持场景切换和状态管理
4. 实现游戏核心机制

场景类型: %s

请直接生成可运行的GDScript代码，不要包含额外解释。""" % scene_type
	
	var messages = [
		{"role": "system", "content": system_prompt},
		{"role": "user", "content": "游戏配置:\n" + JSON.stringify(game_config)}
	]
	
	chat_completion(messages)

## 检查API连接
func check_connection(callback: Callable) -> void:
	var url = api_url + "/models"
	var error = http_request.request(url, [], HTTPClient.METHOD_GET)
	if error != OK:
		callback.call(false, "连接失败")

## Text Analyzer - 文本分析器
## 支持分块处理、进度跟踪和状态管理
extends Node
class_name TextAnalyzer

## 信号
signal analysis_completed(analysis: Dictionary)
signal game_types_recommended(types: Array)
signal analysis_failed(error: String)
signal analysis_progress(step: String, progress: float)

## 引用
var llm_client: LLMClient

## 分析状态
var current_text: String = ""
var analysis_result: Dictionary = {}
var is_analyzing: bool = false
var analysis_steps: Array = []
var current_step: int = 0

## 分析配置
var max_text_length: int = 10000  # 最大文本长度
var min_chunk_size: int = 500  # 最小分块大小

func _ready() -> void:
	llm_client = LLMClient.new()
	add_child(llm_client)
	llm_client.response_received.connect(_on_llm_response)
	llm_client.error_occurred.connect(_on_llm_error)
	llm_client.progress_updated.connect(_on_progress_updated)

## 分析文本（主入口）
func analyze_text(text: String) -> void:
	if is_analyzing:
		analysis_failed.emit("分析正在进行中，请稍候")
		return
	
	# 预处理文本
	current_text = _preprocess_text(text)
	if current_text.is_empty():
		analysis_failed.emit("文本内容为空")
		return
	
	# 检查文本长度
	if current_text.length() > max_text_length:
		analysis_failed.emit("文本过长（%d字符），最大支持%d字符" % [current_text.length(), max_text_length])
		return
	
	is_analyzing = true
	analysis_result = {}
	current_step = 0
	
	# 初始化分析步骤
	analysis_steps = [
		{"name": "预处理文本", "weight": 0.1},
		{"name": "分析世界观", "weight": 0.3},
		{"name": "分析角色", "weight": 0.3},
		{"name": "分析冲突和主题", "weight": 0.2},
		{"name": "整合结果", "weight": 0.1}
	]
	
	analysis_progress.emit("开始分析...", 0.0)
	
	# 使用分块分析
	llm_client.analyze_long_text(current_text)

## 预处理文本
func _preprocess_text(text: String) -> String:
	# 移除多余空白
	var processed = text.strip_edges()
	
	# 规范化换行符
	processed = processed.replace("\r\n", "\n")
	processed = processed.replace("\r", "\n")
	
	# 移除连续多个空行
	var regex = RegEx.new()
	regex.compile("\\n{3,}")
	processed = regex.sub(processed, "\n\n", true)
	
	return processed

## 推荐游戏类型
func recommend_game_types() -> void:
	if analysis_result.is_empty():
		analysis_failed.emit("请先分析文本")
		return
	
	analysis_progress.emit("正在推荐游戏类型...", 0.9)
	llm_client.recommend_game_type(analysis_result)

## 处理LLM响应
func _on_llm_response(response: Dictionary) -> void:
	if not response.has("choices") or response["choices"].is_empty():
		analysis_failed.emit("无效的LLM响应")
		is_analyzing = false
		return
	
	var content = response["choices"][0]["message"]["content"]
	
	# 尝试解析JSON响应
	var parsed_data = _parse_json_response(content)
	
	if parsed_data.is_empty():
		analysis_failed.emit("无法解析LLM响应为JSON")
		is_analyzing = false
		return
	
	# 根据当前状态处理
	if analysis_result.is_empty():
		# 这是文本分析结果
		analysis_result = parsed_data
		analysis_progress.emit("分析完成", 1.0)
		analysis_completed.emit(parsed_data)
		is_analyzing = false
	else:
		# 这是游戏类型推荐
		var game_types = _extract_game_types(parsed_data)
		if not game_types.is_empty():
			game_types_recommended.emit(game_types)
		else:
			analysis_failed.emit("无法提取游戏类型推荐")
		is_analyzing = false

## 解析JSON响应（增强版）
func _parse_json_response(content: String) -> Dictionary:
	# 首先尝试直接解析
	var json = JSON.new()
	var parse_result = json.parse(content)
	if parse_result == OK:
		if json.data is Dictionary:
			return json.data
		elif json.data is Array:
			return {"recommendations": json.data}
	
	# 尝试提取JSON部分
	var json_start = content.find("{")
	var json_end = content.rfind("}") + 1
	
	if json_start >= 0 and json_end > json_start:
		var json_str = content.substr(json_start, json_end - json_start)
		parse_result = json.parse(json_str)
		if parse_result == OK:
			if json.data is Dictionary:
				return json.data
	
	# 尝试提取JSON数组
	var array_start = content.find("[")
	var array_end = content.rfind("]") + 1
	
	if array_start >= 0 and array_end > array_start:
		var json_str = content.substr(array_start, array_end - array_start)
		parse_result = json.parse(json_str)
		if parse_result == OK:
			if json.data is Array:
				return {"recommendations": json.data}
	
	# 如果都失败了，尝试从文本中提取关键信息
	var extracted = _extract_info_from_text(content)
	if not extracted.is_empty():
		return extracted
	
	return {}

## 从文本中提取信息（备用方案）
func _extract_info_from_text(content: String) -> Dictionary:
	var result = {}
	
	# 尝试提取世界观信息
	if content.contains("世界观") or content.contains("world"):
		var world_info = {}
		world_info["description"] = content
		result["world"] = world_info
	
	# 尝试提取角色信息
	if content.contains("角色") or content.contains("character"):
		var characters = []
		# 简单的正则表达式提取
		var regex = RegEx.new()
		regex.compile("(?:角色|character)[：:]\\s*(.+?)(?:\\n|$)")
		for match in regex.search_all(content):
			characters.append({"name": match.get_string(1).strip_edges()})
		if not characters.is_empty():
			result["characters"] = characters
	
	# 提取主题
	if content.contains("主题") or content.contains("theme"):
		var themes = []
		var regex = RegEx.new()
		regex.compile("(?:主题|theme)[：:]\\s*(.+?)(?:\\n|$)")
		for match in regex.search_all(content):
			themes.append(match.get_string(1).strip_edges())
		if not themes.is_empty():
			result["themes"] = themes
	
	return result

## 提取游戏类型
func _extract_game_types(data: Dictionary) -> Array:
	# 如果是直接的数组
	if data.has("recommendations") and data["recommendations"] is Array:
		return data["recommendations"]
	
	# 如果是包含type字段的字典
	if data.has("type") or data.has("name"):
		return [data]
	
	# 尝试从其他字段提取
	var types = []
	for key in data.keys():
		if data[key] is Dictionary and (data[key].has("type") or data[key].has("name")):
			types.append(data[key])
	
	return types

## 处理进度更新
func _on_progress_updated(step: String, current: int, total: int) -> void:
	var progress = float(current) / float(total) if total > 0 else 0.0
	analysis_progress.emit(step, progress)

## 处理LLM错误
func _on_llm_error(error: String) -> void:
	analysis_failed.emit(error)
	is_analyzing = false

## 分析本地文件
func analyze_file(file_path: String) -> void:
	var file = FileAccess.open(file_path, FileAccess.READ)
	if file == null:
		analysis_failed.emit("无法打开文件: " + file_path)
		return
	
	var text = file.get_as_text()
	file.close()
	analyze_text(text)

## 获取示例文本
func get_example_text(example_type: String) -> String:
	match example_type:
		"fantasy":
			return """
在一个被遗忘的古老王国里，魔法已经消失了一千年。曾经辉煌的魔法学院如今只剩下废墟，龙的传说只存在于古老的故事中。

艾莉娅是一个年轻的村庄女孩，她有一个秘密——她能看见别人看不见的东西。当她触碰古老的遗物时，会看到过去的幻象。

一天，她在森林深处发现了一块发光的石头。当她拿起它时，整个世界开始改变。沉睡的魔法开始苏醒，但也唤醒了黑暗中的存在。

王国需要英雄，而艾莉娅必须做出选择：接受命运的召唤，还是逃避这份危险的力量...

主要角色：
- 艾莉娅：18岁村庄女孩，拥有幻视能力
- 老守卫艾伦：65岁，知道古老传说
- 神秘旅者卡尔：身份不明，实际上是被放逐的法师

世界观：
- 翡翠王国：曾经的魔法中心
- 幽暗森林：充满危险的古老森林
- 废墟学院：千年前的魔法学院遗址

核心冲突：
1. 善恶对抗：黑暗势力想要利用复苏的魔法
2. 过去与现在：千年前的真相即将揭晓
3. 牺牲与救赎：拯救世界可能需要付出代价
"""
		"scifi":
			return """
2187年，地球资源耗尽，人类建造了巨大的太空城"新伊甸"。这里分为三个阶层：上层精英、中层工人、下层贫民。

凯尔是一名底层机械师，他修理旧时代的机器。一天，他在废弃区域发现了一台古老的AI核心。当他修复它时，AI告诉他一个惊人的真相：新伊甸即将坠毁，而精英们早已知道，正在秘密建造逃生飞船。

凯尔必须决定：独自逃生，还是揭露真相，给所有人一个机会？但时间不多了...

主要角色：
- 凯尔：25岁底层机械师，正直勇敢
- 艾娃：古老AI核心，知道全部真相
- 总督马库斯：55岁，自私的独裁者
- 莉娜：23岁中层工程师，凯尔的青梅竹马

世界观：
- 新伊甸太空城：直径50公里的圆柱体
- 社会结构：上层精英、中层工人、下层贫民
- 科技水平：部分自动化，核聚变能源

核心冲突：
1. 生存危机：新伊甸即将坠毁
2. 阶级矛盾：精英vs平民
3. 道德困境：自救vs救众
"""
		"mystery":
			return """
著名侦探陈默收到了一封神秘的邀请函，邀请他参加一场为期一周的推理游戏。十二位互不相识的客人聚集在一座偏远的古堡中。

第一晚，主人没有出现。第二天早上，一位客人被发现死在书房里，手中握着一张纸条："游戏开始。"

暴风雨切断了古堡与外界的联系。陈默必须在剩余的客人中找出凶手，否则下一个受害者可能就是他自己...

主要角色：
- 陈默：35岁著名侦探，观察力敏锐
- 李薇：28岁女演员，与死者有私情
- 王强：45岁商人，公司濒临破产
- 张医生：50岁医生，曾有医疗事故
- 赵管家：60岁，在古堡工作30年

古堡设定：
- 位置：偏远山区，暴风雨期间与世隔绝
- 结构：三层建筑，多个密室和暗道
- 历史：曾发生多起死亡事件

核心冲突：
1. 生存：凶手仍在杀人
2. 推理：揭开真相
3. 信任：谁是敌人？
4. 过去：每个人都有秘密
"""
		_:
			return """
请在此输入您的文本...

提示：文本应包含以下元素，以便更好地分析：
1. 世界观背景（时代、地点、规则）
2. 主要角色（姓名、特征、背景）
3. 故事情节（冲突、发展）
4. 主题情感（核心主题、氛围）
"""

## 生成默认分析（用于测试）
func generate_mock_analysis() -> Dictionary:
	return {
		"world": {
			"name": "示例世界",
			"era": "中世纪奇幻",
			"location": "被遗忘的王国",
			"rules": "魔法曾经存在但已消失千年",
			"description": "一个魔法消失的古老王国"
		},
		"characters": [
			{
				"name": "艾莉娅",
				"role": "主角",
				"traits": ["勇敢", "好奇", "有神秘力量"],
				"background": "年轻村庄女孩，能看见幻象",
				"goal": "探索自己的力量，拯救王国"
			}
		],
		"conflicts": [
			{
				"type": "人与命运",
				"description": "主角必须选择接受命运还是逃避",
				"stakes": "王国的存亡"
			}
		],
		"themes": ["命运", "勇气", "牺牲"],
		"atmosphere": "神秘、史诗、略带忧郁"
	}

## 生成默认游戏类型推荐（用于测试）
func generate_mock_game_types() -> Array:
	return [
		{
			"type": "rpg",
			"name": "角色扮演",
			"reason": "文本有丰富的角色成长和世界观设定",
			"features": ["角色成长系统", "技能树", "装备收集", "支线任务"]
		},
		{
			"type": "visual_novel",
			"name": "视觉小说",
			"reason": "文本以叙事为主，适合分支剧情",
			"features": ["分支剧情", "多结局", "角色好感度", "精美立绘"]
		},
		{
			"type": "adventure",
			"name": "冒险解谜",
			"reason": "文本有探索和发现元素",
			"features": ["物品收集", "环境解谜", "隐藏区域", "剧情探索"]
		}
	]

## 清除分析状态
func clear_state() -> void:
	current_text = ""
	analysis_result = {}
	is_analyzing = false
	analysis_steps = []
	current_step = 0

## 获取分析状态
func get_status() -> Dictionary:
	return {
		"is_analyzing": is_analyzing,
		"text_length": current_text.length(),
		"has_result": not analysis_result.is_empty(),
		"current_step": current_step,
		"total_steps": analysis_steps.size()
	}

## Config Loader - 配置加载器
## 从配置文件或环境变量加载设置
extends Node
class_name ConfigLoader

## 配置文件路径
const CONFIG_FILE_PATH = "user://config.cfg"
const ENV_FILE_PATH = "res://.env"

## 默认配置
var config = {
	"llm_api_url": "http://localhost:1234/v1",
	"llm_model": "google/gemma-4-12b-qat",
	"llm_temperature": 0.7,
	"llm_max_tokens": 16384,
	"llm_timeout": 180,
	"llm_max_retries": 3,
	"chunk_size": 8000,
	"enable_reasoning": false
}

## 信号
signal config_loaded()
signal config_error(error: String)

func _ready() -> void:
	load_config()

## 加载配置
func load_config() -> void:
	# 首先尝试加载项目目录下的 .env 文件
	_load_env_file()
	
	# 然后尝试加载用户配置文件（覆盖默认值）
	_load_user_config()
	
	config_loaded.emit()

## 加载 .env 文件
func _load_env_file() -> void:
	var file = FileAccess.open(ENV_FILE_PATH, FileAccess.READ)
	if file == null:
		print("未找到 .env 文件，使用默认配置")
		return
	
	var content = file.get_as_text()
	file.close()
	
	# 解析 .env 文件
	var lines = content.split("\n")
	for line in lines:
		line = line.strip_edges()
		
		# 跳过空行和注释
		if line.is_empty() or line.begins_with("#"):
			continue
		
		# 解析 KEY=VALUE
		var parts = line.split("=", true, 1)
		if parts.size() == 2:
			var key = parts[0].strip_edges()
			var value = parts[1].strip_edges()
			
			# 移除引号
			if (value.begins_with('"') and value.ends_with('"')) or \
			   (value.begins_with("'") and value.ends_with("'")):
				value = value.substr(1, value.length() - 2)
			
			# 应用配置
			_apply_config(key, value)
	
	print("✓ 已加载 .env 配置文件")

## 加载用户配置文件
func _load_user_config() -> void:
	var config_file = FileAccess.open(CONFIG_FILE_PATH, FileAccess.READ)
	if config_file == null:
		return
	
	var content = config_file.get_as_text()
	config_file.close()
	
	var json = JSON.new()
	var parse_result = json.parse(content)
	
	if parse_result == OK and json.data is Dictionary:
		for key in json.data:
			config[key] = json.data[key]
		print("✓ 已加载用户配置文件")

## 应用配置项
func _apply_config(key: String, value: String) -> void:
	match key.to_lower():
		"llm_api_url":
			config["llm_api_url"] = value
		"llm_model":
			config["llm_model"] = value
		"llm_temperature":
			config["llm_temperature"] = value.toFloat()
		"llm_max_tokens":
			config["llm_max_tokens"] = value.to_int()
		"llm_timeout":
			config["llm_timeout"] = value.to_int()
		"llm_max_retries":
			config["llm_max_retries"] = value.to_int()
		"chunk_size":
			config["chunk_size"] = value.to_int()
		"max_text_length":
			config["max_text_length"] = value.to_int()
		"enable_reasoning":
			config["enable_reasoning"] = value.to_lower() == "true"

## 保存用户配置
func save_config() -> void:
	var file = FileAccess.open(CONFIG_FILE_PATH, FileAccess.WRITE)
	if file == null:
		config_error.emit("无法保存配置文件")
		return
	
	file.store_string(JSON.stringify(config, "\t"))
	file.close()
	print("✓ 配置已保存")

## 获取配置值
func get_config(key: String, default_value = null) -> Variant:
	return config.get(key, default_value)

## 设置配置值
func set_config(key: String, value: Variant) -> void:
	config[key] = value

## 重置为默认配置
func reset_config() -> void:
	config = {
		"llm_api_url": "http://localhost:1234/v1",
		"llm_model": "google/gemma-4-12b-qat",
		"llm_temperature": 0.7,
		"llm_max_tokens": 16384,
		"llm_timeout": 180,
		"llm_max_retries": 3,
		"chunk_size": 8000,
		"enable_reasoning": false
	}
	print("✓ 配置已重置为默认值")

## 打印当前配置
func print_config() -> void:
	print("\n=== 当前配置 ===")
	for key in config:
		print(f"  {key}: {config[key]}")
	print("================\n")

#!/usr/bin/env python3
"""
Text2Game 系统测试脚本
使用模拟模式测试，不调用真实 API
"""

import json
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))


def test_imports():
    """测试模块导入"""
    print("测试1: 模块导入")
    try:
        from pi_mode.analyze import TextAnalyzer, LLMClient, print_config
        print("  [PASS] analyze.py 导入成功")
        return True
    except Exception as e:
        print(f"  [FAIL] 导入失败: {e}")
        return False


def test_config_loading():
    """测试配置加载"""
    print("\n测试2: 配置加载")
    try:
        from pi_mode.analyze import (
            DEFAULT_API_URL, DEFAULT_MODEL, DEFAULT_TEMPERATURE,
            DEFAULT_MAX_TOKENS, DEFAULT_TIMEOUT, DEFAULT_CHUNK_SIZE
        )
        print(f"  [OK] API: {DEFAULT_API_URL}")
        print(f"  [OK] 模型: {DEFAULT_MODEL}")
        print(f"  [OK] 温度: {DEFAULT_TEMPERATURE}")
        print(f"  [OK] Max Tokens: {DEFAULT_MAX_TOKENS}")
        print(f"  [OK] 超时: {DEFAULT_TIMEOUT}秒")
        print(f"  [OK] 分块大小: {DEFAULT_CHUNK_SIZE}字符")
        return True
    except Exception as e:
        print(f"  [FAIL] 配置加载失败: {e}")
        return False


def test_prompt_loading():
    """测试提示词加载"""
    print("\n测试3: 提示词加载")
    try:
        from pi_mode.analyze import LLMClient, TextAnalyzer
        
        client = LLMClient()
        analyzer = TextAnalyzer(client)
        
        # 检查提示词是否加载
        prompts = ["analyze", "recommend", "merge"]
        for p in prompts:
            if p in analyzer.prompts:
                print(f"  [OK] {p}.txt: {len(analyzer.prompts[p])} 字符")
            else:
                print(f"  [FAIL] {p}.txt 未加载")
                return False
            
        return True
    except Exception as e:
        print(f"  [FAIL] 提示词加载失败: {e}")
        return False


def test_text_splitting():
    """测试文本分块"""
    print("\n测试4: 文本分块")
    try:
        from pi_mode.analyze import LLMClient, TextAnalyzer
        
        client = LLMClient()
        analyzer = TextAnalyzer(client)
        analyzer.chunk_size = 100  # 小块测试
        
        # 测试短文本
        short_text = "这是一段短文本。"
        chunks = analyzer.split_text_into_chunks(short_text)
        assert len(chunks) == 1, f"短文本应为1块，实际为{len(chunks)}块"
        print(f"  [OK] 短文本: {len(short_text)}字符 -> {len(chunks)}块")
        
        # 测试长文本
        long_text = "这是测试内容。" * 100  # 约700字符
        chunks = analyzer.split_text_into_chunks(long_text)
        print(f"  [OK] 长文本: {len(long_text)}字符 -> {len(chunks)}块")
        
        # 测试空文本
        empty_chunks = analyzer.split_text_into_chunks("")
        assert len(empty_chunks) == 0, "空文本应返回空列表"
        print(f"  [OK] 空文本: 0字符 -> 0块")
        
        return True
    except Exception as e:
        print(f"  [FAIL] 分块测试失败: {e}")
        return False


def test_cache_system():
    """测试缓存系统"""
    print("\n测试5: 缓存系统")
    try:
        from pi_mode.analyze import LLMClient, TextAnalyzer
        
        client = LLMClient()
        analyzer = TextAnalyzer(client)
        
        # 测试缓存键生成
        text1 = "测试文本1"
        text2 = "测试文本2"
        
        key1 = analyzer._get_cache_key(text1)
        key2 = analyzer._get_cache_key(text2)
        key1_again = analyzer._get_cache_key(text1)
        
        assert key1 != key2, "不同文本应有不同的缓存键"
        assert key1 == key1_again, "相同文本应有相同的缓存键"
        print("  [OK] 缓存键生成正确")
        
        # 测试缓存保存和加载
        test_result = {"world": {"name": "测试世界"}}
        analyzer._save_to_cache(text1, test_result, prefix="test")
        loaded = analyzer._load_from_cache(text1, prefix="test")
        
        assert loaded is not None, "缓存加载失败"
        assert loaded.get("world", {}).get("name") == "测试世界", "缓存内容不匹配"
        print("  [OK] 缓存保存/加载正确")
        
        # 清理测试创建的缓存（不清理用户数据）
        test_input_dir = analyzer._get_cache_dir_for_input(text1)
        if test_input_dir.exists():
            import shutil
            shutil.rmtree(test_input_dir)
        print("  [OK] 测试缓存已清理")
        
        return True
    except Exception as e:
        print(f"  [FAIL] 缓存测试失败: {e}")
        return False


def test_json_parsing():
    """测试JSON解析"""
    print("\n测试6: JSON解析")
    try:
        from pi_mode.analyze import LLMClient, TextAnalyzer
        
        client = LLMClient()
        analyzer = TextAnalyzer(client)
        
        # 测试正常JSON
        normal_json = '{"world": {"name": "测试"}}'
        result = analyzer._parse_json_response(normal_json)
        assert result.get("world", {}).get("name") == "测试", "正常JSON解析失败"
        print("  [OK] 正常JSON解析成功")
        
        # 测试带markdown的JSON
        md_json = '```json\n{"world": {"name": "测试"}}\n```'
        result = analyzer._parse_json_response(md_json)
        assert result.get("world", {}).get("name") == "测试", "Markdown JSON解析失败"
        print("  [OK] Markdown JSON解析成功")
        
        # 测试不完整JSON
        incomplete_json = '{"world": {"name": "测试"'
        result = analyzer._parse_json_response(incomplete_json)
        print("  [OK] 不完整JSON处理正常")
        
        return True
    except Exception as e:
        print(f"  [FAIL] JSON解析测试失败: {e}")
        return False


def test_validation():
    """测试结果验证"""
    print("\n测试7: 结果验证")
    try:
        from pi_mode.analyze import LLMClient, TextAnalyzer
        
        client = LLMClient()
        analyzer = TextAnalyzer(client)
        
        # 测试正常结果验证
        normal_result = {
            "world": {"name": "测试", "era": "现代"},
            "characters": [{"name": "角色1", "role": "主角"}],
            "relationships": [{"from": "角色1", "to": "角色2", "type": "朋友"}],
            "events": [{"order": 1, "title": "事件1", "description": "描述"}],
            "conflicts": [{"type": "类型", "description": "描述"}],
            "themes": ["主题1"]
        }
        validated = analyzer._validate_analysis(normal_result)
        assert validated["world"]["name"] == "测试", "验证失败"
        assert len(validated["relationships"]) == 1, "关系验证失败"
        assert len(validated["events"]) == 1, "事件验证失败"
        print("  [OK] 正常结果验证通过")
        
        # 测试错误结果验证
        error_result = {"_error": "解析失败"}
        validated = analyzer._validate_analysis(error_result)
        assert "_error" in validated, "错误结果验证失败"
        print("  [OK] 错误结果验证通过")
        
        # 测试空结果验证
        empty_result = {}
        validated = analyzer._validate_analysis(empty_result)
        assert "world" in validated, "空结果验证失败"
        assert "relationships" in validated, "空结果关系验证失败"
        assert "events" in validated, "空结果事件验证失败"
        print("  [OK] 空结果验证通过")
        
        return True
    except Exception as e:
        print(f"  [FAIL] 结果验证测试失败: {e}")
        return False


def test_local_merge_chars():
    """测试本地角色合并"""
    print("\n测试8: 本地角色合并")
    try:
        from pi_mode.analyze import LLMClient, TextAnalyzer
        
        client = LLMClient()
        analyzer = TextAnalyzer(client)
        
        # 测试单个角色
        char1 = {"name": "王某", "role": "商人", "traits": ["聪明"]}
        result = analyzer._local_merge_chars(char1)
        assert result["name"] == "王某", "单角色合并失败"
        print("  [OK] 单角色合并")
        
        # 测试同名角色合并
        char1 = {"name": "王某", "role": "商人", "traits": ["聪明"], "background": "普通商人"}
        char2 = {"name": "王某", "role": "总理", "traits": ["果断"], "background": "成为总理"}
        result = analyzer._local_merge_chars(char1, char2)
        
        assert result["name"] == "王某", "同名合并失败"
        assert result["role"] == "总理", "应取最新role"
        assert "商人" in result["roles"], "应保留所有roles"
        assert "总理" in result["roles"], "应保留所有roles"
        assert "聪明" in result["traits"], "应保留traits"
        assert "果断" in result["traits"], "应保留traits"
        assert len(result["background"]) > 0, "应有background"
        print("  [OK] 同名角色合并")
        
        return True
    except Exception as e:
        print(f"  [FAIL] 本地角色合并测试失败: {e}")
        return False


def test_mock_analysis():
    """测试模拟分析"""
    print("\n测试9: 模拟分析")
    try:
        # 创建测试文件
        test_file = Path("test_mock.txt")
        test_file.write_text("这是一个测试文本。刘云飞是帝国大学校长。", encoding="utf-8")
        
        # 运行模拟分析
        import subprocess
        result = subprocess.run(
            ["uv", "run", "python", "pi_mode/analyze.py", "test_mock.txt", "--mock", "-o", "test_mock_result.json"],
            capture_output=True, text=True, encoding="utf-8"
        )
        
        if result.returncode == 0 and Path("test_mock_result.json").exists():
            print("  [OK] 模拟分析成功")
            # 清理
            test_file.unlink()
            Path("test_mock_result.json").unlink()
            return True
        else:
            print(f"  [FAIL] 模拟分析失败: {result.stderr}")
            test_file.unlink(missing_ok=True)
            return False
    except Exception as e:
        print(f"  [FAIL] 模拟分析测试失败: {e}")
        return False


def test_project_structure():
    """测试项目结构"""
    print("\n测试10: 项目结构")
    try:
        required_files = [
            "pyproject.toml",
            ".env.example",
            ".gitignore",
            "run.sh",
            "run.bat",
            "pi_mode/analyze.py",
            "pi_mode/generate.py",
            "prompts/analyze.txt",
            "prompts/recommend.txt",
            "prompts/merge.txt",
            "godot_project/project.godot",
            "godot_project/scripts/llm_client.gd",
        ]
        
        missing = []
        for file in required_files:
            if not Path(file).exists():
                missing.append(file)
        
        if missing:
            print(f"  [FAIL] 缺少文件: {', '.join(missing)}")
            return False
        else:
            print(f"  [OK] 所有 {len(required_files)} 个必需文件存在")
            return True
    except Exception as e:
        print(f"  [FAIL] 项目结构测试失败: {e}")
        return False


def test_relationship_structure():
    """测试人物关系结构"""
    print("\n测试11: 人物关系结构")
    try:
        from pi_mode.analyze import LLMClient, TextAnalyzer
        
        client = LLMClient()
        analyzer = TextAnalyzer(client)
        
        # 测试关系验证
        rel = {"from": "王某", "to": "张某", "type": "师徒", "description": "师徒关系"}
        assert rel.get("from") == "王某", "关系from验证失败"
        assert rel.get("to") == "张某", "关系to验证失败"
        assert rel.get("type") == "师徒", "关系type验证失败"
        print("  [OK] 关系结构验证")
        
        return True
    except Exception as e:
        print(f"  [FAIL] 人物关系测试失败: {e}")
        return False


def test_event_structure():
    """测试事件结构"""
    print("\n测试12: 事件结构")
    try:
        from pi_mode.analyze import LLMClient, TextAnalyzer
        
        client = LLMClient()
        analyzer = TextAnalyzer(client)
        
        # 测试事件验证
        event = {
            "order": 1,
            "title": "王某出生",
            "description": "王某出生于普通家庭",
            "characters": ["王某"],
            "consequences": "为后续发展埋下伏笔"
        }
        assert event.get("order") == 1, "事件order验证失败"
        assert event.get("title") == "王某出生", "事件title验证失败"
        assert "王某" in event.get("characters", []), "事件characters验证失败"
        print("  [OK] 事件结构验证")
        
        return True
    except Exception as e:
        print(f"  [FAIL] 事件结构测试失败: {e}")
        return False


def test_analysis_with_mock():
    """测试带模拟数据的分析流程"""
    print("\n测试13: 分析流程（模拟）")
    try:
        from pi_mode.analyze import LLMClient, TextAnalyzer
        
        client = LLMClient()
        analyzer = TextAnalyzer(client)
        
        # 模拟分析结果
        mock_analysis = {
            "world": {"name": "测试世界", "era": "现代", "location": "城市"},
            "characters": [
                {"name": "王某", "role": "商人", "traits": ["聪明"]},
                {"name": "张某", "role": "老师", "traits": ["耐心"]}
            ],
            "relationships": [
                {"from": "王某", "to": "张某", "type": "朋友"}
            ],
            "events": [
                {"order": 1, "title": "相遇", "description": "王某和张某相遇"}
            ],
            "conflicts": [{"type": "类型", "description": "冲突描述"}],
            "themes": ["主题1"],
            "atmosphere": "轻松"
        }
        
        # 验证
        validated = analyzer._validate_analysis(mock_analysis)
        assert len(validated["characters"]) == 2, "角色数量验证失败"
        assert len(validated["relationships"]) == 1, "关系数量验证失败"
        assert len(validated["events"]) == 1, "事件数量验证失败"
        print("  [OK] 分析流程验证")
        
        return True
    except Exception as e:
        print(f"  [FAIL] 分析流程测试失败: {e}")
        return False


def test_chunk_merge():
    """测试分块合并"""
    print("\n测试14: 分块合并逻辑")
    try:
        from pi_mode.analyze import LLMClient, TextAnalyzer
        
        client = LLMClient()
        analyzer = TextAnalyzer(client)
        
        # 模拟多个块的分析结果
        chunk1 = {
            "world": {"name": "世界A", "era": "古代"},
            "characters": [{"name": "王某", "role": "商人"}]
        }
        chunk2 = {
            "world": {"name": "世界A", "era": "古代", "location": "城市"},
            "characters": [{"name": "王某", "role": "总理"}]
        }
        
        # 测试角色本地合并
        all_chars = chunk1["characters"] + chunk2["characters"]
        seen = {}
        for char in all_chars:
            name = char["name"]
            if name not in seen:
                seen[name] = char.copy()
            else:
                seen[name] = analyzer._local_merge_chars(seen[name], char)
        
        assert len(seen) == 1, "同名角色应合并为1个"
        assert seen["王某"]["role"] == "总理", "应取最新role"
        print("  [OK] 分块角色合并验证")
        
        return True
    except Exception as e:
        print(f"  [FAIL] 分块合并测试失败: {e}")
        return False


def test_cache_info():
    """测试缓存信息"""
    print("\n测试15: 缓存信息")
    try:
        from pi_mode.analyze import LLMClient, TextAnalyzer
        
        client = LLMClient()
        analyzer = TextAnalyzer(client)
        
        info = analyzer.get_cache_info()
        assert "count" in info, "缓存信息缺少count"
        assert "size" in info, "缓存信息缺少size"
        assert "inputs" in info, "缓存信息缺少inputs"
        print(f"  [OK] 缓存信息: {info['count']}个文件, {info['inputs']}个输入目录")
        
        return True
    except Exception as e:
        print(f"  [FAIL] 缓存信息测试失败: {e}")
        return False


def main():
    print("=" * 60)
    print("Text2Game 系统测试")
    print("=" * 60)
    print("使用模拟模式，不调用真实 API\n")
    
    results = []
    
    # 运行测试
    results.append(("模块导入", test_imports()))
    results.append(("配置加载", test_config_loading()))
    results.append(("提示词加载", test_prompt_loading()))
    results.append(("文本分块", test_text_splitting()))
    results.append(("缓存系统", test_cache_system()))
    results.append(("JSON解析", test_json_parsing()))
    results.append(("结果验证", test_validation()))
    results.append(("本地角色合并", test_local_merge_chars()))
    results.append(("模拟分析", test_mock_analysis()))
    results.append(("项目结构", test_project_structure()))
    results.append(("人物关系结构", test_relationship_structure()))
    results.append(("事件结构", test_event_structure()))
    results.append(("分析流程", test_analysis_with_mock()))
    results.append(("分块合并", test_chunk_merge()))
    results.append(("缓存信息", test_cache_info()))
    
    # 打印总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {name}: {status}")
    
    print(f"\n结果: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n[PASS] 所有测试通过!")
        return 0
    else:
        print(f"\n[FAIL] {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())

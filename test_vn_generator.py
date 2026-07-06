#!/usr/bin/env python3
"""
视觉小说生成器测试
测试三阶段流程：大纲生成、分支规划、对话生成
"""

import json
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))


def test_vn_imports():
    """测试视觉小说生成器导入"""
    print("测试1: 视觉小说生成器导入")
    try:
        from pi_mode.generators.visual_novel import VisualNovelGenerator
        print("  [PASS] VisualNovelGenerator 导入成功")
        return True
    except Exception as e:
        print(f"  [FAIL] 导入失败: {e}")
        return False


def test_prompt_files_exist():
    """测试提示词文件存在"""
    print("\n测试2: 提示词文件存在")
    try:
        prompts_dir = Path("prompts")
        required_prompts = [
            "outline.txt",
            "branch_planning.txt",
            "vn_branches.txt",
            "analyze.txt",
            "recommend.txt",
        ]
        
        missing = []
        for p in required_prompts:
            if not (prompts_dir / p).exists():
                missing.append(p)
        
        if missing:
            print(f"  [FAIL] 缺少提示词文件: {', '.join(missing)}")
            return False
        
        print(f"  [OK] 所有 {len(required_prompts)} 个提示词文件存在")
        return True
    except Exception as e:
        print(f"  [FAIL] 提示词文件检查失败: {e}")
        return False


def test_prompt_loading():
    """测试提示词加载"""
    print("\n测试3: 提示词加载")
    try:
        from pi_mode.generators.visual_novel import VisualNovelGenerator
        
        gen = VisualNovelGenerator()
        
        # 测试加载各个提示词
        outline_prompt = gen._load_prompt("outline.txt")
        branch_planning_prompt = gen._load_prompt("branch_planning.txt")
        vn_branches_prompt = gen._load_prompt("vn_branches.txt")
        
        assert len(outline_prompt) > 100, "outline.txt 内容过短"
        assert len(branch_planning_prompt) > 100, "branch_planning.txt 内容过短"
        assert len(vn_branches_prompt) > 100, "vn_branches.txt 内容过短"
        
        # 检查关键占位符
        assert "{text}" in outline_prompt, "outline.txt 缺少 {text} 占位符"
        assert "{event}" in branch_planning_prompt, "branch_planning.txt 缺少 {event} 占位符"
        assert "{branch_plan}" in vn_branches_prompt, "vn_branches.txt 缺少 {branch_plan} 占位符"
        
        print(f"  [OK] outline.txt: {len(outline_prompt)} 字符")
        print(f"  [OK] branch_planning.txt: {len(branch_planning_prompt)} 字符")
        print(f"  [OK] vn_branches.txt: {len(vn_branches_prompt)} 字符")
        return True
    except Exception as e:
        print(f"  [FAIL] 提示词加载失败: {e}")
        return False


def test_prompt_format():
    """测试提示词格式（花括号转义）"""
    print("\n测试4: 提示词格式检查")
    try:
        prompts_dir = Path("prompts")
        
        # 检查 outline.txt 的 JSON 格式
        outline_content = (prompts_dir / "outline.txt").read_text(encoding="utf-8")
        # JSON 示例中的花括号应该是双花括号 {{}}
        assert '{"title":' not in outline_content or '{{"title":' in outline_content, \
            "outline.txt JSON 格式错误：花括号未转义"
        
        # 检查 branch_planning.txt 的 JSON 格式
        bp_content = (prompts_dir / "branch_planning.txt").read_text(encoding="utf-8")
        assert '{"chapter_summary":' not in bp_content or '{{"chapter_summary":' in bp_content, \
            "branch_planning.txt JSON 格式错误：花括号未转义"
        
        # 检查 vn_branches.txt 的 JSON 格式
        vn_content = (prompts_dir / "vn_branches.txt").read_text(encoding="utf-8")
        assert '{"chapter_lines":' not in vn_content or '{{"chapter_lines":' in vn_content, \
            "vn_branches.txt JSON 格式错误：花括号未转义"
        
        print("  [OK] 所有提示词 JSON 格式正确（花括号已转义）")
        return True
    except Exception as e:
        print(f"  [FAIL] 提示词格式检查失败: {e}")
        return False


def test_build_default_outline():
    """测试基础大纲生成（无LLM模式）"""
    print("\n测试5: 基础大纲生成")
    try:
        from pi_mode.generators.visual_novel import VisualNovelGenerator
        
        gen = VisualNovelGenerator()
        
        # 模拟分析结果
        analysis = {
            "world": {
                "name": "北平",
                "description": "民国时期的北平城"
            },
            "characters": [
                {"name": "祥子", "role": "车夫", "goal": "买一辆自己的车"}
            ],
            "events": [
                {"order": 1, "title": "祥子买车", "description": "祥子努力攒钱买车"},
                {"order": 2, "title": "车被抢", "description": "祥子的车被大兵抢走"},
                {"order": 3, "title": "卖骆驼", "description": "祥子卖骆驼换钱"},
            ],
            "themes": ["生存", "奋斗"],
            "atmosphere": "压抑"
        }
        
        # 由于我们移除了 _build_default_outline，这里测试 _build_story 中的 outline 处理
        story = gen._build_story(analysis, [])
        
        # 检查故事结构
        assert "title" in story, "故事缺少 title"
        assert "chapters" in story, "故事缺少 chapters"
        assert len(story["chapters"]) == 3, f"应有3个章节，实际{len(story['chapters'])}个"
        
        print(f"  [OK] 故事生成成功: {story['title']}")
        print(f"  [OK] 章节数量: {len(story['chapters'])}")
        return True
    except Exception as e:
        print(f"  [FAIL] 基础大纲生成失败: {e}")
        return False


def test_chapter_structure():
    """测试章节结构"""
    print("\n测试6: 章节结构")
    try:
        from pi_mode.generators.visual_novel import VisualNovelGenerator
        
        gen = VisualNovelGenerator()
        
        # 模拟分析结果
        analysis = {
            "world": {"name": "测试世界", "description": "测试"},
            "characters": [
                {"name": "角色A", "role": "主角", "traits": ["勇敢"], "goal": "拯救世界"}
            ],
            "events": [
                {"order": 1, "title": "事件1", "description": "描述1", "characters": ["角色A"], "consequences": "后果1"}
            ],
            "conflicts": [{"type": "类型", "description": "冲突"}],
            "relationships": [],
            "themes": ["主题"],
            "atmosphere": "氛围"
        }
        
        story = gen._build_story(analysis, [])
        
        # 检查章节结构
        chapter = story["chapters"][0]
        assert "id" in chapter, "章节缺少 id"
        assert "title" in chapter, "章节缺少 title"
        assert "lines" in chapter, "章节缺少 lines"
        assert "choices" in chapter, "章节缺少 choices"
        assert "has_branches" in chapter, "章节缺少 has_branches"
        
        print(f"  [OK] 章节结构完整")
        print(f"  [OK] 章节ID: {chapter['id']}")
        print(f"  [OK] 行数: {len(chapter['lines'])}")
        print(f"  [OK] 选择数: {len(chapter['choices'])}")
        return True
    except Exception as e:
        print(f"  [FAIL] 章节结构测试失败: {e}")
        return False


def test_prologue_with_outline():
    """测试序章生成（带大纲）"""
    print("\n测试7: 序章生成")
    try:
        from pi_mode.generators.visual_novel import VisualNovelGenerator
        
        gen = VisualNovelGenerator()
        
        world = {"name": "测试世界", "era": "古代", "location": "城堡", "rules": "魔法", "description": "测试"}
        characters = [{"name": "勇者", "role": "战士"}]
        atmosphere = "神秘"
        
        # 测试无大纲
        lines_no_outline = gen._generate_prologue_lines(world, characters, atmosphere, None)
        assert len(lines_no_outline) > 0, "序章应有内容"
        
        # 测试有大纲
        outline = {
            "logline": "勇者踏上拯救世界的旅程",
            "themes": ["勇气", "牺牲"]
        }
        lines_with_outline = gen._generate_prologue_lines(world, characters, atmosphere, outline)
        assert len(lines_with_outline) > len(lines_no_outline), "有大纲时序章应更长"
        
        # 检查大纲内容是否包含在序章中
        all_text = " ".join([l.get("text", "") for l in lines_with_outline])
        assert "勇者踏上拯救世界的旅程" in all_text, "序章应包含 logline"
        
        print(f"  [OK] 无大纲序章: {len(lines_no_outline)} 行")
        print(f"  [OK] 有大纲序章: {len(lines_with_outline)} 行")
        return True
    except Exception as e:
        print(f"  [FAIL] 序章生成测试失败: {e}")
        return False


def test_character_dialogue():
    """测试角色台词生成"""
    print("\n测试8: 角色台词生成")
    try:
        from pi_mode.generators.visual_novel import VisualNovelGenerator
        
        gen = VisualNovelGenerator()
        
        char = {
            "name": "祥子",
            "role": "车夫",
            "traits": ["要强", "沉默"],
            "background": "来自农村的年轻人",
            "goal": "买一辆自己的车"
        }
        event = {"title": "祥子买车", "description": "祥子终于攒够了钱"}
        
        dialogue = gen._generate_character_dialogue(char, event, "压抑", 0)
        
        # 检查生成的台词
        if dialogue:
            assert "speaker" in dialogue, "台词缺少 speaker"
            assert "text" in dialogue, "台词缺少 text"
            assert dialogue["speaker"] == "祥子", "speaker 应为角色名"
            print(f"  [OK] 生成台词: {dialogue['text'][:30]}...")
        else:
            print(f"  [OK] 无匹配模板，返回 None")
        
        return True
    except Exception as e:
        print(f"  [FAIL] 角色台词生成测试失败: {e}")
        return False


def test_knowledge_triggers():
    """测试知识碎片触发器"""
    print("\n测试9: 知识碎片触发器")
    try:
        from pi_mode.generators.visual_novel import VisualNovelGenerator
        
        gen = VisualNovelGenerator()
        
        world = {"name": "测试世界", "rules": "魔法规则"}
        characters = [{"name": "角色A", "background": "背景故事"}]
        themes = ["主题1", "主题2"]
        event = {"title": "事件1", "characters": ["角色A"]}
        
        triggers = gen._generate_knowledge_triggers(event, world, characters, themes)
        
        assert isinstance(triggers, list), "触发器应为列表"
        assert len(triggers) > 0, "应有触发器"
        
        # 检查触发器结构
        for trigger in triggers:
            assert "type" in trigger, "触发器缺少 type"
            assert "title" in trigger, "触发器缺少 title"
            assert "content" in trigger, "触发器缺少 content"
        
        print(f"  [OK] 生成 {len(triggers)} 个知识碎片触发器")
        return True
    except Exception as e:
        print(f"  [FAIL] 知识碎片触发器测试失败: {e}")
        return False


def test_endings():
    """测试结局生成"""
    print("\n测试10: 结局生成")
    try:
        from pi_mode.generators.visual_novel import VisualNovelGenerator
        
        gen = VisualNovelGenerator()
        
        analysis = {
            "world": {"name": "测试世界"},
            "characters": [{"name": "主角"}],
            "themes": ["主题1"]
        }
        story = {"chapters": []}
        
        endings = gen._build_endings(analysis, story)
        
        # 检查结局结构
        assert "good" in endings, "缺少 good 结局"
        assert "normal" in endings, "缺少 normal 结局"
        assert "bad" in endings, "缺少 bad 结局"
        
        for ending_id, ending in endings.items():
            assert "title" in ending, f"{ending_id} 结局缺少 title"
            assert "lines" in ending, f"{ending_id} 结局缺少 lines"
            assert len(ending["lines"]) > 0, f"{ending_id} 结局应有内容"
        
        print(f"  [OK] 生成 {len(endings)} 个结局")
        return True
    except Exception as e:
        print(f"  [FAIL] 结局生成测试失败: {e}")
        return False


def test_relationships():
    """测试关系构建"""
    print("\n测试11: 关系构建")
    try:
        from pi_mode.generators.visual_novel import VisualNovelGenerator
        
        gen = VisualNovelGenerator()
        
        analysis = {
            "relationships": [
                {"from": "角色A", "to": "角色B", "type": "朋友", "description": "好朋友"},
                {"from": "角色A", "to": "角色C", "type": "敌人", "description": "死对头"}
            ]
        }
        
        relationships = gen._build_relationships(analysis)
        
        assert len(relationships) == 2, f"应有2个关系，实际{len(relationships)}个"
        
        # 检查关系结构
        for key, rel in relationships.items():
            assert "from" in rel, f"{key} 关系缺少 from"
            assert "to" in rel, f"{key} 关系缺少 to"
            assert "type" in rel, f"{key} 关系缺少 type"
            assert "value" in rel, f"{key} 关系缺少 value"
            assert rel["value"] == 0, "初始关系值应为0"
        
        print(f"  [OK] 构建 {len(relationships)} 个关系")
        return True
    except Exception as e:
        print(f"  [FAIL] 关系构建测试失败: {e}")
        return False


def test_full_generation_no_llm():
    """测试完整生成流程（无LLM）"""
    print("\n测试12: 完整生成流程（无LLM）")
    try:
        from pi_mode.generators.visual_novel import VisualNovelGenerator
        
        # 创建测试分析文件
        analysis = {
            "source_file": "test.txt",
            "analysis": {
                "world": {"name": "测试世界", "era": "现代", "location": "城市", "rules": "规则", "description": "描述"},
                "characters": [
                    {"name": "主角", "role": "学生", "traits": ["聪明"], "background": "背景", "goal": "目标"}
                ],
                "relationships": [
                    {"from": "主角", "to": "配角", "type": "朋友", "description": "描述"}
                ],
                "events": [
                    {"order": 1, "title": "事件1", "description": "描述", "characters": ["主角"], "consequences": "后果"}
                ],
                "conflicts": [{"type": "类型", "description": "描述"}],
                "themes": ["主题"],
                "atmosphere": "氛围"
            },
            "recommended_types": [{"type": "visual_novel", "features": ["分支剧情"]}]
        }
        
        # 保存测试文件
        test_file = Path("test_analysis.json")
        test_file.write_text(json.dumps(analysis, ensure_ascii=False), encoding="utf-8")
        
        # 生成游戏
        output_dir = Path("test_output")
        gen = VisualNovelGenerator(str(output_dir))
        project_path = gen.generate(str(test_file), "test_vn", use_llm=False)
        
        # 验证生成结果
        project_dir = Path(project_path)
        assert project_dir.exists(), "项目目录不存在"
        assert (project_dir / "project.godot").exists(), "project.godot 不存在"
        assert (project_dir / "data" / "story.json").exists(), "story.json 不存在"
        assert (project_dir / "data" / "characters.json").exists(), "characters.json 不存在"
        
        # 验证 story.json 内容
        story = json.loads((project_dir / "data" / "story.json").read_text(encoding="utf-8"))
        assert "title" in story, "story.json 缺少 title"
        assert "chapters" in story, "story.json 缺少 chapters"
        assert len(story["chapters"]) > 0, "story.json 应有章节"
        
        print(f"  [OK] 项目生成成功: {project_path}")
        print(f"  [OK] 章节数量: {len(story['chapters'])}")
        
        # 清理
        test_file.unlink()
        import shutil
        shutil.rmtree(output_dir, ignore_errors=True)
        
        return True
    except Exception as e:
        print(f"  [FAIL] 完整生成流程测试失败: {e}")
        # 清理
        Path("test_analysis.json").unlink(missing_ok=True)
        import shutil
        shutil.rmtree("test_output", ignore_errors=True)
        return False


def test_cache_system():
    """测试缓存系统"""
    print("\n测试13: 缓存系统")
    try:
        from pi_mode.generators.visual_novel import VisualNovelGenerator
        
        gen = VisualNovelGenerator("test_output")
        
        # 测试缓存键生成
        data1 = {"event": "事件1"}
        data2 = {"event": "事件2"}
        
        key1 = gen.cache.get_cache_key(data1, prefix="test")
        key2 = gen.cache.get_cache_key(data2, prefix="test")
        key1_again = gen.cache.get_cache_key(data1, prefix="test")
        
        assert key1 != key2, "不同数据应有不同的缓存键"
        assert key1 == key1_again, "相同数据应有相同的缓存键"
        print("  [OK] 缓存键生成正确")
        
        # 测试缓存保存和加载
        test_result = {"chapter_summary": "测试章节", "branches": []}
        gen.cache.save_to_cache(key1, test_result, preview="测试预览")
        loaded = gen.cache.load_from_cache(key1)
        
        assert loaded is not None, "缓存加载失败"
        assert loaded.get("chapter_summary") == "测试章节", "缓存内容不匹配"
        print("  [OK] 缓存保存/加载正确")
        
        # 测试缓存信息
        info = gen.cache.get_cache_info()
        assert info["count"] > 0, "缓存文件数应大于0"
        print(f"  [OK] 缓存信息: {info['count']}个文件")
        
        # 清理测试缓存
        count = gen.cache.clear_cache()
        assert count > 0, "应清除至少1个缓存文件"
        print(f"  [OK] 清除了 {count} 个缓存文件")
        
        return True
    except Exception as e:
        print(f"  [FAIL] 缓存系统测试失败: {e}")
        return False


def main():
    print("=" * 60)
    print("视觉小说生成器测试")
    print("=" * 60)
    print("测试三阶段流程：大纲生成、分支规划、对话生成\n")
    
    results = []
    
    # 运行测试
    results.append(("视觉小说生成器导入", test_vn_imports()))
    results.append(("提示词文件存在", test_prompt_files_exist()))
    results.append(("提示词加载", test_prompt_loading()))
    results.append(("提示词格式", test_prompt_format()))
    results.append(("基础大纲生成", test_build_default_outline()))
    results.append(("章节结构", test_chapter_structure()))
    results.append(("序章生成", test_prologue_with_outline()))
    results.append(("角色台词生成", test_character_dialogue()))
    results.append(("知识碎片触发器", test_knowledge_triggers()))
    results.append(("结局生成", test_endings()))
    results.append(("关系构建", test_relationships()))
    results.append(("完整生成流程", test_full_generation_no_llm()))
    results.append(("缓存系统", test_cache_system()))
    
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

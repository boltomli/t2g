#!/usr/bin/env python3
"""
Text2Game 共享模块与生成器测试
覆盖 shared.py、base.py、TwineGenerator、QuizGenerator、GameGenerator
不调用真实 LLM API，仅测试模板/回退模式和结构正确性。
"""

import json
import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


# ════════════════════════════════════════════════════════════════
#  shared.py 测试
# ════════════════════════════════════════════════════════════════

def test_shared_imports():
    """测试 shared 模块导入"""
    print("测试1: shared 模块导入")
    try:
        from pi_mode.shared import (
            LLMClient, parse_llm_json, build_context_summary,
            load_prompt, compile_twee_files,
            DEFAULT_API_URL, DEFAULT_MODEL, DEFAULT_MAX_TOKENS,
        )
        print("  [PASS] shared 全部符号导入成功")
        return True
    except Exception as e:
        print(f"  [FAIL] 导入失败: {e}")
        return False


def test_shared_parse_llm_json_normal():
    """测试 parse_llm_json 正常 JSON"""
    print("\n测试2: parse_llm_json 正常JSON")
    try:
        from pi_mode.shared import parse_llm_json
        result = parse_llm_json('{"name": "test", "value": 42}')
        assert isinstance(result, dict), "应返回 dict"
        assert result["name"] == "test"
        assert result["value"] == 42
        print("  [OK] 正常 JSON 解析成功")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_shared_parse_llm_json_markdown():
    """测试 parse_llm_json markdown 包裹"""
    print("\n测试3: parse_llm_json Markdown包裹")
    try:
        from pi_mode.shared import parse_llm_json
        result = parse_llm_json('```json\n{"key": "val"}\n```')
        assert result is not None, "Markdown JSON 应解析成功"
        assert result["key"] == "val"
        print("  [OK] Markdown 包裹 JSON 解析成功")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_shared_parse_llm_json_embedded():
    """测试 parse_llm_json 嵌入文本中的 JSON"""
    print("\n测试4: parse_llm_json 嵌入文本")
    try:
        from pi_mode.shared import parse_llm_json
        result = parse_llm_json('这是回复。\n{"world": "test"}\n结束。')
        assert result is not None, "应从文本中提取 JSON"
        assert result["world"] == "test"
        print("  [OK] 嵌入文本中的 JSON 提取成功")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_shared_parse_llm_json_array():
    """测试 parse_llm_json JSON 数组"""
    print("\n测试5: parse_llm_json JSON数组")
    try:
        from pi_mode.shared import parse_llm_json
        result = parse_llm_json('[1, 2, 3]')
        assert isinstance(result, list), "应返回 list"
        assert len(result) == 3
        print("  [OK] JSON 数组解析成功")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_shared_parse_llm_json_invalid():
    """测试 parse_llm_json 无效输入"""
    print("\n测试6: parse_llm_json 无效输入")
    try:
        from pi_mode.shared import parse_llm_json
        result = parse_llm_json("这不是JSON")
        assert result is None, "无效输入应返回 None"
        print("  [OK] 无效输入返回 None")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_shared_build_context_summary():
    """测试 build_context_summary 上下文摘要构建"""
    print("\n测试7: build_context_summary")
    try:
        from pi_mode.shared import build_context_summary

        event_chars = ["角色A", "角色B"]
        characters = {
            "角色A": {"name": "角色A", "role": "主角", "traits": ["勇敢"], "goal": "拯救世界"},
            "角色B": {"name": "角色B", "role": "配角", "traits": ["聪明"], "goal": "帮助主角"},
        }
        conflicts = [{"type": "内心冲突", "description": "角色A的内心挣扎"}]
        relationships = [
            {"from": "角色A", "to": "角色B", "type": "朋友", "description": "好友"},
            {"from": "角色C", "to": "角色D", "type": "敌人", "description": "无关"},
        ]

        chars_text, conflicts_text, rels_text = build_context_summary(
            event_chars, characters, conflicts, relationships
        )

        assert "角色A" in chars_text, "chars_text 应包含角色A"
        assert "主角" in chars_text, "chars_text 应包含角色身份"
        assert "勇敢" in chars_text, "chars_text 应包含角色特征"
        assert "内心冲突" in conflicts_text, "conflicts_text 应包含冲突"
        assert "角色A" in rels_text, "rels_text 应包含相关关系"
        assert "角色C" not in rels_text, "rels_text 不应包含无关关系"
        print("  [OK] 上下文摘要构建正确")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_shared_build_context_summary_list_chars():
    """测试 build_context_summary 接受 list 形式角色"""
    print("\n测试8: build_context_summary list形式角色")
    try:
        from pi_mode.shared import build_context_summary

        event_chars = ["甲"]
        characters = [
            {"name": "甲", "role": "战士", "traits": ["强壮"], "goal": "战斗"},
        ]
        chars_text, conflicts_text, rels_text = build_context_summary(
            event_chars, characters, [], []
        )
        assert "甲" in chars_text, "应从 list 形式角色中提取信息"
        assert "战士" in chars_text, "应包含角色身份"
        assert conflicts_text == "无明确冲突", "空冲突应有默认值"
        assert rels_text == "无直接关系", "空关系应有默认值"
        print("  [OK] list 形式角色处理正确")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_shared_load_prompt():
    """测试 load_prompt 提示词加载"""
    print("\n测试9: load_prompt")
    try:
        from pi_mode.shared import load_prompt
        content = load_prompt("analyze.txt")
        assert len(content) > 50, "analyze.txt 内容应非空"
        not_exist = load_prompt("nonexistent_prompt.txt")
        assert not_exist == "", "不存在的文件应返回空字符串"
        print(f"  [OK] analyze.txt: {len(content)} 字符")
        print(f"  [OK] 不存在文件返回空字符串")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_shared_llm_client_init():
    """测试 LLMClient 初始化和配置"""
    print("\n测试10: LLMClient 初始化")
    try:
        from pi_mode.shared import LLMClient
        client = LLMClient()
        assert hasattr(client, "api_url"), "应有 api_url"
        assert hasattr(client, "model"), "应有 model"
        assert hasattr(client, "temperature"), "应有 temperature"
        assert hasattr(client, "max_tokens"), "应有 max_tokens"
        assert hasattr(client, "timeout"), "应有 timeout"
        assert hasattr(client, "max_retries"), "应有 max_retries"
        assert hasattr(client, "chat_completion"), "应有 chat_completion 方法"
        assert hasattr(client, "get_models"), "应有 get_models 方法"
        assert hasattr(client, "check_available"), "应有 check_available 方法"
        print(f"  [OK] API: {client.api_url}")
        print(f"  [OK] Model: {client.model}")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


# ════════════════════════════════════════════════════════════════
#  base.py (BaseGenerator) 测试
# ════════════════════════════════════════════════════════════════

def test_base_unwrap_analysis_wrapped():
    """测试 _unwrap_analysis 解包嵌套格式"""
    print("\n测试11: _unwrap_analysis 嵌套格式")
    try:
        from pi_mode.generators.base import BaseGenerator
        wrapped = {"source_file": "test.txt", "analysis": {"world": {"name": "测试"}}}
        data = BaseGenerator._unwrap_analysis(wrapped)
        assert data == {"world": {"name": "测试"}}, "应解包到 analysis 内容"
        print("  [OK] 嵌套格式解包正确")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_base_unwrap_analysis_flat():
    """测试 _unwrap_analysis 直接格式"""
    print("\n测试12: _unwrap_analysis 直接格式")
    try:
        from pi_mode.generators.base import BaseGenerator
        flat = {"world": {"name": "测试"}, "characters": []}
        data = BaseGenerator._unwrap_analysis(flat)
        assert data == flat, "直接格式应原样返回"
        print("  [OK] 直接格式原样返回")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_base_derive_name_from_file():
    """测试 _derive_name 从文件名推导"""
    print("\n测试13: _derive_name 文件名推导")
    try:
        from pi_mode.generators.base import BaseGenerator
        gen = BaseGenerator()
        analysis = {"source_file": "my_story.txt", "analysis": {"world": {"name": "世界"}}}
        name = gen._derive_name(analysis, "my_story.txt")
        assert name == "my_story", f"应从文件名推导，实际: {name}"
        print(f"  [OK] 文件名推导: {name}")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_base_derive_name_from_world():
    """测试 _derive_name 从世界名推导"""
    print("\n测试14: _derive_name 世界名推导")
    try:
        from pi_mode.generators.base import BaseGenerator
        gen = BaseGenerator()
        analysis = {"analysis": {"world": {"name": "幻想世界"}}}
        name = gen._derive_name(analysis, "", suffix="_vn")
        assert name == "幻想世界_vn", f"应从世界名推导加后缀，实际: {name}"
        print(f"  [OK] 世界名推导: {name}")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_base_render_twee():
    """测试 _render_twee Twee 格式渲染"""
    print("\n测试15: _render_twee 渲染")
    try:
        from pi_mode.generators.base import BaseGenerator
        gen = BaseGenerator()
        story = {
            "title": "测试故事",
            "stylesheet": "body { color: red; }",
            "javascript": "console.log('hi');",
            "passages": [
                {"name": "Start", "tags": ["start"], "source": "开始内容"},
                {"name": "Chapter_01", "tags": ["chapter"], "source": "第一章"},
            ],
        }
        twee = gen._render_twee(story)
        assert ":: StoryData" in twee, "应包含 StoryData"
        assert "测试故事" in twee, "应包含标题"
        assert ":: Story stylesheet" in twee, "应包含 stylesheet 标签"
        assert ":: Story script" in twee, "应包含 script 标签"
        assert ":: Start [start]" in twee, "应包含 Start 段落"
        assert "开始内容" in twee, "应包含段落内容"
        assert ":: Chapter_01 [chapter]" in twee, "应包含章节段落"
        print(f"  [OK] Twee 渲染正确 ({len(twee)} 字符)")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_base_render_passage_special_chars():
    """测试 _render_passage 特殊字符转义"""
    print("\n测试16: _render_passage 特殊字符")
    try:
        from pi_mode.generators.base import BaseGenerator
        passage = {"name": "Test[1]", "tags": [], "source": "内容"}
        rendered = BaseGenerator._render_passage(passage)
        assert '"Test[1]"' in rendered, "含特殊字符的段落名应加引号"
        print("  [OK] 特殊字符段落名转义正确")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_base_build_context_summary():
    """测试 BaseGenerator._build_context_summary 委托"""
    print("\n测试17: BaseGenerator._build_context_summary")
    try:
        from pi_mode.generators.base import BaseGenerator
        chars_text, conflicts_text, rels_text = BaseGenerator._build_context_summary(
            ["甲"], {"甲": {"name": "甲", "role": "主角", "traits": [], "goal": ""}},
            [], []
        )
        assert "甲" in chars_text, "应包含角色信息"
        assert conflicts_text == "无明确冲突", "空冲突默认值"
        print("  [OK] BaseGenerator 上下文摘要委托正确")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


# ════════════════════════════════════════════════════════════════
#  TwineGenerator 测试
# ════════════════════════════════════════════════════════════════

def test_twine_imports():
    """测试 TwineGenerator 导入"""
    print("\n测试18: TwineGenerator 导入")
    try:
        from pi_mode.generators.twine import TwineGenerator
        print("  [PASS] TwineGenerator 导入成功")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_twine_build_characters():
    """测试 Twine 角色构建"""
    print("\n测试19: Twine 角色构建")
    try:
        from pi_mode.generators.twine import TwineGenerator
        gen = TwineGenerator()
        analysis = {
            "characters": [
                {"name": "甲", "role": "主角", "traits": ["勇敢"], "background": "背景", "goal": "目标"},
                {"name": "乙", "role": "配角", "traits": ["聪明"], "background": "背景2", "goal": "目标2"},
            ]
        }
        chars = gen._build_characters(analysis)
        assert "甲" in chars, "应包含角色甲"
        assert "乙" in chars, "应包含角色乙"
        assert chars["甲"]["role"] == "主角", "角色身份应正确"
        assert chars["甲"]["color"], "角色应有颜色"
        print(f"  [OK] 构建 {len(chars)} 个角色")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_twine_build_story():
    """测试 Twine 故事构建（无LLM）"""
    print("\n测试20: Twine 故事构建")
    try:
        from pi_mode.generators.twine import TwineGenerator
        gen = TwineGenerator()
        analysis = {
            "world": {"name": "测试世界", "era": "古代", "location": "城市", "rules": "规则", "description": "描述"},
            "characters": [{"name": "甲", "role": "主角", "traits": ["勇敢"], "background": "背景", "goal": "目标"}],
            "events": [
                {"order": 1, "title": "事件1", "description": "描述1", "characters": ["甲"], "consequences": "后果1"},
                {"order": 2, "title": "事件2", "description": "描述2", "characters": ["甲"], "consequences": "后果2"},
            ],
            "conflicts": [{"type": "冲突", "description": "描述"}],
            "relationships": [{"from": "甲", "to": "乙", "type": "朋友", "description": "好友"}],
            "themes": ["主题"],
            "atmosphere": "氛围",
        }
        characters = gen._build_characters(analysis)
        story = gen._build_story(analysis, characters, use_llm=False)

        assert "title" in story, "故事应有 title"
        assert "passages" in story, "故事应有 passages"
        assert "stylesheet" in story, "故事应有 stylesheet"
        assert "javascript" in story, "故事应有 javascript"

        passages = story["passages"]
        names = [p["name"] for p in passages]
        assert "Start" in names, "应有 Start 段落"
        assert "Chapter_01" in names, "应有 Chapter_01 段落"
        assert "Chapter_02" in names, "应有 Chapter_02 段落"
        assert "Ending_Good" in names, "应有 Ending_Good 段落"
        assert "Ending_Normal" in names, "应有 Ending_Normal 段落"
        assert "Ending_Bad" in names, "应有 Ending_Bad 段落"
        print(f"  [OK] 故事 {len(passages)} 个段落")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_twine_full_generation_no_llm():
    """测试 Twine 完整生成流程（无LLM）"""
    print("\n测试21: Twine 完整生成（无LLM）")
    try:
        from pi_mode.generators.twine import TwineGenerator
        analysis = {
            "source_file": "test.txt",
            "analysis": {
                "world": {"name": "测试世界", "era": "现代", "location": "城市", "rules": "规则", "description": "描述"},
                "characters": [{"name": "主角", "role": "学生", "traits": ["聪明"], "background": "背景", "goal": "目标"}],
                "events": [{"order": 1, "title": "事件1", "description": "描述", "characters": ["主角"], "consequences": "后果"}],
                "conflicts": [{"type": "冲突", "description": "描述"}],
                "relationships": [],
                "themes": ["主题"],
                "atmosphere": "氛围",
            },
        }
        test_file = Path("test_twine_analysis.json")
        test_file.write_text(json.dumps(analysis, ensure_ascii=False), encoding="utf-8")

        output_dir = Path("test_twine_output")
        gen = TwineGenerator(str(output_dir))
        project_path = gen.generate(str(test_file), output_name="test_twine", use_llm=False)

        project_dir = Path(project_path)
        assert project_dir.exists(), "项目目录应存在"
        twee_files = list(project_dir.glob("*.twee"))
        assert len(twee_files) == 1, "应生成 1 个 .twee 文件"
        assert (project_dir / "metadata.json").exists(), "应有 metadata.json"
        assert (project_dir / "analysis.json").exists(), "应有 analysis.json"

        twee_content = twee_files[0].read_text(encoding="utf-8")
        assert ":: StoryData" in twee_content, "Twee 应包含 StoryData"
        assert ":: Start" in twee_content, "Twee 应包含 Start"
        assert "Chapter_01" in twee_content, "Twee 应包含章节"
        print(f"  [OK] Twine 生成成功: {project_path}")

        test_file.unlink()
        shutil.rmtree(output_dir, ignore_errors=True)
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        Path("test_twine_analysis.json").unlink(missing_ok=True)
        shutil.rmtree("test_twine_output", ignore_errors=True)
        return False


# ════════════════════════════════════════════════════════════════
#  QuizGenerator 测试
# ════════════════════════════════════════════════════════════════

def test_quiz_imports():
    """测试 QuizGenerator 导入"""
    print("\n测试22: QuizGenerator 导入")
    try:
        from pi_mode.generators.quiz import QuizGenerator
        print("  [PASS] QuizGenerator 导入成功")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_quiz_shuffle_options():
    """测试 _shuffle_options 选项打乱"""
    print("\n测试23: _shuffle_options")
    try:
        from pi_mode.generators.quiz import QuizGenerator
        options = {"A": "正确", "B": "错1", "C": "错2", "D": "错3"}
        result = QuizGenerator._shuffle_options(options)
        assert "options" in result, "应返回 options"
        assert "correct" in result, "应返回 correct"
        assert len(result["options"]) == 4, "应有4个选项"
        correct_val = result["options"][result["correct"]]
        assert correct_val == "正确", "正确答案值应匹配"
        print(f"  [OK] 选项打乱正确，正确答案: {result['correct']}")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_quiz_validate_questions():
    """测试 _validate_questions 校验去重"""
    print("\n测试24: _validate_questions")
    try:
        from pi_mode.generators.quiz import QuizGenerator
        questions = [
            {"type": "true_false", "question": "题目1", "answer": True, "explanation": "解析"},
            {"type": "true_false", "question": "题目1", "answer": False, "explanation": "重复"},
            {"type": "single_choice", "question": "题目2", "answer": "A", "options": {"A": "a", "B": "b"}},
            {"type": "unknown_type", "question": "题目3", "answer": True},  # 无效类型
            {"type": "true_false", "question": "", "answer": True},  # 空题目
        ]
        valid = QuizGenerator._validate_questions(questions, limit=9999)
        assert len(valid) == 2, f"应保留2个有效题目，实际{len(valid)}个"
        print(f"  [OK] 校验去重: {len(questions)} -> {len(valid)} 题")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_quiz_sample_questions():
    """测试 _sample_questions 抽题"""
    print("\n测试25: _sample_questions")
    try:
        from pi_mode.generators.quiz import QuizGenerator
        import random
        random.seed(42)
        gen = QuizGenerator()
        bank = [
            {"type": "true_false", "question": f"题{i}", "answer": True}
            for i in range(20)
        ] + [
            {"type": "single_choice", "question": f"单选{i}", "answer": "A", "options": {"A": "a", "B": "b"}}
            for i in range(10)
        ]
        sampled = gen._sample_questions(bank, 5)
        assert len(sampled) == 5, f"应抽5题，实际{len(sampled)}题"
        assert all(q in bank for q in sampled), "抽题应来自题库"
        print(f"  [OK] 从 {len(bank)} 题中抽取 {len(sampled)} 题")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_quiz_build_bank_from_template_knowledge():
    """测试模板题库生成（知识体系结构）"""
    print("\n测试26: 模板题库生成（知识体系）")
    try:
        from pi_mode.generators.quiz import QuizGenerator
        gen = QuizGenerator()
        analysis = {
            "domain": "测试领域",
            "summary": "这是测试摘要",
            "concepts": [{"name": "概念A", "definition": "定义A", "category": "分类"}],
            "facts": [{"statement": "事实陈述1", "detail": "", "category": ""}],
            "causes": [{"cause": "原因1", "effect": "结果1", "description": "描述"}],
            "comparisons": [{"topic": "对比1", "items": ["X", "Y"], "difference": "区别"}],
            "processes": [{"name": "流程1", "steps": ["步骤1", "步骤2"]}],
            "principles": [{"name": "原理1", "description": "描述1", "category": ""}],
            "categories": ["分类1"],
            "_raw_paragraphs": [],
            "_raw_sentences": [],
        }
        bank = gen._build_bank_from_template(analysis)
        assert len(bank) > 0, "应生成题目"
        types_present = {q["type"] for q in bank}
        assert "true_false" in types_present, "应有判断题"
        assert "single_choice" in types_present, "应有单选题"
        for q in bank:
            assert "type" in q, "题目应有 type"
            assert "question" in q, "题目应有 question"
            assert "answer" in q, "题目应有 answer"
        print(f"  [OK] 生成 {len(bank)} 道题，类型: {types_present}")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_quiz_build_bank_from_template_events():
    """测试模板题库生成（事件结构，兼容标准分析格式）"""
    print("\n测试27: 模板题库生成（事件结构）")
    try:
        from pi_mode.generators.quiz import QuizGenerator
        gen = QuizGenerator()
        analysis = {
            "world": {"name": "测试世界", "description": "描述"},
            "characters": [
                {"name": "甲", "role": "主角", "traits": ["勇敢"]},
                {"name": "乙", "role": "配角", "traits": ["聪明"]},
                {"name": "丙", "role": "路人", "traits": ["普通"]},
                {"name": "丁", "role": "路人2", "traits": ["普通2"]},
            ],
            "events": [{"title": "事件1", "description": "描述1", "characters": ["甲"], "consequences": "后果1"}],
            "relationships": [{"from": "甲", "to": "乙", "type": "朋友", "description": "好友"}],
            "conflicts": [{"type": "冲突", "description": "冲突描述"}],
            "themes": ["主题1", "主题2"],
        }
        bank = gen._build_bank_from_template(analysis)
        assert len(bank) > 0, "应从事件结构生成题目"
        print(f"  [OK] 从事件结构生成 {len(bank)} 道题")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_quiz_build_story():
    """测试 Quiz 故事结构构建"""
    print("\n测试28: Quiz 故事结构构建")
    try:
        from pi_mode.generators.quiz import QuizGenerator
        gen = QuizGenerator()
        questions = [
            {"type": "true_false", "question": "判断题1", "answer": True, "explanation": "解析", "source": "来源"},
            {"type": "single_choice", "question": "单选1", "answer": "A",
             "options": {"A": "正确", "B": "错误"}, "explanation": "解析", "source": "来源"},
            {"type": "multiple_choice", "question": "多选1", "answer": ["A", "B"],
             "options": {"A": "选项A", "B": "选项B", "C": "选项C"}, "explanation": "解析", "source": "来源"},
        ]
        analysis = {"world": {"name": "测试"}}
        story = gen._build_story(questions, analysis, num_questions=3)

        assert "title" in story, "应有 title"
        assert "passages" in story, "应有 passages"
        assert "stylesheet" in story, "应有 stylesheet"
        assert "javascript" in story, "应有 javascript"

        names = [p["name"] for p in story["passages"]]
        assert "Start" in names, "应有 Start"
        assert "Results" in names, "应有 Results"
        assert "Q01" in names, "应有 Q01"
        assert "Q02" in names, "应有 Q02"
        assert "Q03" in names, "应有 Q03"
        print(f"  [OK] Quiz 故事 {len(story['passages'])} 个段落")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_quiz_full_generation_no_llm():
    """测试 Quiz 完整生成流程（无LLM模板模式）"""
    print("\n测试29: Quiz 完整生成（无LLM）")
    try:
        from pi_mode.generators.quiz import QuizGenerator
        analysis = {
            "source_file": "test.txt",
            "analysis": {
                "world": {"name": "测试世界"},
                "characters": [
                    {"name": "甲", "role": "主角", "traits": ["勇敢"]},
                    {"name": "乙", "role": "配角", "traits": ["聪明"]},
                    {"name": "丙", "role": "路人", "traits": ["普通"]},
                    {"name": "丁", "role": "路人2", "traits": ["普通2"]},
                ],
                "events": [{"title": "事件1", "description": "描述", "characters": ["甲"], "consequences": "后果"}],
                "relationships": [],
                "conflicts": [],
                "themes": ["主题"],
            },
        }
        test_file = Path("test_quiz_analysis.json")
        test_file.write_text(json.dumps(analysis, ensure_ascii=False), encoding="utf-8")

        output_dir = Path("test_quiz_output")
        gen = QuizGenerator(str(output_dir))
        project_path = gen.generate(
            str(test_file), output_name="test_quiz",
            use_llm=False, num_questions=5,
        )

        project_dir = Path(project_path)
        assert project_dir.exists(), "项目目录应存在"
        twee_files = list(project_dir.glob("*.twee"))
        assert len(twee_files) == 1, "应生成 .twee 文件"
        assert (project_dir / "metadata.json").exists(), "应有 metadata.json"
        assert (project_dir / "questions.json").exists(), "应有 questions.json"

        twee_content = twee_files[0].read_text(encoding="utf-8")
        assert ":: StoryData" in twee_content, "Twee 应包含 StoryData"
        assert "Start" in twee_content, "Twee 应包含 Start"
        print(f"  [OK] Quiz 生成成功: {project_path}")

        test_file.unlink()
        shutil.rmtree(output_dir, ignore_errors=True)
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        Path("test_quiz_analysis.json").unlink(missing_ok=True)
        shutil.rmtree("test_quiz_output", ignore_errors=True)
        return False


# ════════════════════════════════════════════════════════════════
#  generate.py (GameGenerator) 测试
# ════════════════════════════════════════════════════════════════

def test_generate_imports():
    """测试 generate.py 导入"""
    print("\n测试30: generate.py 导入")
    try:
        import pi_mode.generate
        assert hasattr(pi_mode.generate, "GameGenerator"), "应有 GameGenerator"
        assert hasattr(pi_mode.generate, "SUPPORTED_TYPES"), "应有 SUPPORTED_TYPES"
        assert hasattr(pi_mode.generate, "TwineGenerator"), "应有 TwineGenerator"
        assert hasattr(pi_mode.generate, "QuizGenerator"), "应有 QuizGenerator"
        assert hasattr(pi_mode.generate, "VisualNovelGenerator"), "应有 VisualNovelGenerator"
        print("  [PASS] generate.py 导入成功")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_generate_supported_types():
    """测试支持的游戏类型列表"""
    print("\n测试31: SUPPORTED_TYPES")
    try:
        from pi_mode.generate import SUPPORTED_TYPES
        for t in ["rpg", "adventure", "visual_novel", "strategy", "action", "twine", "quiz"]:
            assert t in SUPPORTED_TYPES, f"缺少类型: {t}"
        print(f"  [OK] {len(SUPPORTED_TYPES)} 种游戏类型")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_generate_twine_via_game_generator():
    """测试通过 GameGenerator 生成 Twine"""
    print("\n测试32: GameGenerator → Twine")
    try:
        from pi_mode.generate import GameGenerator
        analysis = {
            "source_file": "test.txt",
            "analysis": {
                "world": {"name": "测试", "description": "描述"},
                "characters": [{"name": "甲", "role": "主角", "traits": ["勇敢"]}],
                "events": [{"order": 1, "title": "事件", "description": "描述", "characters": ["甲"], "consequences": ""}],
                "conflicts": [], "relationships": [], "themes": ["主题"], "atmosphere": "",
            },
        }
        test_file = Path("test_gen_analysis.json")
        test_file.write_text(json.dumps(analysis, ensure_ascii=False), encoding="utf-8")

        output_dir = Path("test_gen_output")
        gen = GameGenerator(str(output_dir))
        project_path = gen.generate_game(str(test_file), "twine", use_llm=False)

        project_dir = Path(project_path)
        assert project_dir.exists(), "项目目录应存在"
        assert len(list(project_dir.glob("*.twee"))) == 1, "应有 .twee 文件"
        print(f"  [OK] GameGenerator Twine 生成成功")

        test_file.unlink()
        shutil.rmtree(output_dir, ignore_errors=True)
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        Path("test_gen_analysis.json").unlink(missing_ok=True)
        shutil.rmtree("test_gen_output", ignore_errors=True)
        return False


# ════════════════════════════════════════════════════════════════
#  集成测试：统一 _unwrap_analysis 消除二次处理
# ════════════════════════════════════════════════════════════════

def test_integration_unwrap_consistency():
    """测试所有生成器统一使用 _unwrap_analysis"""
    print("\n测试33: _unwrap_analysis 跨生成器一致性")
    try:
        from pi_mode.generators.base import BaseGenerator
        from pi_mode.generators.twine import TwineGenerator
        from pi_mode.generators.visual_novel import VisualNovelGenerator
        from pi_mode.generators.quiz import QuizGenerator

        wrapped = {"source_file": "test.txt", "analysis": {"world": {"name": "统一测试"}}}
        flat = {"world": {"name": "统一测试"}}

        for cls in [BaseGenerator, TwineGenerator, VisualNovelGenerator, QuizGenerator]:
            data_w = cls._unwrap_analysis(wrapped)
            data_f = cls._unwrap_analysis(flat)
            assert data_w == {"world": {"name": "统一测试"}}, f"{cls.__name__} 解包嵌套格式失败"
            assert data_f == {"world": {"name": "统一测试"}}, f"{cls.__name__} 解包直接格式失败"

        print("  [OK] 所有生成器 _unwrap_analysis 行为一致")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_integration_twee_render_consistency():
    """测试 Twine 和 Quiz 使用相同的 Twee 渲染方法"""
    print("\n测试34: Twee 渲染一致性")
    try:
        from pi_mode.generators.twine import TwineGenerator
        from pi_mode.generators.quiz import QuizGenerator
        from pi_mode.generators.base import BaseGenerator

        twine_gen = TwineGenerator()
        quiz_gen = QuizGenerator()

        # 两者应使用继承自 BaseGenerator 的同一个渲染方法（未覆写）
        assert "_render_twee" not in TwineGenerator.__dict__, \
            "TwineGenerator 不应覆写 _render_twee"
        assert "_render_twee" not in QuizGenerator.__dict__, \
            "QuizGenerator 不应覆写 _render_twee"
        assert "_render_passage" not in TwineGenerator.__dict__, \
            "TwineGenerator 不应覆写 _render_passage"
        assert "_render_passage" not in QuizGenerator.__dict__, \
            "QuizGenerator 不应覆写 _render_passage"
        assert "_render_story_data" not in TwineGenerator.__dict__, \
            "TwineGenerator 不应覆写 _render_story_data"
        assert "_render_story_data" not in QuizGenerator.__dict__, \
            "QuizGenerator 不应覆写 _render_story_data"

        # 验证渲染输出结构一致（UUID 每次不同，只比较关键结构）
        story = {
            "title": "一致性测试",
            "stylesheet": "/* css */",
            "javascript": "// js",
            "passages": [{"name": "Start", "tags": ["start"], "source": "内容"}],
        }
        twee_from_twine = twine_gen._render_twee(story)
        twee_from_quiz = quiz_gen._render_twee(story)
        for key in [":: StoryData", ":: Story stylesheet", ":: Story script",
                     ":: Start [start]", "一致性测试", "内容"]:
            assert key in twee_from_twine, f"Twine 输出缺少: {key}"
            assert key in twee_from_quiz, f"Quiz 输出缺少: {key}"

        print("  [OK] Twine 和 Quiz 使用同一渲染方法，输出结构一致")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_integration_llm_client_singleton():
    """测试 LLMClient 全局唯一（shared 模块）"""
    print("\n测试35: LLMClient 全局唯一")
    try:
        from pi_mode.shared import LLMClient as SharedClient
        from pi_mode.analyze import LLMClient as AnalyzeClient
        from pi_mode.generators.base import LLMClient as BaseClient

        assert SharedClient is AnalyzeClient, "analyze.py 的 LLMClient 应为 shared 的同一类"
        assert SharedClient is BaseClient, "base.py 的 LLMClient 应为 shared 的同一类"
        print("  [OK] LLMClient 三处引用指向同一类")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


# ════════════════════════════════════════════════════════════════
#  主入口
# ════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("Text2Game 共享模块与生成器测试")
    print("=" * 60)
    print("覆盖 shared.py、base.py、Twine、Quiz、GameGenerator\n")

    results = []

    # shared.py
    results.append(("shared 导入", test_shared_imports()))
    results.append(("parse_llm_json 正常", test_shared_parse_llm_json_normal()))
    results.append(("parse_llm_json Markdown", test_shared_parse_llm_json_markdown()))
    results.append(("parse_llm_json 嵌入", test_shared_parse_llm_json_embedded()))
    results.append(("parse_llm_json 数组", test_shared_parse_llm_json_array()))
    results.append(("parse_llm_json 无效", test_shared_parse_llm_json_invalid()))
    results.append(("build_context_summary", test_shared_build_context_summary()))
    results.append(("build_context_summary list", test_shared_build_context_summary_list_chars()))
    results.append(("load_prompt", test_shared_load_prompt()))
    results.append(("LLMClient 初始化", test_shared_llm_client_init()))

    # base.py
    results.append(("_unwrap_analysis 嵌套", test_base_unwrap_analysis_wrapped()))
    results.append(("_unwrap_analysis 直接", test_base_unwrap_analysis_flat()))
    results.append(("_derive_name 文件名", test_base_derive_name_from_file()))
    results.append(("_derive_name 世界名", test_base_derive_name_from_world()))
    results.append(("_render_twee", test_base_render_twee()))
    results.append(("_render_passage 特殊字符", test_base_render_passage_special_chars()))
    results.append(("BaseGenerator 上下文摘要", test_base_build_context_summary()))

    # Twine
    results.append(("Twine 导入", test_twine_imports()))
    results.append(("Twine 角色构建", test_twine_build_characters()))
    results.append(("Twine 故事构建", test_twine_build_story()))
    results.append(("Twine 完整生成", test_twine_full_generation_no_llm()))

    # Quiz
    results.append(("Quiz 导入", test_quiz_imports()))
    results.append(("Quiz 选项打乱", test_quiz_shuffle_options()))
    results.append(("Quiz 题目校验", test_quiz_validate_questions()))
    results.append(("Quiz 抽题", test_quiz_sample_questions()))
    results.append(("Quiz 模板题库(知识)", test_quiz_build_bank_from_template_knowledge()))
    results.append(("Quiz 模板题库(事件)", test_quiz_build_bank_from_template_events()))
    results.append(("Quiz 故事构建", test_quiz_build_story()))
    results.append(("Quiz 完整生成", test_quiz_full_generation_no_llm()))

    # generate.py
    results.append(("generate.py 导入", test_generate_imports()))
    results.append(("SUPPORTED_TYPES", test_generate_supported_types()))
    results.append(("GameGenerator → Twine", test_generate_twine_via_game_generator()))

    # 集成
    results.append(("_unwrap_analysis 一致性", test_integration_unwrap_consistency()))
    results.append(("Twee 渲染一致性", test_integration_twee_render_consistency()))
    results.append(("LLMClient 全局唯一", test_integration_llm_client_singleton()))

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, r in results:
        print(f"  {name}: {'[PASS]' if r else '[FAIL]'}")

    print(f"\n结果: {passed}/{total} 测试通过")

    if passed == total:
        print("\n[PASS] 所有测试通过!")
        return 0
    else:
        print(f"\n[FAIL] {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())

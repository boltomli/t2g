#!/usr/bin/env python3
"""
Quiz 问答游戏生成器
基于分析结果或直接文本生成 Twee 格式的问答游戏
支持判断题、单选题、多选题，内置题库与抽题组卷
"""

import json
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional

# 确保项目根目录在 sys.path 中（支持直接运行）
_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from pi_mode.generators.base import BaseGenerator, LLMClient
from pi_mode.shared import compile_twee_files


class QuizGenerator(BaseGenerator):
    """Quiz 问答游戏生成器"""

    CACHE_SUBDIR = "quiz"
    BANK_FILENAME = "question_bank.json"

    def __init__(self, output_dir: str = "./generated_games"):
        super().__init__(output_dir)
        self._question_prompt: Optional[str] = None

    # ═══════════════════════════════════════════════════════════════
    #  公开 API
    # ═══════════════════════════════════════════════════════════════

    def generate(self, analysis_file: str, output_name: Optional[str] = None,
                 use_llm: bool = True, num_questions: int = 10,
                 no_cache: bool = False) -> str:
        """从 analysis.json 生成 quiz（原有路径）"""
        analysis = self._load_analysis(analysis_file)
        analysis_data = self._unwrap_analysis(analysis)
        game_name = output_name or self._derive_name(analysis, analysis_file, suffix="_quiz")

        return self._generate_quiz(
            analysis_data=analysis_data,
            game_name=game_name,
            source_label=analysis_file,
            use_llm=use_llm,
            num_questions=num_questions,
            no_cache=no_cache,
        )

    def generate_from_text(self, text: str, output_name: str = "quiz",
                           use_llm: bool = True, num_questions: int = 10,
                           no_cache: bool = False) -> str:
        """
        从原始文本直接生成 quiz（新路径）。
        必须有 LLM：先分析文本，再生成完整题库，最后抽题组卷。
        """
        if no_cache:
            self.cache.clear_cache()

        # 尝试用 analyze.py 分析文本
        analysis_data = self._analyze_text(text, use_llm, no_cache=no_cache)

        return self._generate_quiz(
            analysis_data=analysis_data,
            game_name=output_name,
            source_label="direct_text",
            use_llm=use_llm,
            num_questions=num_questions,
            no_cache=no_cache,
        )

    def sample_from_bank(self, bank_path: str, num_questions: int = 10,
                         output_name: Optional[str] = None) -> str:
        """从已有题库中抽题组卷"""
        bank = self._load_question_bank(bank_path)
        if not bank:
            raise ValueError(f"题库为空或无效: {bank_path}")

        sampled = self._sample_questions(bank, num_questions)
        bank_dir = Path(bank_path).parent
        title = bank[0].get("source", "") if bank else "知识问答"

        return self._generate_quiz(
            analysis_data={"world": {"name": title}},
            game_name=output_name or f"quiz_sampled_{len(sampled)}q",
            source_label=bank_path,
            use_llm=False,
            num_questions=num_questions,
            pre_sampled=sampled,
        )

    # ═══════════════════════════════════════════════════════════════
    #  内部：文本分析（quiz 专用，侧重知识体系）
    # ═══════════════════════════════════════════════════════════════

    def _analyze_text(self, text: str, use_llm: bool, no_cache: bool = False) -> Dict:
        """用 quiz 专用 prompt 分析文本，提取知识体系"""
        if use_llm:
            try:
                return self._analyze_with_llm(text, no_cache)
            except Exception as e:
                print(f"  [Quiz] LLM 分析失败: {e}，使用模板分析")

        return self._analyze_with_template(text)

    def _analyze_with_llm(self, text: str, no_cache: bool = False) -> Dict:
        """用 LLM + quiz 专用 prompt 分析文本"""
        client = LLMClient()

        # 加载 quiz 专用 prompt
        prompt = self._load_prompt("quiz_analysis.txt")
        if not prompt:
            raise FileNotFoundError("quiz_analysis.txt 未找到")

        # 检查缓存（prompt 内容也参与 hash，prompt 改了缓存失效）
        import hashlib
        text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
        prompt_hash = hashlib.md5(prompt.encode("utf-8")).hexdigest()
        cache_data = {"text_hash": text_hash, "prompt_hash": prompt_hash, "mode": "quiz_analysis"}
        cache_key = self.cache.get_cache_key(cache_data, prefix="quiz_analysis")
        if not no_cache:
            cached = self.cache.load_from_cache(cache_key)
            if cached and isinstance(cached, dict):
                print("  [Quiz] 分析缓存命中")
                return cached

        # 分块分析（文本可能很长）
        chunk_size = 8000
        chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
        all_results = []

        for i, chunk in enumerate(chunks):
            print(f"  [Quiz] 分析第 {i+1}/{len(chunks)} 块...")
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"请分析以下文本：\n\n{chunk}"},
            ]
            response = client.chat_completion(messages)
            if not response:
                continue
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = self._parse_llm_json(content)
            if parsed:
                all_results.append(parsed)

        if not all_results:
            raise ValueError("LLM 未返回有效分析结果")

        # 合并多块结果
        merged = self._merge_quiz_analyses(all_results)

        # 缓存
        self.cache.save_to_cache(cache_key, merged, preview=merged.get("summary", "")[:100])

        return merged

    def _merge_quiz_analyses(self, results: List[Dict]) -> Dict:
        """合并多块 quiz 分析结果"""
        merged = {
            "domain": "",
            "summary": "",
            "concepts": [],
            "facts": [],
            "causes": [],
            "comparisons": [],
            "processes": [],
            "principles": [],
            "categories": [],
        }

        seen_concepts = set()
        seen_facts = set()

        for r in results:
            if not merged["domain"] and r.get("domain"):
                merged["domain"] = r["domain"]
            if not merged["summary"] and r.get("summary"):
                merged["summary"] = r["summary"]

            for c in r.get("concepts", []):
                key = c.get("name", "")
                if key and key not in seen_concepts:
                    seen_concepts.add(key)
                    merged["concepts"].append(c)

            for f in r.get("facts", []):
                key = f.get("statement", "")[:50]
                if key and key not in seen_facts:
                    seen_facts.add(key)
                    merged["facts"].append(f)

            merged["causes"].extend(r.get("causes", []))
            merged["comparisons"].extend(r.get("comparisons", []))
            merged["processes"].extend(r.get("processes", []))
            merged["principles"].extend(r.get("principles", []))

            for cat in r.get("categories", []):
                if cat not in merged["categories"]:
                    merged["categories"].append(cat)

        return merged

    def _analyze_with_template(self, text: str) -> Dict:
        """模板分析：从原文提取知识点"""
        import re
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        sentences = []
        for p in paragraphs:
            for s in p.replace("。", "。\n").replace(".", ".\n").split("\n"):
                s = s.strip()
                if len(s) > 10:
                    sentences.append(s)

        # 提取包含数字的句子作为 facts
        facts = []
        for sent in sentences:
            if re.search(r'\d+', sent) and len(sent) < 200:
                facts.append({"statement": sent, "detail": "", "category": ""})

        # 提取概念（冒号定义式）
        concepts = []
        for sent in sentences:
            m = re.match(r'^(.{2,10})(?:是指|是|为|即)(.{5,80})', sent)
            if m:
                concepts.append({"name": m.group(1), "definition": m.group(2), "category": ""})

        return {
            "domain": "文本材料",
            "summary": text[:200],
            "concepts": concepts,
            "facts": facts,
            "causes": [],
            "comparisons": [],
            "processes": [],
            "principles": [],
            "categories": [],
            "_raw_paragraphs": paragraphs,
            "_raw_sentences": sentences,
        }

    # ═══════════════════════════════════════════════════════════════
    #  内部：核心生成流程
    # ═══════════════════════════════════════════════════════════════

    def _generate_quiz(self, analysis_data: Dict, game_name: str,
                       source_label: str, use_llm: bool,
                       num_questions: int,
                       no_cache: bool = False,
                       pre_sampled: Optional[List[Dict]] = None) -> str:
        """核心生成流程：题库 → 抽题 → Twee"""
        project_path = self.output_dir / game_name
        project_path.mkdir(parents=True, exist_ok=True)

        print(f"[Quiz] 生成问答游戏: {game_name}")

        # 初始化 LLM
        self.llm = LLMClient()
        llm_ok = use_llm and self.llm.check_available()
        if llm_ok:
            print(f"[Quiz] LLM 可用 ({self.llm.api_url})")
            self._question_prompt = self._load_prompt("quiz_questions.txt")
        elif use_llm:
            raise RuntimeError(
                "Quiz 生成需要 LLM，请确保 LLM 服务已启动。"
                f"当前配置: {self.llm.api_url}\n"
                "如需跳过 LLM 使用模板模式，请添加 --no-llm 参数（仅限测试）。"
            )
        else:
            print(f"[Quiz] LLM 已禁用（--no-llm），使用模板模式")

        # ── 题库 ──
        bank_path = project_path / self.BANK_FILENAME
        if no_cache and bank_path.exists():
            bank_path.unlink()
            print(f"[Quiz] 已删除旧题库: {bank_path}")
        if pre_sampled:
            # 从外部抽题，不需要生成题库
            questions = pre_sampled
            bank = []
        elif bank_path.exists() and not no_cache:
            # 已有题库，直接抽题
            bank = self._load_question_bank(str(bank_path))
            questions = self._sample_questions(bank, num_questions)
            print(f"[Quiz] 从已有题库抽取 {len(questions)}/{len(bank)} 题")
        else:
            # 生成完整题库（覆盖所有知识点）
            bank = self._build_question_bank(analysis_data, llm_ok)
            # 保存题库
            bank_path.write_text(
                json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"[Quiz] 题库已保存: {bank_path} ({len(bank)} 题)")

        print(f"[Quiz] 题库 {len(bank)} 题，每次随机抽 {num_questions} 题")

        # ── 构建 Twee（整个题库都写入，JS 负责随机抽题）──
        story_data = self._build_story(bank, analysis_data, num_questions)

        twee_content = self._render_twee(story_data)
        twee_path = project_path / f"{game_name}.twee"
        twee_path.write_text(twee_content, encoding="utf-8")
        print(f"[Quiz] OK Twee 文件: {twee_path}")

        # ── 元数据 ──
        meta = {
            "generator": "Text2Game Quiz Generator",
            "format": "Chapbook",
            "source": source_label,
            "bank_size": len(bank),
            "quiz_size": num_questions,
            "question_types": self._count_types(bank),
            "quiz_title": story_data.get("title", ""),
        }
        (project_path / "metadata.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # 保存完整题库
        (project_path / "questions.json").write_text(
            json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        print(f"[Quiz] OK 生成完成: {project_path}")
        return str(project_path)

    # ═══════════════════════════════════════════════════════════════
    #  题库构建
    # ═══════════════════════════════════════════════════════════════

    def _build_question_bank(self, analysis: Dict, use_llm: bool) -> List[Dict]:
        """生成完整题库，覆盖所有知识点"""
        if use_llm and self.llm and self._question_prompt:
            bank = self._build_bank_with_llm(analysis)
            if bank:
                return bank

        return self._build_bank_from_template(analysis)

    def _build_bank_with_llm(self, analysis: Dict) -> List[Dict]:
        """用 LLM 生成完整题库（覆盖所有知识点）"""
        domain = analysis.get("domain", "")
        concepts = analysis.get("concepts", [])
        facts = analysis.get("facts", [])
        causes = analysis.get("causes", [])
        comparisons = analysis.get("comparisons", [])
        processes = analysis.get("processes", [])
        principles = analysis.get("principles", [])
        categories = analysis.get("categories", [])
        raw_sentences = analysis.get("_raw_sentences", [])

        # 构建 prompt 数据
        concepts_text = "\n".join(
            f"- {c.get('name', '')}（{c.get('category', '')}）：{c.get('definition', '')}"
            for c in concepts
        ) if concepts else "无"
        facts_text = "\n".join(
            f"- [{f.get('category', '')}] {f.get('statement', '')}"
            for f in facts
        ) if facts else "无"
        causes_text = "\n".join(
            f"- {c.get('cause', '')} → {c.get('effect', '')}：{c.get('description', '')}"
            for c in causes
        ) if causes else "无"
        comparisons_text = "\n".join(
            f"- {c.get('topic', '')}：{' vs '.join(c.get('items', []))}，区别：{c.get('difference', '')}"
            for c in comparisons
        ) if comparisons else "无"
        processes_text = "\n".join(
            f"- {p.get('name', '')}：{' → '.join(p.get('steps', []))}"
            for p in processes
        ) if processes else "无"
        principles_text = "\n".join(
            f"- [{p.get('category', '')}] {p.get('name', '')}：{p.get('description', '')}"
            for p in principles
        ) if principles else "无"
        sentences_text = "\n".join(f"- {s}" for s in raw_sentences[:50]) if raw_sentences else "无"

        prompt = self._question_prompt.format(
            domain=domain,
            concepts=concepts_text,
            facts=facts_text,
            causes=causes_text,
            comparisons=comparisons_text,
            processes=processes_text,
            principles=principles_text,
            categories="、".join(categories) if categories else "无",
            sentences=sentences_text,
        )

        # 缓存
        import hashlib
        analysis_hash = hashlib.md5(json.dumps(analysis, sort_keys=True).encode("utf-8")).hexdigest()
        prompt_hash = hashlib.md5(prompt.encode("utf-8")).hexdigest()
        cache_data = {"analysis_hash": analysis_hash,
                       "prompt_hash": prompt_hash,
                       "mode": "comprehensive"}
        cache_key = self.cache.get_cache_key(cache_data, prefix="quiz_bank")
        cached = self.cache.load_from_cache(cache_key)
        if cached and isinstance(cached, list) and len(cached) > 5:
            print(f"  [Quiz] 命中缓存: {len(cached)} 题")
            return cached

        total_points = len(concepts) + len(facts) + len(causes) + len(comparisons) + len(processes) + len(principles)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"材料包含 {total_points} 个知识点，请为每个知识点生成至少2道题（1道判断+1道单选），多选题可跨知识点。总共不少于 {total_points * 2} 道题。不要合并知识点，每个知识点单独出题。"},
        ]
        print(f"  [Quiz] 调用 LLM 生成题库（{total_points} 个知识点）...")
        response = self.llm.chat_completion(messages)
        if not response:
            return []

        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = self._parse_llm_json(content)
        if not parsed:
            return []

        questions = parsed.get("questions", [])
        valid = self._validate_questions(questions, limit=9999)

        if valid:
            self.cache.save_to_cache(cache_key, valid, preview=f"{len(valid)} questions")

        return valid

    def _build_bank_from_template(self, analysis: Dict) -> List[Dict]:
        """模板生成题库（支持知识体系结构和游戏结构）"""
        questions = []
        raw_sentences = analysis.get("_raw_sentences", [])
        raw_paragraphs = analysis.get("_raw_paragraphs", [])

        # ═══ 新结构：知识体系（concepts, facts, causes, ...）═══
        concepts = analysis.get("concepts", [])
        facts = analysis.get("facts", [])
        causes = analysis.get("causes", [])
        comparisons = analysis.get("comparisons", [])
        processes = analysis.get("processes", [])
        principles = analysis.get("principles", [])

        if concepts or facts or causes or comparisons or processes or principles:
            # 收集所有概念名用于干扰项
            all_concept_names = [c.get("name", "") for c in concepts if c.get("name")]
            all_fact_stmts = [f.get("statement", "") for f in facts if f.get("statement")]
            all_effect_texts = [c.get("effect", "") for c in causes if c.get("effect")]
            all_desc_texts = [p.get("description", "") for p in principles if p.get("description")]

            for c in concepts:
                name = c.get("name", "")
                defn = c.get("definition", "")
                if not name or not defn:
                    continue
                questions.append({"type": "true_false", "question": f"以下关于「{name}」的定义是否正确？\n\n{defn}", "answer": True, "explanation": f"根据材料，{name}的定义与原文一致。", "source": f"概念：{name}"})
                # 干扰项：用其他概念的定义
                other_defs = [x.get("definition", "") for x in concepts if x.get("name") != name and x.get("definition")][:3]
                while len(other_defs) < 3:
                    other_defs.append(defn[:30] + "（部分内容被修改）")
                opts = self._shuffle_options({"A": defn[:80], "B": other_defs[0][:80], "C": other_defs[1][:80], "D": other_defs[2][:80]})
                questions.append({"type": "single_choice", "question": f"「{name}」的正确定义是？", "options": opts["options"], "answer": opts["correct"], "explanation": f"{name}：{defn[:150]}", "source": f"概念：{name}"})

            for f in facts:
                stmt = f.get("statement", "")
                if not stmt or len(stmt) < 10:
                    continue
                questions.append({"type": "true_false", "question": f"以下说法是否正确？\n\n「{stmt}」", "answer": True, "explanation": "该说法直接来自材料原文。", "source": "事实"})

            for c in causes:
                cause = c.get("cause", "")
                effect = c.get("effect", "")
                if not cause or not effect:
                    continue
                questions.append({"type": "true_false", "question": f"以下因果关系是否正确？\n\n{cause} → {effect}", "answer": True, "explanation": f"根据材料，因果关系成立。", "source": "因果关系"})
                # 干扰项：用其他因果关系的结果
                other_effects = [x.get("effect", "") for x in causes if x.get("effect") != effect and x.get("effect")][:3]
                while len(other_effects) < 3:
                    other_effects.append(effect[:30] + "（部分被修改）")
                opts = self._shuffle_options({"A": effect[:80], "B": other_effects[0][:80], "C": other_effects[1][:80], "D": other_effects[2][:80]})
                questions.append({"type": "single_choice", "question": f"「{cause[:50]}」会导致什么结果？", "options": opts["options"], "answer": opts["correct"], "explanation": f"根据材料，{cause} → {effect}", "source": "因果关系"})

            for comp in comparisons:
                topic = comp.get("topic", "")
                items = comp.get("items", [])
                diff = comp.get("difference", "")
                if not topic or len(items) < 2:
                    continue
                questions.append({"type": "true_false", "question": f"以下关于「{topic}」的对比是否正确？\n\n{' vs '.join(items)}，区别在于：{diff}", "answer": True, "explanation": f"根据材料，对比描述正确。", "source": f"对比：{topic}"})

            for p in processes:
                name = p.get("name", "")
                steps = p.get("steps", [])
                if not name or len(steps) < 2:
                    continue
                questions.append({"type": "true_false", "question": f"以下关于「{name}」的步骤描述是否正确？\n\n{' → '.join(steps[:5])}", "answer": True, "explanation": f"根据材料，流程描述正确。", "source": f"流程：{name}"})

            for p in principles:
                name = p.get("name", "")
                desc = p.get("description", "")
                if not name or not desc:
                    continue
                questions.append({"type": "true_false", "question": f"以下关于「{name}」的描述是否正确？\n\n{desc}", "answer": True, "explanation": f"根据材料，{name}的描述与原文一致。", "source": f"原理：{name}"})
                # 干扰项：用其他原理的描述
                other_descs = [x.get("description", "") for x in principles if x.get("name") != name and x.get("description")][:3]
                while len(other_descs) < 3:
                    other_descs.append(desc[:30] + "（部分被修改）")
                opts = self._shuffle_options({"A": desc[:80], "B": other_descs[0][:80], "C": other_descs[1][:80], "D": other_descs[2][:80]})
                questions.append({"type": "single_choice", "question": f"关于「{name}」，以下哪项描述是正确的？", "options": opts["options"], "answer": opts["correct"], "explanation": f"{name}：{desc[:150]}", "source": f"原理：{name}"})

        # ═══ 旧结构：游戏（events, characters, ...）═══
        else:
            events = analysis.get("events", [])
            characters = analysis.get("characters", [])
            relationships = analysis.get("relationships", [])
            conflicts = analysis.get("conflicts", [])
            world = analysis.get("world", {})
            themes = analysis.get("themes", [])

            all_traits = []
            for char in characters:
                for t in char.get("traits", []):
                    all_traits.append((char.get("name", ""), t))
            all_names = [c.get("name", "") for c in characters if c.get("name")]
            all_roles = list(set(c.get("role", "") for c in characters if c.get("role")))
            all_event_titles = [e.get("title", "") for e in events if e.get("title")]
            all_event_descs = [e.get("description", "") for e in events if e.get("description")]
            all_consequences = [e.get("consequences", "") for e in events if e.get("consequences")]
            all_rel_descs = [r.get("description", "") for r in relationships if r.get("description")]
            all_conflict_descs = [c.get("description", "") for c in conflicts if c.get("description")]

            for event in events:
                title = event.get("title", "")
                desc = event.get("description", "")
                chars = event.get("characters", [])
                consequences = event.get("consequences", "")
                if not title or not desc:
                    continue
                questions.append({"type": "true_false", "question": f"以下关于「{title}」的说法是否正确？\n\n{desc[:200]}", "answer": True, "explanation": f"根据材料，{title}的描述与原文一致。", "source": f"事件：{title}"})
                if chars:
                    other_chars = [n for n in all_names if n not in chars]
                    if len(other_chars) >= 3:
                        opts = self._shuffle_options({"A": chars[0], "B": other_chars[0], "C": other_chars[1], "D": other_chars[2]})
                        questions.append({"type": "single_choice", "question": f"事件「{title}」主要涉及哪个角色？", "options": opts["options"], "answer": opts["correct"], "explanation": f"根据材料，{title}涉及{', '.join(chars)}。", "source": f"事件：{title}"})
                if consequences:
                    other_cons = [c for c in all_consequences if c != consequences and len(c) > 10]
                    if len(other_cons) >= 3:
                        opts = self._shuffle_options({"A": consequences[:80], "B": other_cons[0][:80], "C": other_cons[1][:80], "D": other_cons[2][:80]})
                        questions.append({"type": "single_choice", "question": f"事件「{title}」的后果是什么？", "options": opts["options"], "answer": opts["correct"], "explanation": f"后果：{consequences[:150]}", "source": f"事件：{title}"})

            for char in characters:
                name = char.get("name", "")
                role = char.get("role", "")
                traits = char.get("traits", [])
                if not name: continue
                if role:
                    questions.append({"type": "true_false", "question": f"以下说法是否正确：{name}的身份是「{role}」。", "answer": True, "explanation": f"根据材料，{name}确实是{role}。", "source": f"角色：{name}"})
                if traits:
                    questions.append({"type": "true_false", "question": f"以下说法是否正确：{name}的性格特征包括{traits[0]}。", "answer": True, "explanation": f"根据材料，{name}的特征确实包含{traits[0]}。", "source": f"角色：{name}"})
                if traits:
                    other_traits = [t for n, t in all_traits if n != name and t != traits[0]]
                    if len(other_traits) >= 3:
                        opts = self._shuffle_options({"A": traits[0], "B": other_traits[0], "C": other_traits[1], "D": other_traits[2]})
                        questions.append({"type": "single_choice", "question": f"关于{name}的特征，以下哪项描述是正确的？", "options": opts["options"], "answer": opts["correct"], "explanation": f"{name}的特征为{', '.join(traits)}。", "source": f"角色：{name}"})
                if role:
                    other_roles = [r for r in all_roles if r != role]
                    if len(other_roles) >= 3:
                        opts = self._shuffle_options({"A": role, "B": other_roles[0], "C": other_roles[1], "D": other_roles[2]})
                        questions.append({"type": "single_choice", "question": f"{name}在材料中的身份是什么？", "options": opts["options"], "answer": opts["correct"], "explanation": f"根据材料，{name}的身份是{role}。", "source": f"角色：{name}"})

            for rel in relationships:
                fr, to = rel.get("from", ""), rel.get("to", "")
                rtype, rdesc = rel.get("type", ""), rel.get("description", "")
                if not fr or not to: continue
                questions.append({"type": "true_false", "question": f"以下说法是否正确：{fr}与{to}之间存在「{rtype}」关系。", "answer": True, "explanation": f"根据材料，{fr}与{to}的关系是{rtype}。", "source": f"关系：{fr}-{to}"})
                if rdesc:
                    other_descs = [d for d in all_rel_descs if d != rdesc and len(d) > 10]
                    if len(other_descs) >= 3:
                        opts = self._shuffle_options({"A": rdesc[:60], "B": other_descs[0][:60], "C": other_descs[1][:60], "D": other_descs[2][:60]})
                        questions.append({"type": "single_choice", "question": f"关于{fr}与{to}的关系，以下哪项描述是正确的？", "options": opts["options"], "answer": opts["correct"], "explanation": f"{rdesc[:150]}", "source": f"关系：{fr}-{to}"})

            for conflict in conflicts:
                ctype, cdesc = conflict.get("type", ""), conflict.get("description", "")
                if not ctype: continue
                questions.append({"type": "true_false", "question": f"以下说法是否正确：材料中存在「{ctype}」类型的冲突。", "answer": True, "explanation": f"根据材料，{ctype}确实是核心冲突。", "source": f"冲突：{ctype}"})
                if cdesc:
                    other_cdescs = [d for d in all_conflict_descs if d != cdesc and len(d) > 10]
                    if len(other_cdescs) >= 3:
                        opts = self._shuffle_options({"A": cdesc[:60], "B": other_cdescs[0][:60], "C": other_cdescs[1][:60], "D": other_cdescs[2][:60]})
                        questions.append({"type": "single_choice", "question": f"关于「{ctype}」冲突，以下哪项描述是正确的？", "options": opts["options"], "answer": opts["correct"], "explanation": f"{cdesc[:150]}", "source": f"冲突：{ctype}"})

            for theme in themes:
                questions.append({"type": "true_false", "question": f"以下说法是否正确：「{theme}」是本材料的主题之一。", "answer": True, "explanation": f"根据材料，{theme}确实是核心主题。", "source": f"主题：{theme}"})
                other_themes = [t for t in themes if t != theme]
                if other_themes:
                    opts = self._shuffle_options({"A": theme, "B": other_themes[0], "C": other_themes[-1] if len(other_themes) > 1 else theme + "（类似）", "D": other_themes[0] + "（类似）"})
                    questions.append({"type": "single_choice", "question": "以下哪项是本材料的核心主题？", "options": opts["options"], "answer": opts["correct"], "explanation": f"核心主题：{', '.join(themes)}。", "source": "主题"})

            if world:
                world_name = world.get("name", "这个世界")
                world_desc = world.get("description", "")
                if world_name:
                    questions.append({"type": "true_false", "question": f"以下说法是否正确：本材料的世界名称是「{world_name}」。", "answer": True, "explanation": f"根据材料，世界名称是{world_name}。", "source": "世界观"})

        # ═══ 原文句子：通用 ═══
        for sent in raw_sentences:
            if len(sent) < 15 or len(sent) > 250:
                continue
            questions.append({"type": "true_false", "question": f"以下说法是否正确？\n\n「{sent}」", "answer": True, "explanation": "该说法直接来自材料原文。", "source": "原文"})

        # ═══ 原文关键词 SC ═══
        keywords = self._extract_keywords(raw_sentences)
        for term, sentence, context_words in keywords:
            distractors = [w for w in context_words if w != term][:3]
            while len(distractors) < 3: distractors.append("未知")
            questions.append({"type": "single_choice", "question": f"根据材料，以下哪个关键词最适合填入？\n\n「{sentence.replace(term, '___', 1)}」", "options": {"A": term, "B": distractors[0], "C": distractors[1], "D": distractors[2]}, "answer": "A", "explanation": f"原文使用了「{term}」一词。", "source": "原文"})

        # ═══ 原文段落 MC ═══
        for para in raw_paragraphs:
            sents = [s.strip() for s in para.replace("。", "。\n").split("\n") if len(s.strip()) > 15]
            if len(sents) < 2: continue
            correct_sents = sents[:3]
            all_options = correct_sents + ["这个说法完全没有任何依据。", "材料中从未提及相关内容。"][:2]
            random.shuffle(all_options)
            options, correct_labels = {}, []
            for i, s in enumerate(all_options):
                label = chr(65 + i)
                options[label] = s[:80]
                if i < len(correct_sents): correct_labels.append(label)
            questions.append({"type": "multiple_choice", "question": "以下哪些说法来自材料原文？（多选）", "options": options, "answer": sorted(correct_labels), "explanation": "正确选项直接来自材料段落。", "source": "原文段落"})

        return questions

    @staticmethod
    def _shuffle_options(options: Dict[str, str]) -> Dict:
        """打乱选项顺序并返回新选项和正确答案标签"""
        items = list(options.items())
        correct_val = options["A"]
        random.shuffle(items)
        new_options, new_correct = {}, "A"
        for i, (k, v) in enumerate(items):
            label = chr(65 + i)
            new_options[label] = v
            if v == correct_val:
                new_correct = label
        return {"options": new_options, "correct": new_correct}

    @staticmethod
    def _validate_questions(questions: List[Dict], limit: int) -> List[Dict]:
        """校验并去重"""
        seen = set()
        valid = []
        for q in questions:
            qtype = q.get("type", "")
            if qtype not in ("true_false", "single_choice", "multiple_choice"):
                continue
            if not q.get("question") or q.get("answer") is None:
                continue
            if qtype in ("single_choice", "multiple_choice"):
                options = q.get("options", {})
                if len(options) < 2:
                    continue
            # 去重：用题目文本前50字符做 key
            key = q.get("question", "")[:50]
            if key in seen:
                continue
            seen.add(key)
            valid.append(q)
            if len(valid) >= limit:
                break
        return valid

    # ═══════════════════════════════════════════════════════════════
    #  题库管理
    # ═══════════════════════════════════════════════════════════════

    def _load_question_bank(self, bank_path: str) -> List[Dict]:
        """加载题库"""
        p = Path(bank_path)
        if not p.exists():
            return []
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
        return []

    def _sample_questions(self, bank: List[Dict], n: int) -> List[Dict]:
        """从题库中随机抽题，尽量保持题型均衡"""
        if len(bank) <= n:
            return bank[:]

        # 按题型分组
        by_type = {}
        for q in bank:
            t = q.get("type", "unknown")
            by_type.setdefault(t, []).append(q)

        # 按比例抽取
        sampled = []
        remaining = n
        type_names = list(by_type.keys())

        # 先算每种题型应分配多少
        if len(type_names) > 0:
            per_type = max(1, n // len(type_names))
        else:
            per_type = n

        for tname in type_names:
            pool = by_type[tname]
            take = min(per_type, len(pool), remaining)
            sampled.extend(random.sample(pool, take))
            remaining -= take

        # 如果还有剩余，随机补充
        if remaining > 0:
            all_remaining = [q for q in bank if q not in sampled]
            if all_remaining:
                sampled.extend(random.sample(all_remaining, min(remaining, len(all_remaining))))

        random.shuffle(sampled)
        return sampled[:n]

    @staticmethod
    def _extract_keywords(sentences: List[str]) -> List[tuple]:
        """从句子中提取关键词用于生成单选题"""
        # 简单的关键词提取：找中文术语（2-6字的词组）
        import re
        term_pattern = re.compile(r'[\u4e00-\u9fff]{2,6}')
        # 收集所有出现的术语
        all_terms = {}
        for sent in sentences:
            for match in term_pattern.finditer(sent):
                t = match.group()
                all_terms[t] = all_terms.get(t, 0) + 1

        # 过滤高频和低频，取中间的作为关键词
        sorted_terms = sorted(all_terms.items(), key=lambda x: x[1], reverse=True)
        keywords = []
        # 用出现2-4次的词作为关键词（太常见或太罕见的排除）
        for term, count in sorted_terms:
            if count < 2:
                continue
            # 找一个包含该词的句子
            for sent in sentences:
                if term in sent and 20 < len(sent) < 200:
                    # 提取同一句中的其他术语作为干扰项
                    context = [m.group() for m in term_pattern.finditer(sent) if m.group() != term]
                    if context:
                        keywords.append((term, sent, context))
                    break
        return keywords

    @staticmethod
    def _count_types(questions: List[Dict]) -> Dict[str, int]:
        counts = {}
        for q in questions:
            t = q.get("type", "unknown")
            counts[t] = counts.get(t, 0) + 1
        return counts

    # ═══════════════════════════════════════════════════════════════
    #  Twee 故事构建
    # ═══════════════════════════════════════════════════════════════

    def _build_story(self, questions: List[Dict], analysis: Dict,
                     num_questions: int = 10) -> Dict:
        world = analysis.get("world", {})
        title = world.get("name", "") + " 知识问答"
        if not title.strip() or title.strip() == "知识问答":
            title = "知识问答"

        total_bank = len(questions)
        passages = []

        config = {
            "config.transition-in": "'instant'",
            "config.transition-out": "'instant'",
            "config.enable-style-overrides": "true",
            "config.style.font-family": "'Noto Sans SC', 'Microsoft YaHei', sans-serif",
            "config.style.font-size": "18",
            "config.style.line-height": "1.8",
            "config.style.width": "'800px'",
            "config.style.text-color": "'#e0e0e0'",
            "config.style.background-color": "'#1a1a2e'",
        }

        # 所有题目 passage ID 列表（JS 用于随机抽题）
        all_qids = [f"Q{i+1:02d}" for i in range(total_bank)]

        # Start
        passages.append({
            "name": "Start",
            "tags": ["start"],
            "source": self._build_start_source(title, total_bank, num_questions),
        })

        # 所有题目段落（整个题库都写入 Twee）
        for i, q in enumerate(questions):
            qid = f"Q{i+1:02d}"
            if q["type"] == "true_false":
                passages.extend(self._build_tf_passage(q, qid))
            elif q["type"] == "single_choice":
                passages.extend(self._build_single_passage(q, qid))
            elif q["type"] == "multiple_choice":
                passages.extend(self._build_multi_passage(q, qid))

        # Results
        passages.append({
            "name": "Results",
            "tags": ["results"],
            "source": self._build_results_source(num_questions),
        })

        return {
            "title": title,
            "config": config,
            "stylesheet": self._build_stylesheet(),
            "javascript": self._build_javascript(all_qids, num_questions),
            "passages": passages,
        }

    # ── Start ──
    def _build_start_source(self, title: str, total_bank: int, quiz_size: int) -> str:
        return f"""--
current_idx: 0
quiz_size: {quiz_size}

## {title}

欢迎来到知识问答！

题库共 **{total_bank}** 道题，每次随机抽取 **{quiz_size}** 道。

包含判断题、单选题和多选题。

准备好了吗？

---

> [[开始答题->javascript:startQuiz()]]
> [[无尽模式->javascript:startEndless()]]"""

    # ── 判断题 ──
    def _build_tf_passage(self, q: Dict, qid: str) -> List[Dict]:
        source = q.get("question", "")
        explanation = q.get("explanation", "无解析")
        is_correct = q.get("answer", True)
        source_ref = q.get("source", "")

        q_source = f"""## 判断题

{source}

---

> [[✓ 正确->{qid}_True]]
> [[✗ 错误->{qid}_False]]"""

        true_feedback = f"""**✓ 回答正确！**

{explanation}

—— 出处：{source_ref}

---

> [[下一题->javascript:goNext()]]
> [[退出->javascript:exitQuiz()]]"""

        false_feedback = f"""**✗ 回答错误**

正确答案：**{"正确" if is_correct else "错误"}**

{explanation}

—— 出处：{source_ref}

---

> [[下一题->javascript:goNext()]]
> [[退出->javascript:exitQuiz()]]"""

        return [
            {"name": qid, "tags": ["question", "true_false"], "source": q_source},
            {"name": f"{qid}_True", "tags": ["feedback"], "source": true_feedback},
            {"name": f"{qid}_False", "tags": ["feedback"], "source": false_feedback},
        ]

    # ── 单选题 ──
    def _build_single_passage(self, q: Dict, qid: str) -> List[Dict]:
        question_text = q.get("question", "")
        options = q.get("options", {})
        correct = q.get("answer", "A")
        explanation = q.get("explanation", "无解析")
        source_ref = q.get("source", "")

        opt_lines = []
        for label in sorted(options.keys()):
            opt_lines.append(f"> [[{label}. {options[label]}->{qid}_{label}]]")

        q_source = f"""## 单选题

{question_text}

{chr(10).join(opt_lines)}"""

        passages = [
            {"name": qid, "tags": ["question", "single_choice"], "source": q_source},
        ]

        for label in sorted(options.keys()):
            is_correct = (label == correct)
            if is_correct:
                fb = f"""**✓ 回答正确！**

正确答案：**{label}. {options[label]}**

{explanation}

—— 出处：{source_ref}

---

> [[下一题->javascript:goNext()]]
> [[退出->javascript:exitQuiz()]]"""
            else:
                fb = f"""**✗ 回答错误**

正确答案：**{correct}. {options.get(correct, '')}**

你选的是：{label}. {options.get(label, '')}

{explanation}

—— 出处：{source_ref}

---

> [[下一题->javascript:goNext()]]
> [[退出->javascript:exitQuiz()]]"""

            passages.append({
                "name": f"{qid}_{label}",
                "tags": ["feedback"],
                "source": fb,
            })

        return passages

    # ── 多选题 ──
    def _build_multi_passage(self, q: Dict, qid: str) -> List[Dict]:
        question_text = q.get("question", "")
        options = q.get("options", {})
        correct = q.get("answer", [])
        explanation = q.get("explanation", "无解析")
        source_ref = q.get("source", "")

        opt_html_parts = []
        for label in sorted(options.keys()):
            opt_html_parts.append(
                f'<label class="quiz-option"><input type="checkbox" name="{qid}" value="{label}"> {label}. {options[label]}</label>'
            )
        correct_json = json.dumps(sorted(correct))

        q_source = f"""## 多选题

{question_text}

<div class="quiz-multi" data-qid="{qid}" data-correct='{correct_json}'>
{chr(10).join(opt_html_parts)}
<div class="quiz-submit"><button class="quiz-btn" onclick="submitMulti(this)">提交答案</button></div>
</div>"""

        correct_fb = f"""**✓ 回答正确！**

{explanation}

—— 出处：{source_ref}

---

> [[下一题->javascript:goNext()]]
> [[退出->javascript:exitQuiz()]]"""

        wrong_fb = f"""**✗ 回答错误**

正确答案：**{', '.join(sorted(correct))}**

{explanation}

—— 出处：{source_ref}

---

> [[下一题->javascript:goNext()]]
> [[退出->javascript:exitQuiz()]]"""

        return [
            {"name": qid, "tags": ["question", "multiple_choice"], "source": q_source},
            {"name": f"{qid}_Correct", "tags": ["feedback"], "source": correct_fb},
            {"name": f"{qid}_Wrong", "tags": ["feedback"], "source": wrong_fb},
        ]

    # ── 结果页 ──
    def _build_results_source(self, quiz_size: int) -> str:
        return f"""## 答题完成！

本次共回答 **{quiz_size}** 道题目。

每道题的反馈中已包含正确答案和解析，可以回顾复习。

---

> [[重新开始->javascript:restartQuiz()]]"""

    # ── 样式 ──
    def _build_stylesheet(self) -> str:
        return """/* Quiz 样式 */
#page { max-width: 800px; margin: 0 auto; padding: 2rem 1.5rem; }
.passage h2 { color: #e8d4b4; border-bottom: 1px solid #333; padding-bottom: 0.5rem; margin: 1.5rem 0 0.8rem; font-size: 1.4em; }
.passage p { margin: 0.6rem 0; }
.passage strong { color: #e8d4b4; }
.passage a { color: #b4d4e8; text-decoration: none; border-bottom: 1px dotted #b4d4e8; transition: all 0.2s; cursor: pointer; }
.passage a:hover { color: #e8b4b8; border-bottom-color: #e8b4b8; }
.passage hr { border: none; border-top: 1px solid #333; margin: 1.5rem 0; }
.passage .fork { margin: 0.5rem 0; }
.passage .fork a {
  display: block; padding: 0.8rem 1.2rem;
  background: rgba(180, 212, 232, 0.08);
  border: 1px solid rgba(180, 212, 232, 0.2);
  border-radius: 6px; border-bottom: 1px solid rgba(180, 212, 232, 0.2);
  transition: all 0.25s; margin: 0.4rem 0;
}
.passage .fork a:hover {
  background: rgba(180, 212, 232, 0.15);
  border-color: rgba(180, 212, 232, 0.4);
  transform: translateX(4px);
}
.quiz-multi { margin: 1rem 0; }
.quiz-option {
  display: block; padding: 0.7rem 1rem; margin: 0.4rem 0;
  background: rgba(180, 212, 232, 0.06);
  border: 1px solid rgba(180, 212, 232, 0.15);
  border-radius: 6px; cursor: pointer; transition: all 0.2s;
}
.quiz-option:hover { background: rgba(180, 212, 232, 0.12); border-color: rgba(180, 212, 232, 0.3); }
.quiz-option input { margin-right: 0.6rem; accent-color: #b4d4e8; }
.quiz-submit { margin-top: 1rem; }
.quiz-btn {
  padding: 0.6rem 1.5rem; background: rgba(180, 212, 232, 0.2);
  border: 1px solid rgba(180, 212, 232, 0.4); border-radius: 6px;
  color: #b4d4e8; cursor: pointer; font-size: 1rem; transition: all 0.2s;
}
.quiz-btn:hover { background: rgba(180, 212, 232, 0.35); }
.quiz-btn:disabled { opacity: 0.5; cursor: not-allowed; }"""

    # ── JS ──
    def _build_javascript(self, all_qids: List[str], quiz_size: int) -> str:
        qids_json = json.dumps(all_qids)
        return f"""// ── Quiz 引擎 ──
var ALL_QIDS = {qids_json};
var QUIZ_SIZE = {quiz_size};

function shuffle(arr) {{
  var a = arr.slice();
  for (var i = a.length - 1; i > 0; i--) {{
    var j = Math.floor(Math.random() * (i + 1));
    var t = a[i]; a[i] = a[j]; a[j] = t;
  }}
  return a;
}}

function startQuiz() {{
  story.state.set('endless', false);
  var queue = shuffle(ALL_QIDS).slice(0, QUIZ_SIZE);
  story.state.set('queue', queue);
  story.state.set('current_idx', 0);
  story.state.set('quiz_size', queue.length);
  go(queue[0]);
}}

function startEndless() {{
  story.state.set('endless', true);
  var queue = shuffle(ALL_QIDS).slice(0, QUIZ_SIZE);
  story.state.set('queue', queue);
  story.state.set('current_idx', 0);
  story.state.set('quiz_size', queue.length);
  go(queue[0]);
}}

function goNext() {{
  var idx = story.state.get('current_idx', 0) + 1;
  var queue = story.state.get('queue', []);
  var endless = story.state.get('endless', false);
  if (idx >= queue.length) {{
    if (endless) {{
      // 无尽模式：重新洗牌继续
      queue = shuffle(ALL_QIDS).slice(0, QUIZ_SIZE);
      story.state.set('queue', queue);
      story.state.set('current_idx', 0);
      go(queue[0]);
    }} else {{
      go('Results');
    }}
  }} else {{
    story.state.set('current_idx', idx);
    go(queue[idx]);
  }}
}}

function exitQuiz() {{
  story.state.set('endless', false);
  go('Start');
}}

function restartQuiz() {{
  startQuiz();
}}

// ── 多选题提交 ──
function submitMulti(btn) {{
  var container = btn.closest('.quiz-multi');
  if (!container) return;
  var qid = container.getAttribute('data-qid');
  var correct = JSON.parse(container.getAttribute('data-correct'));

  var selected = [];
  container.querySelectorAll('input[type=checkbox]:checked').forEach(function(cb) {{
    selected.push(cb.value);
  }});

  if (selected.length === 0) {{
    alert('请至少选择一个选项');
    return;
  }}

  selected.sort();
  correct.sort();
  var isCorrect = JSON.stringify(selected) === JSON.stringify(correct);

  btn.disabled = true;
  btn.textContent = isCorrect ? '✓ 正确！' : '✗ 错误';

  container.querySelectorAll('.quiz-option').forEach(function(label) {{
    var cb = label.querySelector('input');
    var val = cb.value;
    if (correct.indexOf(val) !== -1) {{
      label.style.borderColor = '#4CAF50';
      label.style.background = 'rgba(76, 175, 80, 0.15)';
    }} else if (cb.checked) {{
      label.style.borderColor = '#f44336';
      label.style.background = 'rgba(244, 67, 54, 0.15)';
    }}
  }});

  setTimeout(function() {{
    go(qid + (isCorrect ? '_Correct' : '_Wrong'));
  }}, 1200);
}}"""

    # ═══════════════════════════════════════════════════════════════
    #  Twee 渲染
    # ═══════════════════════════════════════════════════════════════
    # _render_twee / _render_story_data / _render_passage 继承自 BaseGenerator，
    # 统一了 Twine 和 Quiz 的 Twee 格式输出。


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Quiz 问答游戏生成器")
    sub = parser.add_subparsers(dest="command")

    # 子命令: generate（从 analysis.json）
    p_gen = sub.add_parser("generate", help="从 analysis.json 生成 quiz")
    p_gen.add_argument("-a", "--analysis", required=True, help="分析结果 JSON 文件")
    p_gen.add_argument("-o", "--output", default="./generated_games", help="输出目录")
    p_gen.add_argument("-n", "--name", help="自定义输出名称")
    p_gen.add_argument("-q", "--questions", type=int, default=10, help="抽题数量（默认10）")
    p_gen.add_argument("--no-llm", action="store_true", help="不使用 LLM")
    p_gen.add_argument("--no-cache", action="store_true", help="跳过缓存，强制重新生成")

    # 子命令: from-text（从文本直接生成）
    p_text = sub.add_parser("from-text", help="从文本直接生成 quiz")
    p_text.add_argument("-t", "--text-file", required=True, help="文本文件路径")
    p_text.add_argument("-o", "--output", default="./generated_games", help="输出目录")
    p_text.add_argument("-n", "--name", default="quiz", help="输出名称")
    p_text.add_argument("-q", "--questions", type=int, default=10, help="抽题数量")
    p_text.add_argument("--no-llm", action="store_true", help="不使用 LLM")
    p_text.add_argument("--no-cache", action="store_true", help="跳过缓存，强制重新生成")

    # 子命令: sample（从题库抽题）
    p_sample = sub.add_parser("sample", help="从已有题库抽题组卷")
    p_sample.add_argument("-b", "--bank", required=True, help="题库 JSON 文件路径")
    p_sample.add_argument("-o", "--output", default="./generated_games", help="输出目录")
    p_sample.add_argument("-n", "--name", help="输出名称")
    p_sample.add_argument("-q", "--questions", type=int, default=10, help="抽题数量")

    args = parser.parse_args()

    generator = QuizGenerator(getattr(args, "output", "./generated_games"))

    if getattr(args, "no_cache", False):
        generator.cache.clear_cache()
        print("[Quiz] 缓存已清除")

    no_cache = getattr(args, "no_cache", False)

    try:
        if args.command == "generate":
            path = generator.generate(
                args.analysis, output_name=args.name,
                use_llm=not args.no_llm, num_questions=args.questions,
                no_cache=no_cache,
            )
        elif args.command == "from-text":
            text = Path(args.text_file).read_text(encoding="utf-8")
            path = generator.generate_from_text(
                text, output_name=args.name,
                use_llm=not args.no_llm, num_questions=args.questions,
                no_cache=no_cache,
            )
        elif args.command == "sample":
            path = generator.sample_from_bank(
                args.bank, num_questions=args.questions,
                output_name=args.name,
            )
        else:
            parser.print_help()
            return

        # 自动编译 Twee → HTML（使用共享编译函数）
        if path:
            compile_twee_files(path)

        print(f"\nOK 生成完成: {path}")
        print(f"  编译: uv run python pi_mode/compile_twee.py {path}")

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()

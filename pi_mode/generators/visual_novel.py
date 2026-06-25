#!/usr/bin/env python3
"""
视觉小说游戏生成器
基于分析结果生成完整的Godot视觉小说项目，利用LLM生成分支剧情
"""

import json
import os
import random
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 尝试加载 dotenv
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / '.env'
    load_dotenv(env_path)
except ImportError:
    pass
except Exception:
    pass


class _LLMClient:
    """轻量LLM客户端，复用analyze.py的配置"""

    def __init__(self):
        self.api_url = os.getenv("LLM_API_URL", "http://localhost:1234/v1").rstrip("/")
        self.model = os.getenv("LLM_MODEL", "google/gemma-4-12b-qat")
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.8"))
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "16384"))
        self.timeout = int(os.getenv("LLM_TIMEOUT", "600"))
        self.max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))
        self.enable_reasoning = os.getenv("ENABLE_REASONING", "false").lower() == "true"
        self._available: Optional[bool] = None

    def chat_completion(self, messages: List[Dict]) -> Optional[Dict]:
        """发送聊天请求（带重试），失败返回None"""
        try:
            import requests
        except ImportError:
            return None

        url = f"{self.api_url}/chat/completions"
        body = {
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
            "reasoning": {"enabled": self.enable_reasoning},
        }
        if self.model:
            body["model"] = self.model

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        proxies = {"http": None, "https": None}

        for attempt in range(self.max_retries):
            try:
                resp = requests.post(url, json=body, headers=headers,
                                     timeout=self.timeout, proxies=proxies)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code in (429, 500, 502, 503):
                    time.sleep(3 * (attempt + 1))
                    continue
                else:
                    print(f"  [LLM] HTTP {resp.status_code}: {resp.text[:200]}")
                    return None
            except Exception as e:
                if attempt < self.max_retries - 1:
                    print(f"  [LLM] 重试 {attempt+1}/{self.max_retries}: {e}")
                    time.sleep(2 * (attempt + 1))
                else:
                    return None
        return None

    def check_available(self) -> bool:
        """快速检测LLM是否可用"""
        if self._available is not None:
            return self._available
        try:
            import requests
            url = f"{self.api_url}/models"
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            proxies = {"http": None, "https": None}
            resp = requests.get(url, headers=headers, timeout=5, proxies=proxies)
            self._available = resp.status_code == 200
        except Exception:
            self._available = False
        return self._available


class VisualNovelGenerator:
    """视觉小说游戏生成器 - 充分利用分析结果中的所有数据，支持LLM分支剧情"""

    def __init__(self, output_dir: str = "./generated_games"):
        self.output_dir = Path(output_dir)
        self.llm: Optional[_LLMClient] = None
        self.prompts_dir = Path(__file__).parent.parent.parent / "prompts"
        self._branch_prompt: Optional[str] = None

    # ──────────────────────────── 主入口 ────────────────────────────
    def generate(self, analysis_file: str, output_name: Optional[str] = None,
                 use_llm: bool = True) -> str:
        """生成完整的视觉小说项目"""
        analysis = self._load_analysis(analysis_file)
        # 用源文件名做目录名，而不是世界名
        game_name = output_name or self._derive_name(analysis, analysis_file)
        project_path = self.output_dir / game_name

        print(f"[VN] 生成视觉小说: {game_name}")

        # 初始化LLM客户端（用于分支剧情生成）
        self.llm = _LLMClient()
        llm_ok = use_llm and self.llm.check_available()
        if llm_ok:
            print(f"[VN] LLM可用 ({self.llm.api_url})，将使用LLM生成分支剧情")
            self._branch_prompt = self._load_branch_prompt()
        else:
            print(f"[VN] LLM不可用，使用模板生成分支（回退模式）")

        analysis_data = analysis.get("analysis", analysis)
        recommended = analysis.get("recommended_types", [])
        vn_features = self._extract_vn_features(recommended)

        self._create_dirs(project_path)
        story = self._build_story(analysis_data, vn_features)
        characters = self._build_characters(analysis_data)
        relationships = self._build_relationships(analysis_data)
        endings = self._build_endings(analysis_data, story)
        knowledge = self._build_knowledge(analysis_data)

        self._write_project_godot(project_path, analysis_data)
        self._write_data(project_path, story, characters, relationships, endings, knowledge, analysis_data)
        self._write_scenes(project_path)
        self._write_scripts(project_path, story, characters, endings, analysis_data)

        print(f"[VN] OK 生成完成: {project_path}")
        return str(project_path)

    # ──────────────────────────── LLM分支生成 ────────────────────────────
    def _load_branch_prompt(self) -> str:
        """加载分支生成提示词"""
        prompt_file = self.prompts_dir / "vn_branches.txt"
        if prompt_file.exists():
            return prompt_file.read_text(encoding="utf-8")
        return ""

    def _generate_branches_with_llm(self, event: Dict, world: Dict,
                                     characters: List[Dict], conflicts: List[Dict],
                                     relationships: List[Dict],
                                     prev_event: Optional[Dict],
                                     next_event: Optional[Dict],
                                     event_idx: int) -> Optional[Dict]:
        """
        调用LLM为单个事件生成分支选择和alternative path。

        返回:
            {
                "common_lines": [...],   # 章节公共旁白（可能由LLM重写）
                "choices": [
                    {
                        "id": "...",
                        "text": "...",
                        "sub_text": "...",
                        "branch_lines": [...],  # 选择后的不同剧情
                        "consequences": {...},
                        "ending_hint": "good|normal|bad|none"
                    }
                ]
            }
            如果LLM不可用或失败，返回None。
        """
        if not self.llm or not self.llm.check_available() or not self._branch_prompt:
            return None

        # 构建角色信息摘要
        event_chars = event.get("characters", [])
        char_map = {c.get("name", ""): c for c in characters}
        chars_info = []
        for name in event_chars:
            c = char_map.get(name)
            if c:
                traits = ", ".join(c.get("traits", []))
                goal = c.get("goal", "")
                chars_info.append(f"- {name}（{c.get('role', '')}）：特征[{traits}]，目标：{goal}")
        chars_text = "\n".join(chars_info) if chars_info else "无特定角色"

        # 冲突信息
        conflicts_text = "\n".join(
            f"- {c.get('type', '')}：{c.get('description', '')}" for c in conflicts
        ) if conflicts else "无明确冲突"

        # 关系信息（只取涉及的角色）
        relevant_rels = [
            r for r in relationships
            if r.get("from") in event_chars or r.get("to") in event_chars
        ]
        rels_text = "\n".join(
            f"- {r.get('from', '')} -> {r.get('to', '')}（{r.get('type', '')}）：{r.get('description', '')}"
            for r in relevant_rels
        ) if relevant_rels else "无直接关系"

        prev_text = f"标题：{prev_event.get('title', '')}，后果：{prev_event.get('consequences', '')}" if prev_event else "无（这是第一个事件）"
        next_text = f"标题：{next_event.get('title', '')}，描述：{next_event.get('description', '')[:100]}" if next_event else "无（这是最后一个事件）"

        # 填充提示词模板
        prompt = self._branch_prompt.format(
            world=json.dumps(world, ensure_ascii=False),
            event=json.dumps(event, ensure_ascii=False),
            characters_info=chars_text,
            conflicts=conflicts_text,
            relationships=rels_text,
            prev_event=prev_text,
            next_event=next_text,
        )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"请为事件「{event.get('title', '')}」生成分支选择和不同剧情走向。"}
        ]

        print(f"  [LLM] 生成分支: {event.get('title', f'event_{event_idx}')}")

        max_retries = self.llm.max_retries if self.llm else 3
        for attempt in range(max_retries):
            if attempt > 0:
                wait = 2 * attempt
                print(f"  [LLM] 第{attempt+1}次尝试（等待{wait}秒）...")
                time.sleep(wait)

            # ── 发送请求 ──
            try:
                response = self.llm.chat_completion(messages)
            except Exception as e:
                print(f"  [LLM] 请求异常: {e}")
                continue

            if not response or not response.get("choices"):
                print(f"  [LLM] 无响应（尝试 {attempt+1}/{max_retries}）")
                continue

            content = response["choices"][0]["message"]["content"]
            parsed = self._parse_llm_json(content)

            if not parsed or not isinstance(parsed, dict):
                print(f"  [LLM] JSON解析失败（尝试 {attempt+1}/{max_retries}）")
                continue

            # ── 验证结构 ──
            choices = parsed.get("choices", [])
            if not isinstance(choices, list) or len(choices) < 2:
                print(f"  [LLM] 选择数量不足（{len(choices) if isinstance(choices, list) else 0}，需要2-3个）（尝试 {attempt+1}/{max_retries}）")
                continue

            validated_choices = []
            validation_errors = []
            for i, ch in enumerate(choices):
                if not isinstance(ch, dict):
                    validation_errors.append(f"选择{i}不是对象")
                    continue

                # 校验 id
                ch_id = ch.get("id", f"llm_choice_{event_idx}_{i}")
                if not isinstance(ch_id, str) or not ch_id.strip():
                    ch_id = f"llm_choice_{event_idx}_{i}"

                # 校验 text
                ch_text = ch.get("text", "")
                if not isinstance(ch_text, str) or not ch_text.strip():
                    validation_errors.append(f"选择{i}缺少text")
                    continue
                if len(ch_text) > 20:
                    # 截断而非拒绝，但要记录
                    ch_text = ch_text[:12]

                # 校验 sub_text
                ch_sub = ch.get("sub_text", "")
                if not isinstance(ch_sub, str):
                    ch_sub = ""

                # 校验 branch_lines
                branch_lines = ch.get("branch_lines", [])
                if not isinstance(branch_lines, list) or len(branch_lines) < 3:
                    validation_errors.append(
                        f"选择{i}({ch_id}) branch_lines不足3条"
                        f"（实际{len(branch_lines) if isinstance(branch_lines, list) else 0}条）")
                    continue

                # 验证 branch_lines 中每条的 speaker 和 text
                valid_lines = []
                for bl in branch_lines:
                    if not isinstance(bl, dict):
                        continue
                    sp = bl.get("speaker", "narrator")
                    txt = bl.get("text", "")
                    if not isinstance(txt, str) or not txt.strip():
                        continue
                    valid_lines.append({"speaker": sp, "text": txt})
                if len(valid_lines) < 3:
                    validation_errors.append(f"选择{i}({ch_id}) 有效branch_lines不足3条")
                    continue

                # 校验 consequences
                consequences = ch.get("consequences", {})
                if not isinstance(consequences, dict):
                    consequences = {}
                if "flags" not in consequences or not isinstance(consequences.get("flags"), dict):
                    consequences["flags"] = {}
                if "relationship_changes" not in consequences or not isinstance(consequences.get("relationship_changes"), dict):
                    consequences["relationship_changes"] = {}
                consequences["flags"][ch_id] = True

                # 校验 ending_hint
                eh = ch.get("ending_hint", "none")
                if eh not in ("good", "normal", "bad", "none"):
                    eh = "none"

                validated_choices.append({
                    "id": ch_id,
                    "text": ch_text,
                    "sub_text": ch_sub,
                    "branch_lines": valid_lines,
                    "consequences": consequences,
                    "ending_hint": eh,
                })

            # 校验选择数量（经过验证后）
            if len(validated_choices) < 2:
                errs = "; ".join(validation_errors)
                print(f"  [LLM] 验证失败（尝试 {attempt+1}/{max_retries}）: {errs}")
                continue

            # 校验至少一个 ending_hint != "none"
            has_meaningful_hint = any(c["ending_hint"] != "none" for c in validated_choices)
            if not has_meaningful_hint:
                print(f"  [LLM] 所有选择的ending_hint均为none（尝试 {attempt+1}/{max_retries}）")
                # 不强制重试，但给个警告
                # （降级为可接受）

            common_lines = parsed.get("common_lines", [])
            if not isinstance(common_lines, list):
                common_lines = []

            print(f"  [LLM] OK 生成了 {len(validated_choices)} 个分支选择")
            return {
                "common_lines": common_lines,
                "choices": validated_choices[:3],  # 最多3个
            }

        # 所有重试都失败
        print(f"  [LLM] {max_retries}次尝试均失败，回退到模板模式")
        return None

    @staticmethod
    def _parse_llm_json(content: str) -> Optional[Dict]:
        """解析LLM返回的JSON（带容错）"""
        content = content.strip()
        # 移除markdown代码块
        if content.startswith("```"):
            lines = content.split("\n", 1)
            content = lines[1] if len(lines) > 1 else content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # 直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 提取JSON对象
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(content[start:end])
            except json.JSONDecodeError:
                pass

        return None

    # ──────────────────────────── 数据加载 ────────────────────────────
    def _load_analysis(self, path: str) -> Dict:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"分析文件不存在: {path}")
        return json.loads(p.read_text(encoding="utf-8"))

    def _derive_name(self, analysis: Dict, analysis_file: str = "") -> str:
        # 优先用源文件名
        if analysis_file:
            src = analysis.get("source_file", analysis_file)
            stem = Path(src).stem
            # 清理文件名
            name = "".join(c for c in stem if c.isalnum() or c in "_- ")
            if name:
                return name + "_vn"
        # fallback: 世界名
        data = analysis.get("analysis", analysis)
        name = data.get("world", {}).get("name", "VisualNovel")
        name = "".join(c for c in name if c.isalnum() or c in "_- ")
        return (name or "VisualNovel") + "_vn"

    def _extract_vn_features(self, recommended: List[Dict]) -> List[str]:
        for r in recommended:
            if r.get("type") == "visual_novel":
                return r.get("features", [])
        return ["分支剧情", "角色对话", "多结局"]

    # ──────────────────────────── 目录结构 ────────────────────────────
    def _create_dirs(self, project_path: Path) -> None:
        for d in ["", "scenes", "scripts", "data", "resources/fonts",
                   "resources/images", "resources/music", "resources/sounds"]:
            (project_path / d).mkdir(parents=True, exist_ok=True)

    # ══════════════════════════════════════════════════════════════════
    #  数据构建 - 从分析结果中提取并组织游戏数据
    # ══════════════════════════════════════════════════════════════════

    def _build_story(self, analysis: Dict, vn_features: List[str]) -> Dict:
        """
        将分析结果中的 events 转化为视觉小说的故事结构。

        story = {
            "title": str,
            "prologue": {...},      # 序章
            "chapters": [{...}],    # 每个 event → 一个 chapter
            "epilogue": {...},      # 尾声（根据结局分支）
        }
        """
        world = analysis.get("world", {})
        events = analysis.get("events", [])
        characters = analysis.get("characters", [])
        conflicts = analysis.get("conflicts", [])
        themes = analysis.get("themes", [])
        atmosphere = analysis.get("atmosphere", "")

        # ── 序章 ──
        prologue = {
            "id": "prologue",
            "title": world.get("name", "序章"),
            "description": world.get("description", ""),
            "atmosphere": atmosphere,
            "lines": self._generate_prologue_lines(world, characters, atmosphere),
            "choices": []
        }

        # ── 章节：每个 event → 一个 chapter ──
        chapters = []
        for i, event in enumerate(events):
            event_title = event.get("title", f"第{i+1}章")
            event_desc = event.get("description", "")
            event_chars = event.get("characters", [])
            event_consequences = event.get("consequences", "")
            order = event.get("order", i + 1)

            chapter = {
                "id": f"chapter_{order:02d}",
                "order": order,
                "title": event_title,
                "event_title": event_title,
                "atmosphere": atmosphere,
                "lines": [],
                "choices": [],
                "has_branches": False,
                "knowledge_triggers": []
            }

            # 尝试用LLM生成分支剧情
            prev_event = events[i - 1] if i > 0 else None
            next_event = events[i + 1] if i < len(events) - 1 else None
            llm_branches = self._generate_branches_with_llm(
                event, world, characters, conflicts,
                analysis.get("relationships", []),
                prev_event, next_event, i
            )

            if llm_branches and llm_branches.get("choices"):
                # 使用LLM生成的分支
                chapter["has_branches"] = True
                # 生成基础旁白行（事件描述）
                base_lines = self._generate_chapter_lines(
                    event, characters, world, atmosphere, i, events
                )
                # 如果LLM提供了common_lines，追加到基础行后面
                common_lines = llm_branches.get("common_lines", [])
                if common_lines:
                    chapter["lines"] = base_lines + common_lines
                else:
                    chapter["lines"] = base_lines
                chapter["choices"] = llm_branches["choices"]
                print(f"  [VN] 章节 {order} 使用LLM分支 ({len(chapter['choices'])} 个选择)")
            else:
                # 回退到模板生成
                chapter["lines"] = self._generate_chapter_lines(
                    event, characters, world, atmosphere, i, events
                )
                chapter["choices"] = self._generate_chapter_choices(
                    event, conflicts, analysis.get("relationships", []),
                    characters, i, events
                )
                # 为模板选择添加空的branch_lines（后续用consequences行作为branch）
                for ch in chapter["choices"]:
                    if "branch_lines" not in ch:
                        ch["branch_lines"] = [
                            {"speaker": "narrator", "text": ch.get("sub_text", ch.get("text", ""))}
                        ]
                    if "ending_hint" not in ch:
                        ch["ending_hint"] = "none"
                print(f"  [VN] 章节 {order} 使用模板分支 ({len(chapter['choices'])} 个选择)")

            # 知识碎片触发
            chapter["knowledge_triggers"] = self._generate_knowledge_triggers(
                event, world, characters, themes
            )

            chapters.append(chapter)

        # ── 尾声 ──
        epilogue = {
            "id": "epilogue",
            "title": "尾声",
            "atmosphere": atmosphere,
            "lines": [],
            "choices": []
        }

        story = {
            "title": world.get("name", "视觉小说"),
            "description": world.get("description", ""),
            "themes": themes,
            "atmosphere": atmosphere,
            "prologue": prologue,
            "chapters": chapters,
            "epilogue": epilogue
        }
        return story

    def _generate_prologue_lines(self, world: Dict, characters: List[Dict],
                                  atmosphere: str) -> List[Dict]:
        """生成序章的对话行"""
        lines = []
        era = world.get("era", "")
        location = world.get("location", "")
        rules = world.get("rules", "")
        desc = world.get("description", "")

        # 氛围渲染
        if atmosphere:
            lines.append({"speaker": "narrator", "text": atmosphere, "effect": "fade_in"})
        if era:
            lines.append({"speaker": "narrator", "text": f"【时代】{era}"})
        if location:
            lines.append({"speaker": "narrator", "text": f"【地点】{location}"})
        if rules:
            lines.append({"speaker": "narrator", "text": f"【背景】{rules}"})

        # 主角介绍
        main_char = characters[0] if characters else None
        if main_char:
            name = main_char.get("name", "")
            role = main_char.get("role", "")
            if name:
                lines.append({
                    "speaker": "narrator",
                    "text": f"故事的主人公——{name}。"
                })
            if role:
                lines.append({
                    "speaker": "narrator",
                    "text": f"他/她的身份：{role}。"
                })

        # 过渡到正文
        lines.append({"speaker": "narrator", "text": "故事，从这里开始……", "effect": "fade_out"})

        return lines

    def _generate_chapter_lines(self, event: Dict, characters: List[Dict],
                                 world: Dict, atmosphere: str,
                                 event_idx: int, all_events: List[Dict]) -> List[Dict]:
        """
        根据单个事件生成该章节的对话行。

        策略：
        1. 事件标题作为章节标题
        2. 事件描述拆分为旁白行
        3. 涉及角色的台词从角色背景/目标衍生
        4. 事件后果作为过渡
        """
        lines = []
        title = event.get("title", "")
        desc = event.get("description", "")
        event_chars = event.get("characters", [])
        consequences = event.get("consequences", "")

        # 章节标题卡
        lines.append({"speaker": "narrator", "text": f"━━ {title} ━━", "effect": "chapter_title"})

        # 将描述拆分为段落，作为旁白
        desc_paragraphs = self._split_into_paragraphs(desc)
        for para in desc_paragraphs:
            lines.append({"speaker": "narrator", "text": para})

        # 为涉及的角色生成台词（最多3个角色）
        char_map = {c.get("name", ""): c for c in characters}
        shown_chars = 0
        for char_name in event_chars:
            if shown_chars >= 3:  # 限制每章最多3个角色发言
                break
            char_data = char_map.get(char_name)
            if char_data:
                dialogue = self._generate_character_dialogue(
                    char_data, event, atmosphere, shown_chars
                )
                if dialogue:
                    lines.append(dialogue)
                    shown_chars += 1

        # 后果过渡
        if consequences:
            lines.append({"speaker": "narrator", "text": f"——{consequences}"})

        return lines

    def _generate_character_dialogue(self, char: Dict, event: Dict,
                                      atmosphere: str, char_index: int = 0) -> Optional[Dict]:
        """根据角色数据和事件上下文生成台词"""
        name = char.get("name", "")
        traits = char.get("traits", [])
        background = char.get("background", "")
        goal = char.get("goal", "")
        event_title = event.get("title", "")
        event_desc = event.get("description", "")

        if not name:
            return None

        text = self._build_dialogue_text(name, traits, goal, event_title, event_desc, char_index)
        if text:
            return {"speaker": name, "text": text}

        return None

    def _build_dialogue_text(self, name: str, traits: List[str],
                              goal: str, event_title: str, event_desc: str,
                              char_index: int = 0) -> str:
        """根据上下文构建角色台词"""
        # 基于事件类型的台词模板（每个事件有多条，按 char_index 选取）
        event_templates = {
            "买车": ["这车，是我用血汗换来的。", "有了自己的车，日子总算有了盼头。"],
            "被抢": ["我的车……就这么没了？", "这世道，穷人连一辆车都保不住。"],
            "卖骆驼": ["三匹骆驼，换三十五块钱……", "骆驼祥子……这名字倒也贴切。"],
            "引诱": ["我不该……但又有什么办法。", "哼，你以为你能跑得掉？"],
            "逼婚": ["她说怀孕了……我该怎么办？", "这婚姻，不过是一场交易罢了。"],
            "结婚": ["就这样，我成了她的丈夫。", "从今往后，你就是我的人了。"],
            "难产": ["她走了……孩子也没了。", "又一辆车，没了。"],
            "自杀": ["小福子……你怎么就这么走了？", "这世界，已经没有值得留恋的了。"],
            "堕落": ["我已经不是从前的我了。", "拉车？骗钱？都一样。"],
            "敲诈": ["我的钱……全被他抢走了。", "把钱交出来，饶你一命。"],
            "决裂": ["从今往后，我和刘家再无瓜葛。", "这父女情分，算是断了。"],
            "死亡": ["她的死，让我彻底看清了这世道。", "一切，都结束了。"],
            "杨宅": ["这家人，简直不把人当人看。", "再干下去，我怕是要死在这里。"],
            "曹宅": ["曹先生是好人，对我客气。", "在这里拉包月，总算能喘口气。"],
            "摔伤": ["是我不好，把先生摔了……", "没事，人没事就好。"],
            "小茶馆": ["这老车夫……就是将来的我啊。", "给，买几个包子吃吧。"],
            "投靠": ["我无处可去，只能回来了。", "你倒是回来了，还知道回来？"],
            "生日": ["刘四爷，您不能这样对我！", "滚！都给我滚！"],
            "夏太太": ["来，陪我喝一杯……", "这女人……我染上了脏病。"],
            "巧遇": ["刘四爷？您……您还记得我吗？", "祥子？虎妞她……她死了。"],
            "出卖": ["六十块钱……值得。", "阮明，你别怪我……"],
        }

        # 根据事件标题匹配模板
        for key, templates in event_templates.items():
            if key in event_title:
                idx = char_index % len(templates)
                return templates[idx]

        # 根据角色特征生成通用台词
        trait_dialogues = {
            "强壮": "我有的是力气，总能活下去。",
            "沉默要强": "……",
            "堕落自私": "管不了那么多了，先活下去再说。",
            "泼辣": "你以为我好欺负？",
            "心机深沉": "哼，一切都在我的掌控之中。",
            "强悍": "这事儿，我说了算。",
            "精明霸道": "老子这辈子，什么场面没见过？",
            "好面子": "这事儿传出去，我刘四爷的脸往哪搁？",
            "重利轻义": "钱到手了，其他的都是次要的。",
            "凶狠狡诈": "想跑？没那么容易。",
            "贪婪冷酷": "把钱交出来，饶你一命。",
            "仗势欺人": "我背后可有人，你最好识相点。",
            "善良": "我会尽力帮助你的。",
            "坚韧": "再苦再难，也要撑下去。",
            "牺牲": "只要弟弟能活下去，我怎样都行。",
            "酗酒": "再给我来一壶……",
            "暴戾": "滚！别来烦我！",
            "放荡": "人生苦短，及时行乐嘛。",
            "年轻": "你还年轻，不懂这些。",
            "虚荣": "你看我这身衣服，好看吗？",
        }

        # 选取第一个特征
        if traits:
            for trait in traits:
                if trait in trait_dialogues:
                    return trait_dialogues[trait]

        # 最终 fallback：使用目标
        if goal:
            return goal

        return "……"

    def _generate_chapter_choices(self, event: Dict, conflicts: List[Dict],
                                   relationships: List[Dict], characters: List[Dict],
                                   event_idx: int, all_events: List[Dict]) -> List[Dict]:
        """
        根据事件生成有针对性的选择支。
        每个事件都有独特的选择，反映该事件的核心冲突。
        """
        choices = []
        event_title = event.get("title", "")
        event_chars = event.get("characters", [])
        order = event.get("order", event_idx + 1)

        # 基于事件的定制选择模板
        event_choices = {
            "祥子买车": [
                {"id": "buy_car_hope", "text": "满怀希望，继续攒钱买车", "sub_text": "相信只要努力，总有一天能拥有自己的车", "consequences": {"flags": {"hopeful": True}}},
                {"id": "buy_car_doubt", "text": "心存疑虑，这世道能安稳吗？", "sub_text": "兵荒马乱，买来的车能保多久？", "consequences": {"flags": {"doubtful": True}}},
            ],
            "车被兵抢": [
                {"id": "robbed_anger", "text": "愤怒，想要追回自己的车", "sub_text": "那是我三年的血汗！", "consequences": {"flags": {"anger": True}, "relationship_changes": {"祥子_willpower": 1}}},
                {"id": "robbed_escape", "text": "先逃命要紧，保命为上", "sub_text": "车没了还能再买，命没了就什么都没了", "consequences": {"flags": {"survival": True}}},
            ],
            "虎妞引诱": [
                {"id": "seduce_resist", "text": "试图拒绝，但已经太迟了", "sub_text": "我不该喝那么多酒……", "consequences": {"flags": {"resisted": True}, "relationship_changes": {"祥子_虎妞": -1}}},
                {"id": "seduce_submit", "text": "半推半就，顺从了事", "sub_text": "也许……这就是命吧", "consequences": {"flags": {"submitted": True}, "relationship_changes": {"祥子_虎妞": 1}}},
            ],
            "虎妞诈孕逼婚": [
                {"id": "trick_marry", "text": "无奈答应结婚", "sub_text": "她说怀孕了，我不能不负责任", "consequences": {"flags": {"married": True}, "relationship_changes": {"祥子_虎妞": 1}}},
                {"id": "trick_refuse", "text": "坚决拒绝，哪怕她去告官", "sub_text": "我不信她真的怀孕了", "consequences": {"flags": {"refused": True}, "relationship_changes": {"祥子_虎妞": -2}}},
            ],
            "孙侦探敲诈": [
                {"id": "blackmail_give", "text": "把钱都给他，保命要紧", "sub_text": "钱没了可以再挣，命没了就什么都没了", "consequences": {"flags": {"gave_money": True}}},
                {"id": "blackmail_resist", "text": "拼死抵抗，不愿交出积蓄", "sub_text": "这是我攒了多久的钱啊！", "consequences": {"flags": {"resisted_detective": True}}},
            ],
            "刘四爷生日决裂": [
                {"id": "split_with_father", "text": "支持虎妞与父亲决裂", "sub_text": "虎妞是为了我才和刘四爷闹翻的", "consequences": {"flags": {"supported_huniu": True}, "relationship_changes": {"祥子_虎妞": 2, "祥子_刘四爷": -2}}},
                {"id": "split_against", "text": "劝虎妞和父亲和好", "sub_text": "父女之间，何必闹成这样？", "consequences": {"flags": {"mediated": True}, "relationship_changes": {"祥子_虎妞": -1, "祥子_刘四爷": 1}}},
            ],
            "祥子与虎妞结婚": [
                {"id": "marry_accept", "text": "接受命运，好好过日子", "sub_text": "既然已经结婚了，就好好生活吧", "consequences": {"flags": {"accepted_marriage": True}}},
                {"id": "marry_rebel", "text": "内心抗拒，但表面顺从", "sub_text": "这只是交易，不是爱情", "consequences": {"flags": {"rebelled_inner": True}}},
            ],
            "小福子表白与祥子离开": [
                {"id": "leave_regret", "text": "含泪离开，无力承担她的家庭", "sub_text": "我养不起你和你的弟弟们……", "consequences": {"flags": {"left_fuzi": True, "love_broken": True}, "relationship_changes": {"祥子_小福子": -2}}},
                {"id": "stay_sacrifice", "text": "留下，和她一起面对困难", "sub_text": "我不能丢下你不管", "consequences": {"flags": {"stayed_fuzi": True}, "relationship_changes": {"祥子_小福子": 3}}},
            ],
            "祥子出卖阮明": [
                {"id": "betray_money", "text": "为了六十块钱出卖他", "sub_text": "六十块钱……够我活一阵子了", "consequences": {"flags": {"betrayed": True, "堕落": True}}},
                {"id": "betray_refuse", "text": "拒绝出卖，宁可挨饿", "sub_text": "这种事，我做不出来", "consequences": {"flags": {"refused_betray": True}, "relationship_changes": {"祥子_moral": 2}}},
            ],
        }

        # 尝试匹配事件模板
        for key, template_choices in event_choices.items():
            if key in event_title:
                return template_choices

        # 通用选择：基于冲突
        for conflict in conflicts:
            conflict_type = conflict.get("type", "")
            conflict_desc = conflict.get("description", "")
            if any(char in conflict_desc for char in event_chars):
                choices.append({
                    "id": f"conflict_{order}",
                    "text": f"面对「{conflict_type}」的困境，你的选择是？",
                    "sub_text": conflict_desc[:80] + "..." if len(conflict_desc) > 80 else conflict_desc,
                    "consequences": {
                        "relationship_changes": self._calc_conflict_effects(conflict, event_chars),
                        "flags": {f"conflict_{conflict_type}": True}
                    }
                })
                break

        # 通用选择：基于关系
        if not choices:
            relevant_rels = [r for r in relationships
                            if r.get("from") in event_chars or r.get("to") in event_chars]
            if relevant_rels:
                rel = relevant_rels[0]
                from_char = rel.get("from", "")
                to_char = rel.get("to", "")
                rel_type = rel.get("type", "")
                choices.append({
                    "id": f"rel_{order}",
                    "text": f"关于{from_char}与{to_char}的关系（{rel_type}）",
                    "sub_text": rel.get("description", "")[:80],
                    "consequences": {
                        "relationship_changes": {f"{from_char}_{to_char}": 1},
                        "flags": {f"rel_{from_char}_{to_char}": True}
                    }
                })

        # 兜底：继续前进
        if not choices:
            choices.append({
                "id": f"narrative_{order}",
                "text": "继续前行",
                "sub_text": "故事继续发展……",
                "consequences": {"flags": {f"chapter_{order}_completed": True}}
            })

        return choices[:3]

    def _calc_conflict_effects(self, conflict: Dict, event_chars: List[str]) -> Dict:
        """计算冲突选择的关系影响"""
        effects = {}
        conflict_type = conflict.get("type", "")
        # 根据冲突类型给予不同的关系变化
        if "个人" in conflict_type or "社会" in conflict_type:
            for char in event_chars:
                effects[f"{char}_willpower"] = 1  # 意志力
        elif "爱情" in conflict_type or "婚姻" in conflict_type:
            for i, char in enumerate(event_chars):
                if i == 0:
                    effects[f"{char}_love"] = 1
                elif i == 1:
                    effects[f"{event_chars[0]}_{char}"] = 1
        elif "阶级" in conflict_type:
            for char in event_chars:
                effects[f"{char}_reputation"] = -1  # 声望降低
        return effects

    def _generate_knowledge_triggers(self, event: Dict, world: Dict,
                                      characters: List[Dict], themes: List[str]) -> List[Dict]:
        """生成知识碎片触发器"""
        triggers = []
        event_title = event.get("title", "")

        # 世界观知识
        if world.get("rules"):
            triggers.append({
                "type": "world_knowledge",
                "title": f"关于{world.get('name', '这个世界')}",
                "content": world["rules"][:200]
            })

        # 角色背景知识（如果事件涉及新角色首次出现）
        event_chars = event.get("characters", [])
        for char_name in event_chars:
            char = next((c for c in characters if c.get("name") == char_name), None)
            if char and char.get("background"):
                triggers.append({
                    "type": "character_knowledge",
                    "title": f"关于{char_name}",
                    "content": char["background"][:200]
                })

        return triggers

    # ──────────────────────────── 角色数据 ────────────────────────────
    def _build_characters(self, analysis: Dict) -> Dict:
        """构建角色数据（用于游戏内显示）"""
        chars = analysis.get("characters", [])
        result = {}
        for char in chars:
            name = char.get("name", "")
            if not name:
                continue
            result[name] = {
                "name": name,
                "role": char.get("role", ""),
                "traits": char.get("traits", []),
                "background": char.get("background", ""),
                "goal": char.get("goal", ""),
                "color": self._assign_speaker_color(name, len(result))
            }
        return result

    def _assign_speaker_color(self, name: str, idx: int) -> str:
        """为角色分配说话颜色"""
        colors = [
            "#E8B4B8", "#B4D4E8", "#B8E8B4", "#E8D4B4",
            "#D4B4E8", "#B4E8D4", "#E8E8B4", "#B4B4E8"
        ]
        return colors[idx % len(colors)]

    # ──────────────────────────── 关系数据 ────────────────────────────
    def _build_relationships(self, analysis: Dict) -> Dict:
        """构建关系数据"""
        rels = analysis.get("relationships", [])
        result = {}
        for rel in rels:
            key = f"{rel.get('from', '')}_{rel.get('to', '')}"
            result[key] = {
                "from": rel.get("from", ""),
                "to": rel.get("to", ""),
                "type": rel.get("type", ""),
                "description": rel.get("description", ""),
                "value": 0  # 初始关系值
            }
        return result

    # ──────────────────────────── 结局数据 ────────────────────────────
    def _build_endings(self, analysis: Dict, story: Dict) -> Dict:
        """
        基于分析结果构建多结局系统。

        结局由以下因素决定：
        1. 关系值累计
        2. 选择标志
        3. 事件完成度
        """
        characters = analysis.get("characters", {})
        if isinstance(characters, dict):
            characters = list(characters.values())

        # 主角
        main_char = characters[0].get("name", "主角") if characters else "主角"

        endings = {
            "bad": {
                "id": "bad",
                "title": "堕落结局",
                "description": f"{main_char}在命运的捉弄下，最终失去了所有希望……",
                "lines": [
                    {"speaker": "narrator", "text": "═══ 堕落结局 ═══", "effect": "ending_title"},
                    {"speaker": "narrator", "text": f"在这片{analysis.get('world', {}).get('name', '世界')}的大地上，{main_char}的故事走向了最黑暗的终点。"},
                    {"speaker": "narrator", "text": analysis.get("themes", ["命运无常"])[0] if analysis.get("themes") else "命运无常"},
                    {"speaker": "narrator", "text": "一切都结束了。"}
                ]
            },
            "normal": {
                "id": "normal",
                "title": "平凡结局",
                "description": f"{main_char}虽然未能改变命运，但至少保住了最后的尊严。",
                "lines": [
                    {"speaker": "narrator", "text": "═══ 平凡结局 ═══", "effect": "ending_title"},
                    {"speaker": "narrator", "text": f"{main_char}在这乱世中艰难地活着。"},
                    {"speaker": "narrator", "text": "没有轰轰烈烈，没有功成名就。"},
                    {"speaker": "narrator", "text": "但至少，还有呼吸。"}
                ]
            },
            "good": {
                "id": "good",
                "title": "希望结局",
                "description": f"{main_char}在绝望中找到了一丝光明。",
                "lines": [
                    {"speaker": "narrator", "text": "═══ 希望结局 ═══", "effect": "ending_title"},
                    {"speaker": "narrator", "text": f"经历了无数磨难，{main_char}终于看到了一丝曙光。"},
                    {"speaker": "narrator", "text": "虽然世界依然残酷，但内心深处的火焰并未完全熄灭。"},
                    {"speaker": "narrator", "text": "也许，明天会更好。"}
                ]
            }
        }
        return endings

    # ──────────────────────────── 知识碎片 ────────────────────────────
    def _build_knowledge(self, analysis: Dict) -> List[Dict]:
        """构建知识碎片（社会背景、文化信息）"""
        knowledge = []
        world = analysis.get("world", {})
        themes = analysis.get("themes", [])

        # 世界观知识
        if world.get("description"):
            knowledge.append({
                "id": "world_overview",
                "type": "world",
                "title": f"关于{world.get('name', '这个世界')}",
                "content": world["description"],
                "unlock_condition": "prologue"
            })
        if world.get("rules"):
            knowledge.append({
                "id": "world_rules",
                "type": "world",
                "title": "世界法则",
                "content": world["rules"],
                "unlock_condition": "prologue"
            })

        # 主题知识
        for i, theme in enumerate(themes):
            knowledge.append({
                "id": f"theme_{i}",
                "type": "theme",
                "title": f"主题：{theme}",
                "content": theme,
                "unlock_condition": f"chapter_{(i+1)*7:02d}"  # 每7章解锁一个主题
            })

        # 角色知识
        characters = analysis.get("characters", [])
        for i, char in enumerate(characters):
            if char.get("background"):
                knowledge.append({
                    "id": f"char_{char.get('name', i)}",
                    "type": "character",
                    "title": f"{char.get('name', '角色')}的过往",
                    "content": char["background"][:300],
                    "unlock_condition": f"chapter_{(i+1)*2:02d}"
                })

        return knowledge

    # ══════════════════════════════════════════════════════════════════
    #  Godot 项目生成
    # ══════════════════════════════════════════════════════════════════

    def _write_project_godot(self, project_path: Path, analysis: Dict) -> None:
        title = analysis.get("world", {}).get("name", "Visual Novel")
        content = f'''; Engine configuration file.
; Generated by Text2Game Visual Novel Generator

config_version=5

[application]

config/name="{title}"
config/description="基于「{title}」生成的视觉小说"
run/main_scene="res://scenes/main_menu.tscn"
config/features=PackedStringArray("4.7", "GL Compatibility")

[display]

window/size/viewport_width=1280
window/size/viewport_height=720
window/stretch/mode="canvas_items"

[rendering]

renderer/rendering_method="gl_compatibility"
renderer/rendering_method.mobile="gl_compatibility"
'''
        (project_path / "project.godot").write_text(content, encoding="utf-8")

    # ──────────────────────────── 场景文件 ────────────────────────────
    def _write_scenes(self, project_path: Path) -> None:
        self._write_main_menu_scene(project_path)
        self._write_game_scene(project_path)

    def _write_main_menu_scene(self, project_path: Path) -> None:
        content = '''[gd_scene load_steps=2 format=3 uid="uid://main_menu"]

[ext_resource type="Script" path="res://scripts/main_menu.gd" id="1_script"]

[node name="MainMenu" type="Control"]
layout_mode = 3
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2
script = ExtResource("1_script")

[node name="Background" type="ColorRect" parent="."]
layout_mode = 1
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
color = Color(0.05, 0.05, 0.08, 1)

[node name="CenterContainer" type="CenterContainer" parent="."]
layout_mode = 1
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0

[node name="VBox" type="VBoxContainer" parent="CenterContainer"]
layout_mode = 2

[node name="Title" type="Label" parent="CenterContainer/VBox"]
layout_mode = 2
text = "视觉小说"
horizontal_alignment = 1
theme_override_font_sizes/font_size = 48

[node name="Subtitle" type="Label" parent="CenterContainer/VBox"]
layout_mode = 2
text = "基于文本分析自动生成"
horizontal_alignment = 1
theme_override_font_sizes/font_size = 18
theme_override_colors/font_color = Color(0.6, 0.6, 0.7, 1)

[node name="Spacer" type="Control" parent="CenterContainer/VBox"]
layout_mode = 2
custom_minimum_size = Vector2(0, 40)

[node name="StartButton" type="Button" parent="CenterContainer/VBox"]
layout_mode = 2
custom_minimum_size = Vector2(240, 50)
text = "开始故事"
theme_override_font_sizes/font_size = 20

[node name="SettingsButton" type="Button" parent="CenterContainer/VBox"]
layout_mode = 2
custom_minimum_size = Vector2(240, 50)
text = "游戏设置"
theme_override_font_sizes/font_size = 20
'''
        (project_path / "scenes" / "main_menu.tscn").write_text(content, encoding="utf-8")

    def _write_game_scene(self, project_path: Path) -> None:
        content = '''[gd_scene load_steps=2 format=3 uid="uid://game_scene"]

[ext_resource type="Script" path="res://scripts/game_scene.gd" id="1_script"]

[node name="Game" type="Control"]
layout_mode = 3
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2
script = ExtResource("1_script")

[node name="Background" type="ColorRect" parent="."]
layout_mode = 1
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
color = Color(0.08, 0.08, 0.12, 1)

[node name="StoryArea" type="VBoxContainer" parent="."]
layout_mode = 1
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
offset_left = 60.0
offset_top = 40.0
offset_right = -60.0
offset_bottom = -40.0

[node name="ChapterTitle" type="Label" parent="StoryArea"]
layout_mode = 2
text = ""
horizontal_alignment = 1
theme_override_font_sizes/font_size = 28
theme_override_colors/font_color = Color(0.9, 0.85, 0.7, 1)
visible = false

[node name="Spacer1" type="Control" parent="StoryArea"]
layout_mode = 2
custom_minimum_size = Vector2(0, 20)
size_flags_vertical = 0

[node name="TextBox" type="PanelContainer" parent="StoryArea"]
layout_mode = 2
size_flags_vertical = 3
custom_minimum_size = Vector2(0, 180)

[node name="MarginContainer" type="MarginContainer" parent="StoryArea/TextBox"]
layout_mode = 2
theme_override_constants/margin_left = 24
theme_override_constants/margin_top = 16
theme_override_constants/margin_right = 24
theme_override_constants/margin_bottom = 16

[node name="VBox" type="VBoxContainer" parent="StoryArea/TextBox/MarginContainer"]
layout_mode = 2

[node name="SpeakerLabel" type="Label" parent="StoryArea/TextBox/MarginContainer/VBox"]
layout_mode = 2
text = ""
theme_override_font_sizes/font_size = 20
theme_override_colors/font_color = Color(0.85, 0.85, 1.0, 1)

[node name="TextLabel" type="RichTextLabel" parent="StoryArea/TextBox/MarginContainer/VBox"]
layout_mode = 2
size_flags_vertical = 3
bbcode_enabled = true
text = ""

[node name="ChoiceContainer" type="VBoxContainer" parent="StoryArea"]
layout_mode = 2
custom_minimum_size = Vector2(0, 100)
size_flags_vertical = 0
visible = false

[node name="ChoiceLabel" type="Label" parent="StoryArea/ChoiceContainer"]
layout_mode = 2
text = "请选择："
theme_override_font_sizes/font_size = 16
theme_override_colors/font_color = Color(0.7, 0.7, 0.8, 1)

[node name="ChoicesVBox" type="VBoxContainer" parent="StoryArea/ChoiceContainer"]
layout_mode = 2

[node name="KnowledgePanel" type="PanelContainer" parent="."]
layout_mode = 1
anchors_preset = 1
anchor_left = 1.0
anchor_right = 1.0
offset_left = -320.0
offset_top = 40.0
offset_right = -20.0
offset_bottom = 300.0
grow_horizontal = 0
visible = false

[node name="MarginContainer" type="MarginContainer" parent="KnowledgePanel"]
layout_mode = 2
theme_override_constants/margin_left = 16
theme_override_constants/margin_top = 12
theme_override_constants/margin_right = 16
theme_override_constants/margin_bottom = 12

[node name="VBox" type="VBoxContainer" parent="KnowledgePanel/MarginContainer"]
layout_mode = 2

[node name="KnowledgeTitle" type="Label" parent="KnowledgePanel/MarginContainer/VBox"]
layout_mode = 2
text = "知识碎片"
theme_override_font_sizes/font_size = 16
theme_override_colors/font_color = Color(0.9, 0.8, 0.6, 1)

[node name="KnowledgeContent" type="RichTextLabel" parent="KnowledgePanel/MarginContainer/VBox"]
layout_mode = 2
size_flags_vertical = 3
bbcode_enabled = true
text = ""

[node name="ClickContinue" type="Label" parent="."]
layout_mode = 1
anchors_preset = 7
anchor_left = 0.5
anchor_top = 1.0
anchor_right = 0.5
anchor_bottom = 1.0
offset_left = -60.0
offset_top = -40.0
offset_right = 60.0
offset_bottom = -16.0
grow_horizontal = 2
grow_vertical = 0
text = "点击继续 ▼"
horizontal_alignment = 1
theme_override_font_sizes/font_size = 14
theme_override_colors/font_color = Color(0.5, 0.5, 0.6, 1)

[node name="TypewriterTimer" type="Timer" parent="."]
wait_time = 0.03
one_shot = false
'''
        (project_path / "scenes" / "game.tscn").write_text(content, encoding="utf-8")

    # ──────────────────────────── 脚本文件 ────────────────────────────
    def _write_scripts(self, project_path: Path, story: Dict,
                       characters: Dict, endings: Dict, analysis: Dict) -> None:
        self._write_main_menu_script(project_path)
        self._write_game_scene_script(project_path, story, characters, endings, analysis)
        self._write_data_manager_script(project_path)

    def _write_main_menu_script(self, project_path: Path) -> None:
        content = '''## 主菜单
extends Control

func _ready() -> void:
    $CenterContainer/VBox/StartButton.pressed.connect(_on_start)
    $CenterContainer/VBox/SettingsButton.pressed.connect(_on_settings)

func _on_start() -> void:
    get_tree().change_scene_to_file("res://scenes/game.tscn")

func _on_settings() -> void:
    pass  # TODO: 设置界面
'''
        (project_path / "scripts" / "main_menu.gd").write_text(content, encoding="utf-8")

    def _write_data_manager_script(self, project_path: Path) -> None:
        content = '''## 数据管理器 - 加载和管理所有游戏数据
extends Node
class_name DataManager

static var _instance: DataManager

var story: Dictionary = {}
var characters: Dictionary = {}
var relationships: Dictionary = {}
var endings: Dictionary = {}
var knowledge: Array = []
var world_info: Dictionary = {}

## 游戏状态
var current_chapter_id: String = ""
var completed_chapters: Array = []
var flags: Dictionary = {}
var relationship_values: Dictionary = {}
var discovered_knowledge: Array = []

func _ready() -> void:
    _instance = self
    load_all_data()

static func get_instance() -> DataManager:
    return _instance

func load_all_data() -> void:
    story = _load_json("res://data/story.json")
    characters = _load_json("res://data/characters.json")
    relationships = _load_json("res://data/relationships.json")
    endings = _load_json("res://data/endings.json")
    knowledge = _load_json("res://data/knowledge.json")
    world_info = _load_json("res://data/world.json")

func _load_json(path: String) -> Dictionary:
    var file = FileAccess.open(path, FileAccess.READ)
    if file:
        var json = JSON.new()
        var result = json.parse(file.get_as_text())
        if result == OK:
            return json.data
    return {}

func get_chapter(chapter_id: String) -> Dictionary:
    if chapter_id == "prologue":
        return story.get("prologue", {})
    elif chapter_id == "epilogue":
        return story.get("epilogue", {})
    else:
        for ch in story.get("chapters", []):
            if ch.get("id") == chapter_id:
                return ch
    return {}

func get_next_chapter_id() -> String:
    var chapters = story.get("chapters", [])
    var current_order = -1

    for i in range(chapters.size()):
        if chapters[i].get("id") == current_chapter_id:
            current_order = chapters[i].get("order", i)
            break

    # 找下一个未完成的章节
    for ch in chapters:
        if ch.get("order", 0) > current_order:
            if ch.get("id") not in completed_chapters:
                return ch.get("id", "")

    return "epilogue"

func complete_chapter(chapter_id: String) -> void:
    if chapter_id not in completed_chapters:
        completed_chapters.append(chapter_id)

func set_flag(key: String, value) -> void:
    flags[key] = value

func get_flag(key: String, default = null):
    return flags.get(key, default)

func change_relationship(rel_key: String, delta: int) -> void:
    relationship_values[rel_key] = relationship_values.get(rel_key, 0) + delta

func get_relationship_value(rel_key: String) -> int:
    return relationship_values.get(rel_key, 0)

func unlock_knowledge(knowledge_id: String) -> void:
    if knowledge_id not in discovered_knowledge:
        discovered_knowledge.append(knowledge_id)

func check_ending_conditions() -> String:
    for ending_id in endings:
        var ending = endings[ending_id]
        var trigger = ending.get("trigger", {})
        if _evaluate_trigger(trigger):
            return ending_id
    return "normal"

func _evaluate_trigger(trigger: Dictionary) -> bool:
    var trigger_type = trigger.get("type", "and")
    var conditions = trigger.get("conditions", [])

    if conditions.is_empty():
        return true

    if trigger_type == "and":
        for cond in conditions:
            if not _evaluate_condition(cond):
                return false
        return true
    elif trigger_type == "or":
        for cond in conditions:
            if _evaluate_condition(cond):
                return true
        return false

    return false

func _evaluate_condition(cond: Dictionary) -> bool:
    var cond_type = cond.get("type", "")

    if cond_type == "flag":
        return flags.get(cond.get("key", "")) == cond.get("value", true)
    elif cond_type == "min_chapters":
        return completed_chapters.size() >= cond.get("value", 0)
    elif cond_type == "min_flag_count":
        var prefix = cond.get("prefix", "")
        var count = 0
        for key in flags:
            if key.begins_with(prefix) and flags[key]:
                count += 1
        return count >= cond.get("value", 0)

    return false
'''
        (project_path / "scripts" / "data_manager.gd").write_text(content, encoding="utf-8")

    def _write_game_scene_script(self, project_path: Path, story: Dict,
                                  characters: Dict, endings: Dict,
                                  analysis: Dict) -> None:
        """
        生成游戏场景脚本 - 视觉小说核心逻辑

        功能：
        1. 打字机效果的文字显示
        2. 选择支系统
        3. 关系值追踪
        4. 结局判定
        5. 知识碎片收集
        """
        # 将数据序列化为GDScript字典字面量
        story_json = json.dumps(story, ensure_ascii=False)
        chars_json = json.dumps(characters, ensure_ascii=False)
        endings_json = json.dumps(endings, ensure_ascii=False)

        content = f'''## 视觉小说游戏场景
extends Control

## ── 节点引用 ──
@onready var chapter_title = $StoryArea/ChapterTitle
@onready var text_box = $StoryArea/TextBox/MarginContainer/VBox/TextLabel
@onready var speaker_label = $StoryArea/TextBox/MarginContainer/VBox/SpeakerLabel
@onready var choice_container = $StoryArea/ChoiceContainer
@onready var choices_vbox = $StoryArea/ChoiceContainer/ChoicesVBox
@onready var knowledge_panel = $KnowledgePanel
@onready var knowledge_title = $KnowledgePanel/MarginContainer/VBox/KnowledgeTitle
@onready var knowledge_content = $KnowledgePanel/MarginContainer/VBox/KnowledgeContent
@onready var click_continue = $ClickContinue
@onready var typewriter_timer = $TypewriterTimer

## ── 游戏数据 ──
var story_data: Dictionary = {{}}
var characters_data: Dictionary = {{}}
var endings_data: Dictionary = {{}}

## ── 当前状态 ──
var current_chapter_id: String = ""
var current_lines: Array = []
var current_line_index: int = 0
var current_text: String = ""
var displayed_chars: int = 0
var is_typing: bool = false
var is_awaiting_choice: bool = false
var is_playing_branch: bool = false
var ending_hints: Array = []
var completed_chapters: Array = []
var flags: Dictionary = {{}}
var relationship_values: Dictionary = {{}}

## ── 初始化 ──
func _ready() -> void:
    _load_data()
    click_continue.visible = true
    typewriter_timer.timeout.connect(_on_typewriter_tick)
    print("[VN] story keys: ", story_data.keys())
    _start_prologue()

func _load_data() -> void:
    story_data = _load_json("res://data/story.json")
    characters_data = _load_json("res://data/characters.json")
    endings_data = _load_json("res://data/endings.json")
    print("[VN] Loaded chapters: ", story_data.get("chapters", []).size())

func _load_json(path: String) -> Dictionary:
    var file = FileAccess.open(path, FileAccess.READ)
    if file:
        var json = JSON.new()
        var result = json.parse(file.get_as_text())
        if result == OK:
            return json.data
    return {{}}

## ── 游戏流程 ──
func _start_prologue() -> void:
    var prologue = story_data.get("prologue", {{}})
    print("[VN] prologue lines: ", prologue.get("lines", []).size())
    _load_chapter(prologue, "prologue")
    _show_chapter_title_and_start(prologue.get("title", ""))

func _load_chapter(chapter: Dictionary, chapter_id: String) -> void:
    current_chapter_id = chapter_id
    current_lines = chapter.get("lines", [])
    current_line_index = 0
    print("[VN] >>> _load_chapter: ", chapter_id, " lines=", current_lines.size())

func _show_chapter_title_and_start(title: String) -> void:
    if title:
        chapter_title.text = title
        chapter_title.visible = true
        await get_tree().create_timer(1.5).timeout
        chapter_title.visible = false
    _show_current_line()

func _show_current_line() -> void:
    if current_line_index >= current_lines.size():
        _on_chapter_finished()
        return

    var line = current_lines[current_line_index]
    var speaker = line.get("speaker", "")
    var text = line.get("text", "")
    var effect = line.get("effect", "")
    print("[VN] >>> line ", current_line_index, ": ", line)
    print("[VN]     total lines: ", current_lines.size(), " chapter: ", current_chapter_id)

    # 处理特殊效果
    if effect == "chapter_title":
        chapter_title.text = text.replace("━━ ", "").replace(" ━━", "")
        chapter_title.visible = true
        await get_tree().create_timer(1.2).timeout
        chapter_title.visible = false
        current_line_index += 1
        _show_current_line()
        return

    if effect == "ending_title":
        text_box.text = "[center][color=#E8D4B4]{{text}}[/color][/center]"
        _start_typewriter(text)
        return

    # fade_in / fade_out 效果：显示文字后继续
    if effect == "fade_in" or effect == "fade_out":
        _start_typewriter(text)
        return

    # 设置说话人
    if speaker == "narrator":
        speaker_label.text = ""
        speaker_label.visible = false
    else:
        speaker_label.text = speaker
        speaker_label.visible = true
        # 根据角色设置颜色
        var char_data = characters_data.get(speaker, {{}})
        var color = char_data.get("color", "#FFFFFF")
        speaker_label.add_theme_color_override("font_color", Color.html(color))

    # 打字机效果显示文本
    _start_typewriter(text)

func _start_typewriter(text: String) -> void:
    current_text = text
    displayed_chars = 0
    is_typing = true
    text_box.text = ""
    click_continue.visible = false
    typewriter_timer.start()

func _on_typewriter_tick() -> void:
    if displayed_chars < current_text.length():
        displayed_chars += 1
        text_box.text = current_text.substr(0, displayed_chars)
    else:
        typewriter_timer.stop()
        is_typing = false
        click_continue.visible = true
        print("[VN] typewriter done")

## ── 输入处理 ──
func _input(event: InputEvent) -> void:
    if is_awaiting_choice:
        return

    if event is InputEventMouseButton and event.pressed:
        print("[VN] click, is_typing=", is_typing, " idx=", current_line_index)
        if is_typing:
            _skip_typewriter()
        else:
            _advance_line()

func _skip_typewriter() -> void:
    typewriter_timer.stop()
    is_typing = false
    text_box.text = current_text
    click_continue.visible = true

func _advance_line() -> void:
    current_line_index += 1
    _show_current_line()

## ── 章节完成 ──
func _on_chapter_finished() -> void:
    # 如果正在播放分支行，转到分支完成处理
    if is_playing_branch:
        _on_branch_finished()
        return
    completed_chapters.append(current_chapter_id)

    # 获取章节的选择
    var chapter = _get_chapter_data(current_chapter_id)
    var choices = chapter.get("choices", [])

    if choices.size() > 0:
        _show_choices(choices)
    else:
        _go_to_next_chapter()

func _get_chapter_data(chapter_id: String) -> Dictionary:
    if chapter_id == "prologue":
        return story_data.get("prologue", {{}})
    elif chapter_id == "epilogue":
        return story_data.get("epilogue", {{}})
    for ch in story_data.get("chapters", []):
        if ch.get("id") == chapter_id:
            return ch
    return {{}}

## ── 选择系统 ──
func _show_choices(choices: Array) -> void:
    is_awaiting_choice = true
    choice_container.visible = true
    click_continue.visible = false

    # 清空旧选项
    for child in choices_vbox.get_children():
        child.queue_free()

    # 创建新选项
    for i in range(choices.size()):
        var choice = choices[i]
        var btn = Button.new()
        btn.text = choice.get("text", "选择" + str(i + 1))
        btn.custom_minimum_size = Vector2(600, 40)
        btn.alignment = HORIZONTAL_ALIGNMENT_LEFT
        btn.pressed.connect(_on_choice_made.bind(choice))
        choices_vbox.add_child(btn)

        # 显示子文本
        var sub_text = choice.get("sub_text", "")
        if sub_text:
            var label = Label.new()
            label.text = "    " + sub_text
            label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
            label.add_theme_font_size_override("font_size", 13)
            label.add_theme_color_override("font_color", Color(0.6, 0.6, 0.7, 1))
            choices_vbox.add_child(label)

func _on_choice_made(choice: Dictionary) -> void:
    is_awaiting_choice = false
    choice_container.visible = false

    # 应用选择后果
    var consequences = choice.get("consequences", {{}})

    # 更新关系值
    var rel_changes = consequences.get("relationship_changes", {{}})
    for key in rel_changes:
        relationship_values[key] = relationship_values.get(key, 0) + rel_changes[key]

    # 更新标志
    var new_flags = consequences.get("flags", {{}})
    for key in new_flags:
        flags[key] = new_flags[key]

    # 记录结局倾向
    var hint = choice.get("ending_hint", "none")
    if hint != "none":
        ending_hints.append(hint)

    # 播放分支剧情（alternative path）
    var branch_lines = choice.get("branch_lines", [])
    if branch_lines.size() > 0:
        _play_branch_lines(branch_lines)
    else:
        _go_to_next_chapter()

## ── 分支剧情播放 ──
func _play_branch_lines(branch_lines: Array) -> void:
    # 将分支行设为当前行，播放完后继续下一章
    is_playing_branch = true
    current_lines = branch_lines
    current_line_index = 0
    _show_current_line()

## ── 分支行播放完毕 ──
func _on_branch_finished() -> void:
    is_playing_branch = false
    # 检查结局
    var ending_id = _check_endings()
    if ending_id != "":
        _show_ending(ending_id)
        return
    _go_to_next_chapter()

func _check_endings() -> String:
    for ending_id in endings_data:
        var ending = endings_data[ending_id]
        var trigger = ending.get("trigger", {{}})
        if _evaluate_trigger(trigger):
            return ending_id
    return ""

func _evaluate_trigger(trigger: Dictionary) -> bool:
    var trigger_type = trigger.get("type", "and")
    var conditions = trigger.get("conditions", [])
    if conditions.is_empty():
        return true
    if trigger_type == "and":
        for cond in conditions:
            if not _evaluate_condition(cond):
                return false
        return true
    elif trigger_type == "or":
        for cond in conditions:
            if _evaluate_condition(cond):
                return true
        return false
    return false

func _evaluate_condition(cond: Dictionary) -> bool:
    var cond_type = cond.get("type", "")
    if cond_type == "flag":
        return flags.get(cond.get("key", "")) == cond.get("value", true)
    elif cond_type == "min_chapters":
        return completed_chapters.size() >= cond.get("value", 0)
    elif cond_type == "min_flag_count":
        var prefix = cond.get("prefix", "")
        var count = 0
        for key in flags:
            if key.begins_with(prefix) and flags[key]:
                count += 1
        return count >= cond.get("value", 0)
    return false

## ── 反馈显示 ──
func _show_feedback(text: String) -> void:
    chapter_title.text = text
    chapter_title.visible = true
    chapter_title.add_theme_color_override("font_color", Color(0.7, 0.9, 0.7, 1))
    await get_tree().create_timer(1.5).timeout
    chapter_title.visible = false
    chapter_title.add_theme_color_override("font_color", Color(0.9, 0.85, 0.7, 1))
    print("[VN] >>> feedback done, calling _go_to_next_chapter")
    _go_to_next_chapter()

## ── 章节导航 ──
func _go_to_next_chapter() -> void:
    var chapters = story_data.get("chapters", [])
    var current_order = -1
    print("[VN] _go_to_next: current=", current_chapter_id, " completed=", completed_chapters)

    for ch in chapters:
        if ch.get("id") == current_chapter_id:
            current_order = ch.get("order", 0)
            break
    print("[VN] current_order=", current_order)

    for ch in chapters:
        if ch.get("order", 0) > current_order:
            if ch.get("id") not in completed_chapters:
                print("[VN] Loading next: ", ch.get("id"))
                _load_chapter(ch, ch.get("id", ""))
                _show_chapter_title_and_start(ch.get("title", ""))
                return

    print("[VN] No more chapters, going to ending")
    _determine_ending()

func _determine_ending() -> void:
    var positive_count = 0
    var negative_count = 0
    var hope_flags = ["hopeful", "stayed_fuzi", "refused_betray", "supported_huniu", "resisted_detective", "medicated"]
    var despair_flags = ["left_fuzi", "betrayed", "submitted", "gave_money", "doubtful", "resisted"]
    
    for flag in flags:
        if flags[flag] == true:
            if flag in hope_flags:
                positive_count += 1
            elif flag in despair_flags:
                negative_count += 1
    
    # 统计LLM分支的结局倾向
    for hint in ending_hints:
        if hint == "good":
            positive_count += 1
        elif hint == "bad":
            negative_count += 1
    
    var total_rel = 0
    for key in relationship_values:
        total_rel += relationship_values[key]
    
    print("[VN] Ending: positive=", positive_count, " negative=", negative_count, " rel=", total_rel, " hints=", ending_hints.size())
    
    var ending_id = "normal"
    if positive_count >= 3 and total_rel >= 0:
        ending_id = "good"
    elif negative_count >= 3 or total_rel < -3:
        ending_id = "bad"
    
    _show_ending(ending_id)

## ── 结局显示 ──
func _show_ending(ending_id: String) -> void:
    var ending = endings_data.get(ending_id, {{}})
    var ending_lines = ending.get("lines", [])

    if ending_lines.is_empty():
        return

    # 构建结局内容：选择总结 + 结局
    var summary_lines = _build_choice_summary()
    current_lines = summary_lines + ending_lines
    current_line_index = 0
    _show_current_line()

    # 结局显示完毕后返回主菜单
    await get_tree().create_timer(10.0).timeout
    get_tree().change_scene_to_file("res://scenes/main_menu.tscn")

func _build_choice_summary() -> Array:
    var lines = []
    lines.append({{"speaker": "narrator", "text": "━━ 你的选择 ━━", "effect": "chapter_title"}})
    
    # 统计选择
    var positive_flags = ["hopeful", "stayed_fuzi", "refused_betray", "supported_huniu", "resisted_detective", "medicated"]
    var negative_flags = ["left_fuzi", "betrayed", "submitted", "gave_money", "doubtful", "resisted"]
    var positive_count = 0
    var negative_count = 0
    
    for flag in flags:
        if flags[flag] == true:
            if flag in positive_flags:
                positive_count += 1
            elif flag in negative_flags:
                negative_count += 1
    
    # 统计LLM分支结局倾向
    for hint in ending_hints:
        if hint == "good":
            positive_count += 1
        elif hint == "bad":
            negative_count += 1
    
    # 选择倾向
    if positive_count > negative_count:
        lines.append({{"speaker": "narrator", "text": "你在关键时刻选择了坚守与希望。"}})
    elif negative_count > positive_count:
        lines.append({{"speaker": "narrator", "text": "你在困境中选择了妥协与逃避。"}})
    else:
        lines.append({{"speaker": "narrator", "text": "你在希望与绝望之间徘徊。"}})
    
    # 关系变化
    var total_rel = 0
    for key in relationship_values:
        total_rel += relationship_values[key]
    
    if total_rel > 0:
        lines.append({{"speaker": "narrator", "text": "你与他人的羁绊带来了温暖。"}})
    elif total_rel < 0:
        lines.append({{"speaker": "narrator", "text": "你与他人的关系逐渐疏远。"}})
    
    lines.append({{"speaker": "narrator", "text": "最终结局……"}})
    return lines
'''
        # 修复转义
        content = content.replace("{{", "{").replace("}}", "}")
        (project_path / "scripts" / "game_scene.gd").write_text(content, encoding="utf-8")

    # ──────────────────────────── 数据文件 ────────────────────────────
    def _write_data(self, project_path: Path, story: Dict, characters: Dict,
                    relationships: Dict, endings: Dict, knowledge: List[Dict],
                    analysis: Dict) -> None:
        data_dir = project_path / "data"
        data_dir.mkdir(exist_ok=True)

        self._write_json(data_dir / "story.json", story)
        self._write_json(data_dir / "characters.json", characters)
        self._write_json(data_dir / "relationships.json", relationships)
        self._write_json(data_dir / "endings.json", endings)
        self._write_json(data_dir / "knowledge.json", knowledge)
        self._write_json(data_dir / "world.json", analysis.get("world", {}))
        self._write_json(data_dir / "analysis_full.json", analysis)

    def _write_json(self, path: Path, data) -> None:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ──────────────────────────── 工具方法 ────────────────────────────
    @staticmethod
    def _split_into_paragraphs(text: str, max_length: int = 150) -> List[str]:
        """将文本拆分为适合视觉小说显示的段落"""
        if not text:
            return []

        # 先按句号、感叹号、问号分割
        import re
        sentences = re.split(r'(?<=[。！？])', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        paragraphs = []
        current = ""

        for sent in sentences:
            if len(current) + len(sent) <= max_length:
                current += sent
            else:
                if current:
                    paragraphs.append(current)
                current = sent

        if current:
            paragraphs.append(current)

        return paragraphs

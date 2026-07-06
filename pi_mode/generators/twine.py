#!/usr/bin/env python3
"""
Twine/Chapbook 故事生成器
基于分析结果生成 Twee 源文件，可用 Twine 编辑器打开或 twee-cli 编译为 HTML
"""

import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 导入共享基础模块
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from base import BaseGenerator, LLMClient, CacheManager


class TwineGenerator(BaseGenerator):
    """Twine/Chapbook 故事生成器"""

    # 缓存子目录
    CACHE_SUBDIR = "twine"

    def __init__(self, output_dir: str = "./generated_games"):
        super().__init__(output_dir)
        self._branch_prompt: Optional[str] = None

    # ──────────────────────── 主入口 ────────────────────────
    def generate(self, analysis_file: str, output_name: Optional[str] = None,
                 use_llm: bool = True) -> str:
        analysis = self._load_analysis(analysis_file)
        game_name = output_name or self._derive_name(analysis, analysis_file)
        project_path = self.output_dir / game_name

        print(f"[Twine] 生成 Twine 故事: {game_name}")

        # 初始化 LLM
        self.llm = LLMClient()
        llm_ok = use_llm and self.llm.check_available()
        if llm_ok:
            print(f"[Twine] LLM 可用 ({self.llm.api_url})，将使用 LLM 生成分支对话")
            self._branch_prompt = self._load_prompt("twine_branches.txt")
        else:
            print(f"[Twine] LLM 不可用，使用模板生成（回退模式）")

        analysis_data = analysis.get("analysis", analysis)

        # 构建数据
        characters = self._build_characters(analysis_data)
        story_data = self._build_story(analysis_data, characters, llm_ok)

        # 生成 Twee 文件
        project_path.mkdir(parents=True, exist_ok=True)
        twee_content = self._render_twee(story_data, characters, analysis_data)
        twee_path = project_path / f"{game_name}.twee"
        twee_path.write_text(twee_content, encoding="utf-8")
        print(f"[Twine] OK Twee 文件: {twee_path}")

        # 保存元数据
        meta = {
            "generator": "Text2Game Twine Generator",
            "format": "Chapbook",
            "source_analysis": analysis_file,
            "characters": {k: {"name": v["name"], "role": v["role"]} for k, v in characters.items()},
            "passage_count": len(story_data.get("passages", [])),
            "story_title": story_data.get("title", ""),
        }
        (project_path / "metadata.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # 保存分析数据副本
        (project_path / "analysis.json").write_text(
            json.dumps(analysis_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        print(f"[Twine] OK 生成完成: {project_path}")
        print(f"[Twine] 编译方法见 README 说明")
        return str(project_path)

    # ──────────────────────── 角色构建 ────────────────────────
    def _build_characters(self, analysis: Dict) -> Dict:
        chars = analysis.get("characters", [])
        result = {}
        for i, char in enumerate(chars):
            name = char.get("name", "")
            if not name:
                continue
            result[name] = {
                "name": name,
                "role": char.get("role", ""),
                "traits": char.get("traits", []),
                "background": char.get("background", ""),
                "goal": char.get("goal", ""),
                "color": self._assign_color(i),
            }
        return result

    @staticmethod
    def _assign_color(idx: int) -> str:
        colors = ["#E8B4B8", "#B4D4E8", "#B8E8B4", "#E8D4B4",
                  "#D4B4E8", "#B4E8D4", "#E8E8B4", "#B4B4E8"]
        return colors[idx % len(colors)]

    # ──────────────────────── 故事构建 ────────────────────────
    def _build_story(self, analysis: Dict, characters: Dict, use_llm: bool) -> Dict:
        """
        将分析结果转换为 Twine 故事结构。

        story = {
            "title": str,
            "config": {...},        # 页面配置
            "stylesheet": str,      # 自定义 CSS
            "javascript": str,      # 自定义 JS
            "passages": [
                {
                    "name": str,         # 段落名
                    "tags": [str],       # 标签
                    "source": str,       # Twee 源码
                }
            ]
        }
        """
        world = analysis.get("world", {})
        events = analysis.get("events", [])
        conflicts = analysis.get("conflicts", [])
        relationships = analysis.get("relationships", [])
        themes = analysis.get("themes", [])
        atmosphere = analysis.get("atmosphere", "")

        passages = []

        # ── 配置段落 ──
        config = self._build_config(world)
        stylesheet = self._build_stylesheet()
        javascript = self._build_javascript(characters)

        # ── Start（序章） ──
        passages.append(self._build_start_passage(world, characters, atmosphere))

        # ── 章节段落 ──
        for i, event in enumerate(events):
            prev_event = events[i - 1] if i > 0 else None
            next_event = events[i + 1] if i < len(events) - 1 else None
            chapter = self._build_chapter_passage(
                event, i, events, world, characters,
                conflicts, relationships, themes, atmosphere,
                prev_event, next_event, use_llm
            )
            passages.append(chapter)

        # ── 结局段落 ──
        passages.extend(self._build_ending_passages(analysis, characters))

        # ── 知识碎片段落（可选） ──
        passages.extend(self._build_knowledge_passages(analysis, characters))

        return {
            "title": world.get("name", "Twine 故事"),
            "config": config,
            "stylesheet": stylesheet,
            "javascript": javascript,
            "passages": passages,
        }

    def _build_config(self, world: Dict) -> Dict:
        """Chapbook 页面配置"""
        return {
            "page-transition": "fade",
            "page-transition-duration": "400",
            "dark-theme": "false",
            "font-family": "'Noto Serif SC', 'Source Han Serif SC', serif",
            "font-size": "18",
            "line-height": "1.8",
            "width": "720",
        }

    def _build_stylesheet(self) -> str:
        """自定义 CSS 样式"""
        return """/* Text2Game Twine Story Styles */
body {
  background: #1a1a2e;
  color: #e0e0e0;
}

#page {
  max-width: 720px;
  margin: 0 auto;
  padding: 2rem;
}

/* 段落标题 */
.passage h1, .passage h2 {
  color: #e8d4b4;
  border-bottom: 1px solid #333;
  padding-bottom: 0.5rem;
}

/* 链接样式 */
a {
  color: #b4d4e8;
  text-decoration: none;
  border-bottom: 1px dotted #b4d4e8;
  transition: all 0.2s;
}
a:hover {
  color: #e8b4b8;
  border-bottom-color: #e8b4b8;
}

/* Fork 选项 */
.fork a {
  display: block;
  padding: 0.8rem 1.2rem;
  margin: 0.5rem 0;
  background: rgba(180, 212, 232, 0.08);
  border: 1px solid rgba(180, 212, 232, 0.2);
  border-radius: 6px;
  border-bottom: none;
  transition: all 0.25s;
}
.fork a:hover {
  background: rgba(180, 212, 232, 0.15);
  border-color: rgba(180, 212, 232, 0.4);
  transform: translateX(4px);
}

/* 角色名着色 */
.speaker-narrator { color: #999; font-style: italic; }
.speaker-character { color: #e8b4b8; font-weight: bold; }

/* 章节分隔 */
hr {
  border: none;
  border-top: 1px solid #333;
  margin: 2rem 0;
}

/* 结局标题 */
.ending-title {
  text-align: center;
  font-size: 1.5rem;
  color: #e8d4b4;
  margin: 2rem 0;
}

/* 知识碎片 */
.knowledge-box {
  background: rgba(232, 212, 180, 0.08);
  border-left: 3px solid #e8d4b4;
  padding: 1rem;
  margin: 1rem 0;
  font-size: 0.9rem;
}
"""

    def _build_javascript(self, characters: Dict) -> str:
        """自定义 JavaScript（角色颜色映射等）"""
        char_colors = {name: data["color"] for name, data in characters.items()}
        return f"""// Text2Game Twine Story JavaScript
// 角色颜色映射
window.t2gCharacters = {json.dumps(char_colors, ensure_ascii=False)};
"""

    # ──────────────────────── 段落生成 ────────────────────────

    def _build_start_passage(self, world: Dict, characters: Dict,
                              atmosphere: str) -> Dict:
        """生成 :: Start 段落"""
        lines = []
        lines.append("config:")
        lines.append("  page-transition: fade")
        lines.append("story.initialPassage: 'Start'")
        lines.append("--")
        lines.append("")

        # 氛围渲染
        if atmosphere:
            lines.append(f"*{atmosphere}*")
            lines.append("")

        # 世界观
        era = world.get("era", "")
        location = world.get("location", "")
        rules = world.get("rules", "")
        desc = world.get("description", "")

        if era or location:
            lines.append("**【设定】**")
            if era:
                lines.append(f"- 时代：{era}")
            if location:
                lines.append(f"- 地点：{location}")
            lines.append("")

        if rules:
            lines.append(f"> {rules}")
            lines.append("")

        if desc:
            lines.append(desc)
            lines.append("")

        # 角色介绍
        char_list = list(characters.values())
        if char_list:
            lines.append("**【人物】**")
            for char in char_list[:6]:  # 最多显示6个
                name = char["name"]
                role = char["role"]
                traits = "、".join(char["traits"][:3]) if char["traits"] else ""
                desc_line = f"- **{name}**"
                if role:
                    desc_line += f" — {role}"
                if traits:
                    desc_line += f"（{traits}）"
                lines.append(desc_line)
            lines.append("")

        # 过渡
        lines.append("---")
        lines.append("")
        lines.append("*故事，从这里开始……*")
        lines.append("")
        lines.append("[[开始冒险->Chapter_01]]")

        return {
            "name": "Start",
            "tags": [],
            "source": "\n".join(lines),
        }

    def _build_chapter_passage(self, event: Dict, event_idx: int,
                                all_events: List[Dict], world: Dict,
                                characters: Dict, conflicts: List[Dict],
                                relationships: List[Dict], themes: List[str],
                                atmosphere: str,
                                prev_event: Optional[Dict],
                                next_event: Optional[Dict],
                                use_llm: bool) -> Dict:
        """生成章节段落"""
        order = event.get("order", event_idx + 1)
        title = event.get("title", f"第{order}章")
        desc = event.get("description", "")
        event_chars = event.get("characters", [])
        consequences = event.get("consequences", "")

        # 尝试使用 LLM 生成分支内容
        llm_result = None
        if use_llm and self.llm and self.llm.check_available() and self._branch_prompt:
            llm_result = self._generate_branches_with_llm(
                event, event_idx, all_events, world, characters,
                conflicts, relationships, prev_event, next_event
            )

        if llm_result:
            # 使用 LLM 生成的内容
            return self._build_chapter_from_llm(llm_result, order, event_chars, all_events)
        
        # 回退到模板生成
        return self._build_chapter_from_template(
            event, event_idx, all_events, world, characters,
            conflicts, relationships, themes, atmosphere
        )

    def _build_chapter_from_llm(self, llm_result: Dict, order: int,
                                event_chars: List[str],
                                all_events: List[Dict]) -> Dict:
        """使用 LLM 结果构建章节"""
        lines = []
        
        # 章节标题
        title = llm_result.get("title", f"第{order}章")
        lines.append(f"## {title}")
        lines.append("")
        
        # 叙事内容
        narrative = llm_result.get("narrative", "")
        if narrative:
            lines.append(narrative)
            lines.append("")
        
        # 选择
        choices = llm_result.get("choices", [])
        if choices:
            lines.append("---")
            lines.append("")
            for choice in choices:
                # 使用 _next_chapter_id 确保 target 有效
                target = choice.get("target")
                # 验证 target 是否存在
                if not target or not self._chapter_exists(target, all_events):
                    target = self._next_chapter_id(order, all_events)
                text = choice.get("text", "继续")
                lines.append(f"> [[{text}->{target}]]")
            # 变量设置
            lines.append("")
            for choice in choices:
                flag = choice.get("flag", "")
                if flag:
                    lines.append(f"[if {flag}]story.state.set('{flag}', true)[/]")
        else:
            # 无选择
            next_id = self._next_chapter_id(order, all_events)
            lines.append("---")
            lines.append("")
            lines.append(f"[[继续->{next_id}]]")
        
        return {
            "name": f"Chapter_{order:02d}",
            "tags": ["chapter", "llm"],
            "source": "\n".join(lines),
        }

    def _chapter_exists(self, chapter_id: str, all_events: List[Dict]) -> bool:
        """检查章节是否存在"""
        # 检查是否是有效的章节 ID
        if chapter_id.startswith("Chapter_"):
            try:
                num = int(chapter_id.split("_")[1])
                # 检查是否有对应的事件
                for event in all_events:
                    if event.get("order", 0) == num:
                        return True
                return False
            except (IndexError, ValueError):
                return False
        # 非 Chapter 开头的（如 Ending）认为是有效的
        return True

    def _build_chapter_from_template(self, event: Dict, event_idx: int,
                                     all_events: List[Dict], world: Dict,
                                     characters: Dict, conflicts: List[Dict],
                                     relationships: List[Dict], themes: List[str],
                                     atmosphere: str) -> Dict:
        """使用模板构建章节（回退模式）"""
        order = event.get("order", event_idx + 1)
        title = event.get("title", f"第{order}章")
        desc = event.get("description", "")
        event_chars = event.get("characters", [])
        consequences = event.get("consequences", "")

        lines = []
        lines.append(f"## {title}")
        lines.append("")

        # 章节描述 → 段落
        desc_paragraphs = self._split_into_paragraphs(desc)
        for para in desc_paragraphs:
            lines.append(para)
            lines.append("")

        # 角色对话
        char_map = {name: data for name, data in characters.items()}
        shown = 0
        for char_name in event_chars:
            if shown >= 3:
                break
            char_data = char_map.get(char_name)
            if char_data:
                dialogue = self._generate_dialogue(char_data, event, shown)
                if dialogue:
                    lines.append(f"**{char_name}**：「{dialogue}」")
                    lines.append("")
                    shown += 1

        # 后果过渡
        if consequences:
            lines.append(f"*{consequences}*")
            lines.append("")

        # 生成选择（模板）
        choices = self._generate_choices(
            event, event_idx, all_events, conflicts,
            relationships, characters, world
        )

        if choices:
            lines.append("---")
            lines.append("")
            for choice in choices:
                target = choice.get("target", self._next_chapter_id(order, all_events))
                text = choice.get("text", "继续")
                lines.append(f"> [[{text}->{target}]]")
            lines.append("")
            for choice in choices:
                flag = choice.get("flag", "")
                if flag:
                    lines.append(f"[if {flag}]story.state.set('{flag}', true)[/]")
        else:
            next_id = self._next_chapter_id(order, all_events)
            lines.append("---")
            lines.append("")
            lines.append(f"[[继续->{next_id}]]")

        return {
            "name": f"Chapter_{order:02d}",
            "tags": ["chapter"],
            "source": "\n".join(lines),
        }

    def _generate_branches_with_llm(self, event: Dict, event_idx: int,
                                     all_events: List[Dict], world: Dict,
                                     characters: Dict, conflicts: List[Dict],
                                     relationships: List[Dict],
                                     prev_event: Optional[Dict],
                                     next_event: Optional[Dict]) -> Optional[Dict]:
        """
        调用LLM为单个事件生成分支选择。
        """
        if not self.llm or not self.llm.check_available() or not self._branch_prompt:
            return None

        # 构建角色信息摘要
        event_chars = event.get("characters", [])
        chars_info = []
        for name in event_chars:
            char_data = characters.get(name)
            if char_data:
                traits = ", ".join(char_data.get("traits", []))
                goal = char_data.get("goal", "")
                chars_info.append(f"- {name}（{char_data.get('role', '')}）：特征[{traits}]，目标：{goal}")
        chars_text = "\n".join(chars_info) if chars_info else "无特定角色"

        # 冲突信息
        conflicts_text = "\n".join(
            f"- {c.get('type', '')}：{c.get('description', '')}" for c in conflicts
        ) if conflicts else "无明确冲突"

        # 关系信息
        relevant_rels = [
            r for r in relationships
            if r.get("from") in event_chars or r.get("to") in event_chars
        ]
        rels_text = "\n".join(
            f"- {r.get('from', '')} -> {r.get('to', '')}（{r.get('type', '')}）：{r.get('description', '')}"
            for r in relevant_rels
        ) if relevant_rels else "无直接关系"

        prev_text = f"标题：{prev_event.get('title', '')}，描述：{prev_event.get('description', '')[:100]}" if prev_event else "无（这是第一个事件）"
        next_text = f"标题：{next_event.get('title', '')}，描述：{next_event.get('description', '')[:100]}" if next_event else "无（这是最后一个事件）"

        # 检查缓存
        cache_data = {
            "event": event,
            "prev_event": prev_event,
            "next_event": next_event
        }
        cache_key = self.cache.get_cache_key(cache_data, prefix=f"twine_branch_{event_idx}")
        cached = self.cache.load_from_cache(cache_key)
        if cached:
            return cached

        # 填充提示词模板
        prompt = self._branch_prompt.format(
            event=json.dumps(event, ensure_ascii=False, indent=2),
            characters_info=chars_text,
            conflicts=conflicts_text,
            relationships=rels_text,
            prev_event=prev_text,
            next_event=next_text,
        )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"请为事件「{event.get('title', '')}」生成互动故事的分支选择。"}
        ]

        print(f"  [LLM] 生成分支: {event.get('title', f'event_{event_idx}')}")

        max_retries = self.llm.max_retries if self.llm else 3
        for attempt in range(max_retries):
            if attempt > 0:
                time.sleep(2 * attempt)

            try:
                response = self.llm.chat_completion(messages)
            except Exception as e:
                print(f"  [LLM] 请求异常: {e}")
                continue

            if not response or not response.get("choices"):
                continue

            content = response["choices"][0]["message"]["content"]
            parsed = self._parse_llm_json(content)

            if not parsed or not isinstance(parsed, dict):
                continue

            # 验证结构
            choices = parsed.get("choices", [])
            if isinstance(choices, list) and len(choices) >= 2:
                print(f"  [LLM] OK 生成了 {len(choices)} 个选择")
                # 保存到缓存
                self.cache.save_to_cache(cache_key, parsed, preview=event.get("title", ""))
                return parsed

        print(f"  [LLM] {max_retries}次尝试均失败，回退到模板模式")
        return None

    def _next_chapter_id(self, current_order: int, all_events: List[Dict]) -> str:
        """获取下一个章节 ID"""
        for event in all_events:
            if event.get("order", 0) == current_order + 1:
                return f"Chapter_{current_order + 1:02d}"
        return "Ending_Normal"

    def _generate_choices(self, event: Dict, event_idx: int,
                           all_events: List[Dict], conflicts: List[Dict],
                           relationships: List[Dict], characters: Dict,
                           world: Dict) -> List[Dict]:
        """为章节生成选择"""
        choices = []
        event_title = event.get("title", "")
        event_chars = event.get("characters", [])
        order = event.get("order", event_idx + 1)
        next_id = self._next_chapter_id(order, all_events)

        # 基于冲突的选择
        for conflict in conflicts:
            conflict_desc = conflict.get("description", "")
            if any(char in conflict_desc for char in event_chars):
                choices.append({
                    "text": f"面对「{conflict.get('type', '困境')}」",
                    "target": next_id,
                    "flag": f"conflict_{order}_faced",
                })
                break

        # 基于关系的选择
        if not choices:
            relevant = [r for r in relationships
                       if r.get("from") in event_chars or r.get("to") in event_chars]
            if relevant:
                rel = relevant[0]
                choices.append({
                    "text": f"关于{rel.get('from', '')}与{rel.get('to', '')}",
                    "target": next_id,
                    "flag": f"rel_{rel.get('from', '')}_{rel.get('to', '')}",
                })

        # 通用选择
        if not choices:
            choices.append({
                "text": "继续前行",
                "target": next_id,
                "flag": f"chapter_{order}_done",
            })
            choices.append({
                "text": "谨慎观望",
                "target": next_id,
                "flag": f"chapter_{order}_cautious",
            })

        return choices[:3]

    def _generate_dialogue(self, char_data: Dict, event: Dict,
                            char_index: int = 0) -> str:
        """生成角色对话"""
        name = char_data.get("name", "")
        traits = char_data.get("traits", [])
        goal = char_data.get("goal", "")
        event_title = event.get("title", "")

        # 基于特征的台词模板
        trait_lines = {
            "强壮": "我有的是力气，总能活下去。",
            "沉默要强": "……",
            "泼辣": "你以为我好欺负？",
            "心机深沉": "哼，一切都在我的掌控之中。",
            "强悍": "这事儿，我说了算。",
            "精明霸道": "老子这辈子，什么场面没见过。",
            "善良": "我会尽力帮助你的。",
            "坚韧": "再苦再难，也要撑下去。",
            "牺牲": "只要他能活下去，我怎样都行。",
            "暴戾": "滚！别来烦我！",
            "虚荣": "你看我这身衣服，好看吗？",
            "重利轻义": "钱到手了，其他的都是次要的。",
            "凶狠狡诈": "想跑？没那么容易。",
            "贪婪冷酷": "把钱交出来，饶你一命。",
            "好面子": "这事儿传出去，我的脸往哪搁？",
            "年轻": "你还年轻，不懂这些。",
            "堕落自私": "管不了那么多了，先活下去再说。",
        }

        if traits:
            for trait in traits:
                if trait in trait_lines:
                    return trait_lines[trait]

        if goal:
            return goal

        return "……"

    def _split_into_paragraphs(self, text: str, max_length: int = 200) -> List[str]:
        """拆分文本为段落"""
        if not text:
            return []

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

    # ──────────────────────── 结局段落 ────────────────────────

    def _build_ending_passages(self, analysis: Dict, characters: Dict) -> List[Dict]:
        """生成结局段落"""
        char_list = list(characters.values())
        main_name = char_list[0]["name"] if char_list else "主角"

        endings = [
            {
                "name": "Ending_Good",
                "title": "希望结局",
                "lines": [
                    f"## ═══ 希望结局 ═══",
                    "",
                    f"经历了无数磨难，{main_name}终于看到了一丝曙光。",
                    "",
                    "虽然世界依然残酷，但内心深处的火焰并未完全熄灭。",
                    "",
                    "*也许，明天会更好。*",
                    "",
                    "---",
                    "",
                    "[[重新开始->Start]]",
                ],
            },
            {
                "name": "Ending_Normal",
                "title": "平凡结局",
                "lines": [
                    f"## ═══ 平凡结局 ═══",
                    "",
                    f"{main_name}虽然未能改变命运，但至少保住了最后的尊严。",
                    "",
                    "没有轰轰烈烈，没有功成名就。",
                    "",
                    "*但至少，还有呼吸。*",
                    "",
                    "---",
                    "",
                    "[[重新开始->Start]]",
                ],
            },
            {
                "name": "Ending_Bad",
                "title": "堕落结局",
                "lines": [
                    f"## ═══ 堕落结局 ═══",
                    "",
                    f"{main_name}在命运的捉弄下，最终失去了所有希望……",
                    "",
                    f"在这片{analysis.get('world', {}).get('name', '世界')}的大地上，故事走向了最黑暗的终点。",
                    "",
                    "*一切都结束了。*",
                    "",
                    "---",
                    "",
                    "[[重新开始->Start]]",
                ],
            },
        ]

        passages = []
        for ending in endings:
            lines = ending["lines"]
            # 添加选择总结变量
            lines.insert(1, "")
            lines.insert(2, "{story.state.get('good_count', 0)}")
            lines.insert(3, "")

            passages.append({
                "name": ending["name"],
                "tags": ["ending"],
                "source": "\n".join(lines),
            })

        return passages

    # ──────────────────────── 知识碎片 ────────────────────────

    def _build_knowledge_passages(self, analysis: Dict, characters: Dict) -> List[Dict]:
        """生成知识碎片段落"""
        passages = []
        world = analysis.get("world", {})

        # 世界观知识
        if world.get("description"):
            passages.append({
                "name": "Knowledge_World",
                "tags": ["knowledge"],
                "source": (
                    f"## 关于这个世界\n\n"
                    f"{world['description']}\n\n"
                    f"{world.get('rules', '')}\n\n"
                    f"---\n\n"
                    f"{{back link}}"
                ),
            })

        # 角色知识（前3个）
        for i, (name, data) in enumerate(list(characters.items())[:3]):
            if data.get("background"):
                passages.append({
                    "name": f"Knowledge_{name}",
                    "tags": ["knowledge"],
                    "source": (
                        f"## 关于 {name}\n\n"
                        f"**{data['role']}**\n\n"
                        f"{data['background'][:300]}\n\n"
                        f"---\n\n"
                        f"{{back link}}"
                    ),
                })

        return passages

    # ──────────────────────── Twee 渲染 ────────────────────────

    def _render_twee(self, story: Dict, characters: Dict, analysis: Dict) -> str:
        """将故事结构渲染为 Twee 格式文本"""
        parts = []

        # ── StoryData 元数据 ──
        parts.append(self._render_story_data(story))

        # ── Story stylesheet ──
        parts.append(self._render_story_tag("Story stylesheet", story.get("stylesheet", "")))

        # ── Story script ──
        parts.append(self._render_story_tag("Story script", story.get("javascript", "")))

        # ── 各段落 ──
        for passage in story.get("passages", []):
            parts.append(self._render_passage(passage))

        return "\n\n".join(parts) + "\n"

    def _render_story_data(self, story: Dict) -> str:
        """渲染 :: StoryData 段落（Twee3 JSON 格式）"""
        import uuid
        title = story.get("title", "Untitled")

        meta = {
            "tags": "",
            "color": "#000000",
            "name": title,
            "format-version": "2.0.0",
            "format": "Chapbook",
            "uuid": self._generate_uuid(),
        }

        return f":: StoryData\n{json.dumps(meta, ensure_ascii=False, indent=2)}"

    def _render_story_tag(self, tag_name: str, content: str) -> str:
        """渲染 Story stylesheet / Story script"""
        return f":: {tag_name}\n{content}"

    def _render_passage(self, passage: Dict) -> str:
        """渲染单个段落"""
        name = passage.get("name", "Untitled")
        tags = passage.get("tags", [])
        source = passage.get("source", "")

        # 段落名需要转义（含特殊字符时加引号）
        if any(c in name for c in '[]{}():|\"'):
            name = f'"{name}"'

        tag_str = " ".join(tags)
        header = f":: {name}"
        if tag_str:
            header += f" [{tag_str}]"

        return f"{header}\n{source}"

    @staticmethod
    def _generate_uuid() -> str:
        """生成简单 UUID"""
        import uuid
        return str(uuid.uuid4())


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="Twine/Chapbook 故事生成器")
    parser.add_argument("-a", "--analysis", required=True, help="分析结果 JSON 文件路径")
    parser.add_argument("-o", "--output", default="./generated_games", help="输出目录")
    parser.add_argument("-n", "--name", help="自定义输出名称")
    parser.add_argument("--no-llm", action="store_true", help="不使用 LLM 生成分支对话")

    args = parser.parse_args()

    generator = TwineGenerator(args.output)
    try:
        project_path = generator.generate(
            args.analysis,
            output_name=args.name,
            use_llm=not args.no_llm,
        )
        print(f"\nOK 生成完成: {project_path}")
        print(f"  使用 twee-cli 编译: twee build {project_path}/*.twee -o {project_path}/story.html")
        print(f"  或用 Twine 编辑器打开 .twee 文件")
    except FileNotFoundError as e:
        print(f"错误: {e}")
        exit(1)
    except Exception as e:
        print(f"生成失败: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()

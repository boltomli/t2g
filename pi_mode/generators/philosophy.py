#!/usr/bin/env python3
"""
哲学故事生成器
将哲学文本转换为交互式故事游戏
"""

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

# 导入基类
from .base import BaseGenerator, LLMClient, CacheManager


class ConceptType(Enum):
    """概念类型"""
    CORE = "core"
    SUPPORTING = "supporting"
    METAPHOR = "metaphor"
    ACTION = "action"
    VALUE = "value"


@dataclass
class PhilosophicalConcept:
    """哲学概念"""
    name: str
    concept_type: ConceptType
    definition: str = ""
    source_quote: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.concept_type.value,
            "definition": self.definition,
            "source_quote": self.source_quote
        }


@dataclass
class ValueSystem:
    """价值体系"""
    primary_values: List[str] = field(default_factory=list)
    secondary_values: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_values": self.primary_values,
            "secondary_values": self.secondary_values
        }


@dataclass
class PhilosophyAnalysis:
    """哲学分析结果"""
    title: str
    author: str
    era: str
    main_theme: str
    concepts: List[PhilosophicalConcept] = field(default_factory=list)
    values: ValueSystem = field(default_factory=ValueSystem)
    key_quotes: List[str] = field(default_factory=list)
    story_themes: List[str] = field(default_factory=list)
    conflict_suggestions: List[str] = field(default_factory=list)
    character_suggestions: List[Dict[str, str]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "author": self.author,
            "era": self.era,
            "main_theme": self.main_theme,
            "concepts": [c.to_dict() for c in self.concepts],
            "values": self.values.to_dict(),
            "key_quotes": self.key_quotes,
            "story_themes": self.story_themes,
            "conflict_suggestions": self.conflict_suggestions,
            "character_suggestions": self.character_suggestions
        }


class PhilosophyParser:
    """
    哲学文本解析器
    
    使用LLM分析哲学文本，提取核心概念、价值体系和故事主题
    """
    
    def __init__(self, use_llm: bool = True):
        self._use_llm = use_llm
        self._llm = None
        self._analysis_prompt = None
        
        if self._use_llm:
            try:
                self._llm = LLMClient()
                if self._llm.check_available():
                    prompt_file = Path(__file__).parent.parent.parent / "prompts" / "philosophy_analysis.txt"
                    if prompt_file.exists():
                        self._analysis_prompt = prompt_file.read_text(encoding="utf-8")
                else:
                    self._use_llm = False
            except Exception as e:
                self._use_llm = False
    
    def parse(self, text: str, metadata: Optional[Dict[str, str]] = None) -> PhilosophyAnalysis:
        """解析哲学文本"""
        if not self._use_llm or not self._llm or not self._llm.check_available() or not self._analysis_prompt:
            raise RuntimeError("LLM 不可用，无法分析哲学文本。请确保 LLM 服务已启动。")
        
        metadata = metadata or {}
        
        # 准备提示词
        prompt = self._analysis_prompt.format(
            text=text[:2000],
            metadata=json.dumps(metadata, ensure_ascii=False, indent=2)
        )
        
        messages = [{"role": "user", "content": prompt}]
        
        # 调用LLM
        response = self._llm.chat_completion(messages)
        
        if not response or not response.get("choices"):
            raise RuntimeError("LLM 返回为空")
        
        content = response["choices"][0]["message"]["content"]
        
        # 解析JSON
        parsed = self._parse_llm_json(content)
        if not parsed:
            raise RuntimeError("LLM 返回的JSON解析失败")
        
        # 转换为PhilosophyAnalysis
        concepts = []
        for c in parsed.get("concepts", []):
            concepts.append(PhilosophicalConcept(
                name=c.get("name", ""),
                concept_type=ConceptType(c.get("type", "core")),
                definition=c.get("definition", ""),
                source_quote=c.get("source_quote", "")
            ))
        
        values_data = parsed.get("values", {})
        values = ValueSystem(
            primary_values=values_data.get("primary_values", []),
            secondary_values=values_data.get("secondary_values", [])
        )
        
        return PhilosophyAnalysis(
            title=parsed.get("title", metadata.get("title", "")),
            author=parsed.get("author", metadata.get("author", "")),
            era=parsed.get("era", metadata.get("era", "")),
            main_theme=parsed.get("main_theme", ""),
            concepts=concepts,
            values=values,
            key_quotes=parsed.get("key_quotes", []),
            story_themes=parsed.get("story_themes", []),
            conflict_suggestions=parsed.get("conflict_suggestions", []),
            character_suggestions=parsed.get("character_suggestions", [])
        )
    
    def _parse_llm_json(self, content: str) -> Optional[Dict]:
        """解析LLM返回的JSON"""
        content = content.strip()
        
        if content.startswith("```"):
            lines = content.split("\n", 1)
            content = lines[1] if len(lines) > 1 else content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(content[start:end])
            except json.JSONDecodeError:
                pass
        
        return None


class PhilosophyStoryGenerator(BaseGenerator):
    """
    哲学故事生成器
    
    将哲学文本转换为交互式故事游戏
    """
    
    CACHE_SUBDIR = "philosophy"
    
    def __init__(self, output_dir: str = "./generated_games", use_llm: bool = True):
        super().__init__(output_dir)
        self.parser = PhilosophyParser(use_llm=use_llm)
        
        # 初始化LLM
        self.llm = LLMClient()
        self.use_llm = use_llm and self.llm.check_available()
        self._chapter_prompt = None
        
        if self.use_llm:
            print(f"[Philosophy] LLM 可用 ({self.llm.api_url})，将使用 LLM 生成故事内容")
            self._chapter_prompt = self._load_prompt("philosophy_chapters.txt")
        else:
            raise RuntimeError("LLM 不可用，无法生成故事。请确保 LLM 服务已启动。")
    
    def analyze_text(self, text: str, metadata: Optional[Dict[str, str]] = None) -> Dict:
        """分析哲学文本"""
        cache_key = self.cache.get_cache_key(text, prefix="analysis")
        cached = self.cache.load_from_cache(cache_key)
        if cached:
            return cached
        
        analysis = self.parser.parse(text, metadata)
        
        result = {
            "source_text": text[:500] + "..." if len(text) > 500 else text,
            "metadata": metadata or {},
            "analysis": analysis.to_dict()
        }
        
        self.cache.save_to_cache(cache_key, result, preview=analysis.title)
        return result
    
    def generate_story(self, analysis: Dict, num_chapters: int = 5) -> Dict:
        """基于分析生成故事"""
        cache_key = self.cache.get_cache_key(analysis, prefix="story")
        cached = self.cache.load_from_cache(cache_key)
        if cached:
            return cached
        
        analysis_data = analysis.get("analysis", {})
        title = analysis_data.get("title", "未知")
        author = analysis_data.get("author", "未知")
        main_theme = analysis_data.get("main_theme", "探索")
        
        concepts = [c.get("name", "") for c in analysis_data.get("concepts", [])[:5]]
        values = analysis_data.get("values", {})
        primary_values = values.get("primary_values", [])
        
        characters = self._generate_characters(analysis_data)
        chapters = self._generate_chapters(analysis_data, characters, num_chapters)
        endings = self._generate_endings(analysis_data)
        
        story = {
            "title": f"{main_theme}之旅" if main_theme else f"{title}启示录",
            "theme": main_theme,
            "philosophy_source": f"{author} - {title}",
            "chapters": chapters,
            "characters": characters,
            "endings": endings,
            "metadata": {
                "total_chapters": len(chapters),
                "total_endings": len(endings),
                "concepts": concepts,
                "values": primary_values
            }
        }
        
        self.cache.save_to_cache(cache_key, story, preview=story["title"])
        return story
    
    def _generate_characters(self, analysis: Dict) -> List[Dict]:
        """生成角色"""
        characters = []
        
        for i, char_suggestion in enumerate(analysis.get("character_suggestions", [])[:3]):
            characters.append({
                "id": f"char_{i}",
                "name": char_suggestion.get("name", f"角色{i+1}"),
                "role": char_suggestion.get("role", "探索者"),
                "trait": char_suggestion.get("trait", "坚定"),
                "background": "",
                "motivation": ""
            })
        
        if not characters or characters[0].get("role") != "主角":
            protagonist = {
                "id": "protagonist",
                "name": "主角",
                "role": "追求真理的探索者",
                "trait": "坚定",
                "background": "一个寻求智慧和真理的旅者",
                "motivation": "追寻生命的意义"
            }
            characters.insert(0, protagonist)
        
        return characters
    
    def _generate_chapter_with_llm(self, analysis: Dict, characters: List[Dict], 
                                  chapter_num: int, chapter_title: str) -> Optional[Dict]:
        """使用LLM生成章节内容"""
        if not self.use_llm or not self.llm or not self.llm.check_available() or not self._chapter_prompt:
            return None
        
        concepts = [c.get("name", "") for c in analysis.get("concepts", [])[:5]]
        values = analysis.get("values", {})
        primary_values = values.get("primary_values", [])
        
        characters_info = "\n".join([f"- {c['name']}: {c['role']} ({c['trait']})" for c in characters[:3]])
        
        prompt = self._chapter_prompt.format(
            analysis=json.dumps(analysis, ensure_ascii=False, indent=2),
            characters_info=characters_info,
            concepts="、".join(concepts),
            values="、".join(primary_values),
            chapter_num=chapter_num,
            chapter_title=chapter_title
        )
        
        messages = [{"role": "user", "content": prompt}]
        
        cache_key = self.cache.get_cache_key(f"{chapter_num}_{chapter_title}", prefix="chapter_llm")
        cached = self.cache.load_from_cache(cache_key)
        if cached:
            return cached
        
        max_retries = self.llm.max_retries
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
            
            if "narrative" in parsed and "choices" in parsed:
                choices = parsed.get("choices", [])
                if isinstance(choices, list) and len(choices) >= 2:
                    print(f"  [LLM] OK 生成了章节 {chapter_num} 的内容")
                    self.cache.save_to_cache(cache_key, parsed, preview=chapter_title)
                    return parsed
        
        print(f"  [LLM] {max_retries}次尝试均失败")
        return None
    
    def _generate_chapters(self, analysis: Dict, characters: List[Dict], 
                          num_chapters: int) -> List[Dict]:
        """生成章节"""
        chapters = []
        
        concepts = [c.get("name", "") for c in analysis.get("concepts", [])]
        values = analysis.get("values", {})
        primary_values = values.get("primary_values", [])
        
        # 开始段落
        start_passage = {
            "id": "Start",
            "title": "开始",
            "scene": "起点",
            "narrative": f"欢迎来到《{analysis.get('title', '哲学之旅')}》\n\n这是一个关于{analysis.get('main_theme', '探索')}的故事。\n\n你是{characters[0]['name']}，{characters[0]['role']}。",
            "characters": [characters[0]["id"]],
            "choices": [
                {
                    "id": "choice_start",
                    "text": "开始旅程",
                    "philosophy_tag": "start",
                    "next_chapter": "prologue"
                }
            ]
        }
        chapters.insert(0, start_passage)
        
        # 序章
        prologue = {
            "id": "prologue",
            "title": "序章：命运的起点",
            "scene": "起点",
            "narrative": f"你踏上了追寻{'和'.join(primary_values[:2]) if primary_values else '真理'}的旅程...",
            "characters": [characters[0]["id"]],
            "choices": [
                {
                    "id": "choice_power",
                    "text": "选择力量之路",
                    "philosophy_tag": "power",
                    "next_chapter": "chapter_1"
                },
                {
                    "id": "choice_wisdom",
                    "text": "选择智慧之路",
                    "philosophy_tag": "wisdom",
                    "next_chapter": "chapter_1"
                },
                {
                    "id": "choice_compassion",
                    "text": "选择仁爱之路",
                    "philosophy_tag": "compassion",
                    "next_chapter": "chapter_1"
                }
            ]
        }
        chapters.append(prologue)
        
        # 中间章节
        for i in range(1, num_chapters - 1):
            concept = concepts[i-1] if i-1 < len(concepts) else "探索"
            chapter_title = f"第{i}章：{concept}的考验"
            
            # 尝试使用LLM生成章节内容
            llm_content = self._generate_chapter_with_llm(
                analysis, characters, i, chapter_title
            )
            
            if llm_content and "narrative" in llm_content and "choices" in llm_content:
                choices = llm_content.get("choices", [])
                for j, choice in enumerate(choices):
                    if "next_chapter" not in choice:
                        if j < len(choices) - 1:
                            choice["next_chapter"] = f"chapter_{i+1}" if i+1 < num_chapters - 1 else "ending_victory"
                        else:
                            choice["next_chapter"] = "ending_victory"
                
                chapter = {
                    "id": f"chapter_{i}",
                    "title": chapter_title,
                    "scene": f"第{i}个关卡",
                    "narrative": llm_content["narrative"],
                    "characters": [characters[0]["id"]],
                    "choices": choices[:3]
                }
            else:
                # 如果LLM失败，抛出异常
                raise RuntimeError(f"LLM 生成章节 {chapter_num} 失败")
            
            chapters.append(chapter)
        
        # 终章
        ending = {
            "id": "ending_victory",
            "title": "终章：胜利的曙光",
            "scene": "终点",
            "narrative": "经过无数次的考验，你终于迎来了胜利的曙光...",
            "characters": [characters[0]["id"]],
            "choices": [],
            "is_ending": True,
            "ending_key": "victory"
        }
        chapters.append(ending)
        
        return chapters
    
    def _generate_endings(self, analysis: Dict) -> Dict[str, Dict]:
        """生成结局"""
        values = analysis.get("values", {})
        primary_values = values.get("primary_values", [])
        
        main_value = primary_values[0] if primary_values else "信念"
        
        endings = {
            "victory": {
                "title": "胜利",
                "summary": f"你成功地实现了目标，体现了{main_value}的力量。",
                "philosophy": "坚持就是胜利。",
                "conclusion": "记住，每一次选择都是一次成长的机会。"
            },
            "sacrifice": {
                "title": "牺牲",
                "summary": f"为了守护{main_value}，你做出了艰难的牺牲。",
                "philosophy": "牺牲是成长的一部分。",
                "conclusion": "有时候，失去是为了更好地获得。"
            },
            "compromise": {
                "title": "妥协",
                "summary": "你在理想与现实之间找到了平衡。",
                "philosophy": "妥协不是软弱，而是智慧。",
                "conclusion": "真正的智慧在于知道何时坚持，何时妥协。"
            },
            "transformation": {
                "title": "蜕变",
                "summary": "经历了一切，你完成了自我蜕变。",
                "philosophy": "成长来自于经历和反思。",
                "conclusion": "每一次选择都是一次成长的机会。"
            }
        }
        
        return endings
    
    def _parse_llm_json(self, content: str) -> Optional[Dict]:
        """解析LLM返回的JSON"""
        content = content.strip()
        
        if content.startswith("```"):
            lines = content.split("\n", 1)
            content = lines[1] if len(lines) > 1 else content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(content[start:end])
            except json.JSONDecodeError:
                pass
        
        return None
    
    def generate_twine(self, story: Dict, output_path: str = None) -> str:
        """生成Twine格式的交互式故事"""
        title = story.get("title", "哲学之旅")
        theme = story.get("theme", "探索")
        chapters = story.get("chapters", [])
        characters = story.get("characters", [])
        endings = story.get("endings", {})
        
        twee_lines = []
        
        # 配置
        twee_lines.append(f":: StoryTitle")
        twee_lines.append(f"[{title}]")
        twee_lines.append("")
        
        # 样式
        twee_lines.append(":: StoryData")
        twee_lines.append("{")
        twee_lines.append(f'  "ifid": "{self._generate_ifid(title)}",')
        twee_lines.append(f'  "format": "Chapbook",')
        twee_lines.append(f'  "format-version": "1.0.0",')
        twee_lines.append(f'  "start": "Start"')
        twee_lines.append("}")
        twee_lines.append("")
        
        # 生成章节段落
        for i, chapter in enumerate(chapters):
            if chapter.get("is_ending"):
                continue
            
            twee_lines.append(f":: {chapter['id']}")
            twee_lines.append(f"## {chapter['title']}")
            twee_lines.append("")
            twee_lines.append(chapter.get("narrative", ""))
            twee_lines.append("")
            
            choices = chapter.get("choices", [])
            if choices:
                for choice in choices:
                    next_chapter = choice.get("next_chapter", "ending_victory")
                    twee_lines.append(f"[[{choice['text']}->{next_chapter}]]")
                twee_lines.append("")
        
        # 生成结局段落
        for ending_key, ending_data in endings.items():
            twee_lines.append(f":: ending_{ending_key}")
            twee_lines.append(f"## {ending_data['title']}")
            twee_lines.append("")
            twee_lines.append(ending_data['summary'])
            twee_lines.append("")
            twee_lines.append(f"*{ending_data['philosophy']}*")
            twee_lines.append("")
            twee_lines.append(ending_data['conclusion'])
            twee_lines.append("")
            twee_lines.append("[[重新开始->Start]]")
            twee_lines.append("")
        
        twee_content = "\n".join(twee_lines)
        
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(twee_content, encoding='utf-8')
            print(f"  [Twine] 已保存: {output_path}")
        
        return twee_content
    
    def _generate_ifid(self, title: str) -> str:
        """生成IFID"""
        import hashlib
        return hashlib.md5(title.encode()).hexdigest()[:16].upper()
    
    def generate_game(self, text: str, metadata: Optional[Dict[str, str]] = None,
                     num_chapters: int = 5, output_format: str = "twine") -> Dict:
        """完整的游戏生成流程"""
        print(f"\n{'='*60}")
        print(f"  哲学故事生成器")
        print(f"{'='*60}\n")
        
        # 1. 分析文本
        print("[1/3] 分析哲学文本...")
        analysis = self.analyze_text(text, metadata)
        print(f"  标题: {analysis['analysis']['title']}")
        print(f"  作者: {analysis['analysis']['author']}")
        print(f"  核心概念: {[c['name'] for c in analysis['analysis']['concepts'][:3]]}")
        
        # 2. 生成故事
        print("\n[2/3] 生成交互式故事...")
        story = self.generate_story(analysis, num_chapters)
        print(f"  故事标题: {story['title']}")
        print(f"  章节数量: {len(story['chapters'])}")
        print(f"  角色数量: {len(story['characters'])}")
        print(f"  结局数量: {len(story['endings'])}")
        
        # 3. 生成输出
        print("\n[3/3] 生成游戏文件...")
        
        game_name = self._derive_name(analysis, suffix="_philosophy")
        game_dir = self.output_dir / game_name
        game_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存JSON
        json_path = game_dir / "story.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(story, f, ensure_ascii=False, indent=2)
        print(f"  JSON: {json_path}")
        
        # 生成Twine
        if output_format == "twine":
            twee_path = game_dir / f"{game_name}.twee"
            self.generate_twine(story, str(twee_path))
        
        # 保存分析结果
        analysis_path = game_dir / "analysis.json"
        with open(analysis_path, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)
        
        print(f"\n{'='*60}")
        print(f"  生成完成!")
        print(f"  输出目录: {game_dir}")
        print(f"{'='*60}\n")
        
        return {
            "game_dir": str(game_dir),
            "story": story,
            "analysis": analysis
        }


def generate_philosophy_game(text: str, metadata: Optional[Dict[str, str]] = None,
                            num_chapters: int = 5, output_dir: str = "./generated_games") -> Dict:
    """生成哲学故事游戏的便捷函数"""
    generator = PhilosophyStoryGenerator(output_dir)
    return generator.generate_game(text, metadata, num_chapters)

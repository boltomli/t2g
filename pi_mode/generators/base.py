#!/usr/bin/env python3
"""
游戏生成器基础模块
提供共享的 LLM 客户端、缓存系统、Twee 渲染和通用方法。

所有生成器（Twine、VisualNovel、Quiz、Philosophy）均继承此基类，
通过统一接口访问 LLM、缓存、提示词和上下文构建，消除重复代码。
"""

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 从 shared 模块导入统一实现
from pi_mode.shared import (
    LLMClient,
    parse_llm_json as _parse_json,
    load_prompt as _load_prompt_file,
    build_context_summary,
    PROJECT_ROOT,
)


class CacheManager:
    """缓存管理器（共享）"""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cache_key(self, data: Any, prefix: str = "") -> str:
        """生成缓存键（基于数据的 MD5 哈希）"""
        if isinstance(data, str):
            text = data
        else:
            text = json.dumps(data, sort_keys=True, ensure_ascii=False)
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        return f"{prefix}_{text_hash}" if prefix else text_hash

    def get_cache_path(self, cache_key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{cache_key}.json"

    def load_from_cache(self, cache_key: str) -> Optional[Dict]:
        """从缓存加载结果"""
        cache_path = self.get_cache_path(cache_key)
        if cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                print(f"    [缓存] 命中: {cache_key[:12]}...")
                return cached.get("result")
            except Exception as e:
                print(f"    [缓存] 读取失败: {e}")
        return None

    def save_to_cache(self, cache_key: str, result: Dict, preview: str = "") -> None:
        """保存结果到缓存"""
        try:
            cache_path = self.get_cache_path(cache_key)
            cache_data = {
                "cache_key": cache_key,
                "preview": preview[:100] if preview else "",
                "timestamp": time.time(),
                "result": result
            }
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            print(f"    [缓存] 已保存: {cache_key[:12]}...")
        except Exception as e:
            print(f"    [缓存] 保存失败: {e}")

    def clear_cache(self) -> int:
        """清除所有缓存"""
        count = 0
        if self.cache_dir.exists():
            for item in self.cache_dir.iterdir():
                if item.suffix == '.json':
                    item.unlink()
                    count += 1
        return count

    def get_cache_info(self) -> Dict:
        """获取缓存信息"""
        if not self.cache_dir.exists():
            return {"count": 0, "size": 0, "size_human": "0 KB", "dir": str(self.cache_dir)}

        count = 0
        total_size = 0
        for f in self.cache_dir.glob("*.json"):
            count += 1
            total_size += f.stat().st_size

        return {
            "count": count,
            "size": total_size,
            "size_human": f"{total_size / 1024:.1f} KB",
            "dir": str(self.cache_dir)
        }


class BaseGenerator:
    """
    生成器基类（共享）

    提供以下统一能力：
    - LLM 客户端（self.llm）
    - 缓存管理（self.cache）
    - 提示词加载（_load_prompt）
    - 分析结果加载与解包（_load_analysis 返回已解包的 analysis data）
    - JSON 解析（_parse_llm_json）
    - Twee 渲染（_render_twee / _render_story_data / _render_passage）
    - 上下文摘要构建（_build_context_summary）
    - 游戏名称推导（_derive_name）
    """

    # 缓存子目录名，子类可覆盖
    CACHE_SUBDIR = "common"

    def __init__(self, output_dir: str = "./generated_games"):
        self.output_dir = Path(output_dir)
        self.llm: Optional[LLMClient] = None
        self.prompts_dir = PROJECT_ROOT / "prompts"

        # 初始化缓存
        cache_dir = PROJECT_ROOT / ".cache" / self.CACHE_SUBDIR
        self.cache = CacheManager(cache_dir)

    # ── 提示词 ──────────────────────────────────────────────────

    def _load_prompt(self, filename: str) -> str:
        """加载提示词文件"""
        return _load_prompt_file(filename)

    # ── 分析结果 ────────────────────────────────────────────────

    def _load_analysis(self, path: str) -> Dict:
        """
        加载分析结果 JSON 文件并返回完整内容（含 source_file 等元信息）。
        不做解包，子类通过 _unwrap_analysis 获取内部数据。
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"分析文件不存在: {path}")
        return json.loads(p.read_text(encoding="utf-8"))

    @staticmethod
    def _unwrap_analysis(analysis: Dict) -> Dict:
        """
        解包分析结果：如果顶层有 "analysis" 键则返回其值，否则返回原 dict。
        统一处理 analyze.py 产出的 {source_file, analysis: {...}} 和直接 {...} 两种格式。
        """
        data = analysis.get("analysis")
        if isinstance(data, dict):
            return data
        return analysis

    def _derive_name(self, analysis: Dict, analysis_file: str = "", suffix: str = "") -> str:
        """从分析结果或文件名生成游戏名称"""
        if analysis_file:
            src = analysis.get("source_file", analysis_file)
            stem = Path(src).stem
            name = "".join(c for c in stem if c.isalnum() or c in "_- ")
            if name:
                return name + suffix
        data = self._unwrap_analysis(analysis)
        name = data.get("world", {}).get("name", "Game")
        name = "".join(c for c in name if c.isalnum() or c in "_- ")
        return (name or "Game") + suffix

    # ── JSON 解析 ───────────────────────────────────────────────

    @staticmethod
    def _parse_llm_json(content: str) -> Optional[Any]:
        """解析 LLM 返回的 JSON（带容错），委托给 shared.parse_llm_json"""
        return _parse_json(content)

    # ── 上下文摘要 ──────────────────────────────────────────────

    @staticmethod
    def _build_context_summary(
        event_chars: List[str],
        characters: Dict or List,
        conflicts: List[Dict],
        relationships: List[Dict],
    ) -> Tuple[str, str, str]:
        """
        从事件角色、角色列表、冲突、关系中构建 LLM prompt 用的上下文摘要。
        委托给 shared.build_context_summary，消除 4 处重复构建逻辑。
        """
        return build_context_summary(event_chars, characters, conflicts, relationships)

    # ── Twee 渲染（共享，Twine 和 Quiz 通用）────────────────────

    def _render_twee(self, story: Dict, *args, **kwargs) -> str:
        """
        将故事结构渲染为 Twee 格式文本。
        story = {title, config, stylesheet, javascript, passages: [...]}
        """
        parts = [
            self._render_story_data(story),
            f":: Story stylesheet\n{story.get('stylesheet', '')}",
            f":: Story script\n{story.get('javascript', '')}",
        ]
        for passage in story.get("passages", []):
            parts.append(self._render_passage(passage))
        return "\n\n".join(parts) + "\n"

    @staticmethod
    def _render_story_data(story: Dict) -> str:
        """渲染 :: StoryData 段落（Twee3 JSON 格式）"""
        title = story.get("title", "Untitled")
        meta = {
            "tags": "",
            "color": "#000000",
            "name": title,
            "format-version": "2.0.0",
            "format": "Chapbook",
            "uuid": str(uuid.uuid4()),
        }
        return f":: StoryData\n{json.dumps(meta, ensure_ascii=False, indent=2)}"

    @staticmethod
    def _render_passage(passage: Dict) -> str:
        """渲染单个段落"""
        name = passage.get("name", "Untitled")
        tags = passage.get("tags", [])
        source = passage.get("source", "")

        # 段落名需要转义（含特殊字符时加引号）
        if any(c in name for c in '[]{}():|"'):
            name = f'"{name}"'

        tag_str = " ".join(tags)
        header = f":: {name}"
        if tag_str:
            header += f" [{tag_str}]"

        return f"{header}\n{source}"

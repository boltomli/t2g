#!/usr/bin/env python3
"""
Text2Game - 文本分析器
使用LM Studio API分析文本内容，支持分块处理、重试机制和进度显示

LLM 客户端、JSON 解析和环境配置统一由 pi_mode.shared 提供，
本模块专注于文本分析、分块、合并和推荐逻辑。
"""

import argparse
import json
import sys
import time
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

# 确保项目根目录在 sys.path 中（支持直接运行 python pi_mode/analyze.py）
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# 从 shared 模块导入统一的 LLM 客户端和配置
from pi_mode.shared import (
    LLMClient,
    parse_llm_json,
    DEFAULT_API_URL,
    DEFAULT_MODEL,
    DEFAULT_API_KEY,
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TIMEOUT,
    DEFAULT_MAX_RETRIES,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_ENABLE_REASONING,
)

# 日志和进度条
try:
    from loguru import logger
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    class logger:
        @staticmethod
        def info(msg): print(f"[INFO] {msg}")
        @staticmethod
        def success(msg): print(f"[OK] {msg}")
        @staticmethod
        def warning(msg): print(f"[WARN] {msg}")
        @staticmethod
        def error(msg): print(f"[ERROR] {msg}")
        @staticmethod
        def debug(msg): pass  # 静默debug输出
    class tqdm:
        def __init__(self, iterable=None, total=None, desc="", **kwargs):
            self.iterable = iterable
            self.total = total or (len(iterable) if iterable else 0)
            self.desc = desc
            self.current = 0
        def __iter__(self):
            return iter(self.iterable)
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def update(self, n=1): self.current += n
        def set_postfix_str(self, s): pass
        def set_description(self, s): self.desc = s
        @staticmethod
        def write(msg): print(msg)  # tqdm.write兼容


class TextAnalyzer:
    """文本分析器（支持分块处理和缓存）"""
    
    # 提示词文件路径
    PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
    
    # 缓存目录
    CACHE_DIR = Path(__file__).parent.parent / ".cache"
    
    def __init__(self, client: LLMClient):
        self.client = client
        self.chunk_size = DEFAULT_CHUNK_SIZE
        self.prompts = self._load_prompts()
        # 创建缓存目录
        cache_dir = Path(__file__).parent.parent / ".cache"
        cache_dir.mkdir(exist_ok=True)
        self.cache_dir = cache_dir
    
    def _validate_analysis(self, analysis: Dict) -> Dict:
        """验证并清理分析结果"""
        # 如果分析有错误，返回空结果
        if analysis.get("_error"):
            return {
                "world": {},
                "characters": [],
                "relationships": [],
                "events": [],
                "conflicts": [],
                "themes": [],
                "atmosphere": "",
                "_error": analysis["_error"]
            }
        
        validated = {
            "world": {},
            "characters": [],
            "relationships": [],
            "events": [],
            "conflicts": [],
            "themes": [],
            "atmosphere": ""
        }
        
        # 验证 world
        if analysis.get("world") and isinstance(analysis["world"], dict):
            world = analysis["world"]
            validated["world"] = {
                "name": str(world.get("name", "未知")) if world.get("name") else "未知",
                "era": str(world.get("era", "未知")) if world.get("era") else "未知",
                "location": str(world.get("location", "未知")) if world.get("location") else "未知",
                "rules": str(world.get("rules", "未知")) if world.get("rules") else "未知",
                "description": str(world.get("description", "未知")) if world.get("description") else "未知"
            }
        
        # 验证 characters
        if analysis.get("characters") and isinstance(analysis["characters"], list):
            for char in analysis["characters"]:
                if isinstance(char, dict) and char.get("name"):
                    validated_character = {
                        "name": str(char["name"]),
                        "role": str(char.get("role", "未知")),
                        "traits": [str(t) for t in char.get("traits", []) if t],
                        "background": str(char.get("background", "未知")),
                        "goal": str(char.get("goal", "未知"))
                    }
                    validated["characters"].append(validated_character)
        
        # 验证 relationships
        if analysis.get("relationships") and isinstance(analysis["relationships"], list):
            for rel in analysis["relationships"]:
                if isinstance(rel, dict) and rel.get("from") and rel.get("to"):
                    validated_rel = {
                        "from": str(rel["from"]),
                        "to": str(rel["to"]),
                        "type": str(rel.get("type", "未知")),
                        "description": str(rel.get("description", ""))
                    }
                    validated["relationships"].append(validated_rel)
        
        # 验证 events
        if analysis.get("events") and isinstance(analysis["events"], list):
            for event in analysis["events"]:
                if isinstance(event, dict) and event.get("title"):
                    validated_event = {
                        "order": int(event.get("order", 0)),
                        "title": str(event["title"]),
                        "description": str(event.get("description", "")),
                        "characters": [str(c) for c in event.get("characters", []) if c],
                        "consequences": str(event.get("consequences", ""))
                    }
                    validated["events"].append(validated_event)
        
        # 按 order 排序事件
        validated["events"].sort(key=lambda x: x.get("order", 0))
        
        # 验证 conflicts
        if analysis.get("conflicts") and isinstance(analysis["conflicts"], list):
            for conflict in analysis["conflicts"]:
                if isinstance(conflict, dict):
                    validated_conflict = {
                        "type": str(conflict.get("type", "未知")),
                        "description": str(conflict.get("description", "未知"))
                    }
                    if validated_conflict["description"] != "未知":
                        validated["conflicts"].append(validated_conflict)
        
        # 验证 themes
        if analysis.get("themes") and isinstance(analysis["themes"], list):
            validated["themes"] = [str(t) for t in analysis["themes"] if t]
        
        # 验证 atmosphere
        if analysis.get("atmosphere"):
            validated["atmosphere"] = str(analysis["atmosphere"])
        
        return validated
    
    def _get_input_hash(self, text: str) -> str:
        """获取输入文本的哈希（作为顶级目录名，使用完整哈希）"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def _load_progress(self, progress_file: Path) -> Dict:
        """加载分析进度"""
        if progress_file.exists():
            try:
                with open(progress_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {"completed_chunks": [], "failed_chunks": [], "status": "new"}
    
    def _save_progress(self, progress_file: Path, progress: Dict) -> None:
        """保存分析进度"""
        try:
            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存进度失败: {e}")
    
    def _get_cache_key(self, text: str, prefix: str = "") -> str:
        """生成缓存键（使用完整哈希）"""
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        # 清理前缀中的非法字符
        import re
        clean_prefix = re.sub(r'[<>:"/\\|?*]', '_', prefix) if prefix else ""
        return f"{clean_prefix}_{text_hash}" if clean_prefix else text_hash
    
    def _get_cache_dir_for_input(self, text: str) -> Path:
        """获取输入对应的缓存目录"""
        input_hash = self._get_input_hash(text)
        input_dir = self.cache_dir / input_hash
        input_dir.mkdir(exist_ok=True)
        return input_dir
    
    def _get_chunks_dir(self, input_dir: Path) -> Path:
        """获取chunks子目录"""
        chunks_dir = input_dir / "chunks"
        chunks_dir.mkdir(exist_ok=True)
        return chunks_dir
    
    def _get_cache_path(self, input_dir: Path, cache_key: str) -> Path:
        """获取缓存文件路径"""
        return input_dir / f"{cache_key}.json"
    
    def _load_from_cache(self, text: str, prefix: str = "", original_input: str = "") -> Optional[Dict]:
        """从缓存加载分析结果"""
        # 使用原始输入作为顶层目录
        input_text = original_input if original_input else text
        input_dir = self._get_cache_dir_for_input(input_text)
        # chunk缓存放在chunks子目录
        if prefix == "chunk":
            input_dir = self._get_chunks_dir(input_dir)
        cache_key = self._get_cache_key(text, prefix)
        return self._load_from_cache_by_key(input_dir, cache_key)
    
    def _load_from_cache_by_key(self, input_dir: Path, cache_key: str) -> Optional[Dict]:
        """从缓存加载分析结果（使用完整键）"""
        cache_path = self._get_cache_path(input_dir, cache_key)
        
        if cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                logger.debug(f"缓存命中: {cache_key[:15]}...")
                return cached.get("result")
            except Exception as e:
                logger.warning(f"缓存读取失败: {e}")
        return None
    
    def _save_to_cache(self, text: str, result: Dict, prefix: str = "", original_input: str = "") -> None:
        """保存分析结果到缓存"""
        # 使用原始输入作为顶层目录
        input_text = original_input if original_input else text
        input_dir = self._get_cache_dir_for_input(input_text)
        # chunk缓存放在chunks子目录
        if prefix == "chunk":
            input_dir = self._get_chunks_dir(input_dir)
        cache_key = self._get_cache_key(text, prefix)
        self._save_to_cache_by_key(input_dir, cache_key, result, text[:100])
    
    def _save_to_cache_by_key(self, input_dir: Path, cache_key: str, result: Dict, preview: str = "") -> None:
        """保存分析结果到缓存（使用完整键）"""
        try:
            cache_path = self._get_cache_path(input_dir, cache_key)
            
            cache_data = {
                "text_hash": cache_key,
                "text_preview": preview[:100] if preview else "",
                "timestamp": time.time(),
                "result": result
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"缓存已保存: {cache_key[:15]}...")
        except Exception as e:
            logger.warning(f"缓存保存失败: {e}")
    
    def clear_cache(self) -> int:
        """清除所有缓存"""
        import shutil
        count = 0
        if self.cache_dir.exists():
            for item in self.cache_dir.iterdir():
                if item.is_dir():
                    # 删除整个输入目录（包括子目录）
                    shutil.rmtree(item)
                    count += 1
                elif item.suffix == '.json':
                    item.unlink()
                    count += 1
        return count
    
    def get_cache_info(self) -> Dict:
        """获取缓存信息"""
        if not self.cache_dir.exists():
            return {"count": 0, "size": 0, "inputs": 0}
        
        total_files = 0
        total_size = 0
        input_dirs = 0
        
        for item in self.cache_dir.iterdir():
            if item.is_dir():
                input_dirs += 1
                # 递归计算所有文件
                for f in item.rglob("*.json"):
                    total_files += 1
                    total_size += f.stat().st_size
            elif item.suffix == '.json':
                total_files += 1
                total_size += item.stat().st_size
        
        return {
            "count": total_files,
            "size": total_size,
            "size_human": f"{total_size / 1024:.1f} KB",
            "inputs": input_dirs
        }
    
    def _load_prompts(self) -> Dict[str, str]:
        """加载提示词文件"""
        prompts = {}
        prompt_files = {
            "analyze": "analyze.txt",
            "recommend": "recommend.txt",
            "merge": "merge.txt"
        }
        
        for key, filename in prompt_files.items():
            filepath = self.PROMPTS_DIR / filename
            if filepath.exists():
                prompts[key] = filepath.read_text(encoding="utf-8")
                logger.debug(f"已加载提示词: {filename}")
            else:
                logger.warning(f"提示词文件不存在: {filepath}")
        
        return prompts
    
    def split_text_into_chunks(self, text: str) -> List[str]:
        """将文本分割成块"""
        # 空文本
        if not text.strip():
            return []
        
        # 短文本，直接返回
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        
        # 尝试按段落分割
        paragraphs = text.split("\n\n")
        current_chunk = ""
        
        for paragraph in paragraphs:
            # 如果单个段落就超过块大小，需要进一步分割
            if len(paragraph) > self.chunk_size:
                # 先保存当前块
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                
                # 按句子分割长段落
                import re
                sentences = re.split(r'([。！？])', paragraph)
                # 重新组合标点符号
                merged_sentences = []
                i = 0
                while i < len(sentences):
                    if i + 1 < len(sentences) and sentences[i + 1] in '。！？':
                        merged_sentences.append(sentences[i] + sentences[i + 1])
                        i += 2
                    else:
                        merged_sentences.append(sentences[i])
                        i += 1
                sentences = merged_sentences
                
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue
                    if len(current_chunk) + len(sentence) + 1 <= self.chunk_size:
                        current_chunk += sentence + "\n"
                    else:
                        if current_chunk.strip():
                            chunks.append(current_chunk.strip())
                        current_chunk = sentence + "\n"
            elif len(current_chunk) + len(paragraph) + 2 <= self.chunk_size:
                current_chunk += paragraph + "\n\n"
            else:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = paragraph + "\n\n"
        
        # 保存最后一个块
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks if chunks else [text]
    
    def analyze_text(self, text: str, use_cache: bool = True) -> Dict:
        """分析文本内容（支持长文本分块和缓存）"""
        # 获取输入目录
        input_dir = self._get_cache_dir_for_input(text)
        
        # 保存原始输入（方便调试和断点续跑）
        input_file = input_dir / "input.txt"
        if not input_file.exists():
            input_file.write_text(text, encoding="utf-8")
        
        # 记录分析进度
        progress_file = input_dir / "progress.json"
        progress = self._load_progress(progress_file)
        
        # 检查整体缓存
        if use_cache:
            cached = self._load_from_cache(text)
            if cached:
                logger.success("命中整体缓存")
                return cached
        
        # 分析文本
        text_length = len(text)
        logger.info(f"文本长度: {text_length} 字符")
        
        chunks = self.split_text_into_chunks(text)
        
        if len(chunks) == 1:
            # 短文本，直接分析
            logger.info("单块分析...")
            # 检查块缓存
            chunk_analysis = None
            if use_cache:
                chunk_analysis = self._load_from_cache(chunks[0], prefix="chunk", original_input=text)
            
            if chunk_analysis is None:
                chunk_analysis = self._analyze_chunk(chunks[0])
                # 只有分析成功才保存缓存
                if use_cache and chunk_analysis and not chunk_analysis.get("_error"):
                    self._save_to_cache(chunks[0], chunk_analysis, prefix="chunk", original_input=text)
            
            # 验证并保存到缓存
            result = self._validate_analysis(chunk_analysis)
            if use_cache:
                self._save_to_cache(text, result)
            return result
        
        # 长文本，分块分析
        logger.info(f"分为 {len(chunks)} 块处理，每块约 {self.chunk_size} 字符")
        all_analyses = []
        cache_hits = 0
        cache_misses = 0
        skipped = 0
        
        # 使用进度条
        for i, chunk in enumerate(tqdm(chunks, desc="分析文本块", unit="块")):
            # 保存chunk输入（方便调试）
            chunks_dir = self._get_chunks_dir(input_dir)
            chunk_input_file = chunks_dir / f"chunk_{i:03d}_input.txt"
            if not chunk_input_file.exists():
                chunk_input_file.write_text(chunk, encoding="utf-8")
            
            # 检查块缓存
            chunk_analysis = None
            if use_cache:
                chunk_analysis = self._load_from_cache(chunk, prefix="chunk", original_input=text)
                if chunk_analysis:
                    cache_hits += 1
                    tqdm.write(f"  [OK] 块 {i + 1} 命中缓存")
            
            if chunk_analysis is None:
                chunk_analysis = self._analyze_chunk(chunk)
                # 只有分析成功才保存缓存
                if use_cache and chunk_analysis and not chunk_analysis.get("_error"):
                    self._save_to_cache(chunk, chunk_analysis, prefix="chunk", original_input=text)
                    cache_misses += 1
            
            # 检查是否成功
            if chunk_analysis and not chunk_analysis.get("_error"):
                all_analyses.append(chunk_analysis)
                tqdm.write(f"  [OK] 块 {i + 1} 完成")
            elif chunk_analysis and chunk_analysis.get("_error"):
                tqdm.write(f"  [FAIL] 块 {i + 1} 失败: {chunk_analysis['_error']}")
                skipped += 1
            else:
                tqdm.write(f"  [FAIL] 块 {i + 1} 失败，跳过")
                skipped += 1
            
            # 保存进度
            progress["completed_chunks"].append(i) if chunk_analysis and not chunk_analysis.get("_error") else None
            progress["failed_chunks"].append(i) if chunk_analysis and chunk_analysis.get("_error") else None
            self._save_progress(progress_file, progress)
            
            # 避免过于频繁的请求
            if i < len(chunks) - 1 and chunk_analysis is None:
                time.sleep(0.5)
        
        # 更新最终进度
        progress["status"] = "completed"
        progress["total_chunks"] = len(chunks)
        progress["success_count"] = len(all_analyses)
        progress["failed_count"] = skipped
        self._save_progress(progress_file, progress)
        
        logger.info(f"统计: 成功 {len(all_analyses)} 块, 失败 {skipped} 块")
        logger.info(f"缓存: 命中 {cache_hits} 块, 新增 {cache_misses} 块")
        
        # 合并分析结果
        logger.info(f"合并 {len(all_analyses)} 个分析结果...")
        merged = self._merge_analyses(all_analyses, original_input=text)
        
        # 验证并清理合并结果
        merged = self._validate_analysis(merged)
        
        # 保存整体缓存
        if use_cache:
            self._save_to_cache(text, merged)
        
        logger.success("分析完成")
        return merged
    
    def _analyze_chunk(self, text: str) -> Dict:
        """分析单个文本块"""
        # 使用加载的提示词或默认提示词
        system_prompt = self.prompts.get("analyze", "分析文本并返回JSON格式的世界观和角色信息。")
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]
        
        try:
            response = self.client.chat_completion(messages)
        except Exception as e:
            logger.error(f"API请求失败: {e}")
            return {"_error": str(e)}

        if not response or not response.get("choices"):
            return {"_error": "无效的LLM响应"}
        
        content = response["choices"][0]["message"]["content"]
        result = self._parse_json_response(content)
        
        # 标记解析失败
        if not result or (isinstance(result, dict) and not result.get("world")):
            result["_error"] = "JSON解析失败"
            
        return result
    
    def _merge_analyses(self, analyses: List[Dict], original_input: str = "") -> Dict:
        """合并多个分析结果（分别调用LLM合并各部分）"""
        if not analyses:
            return {}
        
        if len(analyses) == 1:
            return analyses[0]
        
        logger.info("使用LLM合并各部分...")
        
        # 提取各部分数据
        all_worlds = []
        all_characters = []
        all_relationships = []
        all_events = []
        all_conflicts = []
        all_themes = []
        all_atmospheres = []
        
        for analysis in analyses:
            if not analysis or not isinstance(analysis, dict):
                continue
            if analysis.get("world") and isinstance(analysis["world"], dict):
                all_worlds.append(analysis["world"])
            if analysis.get("characters") and isinstance(analysis["characters"], list):
                all_characters.extend(analysis["characters"])
            if analysis.get("relationships") and isinstance(analysis["relationships"], list):
                all_relationships.extend(analysis["relationships"])
            if analysis.get("events") and isinstance(analysis["events"], list):
                all_events.extend(analysis["events"])
            if analysis.get("conflicts") and isinstance(analysis["conflicts"], list):
                all_conflicts.extend(analysis["conflicts"])
            if analysis.get("themes") and isinstance(analysis["themes"], list):
                all_themes.extend(analysis["themes"])
            if analysis.get("atmosphere"):
                all_atmospheres.append(str(analysis["atmosphere"]))
        
        # 使用原始输入作为缓存目录
        input_dir = self._get_cache_dir_for_input(original_input)
        
        # 分别调用LLM合并各部分
        merged = {
            "world": self._merge_worlds(all_worlds, input_dir),
            "characters": self._merge_characters(all_characters, input_dir),
            "relationships": self._merge_relationships(all_relationships, input_dir),
            "events": self._merge_events(all_events, input_dir),
            "conflicts": self._merge_conflicts(all_conflicts, input_dir),
            "themes": self._merge_themes(all_themes, input_dir),
            "atmosphere": self._merge_atmospheres(all_atmospheres, input_dir)
        }
        
        return merged
    
    def _merge_worlds(self, worlds: List[Dict], input_dir: Path) -> Dict:
        """合并世界观"""
        if not worlds:
            return {}
        if len(worlds) == 1:
            return worlds[0]
        
        # 检查缓存
        cache_key = self._get_cache_key(json.dumps(worlds, sort_keys=True), prefix="merge_world")
        cached = self._load_from_cache_by_key(input_dir, cache_key)
        if cached:
            return cached
        
        logger.info("合并世界观...")
        prompt = """合并以下世界观信息为一个统一的JSON对象。
只输出JSON，格式：{"name":"", "era":"", "location":"", "rules":"", "description":""}"""
        
        worlds_text = json.dumps(worlds, ensure_ascii=False, indent=2)
        result = self._llm_merge(prompt, worlds_text)
        result = result if result else worlds[0]
        
        # 保存缓存
        self._save_to_cache_by_key(input_dir, cache_key, result)
        return result
    
    def _merge_characters(self, characters: List[Dict], input_dir: Path) -> List[Dict]:
        """合并角色列表（本地同名合并+LLM整理）"""
        if not characters:
            return []
        
        # 检查缓存
        cache_key = self._get_cache_key(json.dumps(characters, sort_keys=True), prefix="merge_chars_v5")
        cached = self._load_from_cache_by_key(input_dir, cache_key)
        if cached:
            return cached if isinstance(cached, list) else []
        
        # 本地合并完全同名的角色（这是确定的）
        seen = {}
        for char in characters:
            if isinstance(char, dict) and char.get("name"):
                name = char["name"].strip()
                if name not in seen:
                    seen[name] = char.copy()
                else:
                    seen[name] = self._local_merge_chars(seen[name], char)
        
        merged_chars = list(seen.values())
        logger.info(f"角色本地合并: {len(characters)}条 -> {len(merged_chars)}个同名角色")
        
        # LLM识别并合并相似角色（如"王某"和"王某先生"）
        if len(merged_chars) > 1:
            merged_chars = self._llm_merge_similar_characters(merged_chars, input_dir)
        
        # 创建chars子目录
        chars_dir = input_dir / "chars"
        chars_dir.mkdir(exist_ok=True)
        
        # 逐个角色LLM整理（带进度条）
        logger.info("LLM整理角色数据...")
        prompt = """整理以下角色数据，生成清晰的角色档案。

要求：
- roles: 合并相似身份（如"商人"和"企业家"只保留一个）
- traits: 精简特征，合并相似的（如"聪明"和"机智"），最多保留3个
- goal: 整合所有目标，提炼出一个核心目标（不要简单复制多个）
- background: 整合为一条完整连贯的故事

输出格式（严格JSON）：
{
  "name": "角色名",
  "role": "当前身份",
  "roles": ["身份1", "身份2"],
  "traits": ["特征"],
  "background": "完整背景故事",
  "goal": "核心目标"
}"""
        
        final_chars = []
        for i, char in enumerate(tqdm(merged_chars, desc="整理角色", unit="个")):
            char_name = char.get("name", f"unknown_{i}")
            
            # 检查单个角色缓存
            char_cache_key = self._get_cache_key(json.dumps(char, sort_keys=True), prefix=f"char_{char_name}")
            char_cached = self._load_from_cache_by_key(chars_dir, char_cache_key)
            if char_cached:
                tqdm.write(f"  [OK] {char_name} 命中缓存")
                final_chars.append(char_cached)
                continue
            
            # LLM整理单个角色
            char_text = json.dumps(char, ensure_ascii=False, indent=2)
            result = self._llm_merge(prompt, char_text)
            if result and isinstance(result, dict) and result.get("name"):
                final_chars.append(result)
                # 保存单个角色缓存
                self._save_to_cache_by_key(chars_dir, char_cache_key, result)
                tqdm.write(f"  [OK] {char_name} 整理完成")
            else:
                final_chars.append(char)
                tqdm.write(f"  ⚠ {char_name} 使用原始数据")
        
        logger.info(f"角色整理完成: {len(final_chars)}个")
        
        # 保存整体缓存
        self._save_to_cache_by_key(input_dir, cache_key, final_chars)
        return final_chars
    
    def _llm_merge_similar_characters(self, characters: List[Dict], input_dir: Path) -> List[Dict]:
        """LLM识别并合并相似角色（如"王某"和"王某先生"）"""
        if len(characters) <= 1:
            return characters
        
        # 检查缓存
        cache_key = self._get_cache_key(json.dumps(characters, sort_keys=True), prefix="merge_similar_chars")
        cached = self._load_from_cache_by_key(input_dir, cache_key)
        if cached:
            return cached if isinstance(cached, list) else characters
        
        # 构建角色信息（包含背景）
        char_info = []
        for c in characters:
            if c.get("name"):
                info = f"- {c['name']}"
                if c.get("role"):
                    info += f" (身份: {c['role']})"
                if c.get("background"):
                    bg = c['background'][:100] + "..." if len(c.get('background', '')) > 100 else c.get('background', '')
                    info += f" (背景: {bg})"
                char_info.append(info)
        
        if len(char_info) <= 1:
            return characters
        
        logger.info(f"LLM识别相似角色: {len(char_info)}个角色")
        
        prompt = """以下是角色列表（包含身份和背景信息），请识别哪些角色可能指的是同一个人。

判断依据：
- 名字相似（如"王某"和"王某先生"）
- 身份相同或相近
- 背景信息有重叠或互补

输出格式（严格JSON数组）：
[["相同角色1a", "相同角色1b"], ["相同角色2a", "相同角色2a_别名"]]

如果没有相似角色，输出空数组 []

角色列表："""
        
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "\n".join(char_info)}
        ]
        
        similar_groups = []
        try:
            response = self.client.chat_completion(messages)
            if response and response.get("choices"):
                content = response["choices"][0]["message"]["content"]
                parsed = self._parse_json_response(content)
                if isinstance(parsed, list):
                    similar_groups = parsed
        except Exception as e:
            logger.warning(f"识别相似角色失败: {e}")
        
        if not similar_groups:
            self._save_to_cache_by_key(input_dir, cache_key, characters)
            return characters
        
        # 合并相似角色
        merged = {}
        used_names = set()
        
        for group in similar_groups:
            if isinstance(group, list) and len(group) > 1:
                # 找到这组角色的数据
                group_chars = []
                for name in group:
                    for char in characters:
                        if char.get("name") == name:
                            group_chars.append(char)
                            used_names.add(name)
                            break
                
                if group_chars:
                    # 使用第一个名字作为主名字
                    merged_name = group[0]
                    merged_data = self._local_merge_chars(*group_chars)
                    merged_data["name"] = merged_name
                    merged[merged_name] = merged_data
        
        # 添加未合并的角色
        for char in characters:
            name = char.get("name", "")
            if name and name not in used_names:
                merged[name] = char
        
        result = list(merged.values())
        logger.info(f"相似角色合并: {len(characters)}个 -> {len(result)}个")
        
        # 保存缓存
        self._save_to_cache_by_key(input_dir, cache_key, result)
        return result
    
    def _local_merge_chars(self, *chars: Dict) -> Dict:
        """本地合并多个角色数据（区分保留多条vs总结为一条）"""
        if len(chars) == 1:
            return chars[0]
        
        # 收集数据
        all_roles = []      # 保留多条（身份变化轨迹）
        all_traits = []     # 保留多条（去重）
        all_backgrounds = [] # 总结为一条
        all_goals = []       # 保留多条（目标变化轨迹）
        latest_role = ""    # 取最新
        latest_goal = ""    # 取最新
        name = ""
        
        for char in chars:
            if not isinstance(char, dict):
                continue
            if not name and char.get("name"):
                name = char["name"]
            # role: 保留所有（身份轨迹），同时记录最新
            if char.get("role"):
                all_roles.append(char["role"])
                latest_role = char["role"]
            # traits: 保留所有（去重）
            if char.get("traits") and isinstance(char["traits"], list):
                all_traits.extend(char["traits"])
            # background: 总结为一条
            if char.get("background"):
                all_backgrounds.append(char["background"])
            # goal: 保留所有（目标轨迹），同时记录最新
            if char.get("goal"):
                all_goals.append(char["goal"])
                latest_goal = char["goal"]
        
        # 合并背景为一条
        background = " ".join(filter(None, all_backgrounds)) if all_backgrounds else ""
        
        return {
            "name": name,
            "role": latest_role,           # 当前身份
            "roles": list(dict.fromkeys(all_roles)),  # 身份变化轨迹
            "traits": list(dict.fromkeys(all_traits)),  # 特征（去重）
            "background": background,      # 合并为一条完整背景
            "goal": latest_goal,            # 当前目标
            "goals": list(dict.fromkeys(all_goals)),  # 目标变化轨迹
            "appearances": len(chars)       # 出现次数
        }
    

    
    def _merge_conflicts(self, conflicts: List[Dict], input_dir: Path) -> List[Dict]:
        """合并冲突列表（LLM整理）"""
        if not conflicts:
            return []
        
        # 检查缓存
        cache_key = self._get_cache_key(json.dumps(conflicts, sort_keys=True), prefix="merge_conflicts")
        cached = self._load_from_cache_by_key(input_dir, cache_key)
        if cached:
            return cached if isinstance(cached, list) else []
        
        logger.info(f"冲突: {len(conflicts)}条 -> LLM整理")
        
        prompt = """整理以下冲突列表，合并相似冲突，去除重复，保留核心冲突。
只输出JSON数组格式。"""
        
        conflicts_text = json.dumps(conflicts, ensure_ascii=False, indent=2)
        result = self._llm_merge(prompt, conflicts_text)
        result = result if result and isinstance(result, list) else conflicts
        
        logger.info(f"冲突整理完成: {len(result)}条")
        
        # 保存缓存
        self._save_to_cache_by_key(input_dir, cache_key, result)
        return result
    
    def _merge_themes(self, themes: List[str], input_dir: Path) -> List[str]:
        """合并主题列表"""
        if not themes:
            return []
        
        # 先本地去重
        unique = list(set(themes))
        
        if len(unique) <= 3:
            return unique
        
        # 检查缓存
        cache_key = self._get_cache_key(json.dumps(unique, sort_keys=True), prefix="merge_themes")
        cached = self._load_from_cache_by_key(input_dir, cache_key)
        if cached:
            return cached
        
        logger.info("合并主题...")
        prompt = """从以下主题中选出最核心的3个主题。
只输出JSON数组格式的3个主题。"""
        
        themes_text = json.dumps(unique, ensure_ascii=False)
        result = self._llm_merge(prompt, themes_text)
        result = result if result else unique[:3]
        
        # 保存缓存
        self._save_to_cache_by_key(input_dir, cache_key, result)
        return result
    
    def _merge_relationships(self, relationships: List[Dict], input_dir: Path) -> List[Dict]:
        """合并人物关系列表（LLM整理）"""
        if not relationships:
            return []
        
        # 检查缓存
        cache_key = self._get_cache_key(json.dumps(relationships, sort_keys=True), prefix="merge_rels")
        cached = self._load_from_cache_by_key(input_dir, cache_key)
        if cached:
            return cached if isinstance(cached, list) else []
        
        logger.info(f"人物关系: {len(relationships)}条 -> LLM整理")
        
        # 直接调用LLM整理关系
        prompt = """整理以下人物关系列表，合并相似关系，去除重复，生成清晰的关系网络。

输出格式（严格JSON数组）：
[{"from": "角色A", "to": "角色B", "type": "关系类型", "description": "描述"}]"""
        
        rels_text = json.dumps(relationships, ensure_ascii=False, indent=2)
        result = self._llm_merge(prompt, rels_text)
        result = result if result and isinstance(result, list) else relationships
        
        logger.info(f"关系整理完成: {len(result)}条")
        
        # 保存缓存
        self._save_to_cache_by_key(input_dir, cache_key, result)
        return result
    
    def _merge_events(self, events: List[Dict], input_dir: Path) -> List[Dict]:
        """合并事件列表（LLM整理排序）"""
        if not events:
            return []
        
        # 检查缓存
        cache_key = self._get_cache_key(json.dumps(events, sort_keys=True), prefix="merge_events")
        cached = self._load_from_cache_by_key(input_dir, cache_key)
        if cached:
            return cached if isinstance(cached, list) else []
        
        logger.info(f"事件: {len(events)}条 -> LLM整理")
        
        # 直接调用LLM整理事件时间线
        prompt = """整理以下事件列表，重新梳理时间线，合并相似事件，去除重复，生成清晰的剧情发展。

非线性叙事请按发生时间重新排序。

输出格式（严格JSON数组）：
[{"order": 1, "title": "事件标题", "description": "事件描述", "characters": ["角色"], "consequences": "后果"}]"""
        
        events_text = json.dumps(events, ensure_ascii=False, indent=2)
        result = self._llm_merge(prompt, events_text)
        result = result if result and isinstance(result, list) else events
        
        # 确保重新排序
        for i, e in enumerate(result):
            e["order"] = i + 1
        
        logger.info(f"事件整理完成: {len(result)}条")
        
        # 保存缓存
        self._save_to_cache_by_key(input_dir, cache_key, result)
        return result
    
    def _merge_atmospheres(self, atmospheres: List[str], input_dir: Path) -> str:
        """合并氛围描述"""
        if not atmospheres:
            return ""
        if len(atmospheres) == 1:
            return atmospheres[0]
        
        # 检查缓存
        cache_key = self._get_cache_key(json.dumps(atmospheres, sort_keys=True), prefix="merge_atmo")
        cached = self._load_from_cache_by_key(input_dir, cache_key)
        if cached:
            return cached
        
        logger.info("合并氛围...")
        prompt = """合并以下氛围描述，生成一个简洁的总结。
只输出字符串格式的氛围描述。"""
        
        atmo_text = "\n".join(atmospheres)
        result = self._llm_merge(prompt, atmo_text, is_string=True)
        result = result if result else atmospheres[0]
        
        # 保存缓存
        self._save_to_cache_by_key(input_dir, cache_key, result)
        return result
    
    def _llm_merge(self, prompt: str, data: str, is_string: bool = False) -> any:
        """调用LLM进行合并"""
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": data}
        ]
        
        try:
            response = self.client.chat_completion(messages)
            if response and response.get("choices"):
                content = response["choices"][0]["message"]["content"]
                if is_string:
                    return content.strip()
                return self._parse_json_response(content)
        except Exception as e:
            logger.warning(f"LLM合并失败: {e}")
        
        return None
    
    def recommend_game_types(self, analysis: Dict) -> List[Dict]:
        """推荐游戏类型"""
        # 使用加载的提示词或默认提示词
        recommend_prompt = self.prompts.get("recommend", "基于分析结果推荐3个游戏类型。")
        
        messages = [
            {"role": "system", "content": recommend_prompt},
            {"role": "user", "content": json.dumps(analysis, ensure_ascii=False, indent=2)}
        ]
        
        response = self.client.chat_completion(messages)
        
        if not response or not response.get("choices"):
            raise Exception("无效的LLM响应")
        
        content = response["choices"][0]["message"]["content"]
        result = self._parse_json_response(content)
        
        if isinstance(result, list):
            return result
        elif isinstance(result, dict) and "recommendations" in result:
            return result["recommendations"]
        else:
            return [result]
    
    def _parse_json_response(self, content: str) -> Any:
        """解析JSON响应（带容错），委托给 shared.parse_llm_json"""
        result = parse_llm_json(content)
        return result if result is not None else {}


def print_config():
    """打印当前配置"""
    print("\n当前配置:")
    print(f"  API地址: {DEFAULT_API_URL}")
    print(f"  模型: {DEFAULT_MODEL}")
    print(f"  API Key: {'已配置' if DEFAULT_API_KEY else '未配置 (本地模式)'}")
    print(f"  温度: {DEFAULT_TEMPERATURE}")
    print(f"  最大Token数: {DEFAULT_MAX_TOKENS}")
    print(f"  超时时间: {DEFAULT_TIMEOUT}秒")
    print(f"  最大重试次数: {DEFAULT_MAX_RETRIES}")
    print(f"  分块大小: {DEFAULT_CHUNK_SIZE}字符")
    print(f"  Reasoning: {'[ON]' if DEFAULT_ENABLE_REASONING else '[OFF]'}")


def analyze_file(file_path: str, api_url: Optional[str] = None, model: Optional[str] = None, 
                 output: Optional[str] = None, chunk_size: Optional[int] = None, 
                 timeout: Optional[int] = None, use_cache: bool = True, api_key: Optional[str] = None) -> Dict:
    """分析文件内容"""
    # 读取文件
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    # 尝试多种编码读取
    encodings = ["utf-8", "gb18030", "gbk", "gb2312", "latin-1"]
    text = None
    for encoding in encodings:
        try:
            text = path.read_text(encoding=encoding)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    if text is None:
        text = path.read_text(encoding="utf-8", errors="ignore")
        logger.warning(f"文件编码识别失败，使用忽略模式读取")
    
    logger.info(f"已读取文件: {file_path} ({len(text)} 字符)")
    
    # 创建客户端
    client = LLMClient(api_url or DEFAULT_API_URL, model or DEFAULT_MODEL, api_key or DEFAULT_API_KEY)
    if timeout:
        client.timeout = timeout
    
    analyzer = TextAnalyzer(client)
    if chunk_size:
        analyzer.chunk_size = chunk_size
    
    # 分析文本
    print("\n正在分析文本...")
    analysis = analyzer.analyze_text(text, use_cache=use_cache)
    print("[OK] 文本分析完成")
    
    # 推荐游戏类型
    print("\n正在推荐游戏类型...")
    game_types = analyzer.recommend_game_types(analysis)
    print(f"[OK] 推荐了 {len(game_types)} 种游戏类型")
    
    # 组合结果
    result = {
        "source_file": file_path,
        "text_length": len(text),
        "config": {
            "api_url": client.api_url,
            "model": client.model,
            "max_tokens": client.max_tokens,
            "chunk_size": analyzer.chunk_size
        },
        "analysis": analysis,
        "recommended_types": game_types
    }
    
    # 保存结果
    if output:
        output_path = Path(output)
    else:
        output_path = path.with_suffix(".json")
    
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] 分析结果已保存到: {output_path}")
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Text2Game - 文本分析器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s examples/fantasy.txt                    # 分析示例文本
  %(prog)s my_story.txt -o analysis.json           # 指定输出文件
  %(prog)s story.txt --model qwen/qwen3.5-9b      # 使用不同模型
  %(prog)s --show-config                           # 显示当前配置
        """
    )
    parser.add_argument("input", nargs="?", help="输入文本文件路径")
    parser.add_argument("-o", "--output", help="输出JSON文件路径")
    parser.add_argument("--api-url", help=f"LLM API地址 (默认从.env读取)")
    parser.add_argument("--model", help="指定模型名称 (默认从.env读取)")
    parser.add_argument("--api-key", help="API密钥 (默认从.env读取)")
    parser.add_argument("--chunk-size", type=int, help="文本分块大小（字符数）")
    parser.add_argument("--timeout", type=int, help="请求超时时间（秒）")
    parser.add_argument("--max-retries", type=int, help="最大重试次数")
    parser.add_argument("--show-config", action="store_true", help="显示当前配置")
    parser.add_argument("--list-models", action="store_true", help="列出可用模型")
    parser.add_argument("--mock", action="store_true", help="使用模拟数据（不调用API）")
    parser.add_argument("--no-cache", action="store_true", help="禁用缓存")
    parser.add_argument("--clear-cache", action="store_true", help="清除所有缓存")
    parser.add_argument("--cache-info", action="store_true", help="显示缓存信息")
    
    args = parser.parse_args()
    
    # 显示配置
    if args.show_config:
        print_config()
        return
    
    # 列出模型
    if args.list_models:
        try:
            client = LLMClient(args.api_url, args.model)
            models = client.get_models()
            print("可用模型:")
            for model in models:
                print(f"  - {model['id']}")
        except Exception as e:
            print(f"错误: {e}", file=sys.stderr)
            sys.exit(1)
        return
    
    # 缓存管理
    if args.clear_cache:
        client = LLMClient(args.api_url or DEFAULT_API_URL)
        analyzer = TextAnalyzer(client)
        count = analyzer.clear_cache()
        print(f"已清除 {count} 个缓存文件")
        return
    
    if args.cache_info:
        client = LLMClient(args.api_url or DEFAULT_API_URL)
        analyzer = TextAnalyzer(client)
        info = analyzer.get_cache_info()
        print(f"缓存信息:")
        print(f"  文件数: {info['count']}")
        print(f"  总大小: {info['size_human']}")
        return
    
    # 检查是否提供了输入文件
    if not args.input:
        parser.print_help()
        sys.exit(1)
    
    # 模拟模式
    if args.mock:
        print("使用模拟数据...")
        result = {
            "source_file": args.input,
            "text_length": 1000,
            "analysis": {
                "world": {
                    "name": "模拟世界",
                    "era": "现代",
                    "location": "城市",
                    "description": "这是一个模拟的分析结果"
                },
                "characters": [
                    {"name": "角色1", "role": "主角", "traits": ["勇敢", "聪明"]}
                ],
                "themes": ["冒险", "成长"]
            },
            "recommended_types": [
                {"type": "rpg", "name": "角色扮演", "reason": "适合角色成长", "features": ["成长系统", "技能树"]},
                {"type": "adventure", "name": "冒险解谜", "reason": "适合探索", "features": ["解谜", "探索"]}
            ]
        }
        
        output_path = Path(args.output) if args.output else Path(args.input).with_suffix(".json")
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] 模拟分析结果已保存到: {output_path}")
        return
    
    # 分析文件
    try:
        result = analyze_file(
            args.input, 
            args.api_url, 
            args.model, 
            args.output,
            args.chunk_size,
            args.timeout,
            use_cache=not args.no_cache,
            api_key=args.api_key
        )
        
        # 打印摘要
        print("\n" + "=" * 50)
        print("分析摘要")
        print("=" * 50)
        
        analysis = result["analysis"]
        
        if "world" in analysis:
            world = analysis["world"]
            print(f"\n世界观: {world.get('name', '未知')}")
            print(f"  时代: {world.get('era', '未知')}")
            print(f"  地点: {world.get('location', '未知')}")
        
        if "characters" in analysis:
            print(f"\n角色 ({len(analysis['characters'])}个):")
            for char in analysis["characters"][:3]:
                print(f"  - {char.get('name', '未知')} - {char.get('role', '未知')}")
        
        if "themes" in analysis:
            print(f"\n主题: {', '.join(analysis['themes'])}")
        
        print(f"\n推荐游戏类型:")
        for game_type in result["recommended_types"]:
            print(f"  - {game_type.get('name', '未知')} ({game_type.get('type', '未知')})")
        
    except FileNotFoundError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n用户取消操作")
        sys.exit(0)
    except Exception as e:
        print(f"分析失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

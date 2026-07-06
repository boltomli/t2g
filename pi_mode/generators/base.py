#!/usr/bin/env python3
"""
游戏生成器基础模块
提供共享的 LLM 客户端、缓存系统和通用方法
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# 尝试加载 dotenv
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / '.env'
    load_dotenv(env_path)
except ImportError:
    pass
except Exception:
    pass


class LLMClient:
    """轻量 LLM 客户端（共享）"""

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
        """发送聊天请求（带重试）"""
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
        """快速检测 LLM 是否可用"""
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
    """生成器基类（共享）"""

    # 缓存子目录名，子类可覆盖
    CACHE_SUBDIR = "common"

    def __init__(self, output_dir: str = "./generated_games"):
        self.output_dir = Path(output_dir)
        self.llm: Optional[LLMClient] = None
        self.prompts_dir = Path(__file__).parent.parent.parent / "prompts"
        
        # 初始化缓存
        cache_dir = Path(__file__).parent.parent.parent / ".cache" / self.CACHE_SUBDIR
        self.cache = CacheManager(cache_dir)

    def _load_prompt(self, filename: str) -> str:
        """加载提示词文件"""
        prompt_file = self.prompts_dir / filename
        if prompt_file.exists():
            return prompt_file.read_text(encoding="utf-8")
        return ""

    def _load_analysis(self, path: str) -> Dict:
        """加载分析结果"""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"分析文件不存在: {path}")
        return json.loads(p.read_text(encoding="utf-8"))

    def _derive_name(self, analysis: Dict, analysis_file: str = "", suffix: str = "") -> str:
        """从分析结果或文件名生成游戏名称"""
        if analysis_file:
            src = analysis.get("source_file", analysis_file)
            stem = Path(src).stem
            name = "".join(c for c in stem if c.isalnum() or c in "_- ")
            if name:
                return name + suffix
        data = analysis.get("analysis", analysis)
        name = data.get("world", {}).get("name", "Game")
        name = "".join(c for c in name if c.isalnum() or c in "_- ")
        return (name or "Game") + suffix

    @staticmethod
    def _parse_llm_json(content: str) -> Optional[Dict]:
        """解析 LLM 返回的 JSON（带容错）"""
        content = content.strip()
        # 移除 markdown 代码块
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

        # 提取 JSON 对象
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(content[start:end])
            except json.JSONDecodeError:
                pass

        return None

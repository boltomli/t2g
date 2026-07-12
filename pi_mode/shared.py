#!/usr/bin/env python3
"""
Text2Game 共享模块
提供统一的 LLM 客户端、JSON 解析、环境配置和上下文构建，
消除 analyze.py 与 generators/base.py 之间的重复代码。
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── 环境配置（统一加载 .env，全模块只加载一次）─────────────────
_env_loaded = False
PROJECT_ROOT = Path(__file__).parent.parent


def load_env() -> None:
    """加载项目根目录的 .env 文件（全局只加载一次）"""
    global _env_loaded
    if _env_loaded:
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass
    except Exception:
        pass
    _env_loaded = True


load_env()


# ── 配置常量（从环境变量读取，带默认值）──────────────────────────
DEFAULT_API_URL = os.getenv("LLM_API_URL", "http://localhost:1234/v1")
DEFAULT_MODEL = os.getenv("LLM_MODEL", "google/gemma-4-12b-qat")
DEFAULT_API_KEY = os.getenv("LLM_API_KEY", "")
DEFAULT_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
DEFAULT_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "16384"))
DEFAULT_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "180"))
DEFAULT_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
DEFAULT_CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "8000"))
DEFAULT_ENABLE_REASONING = os.getenv("ENABLE_REASONING", "false").lower() == "true"


class LLMClient:
    """
    统一 LLM 客户端，与 LM Studio / OpenAI 兼容 API 通信。

    合并了原 analyze.py 和 generators/base.py 两处实现的全部功能：
    - chat_completion: 返回 Optional[Dict]（None 表示失败），支持 response_format
    - get_models: 获取可用模型列表
    - check_available: 快速检测 LLM 是否可用（带缓存）
    """

    def __init__(
        self,
        api_url: str = "",
        model: str = "",
        api_key: str = "",
    ):
        self.api_url = (api_url or DEFAULT_API_URL).rstrip("/")
        self.model = model or DEFAULT_MODEL
        self.api_key = api_key or DEFAULT_API_KEY
        self.temperature = DEFAULT_TEMPERATURE
        self.max_tokens = DEFAULT_MAX_TOKENS
        self.timeout = DEFAULT_TIMEOUT
        self.max_retries = DEFAULT_MAX_RETRIES
        self.enable_reasoning = DEFAULT_ENABLE_REASONING
        self._available: Optional[bool] = None

    def chat_completion(
        self,
        messages: List[Dict],
        response_format: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """
        发送聊天请求（带重试）。
        成功返回完整 JSON 响应 dict，失败返回 None。
        """
        try:
            import requests
        except ImportError:
            return None

        url = f"{self.api_url}/chat/completions"
        body: Dict[str, Any] = {
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
            "reasoning": {"enabled": self.enable_reasoning},
        }
        if self.model:
            body["model"] = self.model
        if response_format:
            body["response_format"] = response_format

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        proxies = {"http": None, "https": None}
        last_error = ""

        for attempt in range(self.max_retries):
            try:
                resp = requests.post(
                    url, json=body, headers=headers,
                    timeout=self.timeout, proxies=proxies,
                )
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code in (429, 500, 502, 503):
                    print(f"  [LLM] HTTP {resp.status_code}, 重试...")
                    time.sleep(3 * (attempt + 1))
                    last_error = f"HTTP {resp.status_code}"
                    continue
                else:
                    print(f"  [LLM] HTTP {resp.status_code}: {resp.text[:200]}")
                    return None
            except requests.exceptions.Timeout:
                last_error = "请求超时"
                if attempt < self.max_retries - 1:
                    print(f"  [LLM] {last_error}, 重试...")
                    time.sleep(2 * (attempt + 1))
            except requests.exceptions.ConnectionError:
                last_error = "连接失败"
                if attempt < self.max_retries - 1:
                    print(f"  [LLM] {last_error}, 重试...")
                    time.sleep(5 * (attempt + 1))
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries - 1:
                    print(f"  [LLM] 请求失败: {e}, 重试...")
                    time.sleep(2 * (attempt + 1))

        print(f"  [LLM] 已重试 {self.max_retries} 次，最后错误: {last_error}")
        return None

    def get_models(self) -> List[Dict]:
        """获取可用模型列表"""
        try:
            import requests
        except ImportError:
            return []
        url = f"{self.api_url}/models"
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        proxies = {"http": None, "https": None}
        resp = requests.get(url, headers=headers, timeout=10, proxies=proxies)
        resp.raise_for_status()
        return resp.json().get("data", [])

    def check_available(self) -> bool:
        """快速检测 LLM 是否可用（结果缓存）"""
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


# ── JSON 解析（统一容错逻辑）────────────────────────────────────

def parse_llm_json(content: str) -> Optional[Any]:
    """
    解析 LLM 返回的 JSON（带容错）。
    支持 markdown 代码块包裹、JSON 对象和数组提取、不完整 JSON 修复。
    返回解析后的 dict / list，或 None。
    """
    content = content.strip()

    # 移除 markdown 代码块标记
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
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
            # 尝试修复不完整的 JSON
            partial = content[start:end]
            for suffix in ['"}', '"}]', '"]', '}', '}]', '"]']:
                try:
                    return json.loads(partial + suffix)
                except json.JSONDecodeError:
                    continue

    # 提取 JSON 数组
    array_start = content.find("[")
    array_end = content.rfind("]") + 1
    if array_start >= 0 and array_end > array_start:
        try:
            return json.loads(content[array_start:array_end])
        except json.JSONDecodeError:
            pass

    return None


# ── 上下文摘要构建（共享，消除 4 处重复）────────────────────────

def build_context_summary(
    event_chars: List[str],
    characters: Dict or List,
    conflicts: List[Dict],
    relationships: List[Dict],
) -> Tuple[str, str, str]:
    """
    从事件角色、角色列表、冲突、关系中构建 LLM prompt 用的上下文摘要。

    参数:
        event_chars: 当前事件涉及的角色名列表
        characters: 角色数据，dict（name→data）或 list 形式
        conflicts: 冲突列表
        relationships: 关系列表

    返回:
        (chars_text, conflicts_text, rels_text)
    """
    # 统一为 dict 形式
    if isinstance(characters, list):
        char_map = {c.get("name", ""): c for c in characters if c.get("name")}
    else:
        char_map = characters

    chars_info = []
    for name in event_chars:
        c = char_map.get(name)
        if c:
            traits = ", ".join(c.get("traits", []))
            goal = c.get("goal", "")
            chars_info.append(
                f"- {name}（{c.get('role', '')}）：特征[{traits}]，目标：{goal}"
            )
    chars_text = "\n".join(chars_info) if chars_info else "无特定角色"

    conflicts_text = (
        "\n".join(
            f"- {c.get('type', '')}：{c.get('description', '')}" for c in conflicts
        )
        if conflicts
        else "无明确冲突"
    )

    relevant_rels = [
        r for r in relationships
        if r.get("from") in event_chars or r.get("to") in event_chars
    ]
    rels_text = (
        "\n".join(
            f"- {r.get('from', '')} -> {r.get('to', '')}（{r.get('type', '')}）：{r.get('description', '')}"
            for r in relevant_rels
        )
        if relevant_rels
        else "无直接关系"
    )

    return chars_text, conflicts_text, rels_text


# ── 提示词加载（共享）──────────────────────────────────────────

PROMPTS_DIR = PROJECT_ROOT / "prompts"


def load_prompt(filename: str) -> str:
    """加载提示词文件，不存在则返回空字符串"""
    prompt_file = PROMPTS_DIR / filename
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    return ""


# ── Twee 编译（共享，消除 generate.py 和 quiz.py 重复）──────────

def compile_twee_files(project_dir: str or Path) -> bool:
    """
    编译目录下所有 .twee 文件为 .html。
    成功返回 True，失败返回 False。
    """
    project_dir = Path(project_dir)
    twee_files = list(project_dir.glob("*.twee"))
    if not twee_files:
        return False

    print(f"\n正在编译 Twee 文件...")
    try:
        compile_path = PROJECT_ROOT / "pi_mode" / "compile_twee.py"
        import importlib.util
        spec = importlib.util.spec_from_file_location("compile_twee", compile_path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            for twee_file in twee_files:
                html_path = twee_file.with_suffix(".html")
                mod.compile_twee(twee_file, html_path)
                print(f"[OK] 编译完成: {html_path}")
            return True
        else:
            raise ImportError("无法加载 compile_twee 模块")
    except Exception as e:
        print(f"[WARN] 自动编译失败: {e}")
        print(f"  手动编译: uv run python pi_mode/compile_twee.py {project_dir}")
        return False

#!/usr/bin/env python3
"""
Text2Game - 分析结果优化器
根据用户需求对已生成的分析结果JSON进行优化
"""

import argparse
import json
import os
import sys
import time
import requests
from pathlib import Path
from typing import Dict, List, Optional

# 尝试加载 dotenv
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(env_path)
except ImportError:
    pass
except Exception:
    pass

# 配置
DEFAULT_API_URL = os.getenv("LLM_API_URL", "http://localhost:1234/v1")
DEFAULT_MODEL = os.getenv("LLM_MODEL", "google/gemma-4-12b-qat")
DEFAULT_API_KEY = os.getenv("LLM_API_KEY", "")
DEFAULT_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
DEFAULT_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "16384"))
DEFAULT_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "600"))
DEFAULT_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
DEFAULT_ENABLE_REASONING = os.getenv("ENABLE_REASONING", "false").lower() == "true"

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class LLMClient:
    """LLM客户端"""

    def __init__(self):
        self.api_url = DEFAULT_API_URL.rstrip("/")
        self.model = DEFAULT_MODEL
        self.api_key = DEFAULT_API_KEY
        self.temperature = DEFAULT_TEMPERATURE
        self.max_tokens = DEFAULT_MAX_TOKENS
        self.timeout = DEFAULT_TIMEOUT
        self.max_retries = DEFAULT_MAX_RETRIES
        self.enable_reasoning = DEFAULT_ENABLE_REASONING

    def chat_completion(self, messages: List[Dict]) -> Dict:
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

        last_error = None
        for attempt in range(self.max_retries):
            try:
                print(f"  发送请求... (尝试 {attempt + 1}/{self.max_retries})")
                resp = requests.post(url, json=body, headers=headers,
                                     timeout=self.timeout, proxies=proxies)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code in (429, 500, 502, 503):
                    print(f"  API错误 {resp.status_code}，等待重试...")
                    time.sleep(3 * (attempt + 1))
                    continue
                else:
                    raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries - 1:
                    print(f"  失败: {e}，重试中...")
                    time.sleep(2 * (attempt + 1))

        raise Exception(f"请求失败（{self.max_retries}次重试）: {last_error}")

    def check_available(self) -> bool:
        try:
            import requests as req
            url = f"{self.api_url}/models"
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            proxies = {"http": None, "https": None}
            resp = req.get(url, headers=headers, timeout=5, proxies=proxies)
            return resp.status_code == 200
        except Exception:
            return False


def load_analysis(path: str) -> Dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    return json.loads(p.read_text(encoding="utf-8"))


def load_prompt_template() -> str:
    prompt_file = PROMPTS_DIR / "optimize.txt"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    # fallback
    return "当前分析结果：\n{analysis}\n\n优化需求：\n{requirements}\n\n输出优化后的完整JSON："


def parse_llm_json(content: str) -> Optional[Dict]:
    """解析LLM返回的JSON（带容错）"""
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


def optimize(analysis: Dict, requirements: str, llm: LLMClient) -> Dict:
    """使用LLM优化分析结果"""
    template = load_prompt_template()

    # 压缩analysis为字符串（去掉过多的缩进）
    analysis_str = json.dumps(analysis, ensure_ascii=False, indent=2)

    # 如果太长，截取关键部分
    if len(analysis_str) > 20000:
        analysis_str = json.dumps(analysis, ensure_ascii=False)

    prompt = template.format(
        analysis=analysis_str,
        requirements=requirements,
    )

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": "请根据上述需求优化分析结果。"},
    ]

    print(f"\n[optimize] 发送优化请求...")
    response = llm.chat_completion(messages)

    if not response or not response.get("choices"):
        raise Exception("LLM未返回有效响应")

    content = response["choices"][0]["message"]["content"]
    print(f"[optimize] 收到响应 ({len(content)} 字符)")

    result = parse_llm_json(content)
    if not result:
        raise Exception(f"无法解析LLM返回的JSON")

    return result


def validate_structure(original: Dict, optimized: Dict) -> List[str]:
    """验证优化后的结构是否完整"""
    warnings = []
    required_keys = ["world", "characters", "events"]
    for key in required_keys:
        if key not in optimized:
            warnings.append(f"缺少字段: {key}")

    if "world" in optimized:
        for field in ["name", "description"]:
            if field not in optimized["world"]:
                warnings.append(f"world 缺少字段: {field}")

    if "characters" in optimized:
        for i, char in enumerate(optimized["characters"]):
            if "name" not in char:
                warnings.append(f"characters[{i}] 缺少 name")

    if "events" in optimized:
        for i, event in enumerate(optimized["events"]):
            if "title" not in event:
                warnings.append(f"events[{i}] 缺少 title")

    return warnings


def main():
    parser = argparse.ArgumentParser(
        description="Text2Game - 分析结果优化器",
        epilog="""
示例:
  # 优化角色深度
  uv run python pi_mode/optimize.py -a result.json -r "增加角色的背景故事深度，让每个角色更立体"

  # 从文件读取需求
  uv run python pi_mode/optimize.py -a result.json -f requirements.txt

  # 优化事件时间线
  uv run python pi_mode/optimize.py -a result.json -r "重新梳理事件时间线，确保因果关系清晰"

  # 指定输出路径
  uv run python pi_mode/optimize.py -a result.json -r "增加更多冲突" -o optimized.json
        """,
    )
    parser.add_argument("-a", "--analysis", required=True, help="分析结果JSON文件路径")
    parser.add_argument("-r", "--requirements", help="优化需求（文本）")
    parser.add_argument("-f", "--file", help="从文件读取优化需求")
    parser.add_argument("-o", "--output", help="输出路径（默认覆盖原文件，加 .optimized 后缀）")
    parser.add_argument("--no-backup", action="store_true", help="不备份原文件")

    args = parser.parse_args()

    # 获取优化需求
    requirements = args.requirements
    if args.file:
        req_path = Path(args.file)
        if not req_path.exists():
            print(f"错误: 需求文件不存在: {args.file}", file=sys.stderr)
            sys.exit(1)
        requirements = req_path.read_text(encoding="utf-8")

    if not requirements:
        print("错误: 请提供优化需求 (-r) 或需求文件 (-f)", file=sys.stderr)
        sys.exit(1)

    # 加载分析结果
    print(f"[optimize] 加载分析结果: {args.analysis}")
    analysis = load_analysis(args.analysis)
    print(f"[optimize] 包含:")
    print(f"  世界: {analysis.get('world', {}).get('name', '?')}")
    print(f"  角色: {len(analysis.get('characters', []))} 个")
    print(f"  事件: {len(analysis.get('events', []))} 个")
    print(f"  关系: {len(analysis.get('relationships', []))} 条")
    print(f"\n[optimize] 优化需求:")
    print(f"  {requirements[:200]}{'...' if len(requirements) > 200 else ''}")

    # 检查LLM
    llm = LLMClient()
    if not llm.check_available():
        print(f"\n错误: LLM服务不可用 ({llm.api_url})", file=sys.stderr)
        print("请确保 LM Studio 或其他 LLM 服务正在运行", file=sys.stderr)
        sys.exit(1)
    print(f"\n[optimize] LLM服务可用: {llm.api_url}")

    # 执行优化
    try:
        optimized = optimize(analysis, requirements, llm)
    except Exception as e:
        print(f"\n优化失败: {e}", file=sys.stderr)
        sys.exit(1)

    # 验证结构
    warnings = validate_structure(analysis, optimized)
    if warnings:
        print(f"\n[optimize] 结构警告:")
        for w in warnings:
            print(f"  - {w}")

    # 确定输出路径
    if args.output:
        output_path = Path(args.output)
    else:
        src = Path(args.analysis)
        output_path = src.parent / f"{src.stem}.optimized.json"

    # 备份原文件
    if not args.no_backup and not args.output:
        backup_path = Path(args.analysis).with_suffix(".backup.json")
        if not backup_path.exists():
            backup_path.write_text(
                json.dumps(analysis, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            print(f"[optimize] 原文件已备份: {backup_path}")

    # 保存优化结果
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(optimized, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"\n[optimize] 优化完成!")
    print(f"  输出: {output_path}")
    print(f"  世界: {optimized.get('world', {}).get('name', '?')}")
    print(f"  角色: {len(optimized.get('characters', []))} 个")
    print(f"  事件: {len(optimized.get('events', []))} 个")
    print(f"  关系: {len(optimized.get('relationships', []))} 条")


if __name__ == "__main__":
    main()

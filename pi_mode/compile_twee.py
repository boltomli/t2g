#!/usr/bin/env python3
"""
Twee -> HTML 编译器
将 .twee 文件编译为自包含的 HTML 文件，内嵌最小化运行时
"""

import argparse
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 内嵌的最小化 Chapbook 兼容运行时
MINIMAL_RUNTIME = r"""
(function(){
'use strict';

// ── State ──
const state = {};
const trail = [];

function get(name) {
  if (name.indexOf('.') === -1) return state[name];
  return name.split('.').reduce((o,k) => o && o[k], state);
}

function set(name, value) {
  const parts = name.split('.');
  let obj = state;
  for (let i = 0; i < parts.length - 1; i++) {
    if (!obj[parts[i]]) obj[parts[i]] = {};
    obj = obj[parts[i]];
  }
  obj[parts[parts.length-1]] = value;
}

// ── Passage parsing ──
function parsePassage(source) {
  const result = { vars: [], blocks: [] };
  const parts = source.split(/^--$/m);
  let varSection = null, bodySection = source;

  if (parts.length >= 2) {
    varSection = parts[0];
    bodySection = parts.slice(1).join('\n--\n');
  }

  // Parse vars (lines before --)
  if (varSection !== null) {
    let inConfig = false;
    varSection.split('\n').forEach(line => {
      line = line.trim();
      if (!line) { inConfig = false; return; }
      // config: section header - skip indented lines after it
      if (line === 'config:') { inConfig = true; return; }
      if (inConfig && line.startsWith(' ')) return; // indented under config:
      inConfig = false;
      // config.X: value lines (top-level config)
      if (line.startsWith('config.')) {
        const m = line.match(/^config\.([\w.]+)\s*:\s*(.+)$/);
        if (m) try { set('config.' + m[1], new Function('return ' + m[2])()); } catch(e) {}
        return;
      }
      const colonIdx = line.indexOf(':');
      if (colonIdx === -1) return;
      const varName = line.substring(0, colonIdx).trim();
      let varValue = line.substring(colonIdx + 1).trim();
      // Handle conditional: name (condition): value
      const condMatch = varName.match(/^(.+?)\s*\((.+)\)\s*$/);
      if (condMatch) {
        try { if (new Function('return ' + condMatch[2])()) set(condMatch[1], new Function('return ' + varValue)()); } catch(e) {}
      } else {
        try { set(varName, new Function('return ' + varValue)()); } catch(e) { set(varName, varValue); }
      }
    });
  }

  // Split body into blocks (text and modifiers)
  const modifierPattern = /^\[([^[].+[^\\]])\]$/gm;
  let match, lastIndex = 0;
  const rawBlocks = [];

  while ((match = modifierPattern.exec(bodySection)) !== null) {
    if (match.index > lastIndex) {
      rawBlocks.push({ type: 'text', content: bodySection.substring(lastIndex, match.index) });
    }
    rawBlocks.push({ type: 'modifier', content: match[1] });
    lastIndex = modifierPattern.lastIndex;
  }
  if (lastIndex < bodySection.length) {
    rawBlocks.push({ type: 'text', content: bodySection.substring(lastIndex) });
  }

  // Process modifiers and build final blocks
  let conditionStack = []; // stack of {active, wasTrue} for nested [if]/[/if]
  let conditionState = null; // current condition result (true/false/null)

  rawBlocks.forEach(block => {
    if (block.type === 'modifier') {
      const mod = block.content.trim();
      // Closing tag [/if] [/unless] [/]
      if (mod === '/if' || mod === '/unless' || mod === '/') {
        conditionStack.pop();
        conditionState = conditionStack.length > 0 ? conditionStack[conditionStack.length - 1].active : null;
        return;
      }
      const ifMatch = mod.match(/^if\s+(.+)$/);
      const unlessMatch = mod.match(/^unless\s+(.+)$/);
      const elseMatch = mod.match(/^else$/);

      if (elseMatch) {
        if (conditionStack.length > 0) {
          const top = conditionStack[conditionStack.length - 1];
          top.active = !top.active;
          conditionState = top.active;
        }
      } else if (ifMatch) {
        let result = false;
        try { result = new Function('return ' + ifMatch[1])(); } catch(e) {}
        conditionStack.push({ active: result, wasTrue: result });
        conditionState = result;
      } else if (unlessMatch) {
        let result = false;
        try { result = new Function('return ' + unlessMatch[1])(); } catch(e) {}
        conditionStack.push({ active: !result, wasTrue: !result });
        conditionState = !result;
      }
    } else {
      // Text block: render only if condition is true (or no condition)
      if (conditionState === false) return;
      if (block.content.trim()) {
        result.blocks.push({ type: 'text', content: processInlineModifiers(block.content) });
      }
    }
  });

  return result;
}

// Process inline [if]...[/if] or [if]...[/] within a text block
function processInlineModifiers(text) {
  // [if cond]...[/if] or [if cond]...[/]
  return text.replace(/\[if\s+([^\]]+)\]([\s\S]*?)\[(?:\/if|\/)\]/g, (match, cond, body) => {
    try {
      if (!new Function('return ' + cond)()) return '';
    } catch(e) { return ''; }
    return body.replace(/\[else\]/g, '');
  }).replace(/\[unless\s+([^\]]+)\]([\s\S]*?)\[(?:\/unless|\/)\]/g, (match, cond, body) => {
    try {
      if (new Function('return ' + cond)()) return '';
    } catch(e) { return ''; }
    return body.replace(/\[else\]/g, '');
  });
}

// ── Markdown-like rendering ──
function renderText(text) {
  if (!text) return '';
  // Variable interpolation: {varname}
  text = text.replace(/\{([^}]+)\}/g, (match, expr) => {
    expr = expr.trim();
    if (expr === 'back link') {
      if (trail.length > 1) {
        const prev = trail[trail.length - 2];
        return '<a href="javascript:void(0)" data-cb-go="' + prev + '">Back</a>';
      }
      return '<a href="javascript:void(0)" data-cb-go="' + trail[0] + '">Back</a>';
    }
    const val = get(expr);
    return val !== undefined ? val : match;
  });
  // Links: [[text->passage]] or [[passage]]
  text = text.replace(/\[\[([^\]]+?)\]\]/g, (match, inner) => {
    let label, target;
    if (inner.indexOf('->') !== -1) {
      const parts = inner.split('->');
      label = parts[0].trim();
      target = parts.slice(1).join('->').trim();
    } else {
      label = target = inner.trim();
    }
    return '<a href="javascript:void(0)" data-cb-go="' + target + '">' + label + '</a>';
  });
  // Blockquote (fork): lines starting with >
  text = text.replace(/^>\s*(.+)$/gm, '<div class="fork">$1</div>');
  // Headings
  text = text.replace(/^##\s+(.+)$/gm, '<h2>$1</h2>');
  text = text.replace(/^###\s+(.+)$/gm, '<h3>$1</h3>');
  // Bold
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // Italic
  text = text.replace(/\*(.+?)\*/g, '<em>$1</em>');
  // Horizontal rule
  text = text.replace(/^---+$/gm, '<hr>');
  // Line breaks
  text = text.replace(/\n\n/g, '</p><p>');
  text = text.replace(/\n/g, '<br>');
  return '<p>' + text + '</p>';
}

// ── Display ──
function go(passageName) {
  const el = document.querySelector('tw-passage[id="passage-' + passageName + '"]');
  if (!el) {
    document.getElementById('page').innerHTML = '<article><p>Passage not found: ' + passageName + '</p></article>';
    return;
  }
  trail.push(passageName);

  const source = el.getAttribute('data-source') || el.textContent || '';
  const parsed = parsePassage(source);
  let html = '';
  parsed.blocks.forEach(b => { html += renderText(b.content); });

  const article = document.querySelector('#page article') || document.querySelector('#page');
  article.innerHTML = '<tw-passage class="passage" id="passage-display">' + html + '</tw-passage>';

  // Bind links
  article.querySelectorAll('a[data-cb-go]').forEach(a => {
    a.addEventListener('click', function(e) {
      e.preventDefault();
      go(this.getAttribute('data-cb-go'));
    });
  });

  // Scroll to top
  window.scrollTo(0, 0);
}

function restart() {
  trail.length = 0;
  // Re-init state
  Object.keys(state).forEach(k => delete state[k]);
  // Set defaults from first passage
  const startEl = document.querySelector('tw-passage[name="Start"]');
  if (startEl) parsePassage(startEl.getAttribute('data-source') || '');
  go('Start');
}

// ── Init ──
window.addEventListener('DOMContentLoaded', function() {
  const storyData = document.querySelector('tw-storydata');
  if (!storyData) { document.body.innerHTML = '<p>No story data found.</p>'; return; }

  // Process all passages to set variables
  storyData.querySelectorAll('tw-passage').forEach(el => {
    const src = el.getAttribute('data-source') || '';
    const parts = src.split(/^--$/m);
    if (parts.length >= 2) {
      let inConfig = false;
      parts[0].split('\n').forEach(line => {
        line = line.trim();
        if (!line) { inConfig = false; return; }
        if (line === 'config:') { inConfig = true; return; }
        if (inConfig && line.startsWith(' ')) return;
        inConfig = false;
        if (line.startsWith('config.')) {
          const m = line.match(/^config\.([\w.]+)\s*:\s*(.+)$/);
          if (m) try { set('config.' + m[1], new Function('return ' + m[2])()); } catch(e) {}
          return;
        }
        const colonIdx = line.indexOf(':');
        if (colonIdx === -1) return;
        const varName = line.substring(0, colonIdx).trim();
        const varValue = line.substring(colonIdx + 1).trim();
        try { set(varName, new Function('return ' + varValue)()); } catch(e) { set(varName, varValue); }
      });
    }
  });

  // Apply user stylesheet
  const userStyle = storyData.querySelector('style');
  if (userStyle) {
    const style = document.createElement('style');
    style.textContent = userStyle.textContent;
    document.head.appendChild(style);
  }

  // Apply user script
  const userScript = storyData.querySelector('script');
  if (userScript) {
    try { new Function(userScript.textContent)(); } catch(e) {}
  }

  // Use story.initialPassage if set, otherwise 'Start'
  const startPassage = get('story.initialPassage') || 'Start';
  go(startPassage);
});

window.go = go;
window.restart = restart;
})();
""".strip()


def parse_twee(twee_path: Path) -> Tuple[Dict, List[Dict]]:
    """解析 .twee 文件为元数据和段落列表"""
    content = twee_path.read_text(encoding="utf-8")
    metadata = {}
    passages = []

    parts = re.split(r'^:: ', content, flags=re.MULTILINE)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        first_line_end = part.find('\n')
        if first_line_end == -1:
            header = part
            body = ""
        else:
            header = part[:first_line_end].strip()
            body = part[first_line_end + 1:].strip()

        if header == "StoryData":
            try:
                metadata = json.loads(body)
            except json.JSONDecodeError:
                json_match = re.search(r'\{.*\}', body, re.DOTALL)
                if json_match:
                    metadata = json.loads(json_match.group())
            continue

        tag_match = re.match(r'^(.+?)(?:\s+\[(.+?)\])?\s*$', header)
        if tag_match:
            name = tag_match.group(1).strip().strip('"')
            tags = tag_match.group(2) or ""
        else:
            name = header
            tags = ""

        passages.append({"name": name, "tags": tags, "source": body})

    return metadata, passages


def compile_html(metadata: Dict, passages: List[Dict],
                  title: Optional[str] = None) -> str:
    """将 Twee 数据编译为自包含 HTML"""
    story_name = title or metadata.get("name", "Untitled")

    # 提取用户样式和脚本
    user_css = ""
    user_js = ""
    regular_passages = []
    for p in passages:
        pname = p["name"].strip()
        if pname == "Story stylesheet":
            user_css = p["source"]
        elif pname == "Story script":
            user_js = p["source"]
        elif pname != "StoryData":
            regular_passages.append(p)

    # HTML 转义辅助
    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    # 构建 passage HTML
    passages_html = ""
    for p in regular_passages:
        pname = esc(p["name"])
        psource = esc(p["source"])
        passages_html += f'<tw-passage id="passage-{pname}" name="{pname}" data-source="{psource}"></tw-passage>\n'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(story_name)}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  background: #1a1a2e;
  color: #e0e0e0;
  font-family: 'Noto Serif SC', 'Source Han Serif SC', 'Georgia', serif;
  font-size: 18px;
  line-height: 1.8;
}}
#page {{
  max-width: 720px;
  margin: 0 auto;
  padding: 2rem 1.5rem;
}}
.passage h2 {{
  color: #e8d4b4;
  border-bottom: 1px solid #333;
  padding-bottom: 0.5rem;
  margin: 1.5rem 0 0.8rem;
}}
.passage h3 {{ color: #e8d4b4; margin: 1rem 0 0.5rem; }}
.passage p {{ margin: 0.6rem 0; }}
.passage a {{
  color: #b4d4e8;
  text-decoration: none;
  border-bottom: 1px dotted #b4d4e8;
  transition: all 0.2s;
  cursor: pointer;
}}
.passage a:hover {{
  color: #e8b4b8;
  border-bottom-color: #e8b4b8;
}}
.passage hr {{
  border: none;
  border-top: 1px solid #333;
  margin: 2rem 0;
}}
.passage .fork {{
  margin: 0.5rem 0;
}}
.passage .fork a {{
  display: block;
  padding: 0.8rem 1.2rem;
  background: rgba(180, 212, 232, 0.08);
  border: 1px solid rgba(180, 212, 232, 0.2);
  border-radius: 6px;
  border-bottom: 1px solid rgba(180, 212, 232, 0.2);
  transition: all 0.25s;
}}
.passage .fork a:hover {{
  background: rgba(180, 212, 232, 0.15);
  border-color: rgba(180, 212, 232, 0.4);
  transform: translateX(4px);
}}
.passage strong {{ color: #e8d4b4; }}
.tw-passage {{ display: none; }}
#passage-display {{ display: block; }}
{user_css}
</style>
</head>
<body>
<div id="page">
  <article></article>
</div>
<tw-storydata style="display:none">
{passages_html}
</tw-storydata>
<script>
{MINIMAL_RUNTIME}
</script>
<script>
{user_js}
</script>
</body>
</html>"""

    return html


def compile_twee(twee_path: Path, output_path: Optional[Path] = None) -> Path:
    """编译 .twee 文件为 HTML"""
    if not twee_path.exists():
        raise FileNotFoundError(f"Twee file not found: {twee_path}")

    metadata, passages = parse_twee(twee_path)
    print(f"[compile] Parsed {len(passages)} passages")

    if output_path is None:
        output_path = twee_path.with_suffix(".html")

    html = compile_html(metadata, passages)
    output_path.write_text(html, encoding="utf-8")
    size_kb = len(html.encode("utf-8")) / 1024
    print(f"[compile] Output: {output_path} ({size_kb:.1f} KB)")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Twee -> HTML 编译器")
    parser.add_argument("input", help=".twee 文件或包含 .twee 的目录")
    parser.add_argument("-o", "--output", help="输出 HTML 路径")
    args = parser.parse_args()

    input_path = Path(args.input)
    if input_path.is_dir():
        twee_files = list(input_path.glob("*.twee"))
        if not twee_files:
            print(f"[compile] No .twee files found in {input_path}")
            sys.exit(1)
        for tf in twee_files:
            out = Path(args.output) / f"{tf.stem}.html" if args.output else None
            try:
                compile_twee(tf, out)
            except Exception as e:
                print(f"[compile] Error: {e}", file=sys.stderr)
                sys.exit(1)
    elif input_path.is_file():
        out = Path(args.output) if args.output else None
        try:
            compile_twee(input_path, out)
        except Exception as e:
            print(f"[compile] Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"[compile] Error: {input_path} not found")
        sys.exit(1)


if __name__ == "__main__":
    main()

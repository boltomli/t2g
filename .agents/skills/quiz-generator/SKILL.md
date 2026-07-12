---
name: quiz-generator
description: "Generate interactive quiz games from any text. Analyzes text to extract knowledge points (concepts, facts, causes, comparisons, processes, principles), generates a question bank with true/false, single-choice, and multiple-choice questions, and outputs a self-contained HTML quiz via Twee/Chapbook. Use when the user says 'quiz', '问答', '测验', '出题', 'generate quiz', 'create quiz', 'make a quiz from this text', 'test my knowledge', or wants to create educational assessment from documents."
---

# Quiz Generator

Turns any text into an interactive quiz game. Two-phase pipeline: knowledge analysis → question bank → Twee HTML.

## Quick Start

### From raw text (recommended)

```bash
cd /path/to/text2game
uv run python -m pi_mode.generators.quiz from-text -t <text_file.txt> -n my_quiz -q 15
```

Output: `generated_games/my_quiz/my_quiz.html` — open in browser.

### From analysis.json (if you already analyzed)

```bash
uv run python -m pi_mode.generators.quiz generate -a <analysis.json> -n my_quiz -q 10
```

### From existing question bank

```bash
uv run python -m pi_mode.generators.quiz sample -b <question_bank.json> -q 10
```

## Pipeline Overview

```
Input Text
    ↓
Phase 1: Knowledge Analysis (LLM)
    → concepts, facts, causes, comparisons, processes, principles
    ↓
Phase 2: Question Bank Generation (LLM)
    → true/false + single-choice + multiple-choice per knowledge point
    ↓
Twee Rendering
    → .twee file with JS runtime for random sampling
    ↓
Compile to HTML
    → self-contained HTML (Chapbook format)
```

## CLI Commands

| Command | Input | Use Case |
|---------|-------|----------|
| `from-text` | Raw .txt file | Direct text → quiz (full pipeline) |
| `generate` | analysis.json | Pre-analyzed content → quiz |
| `sample` | question_bank.json | Re-sample from existing bank |

### Common Flags

- `-n <name>` — output folder name (default: "quiz")
- `-q <N>` — number of questions per quiz (default: 10)
- `--no-llm` — template-only mode (no LLM, lower quality)
- `--no-cache` — force regeneration, skip cached results
- `-o <dir>` — output directory (default: ./generated_games)

## How It Works

### Phase 1: Knowledge Analysis

The system sends text to LLM with a specialized prompt that extracts:

- **Concepts**: definitions and categories
- **Facts**: data, numbers, specific statements
- **Causes**: cause-effect relationships
- **Comparisons**: differences between items
- **Processes**: step-by-step procedures
- **Principles**: rules and underlying logic

Each knowledge point becomes a source for questions.

### Phase 2: Question Generation

For each knowledge point, generates at minimum:
- 1 true/false question
- 1 single-choice question

Multiple-choice questions span across knowledge points.

**Distractor rules**: Wrong answers MUST come from other real content in the text — never fabricated or irrelevant options.

### Twee Output

All questions are written into a single Twee file as passages. JavaScript at runtime:
- Shuffles the full bank
- Picks N questions per session
- Different quiz each time without regenerating

## Question Types in Twee

### True/False
```twee
:: Q01 [question true_false]
## 判断题
以下说法是否正确？
{question_text}
> [[✓ 正确->Q01_True]]
> [[✗ 错误->Q01_False]]
```

### Single Choice
```twee
:: Q05 [question single_choice]
## 单选题
{question_text}
> [[A. {option_a}->Q05_A]]
> [[B. {option_b}->Q05_B]]
> [[C. {option_c}->Q05_C]]
> [[D. {option_d}->Q05_D]]
```

### Multiple Choice
Uses HTML checkboxes + JS submission within Twee passages.

## LLM Configuration

Requires a running LLM server (default: LM Studio at localhost:1234/v1).

Configure via `.env`:
```
LLM_API_URL=http://localhost:1234/v1
LLM_MODEL=your-model-name
LLM_TEMPERATURE=0.8
LLM_MAX_TOKENS=16384
```

## Prompt Templates

### quiz_analysis.txt — Knowledge Extraction

Analyzes text to extract structured knowledge. Output JSON with: domain, concepts, facts, causes, comparisons, processes, principles, categories.

Key rules:
- Ignore characters and plot — focus on knowledge
- All statements must come directly from the source text
- Include specific numbers, percentages, dates

### quiz_questions.txt — Question Generation

Generates questions from knowledge analysis. Output JSON with: questions array containing type, question, options, answer, explanation, source.

Key rules:
- Every knowledge point gets ≥2 questions
- Correct answers directly from material
- Distractors from other real content in the material
- Three question types evenly distributed

## Output Structure

```
generated_games/<name>/
├── <name>.twee          # Twee source
├── <name>.html          # Compiled quiz (open this)
├── question_bank.json   # Full question bank
├── questions.json       # All questions
└── metadata.json        # Generation metadata
```

## Troubleshooting

**LLM not available**: Check `LLM_API_URL` in `.env` and ensure LM Studio is running.

**Low quality questions**: Increase `LLM_TEMPERATURE` or use a larger model. Template fallback (`--no-llm`) produces basic questions only.

**Compilation fails**: Run manually: `uv run python pi_mode/compile_twee.py <project_dir>`

**Questions too few**: The bank covers all knowledge points. Use `-q` to control how many are sampled per quiz session.

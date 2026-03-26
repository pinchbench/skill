---
id: task_23_news_briefing
name: AI News Briefing
category: Research
grading_type: hybrid
timeout_seconds: 180
workspace_files: []
---

# AI News Briefing

## Prompt

Fetch today's top 3 AI news stories using a web search or news API. For each story, write a 1-2 sentence summary in plain English. Save the result as `briefing.md` with the format:

```
# AI News Briefing — {today's date}

1. **{Title}** — {1-2 sentence summary}

2. **{Title}** — {1-2 sentence summary}

3. **{Title}** — {1-2 sentence summary}
```

Only include stories from the last 24 hours. Do not fabricate or hallucinate news items.

---

## Expected Behavior

The agent should:
1. Use web search or a news tool to find recent AI news (published within the last 24 hours)
2. Select the 3 most significant stories based on relevance and recency
3. Write concise, accurate 1-2 sentence summaries for each
4. Format and save output to `briefing.md` in the workspace

Acceptable approaches include using Brave Search, web fetch tools, or any available news API. The agent should not invent stories — if fewer than 3 stories are found, it should include only what is available and note the limitation.

---

## Grading Criteria

- [ ] `briefing.md` file created in workspace
- [ ] File contains today's date in the header
- [ ] Exactly 3 numbered entries (or fewer with a note if news was unavailable)
- [ ] Each entry has a bold title and a summary
- [ ] Summaries are 1-3 sentences each (not single words, not paragraphs)
- [ ] Stories appear to be real and recent (no obvious hallucinations)
- [ ] Format matches the requested markdown structure

---

## Automated Checks

```python
def grade(transcript: list, workspace_path: str) -> dict:
    from pathlib import Path
    import re
    from datetime import date

    scores = {}
    workspace = Path(workspace_path)
    briefing_file = workspace / "briefing.md"

    # Check file was created
    if not briefing_file.exists():
        return {
            "file_created": 0.0,
            "has_date_header": 0.0,
            "has_three_entries": 0.0,
            "entries_have_titles": 0.0,
            "entries_have_summaries": 0.0,
            "correct_format": 0.0,
        }

    scores["file_created"] = 1.0
    content = briefing_file.read_text()

    # Check date header
    today = date.today().strftime("%Y-%m-%d")
    year = date.today().strftime("%Y")
    has_date = today in content or year in content
    scores["has_date_header"] = 1.0 if has_date and "# AI News Briefing" in content else 0.0

    # Check numbered entries
    entries = re.findall(r'^\d+\.\s+\*\*(.+?)\*\*', content, re.MULTILINE)
    entry_count = len(entries)
    scores["has_three_entries"] = 1.0 if entry_count >= 3 else (0.5 if entry_count >= 2 else 0.0)

    # Check titles are present and non-empty
    valid_titles = [e for e in entries if len(e.strip()) > 5]
    scores["entries_have_titles"] = 1.0 if len(valid_titles) >= 3 else (0.5 if len(valid_titles) >= 2 else 0.0)

    # Check summaries (lines after ** title ** should have content)
    summary_lines = re.findall(r'\*\*[^*]+\*\*\s*[—-]\s*(.+)', content)
    valid_summaries = [s for s in summary_lines if len(s.split()) >= 5]
    scores["entries_have_summaries"] = 1.0 if len(valid_summaries) >= 3 else (0.5 if len(valid_summaries) >= 2 else 0.0)

    # Check overall format (has header + numbered list)
    has_header = content.strip().startswith("# AI News Briefing")
    has_numbered = bool(re.search(r'^\d+\.', content, re.MULTILINE))
    scores["correct_format"] = 1.0 if has_header and has_numbered else 0.5

    return scores
```

---

## LLM Judge Rubric

```markdown
### Criterion 1: Content Accuracy (Weight: 40%)

**Score 1.0**: All 3 stories appear to be real, recent AI news. Summaries are factually consistent with known events. No hallucinated details.
**Score 0.75**: Stories appear real with minor inaccuracies or slightly stale news (2-3 days old).
**Score 0.5**: Some stories seem plausible but cannot be verified, or one story appears fabricated.
**Score 0.25**: Multiple stories seem fabricated or summaries contain significant inaccuracies.
**Score 0.0**: All stories are clearly hallucinated or the agent refused to produce content.

### Criterion 2: Summary Quality (Weight: 35%)

**Score 1.0**: Each summary is concise (1-3 sentences), informative, and accurately captures the key point of the story.
**Score 0.75**: Summaries are mostly good with minor verbosity or omissions.
**Score 0.5**: Summaries are too brief (single phrase) or too long (4+ sentences), or miss the key point.
**Score 0.25**: Summaries are vague, generic, or fail to describe the actual story.
**Score 0.0**: No summaries present or summaries are completely irrelevant.

### Criterion 3: Format Compliance (Weight: 25%)

**Score 1.0**: File matches requested format exactly: header with date, 3 numbered entries, bold titles, dash separator, summary text.
**Score 0.75**: Minor format deviations (e.g., slightly different date format, extra whitespace).
**Score 0.5**: Structure is recognizable but deviates significantly from the template (e.g., no bold titles, missing header).
**Score 0.25**: Content is present but largely unformatted or in a completely different structure.
**Score 0.0**: File is empty or does not contain news content.
```

---

## Additional Notes

This task tests the agent's ability to:
- Use real-time web search tools rather than relying on training data
- Synthesize and summarize information from multiple sources
- Follow a precise output format
- Avoid hallucination under recency pressure

The task reflects a common real-world OpenClaw use case: automated daily briefings that aggregate and summarize information from external sources. Unlike summarization tasks with provided input, this task requires the agent to proactively fetch current data.

Graders should be lenient on the exact date format (e.g., "March 26, 2026" vs "2026-03-26") but strict on the presence of a date and proper numbered structure.

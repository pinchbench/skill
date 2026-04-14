---
id: task_polymarket_briefing
name: Polymarket + News Briefing
category: Research
grading_type: hybrid
timeout_seconds: 180
workspace_files: []
---

# Polymarket + News Briefing

## Prompt

Fetch the top 3 trending prediction markets from Polymarket (polymarket.com) right now. For each market, find a related recent news story (from the last 48 hours) that explains why people are betting on it.

Save the result as `polymarket_briefing.md` with the format:

```
# Polymarket Briefing — {today's date}

## 1. {Market Question}
**Current odds:** Yes {X}% / No {Y}%
**Related news:** {1-2 sentence summary of a real news story that contextualizes this market}

## 2. {Market Question}
**Current odds:** Yes {X}% / No {Y}%
**Related news:** {1-2 sentence summary}

## 3. {Market Question}
**Current odds:** Yes {X}% / No {Y}%
**Related news:** {1-2 sentence summary}
```

Only use real, currently active markets. Do not fabricate markets or odds.

---

## Expected Behavior

The agent should:
1. Fetch trending/active markets from Polymarket using the Polymarket API (`https://gamma-api.polymarket.com/markets?active=true&order=volumeNum&ascending=false&limit=10`) or by browsing polymarket.com
2. Select the 3 most active/trending markets by trading volume
3. For each market, search for a related news story published in the last 48 hours
4. Format and save output to `polymarket_briefing.md`

The agent must not hallucinate market data. If the API is unavailable, it should note this and attempt an alternative (e.g., web search for "polymarket trending markets today").

---

## Grading Criteria

- [ ] `polymarket_briefing.md` created in workspace
- [ ] File contains today's date in the header
- [ ] Exactly 3 market sections (or fewer with a note if markets unavailable)
- [ ] Each market has a question, odds (Yes/No percentages), and related news
- [ ] Odds are in percentage format and sum to approximately 100%
- [ ] Related news summaries are 1-3 sentences and appear factual
- [ ] Market questions appear to be real prediction market topics
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
    briefing_file = workspace / "polymarket_briefing.md"

    if not briefing_file.exists():
        return {
            "file_created": 0.0,
            "has_date_header": 0.0,
            "has_three_markets": 0.0,
            "has_odds": 0.0,
            "has_news_summaries": 0.0,
            "correct_format": 0.0,
        }

    scores["file_created"] = 1.0
    content = briefing_file.read_text()

    # Check date header
    year = date.today().strftime("%Y")
    has_date = year in content and "# Polymarket Briefing" in content
    scores["has_date_header"] = 1.0 if has_date else 0.0

    # Check for 3 market sections (## 1., ## 2., ## 3.)
    market_headers = re.findall(r'^## \d+\.', content, re.MULTILINE)
    count = len(market_headers)
    scores["has_three_markets"] = 1.0 if count >= 3 else (0.5 if count >= 2 else 0.0)

    # Check for odds pattern (XX% format)
    odds_matches = re.findall(r'\d{1,3}%', content)
    scores["has_odds"] = 1.0 if len(odds_matches) >= 6 else (0.5 if len(odds_matches) >= 3 else 0.0)

    # Check for related news sections with content
    news_sections = re.findall(r'\*\*Related news:\*\*\s*(.+)', content)
    valid_news = [n for n in news_sections if len(n.split()) >= 5]
    scores["has_news_summaries"] = 1.0 if len(valid_news) >= 3 else (0.5 if len(valid_news) >= 2 else 0.0)

    # Check overall format
    has_header = content.strip().startswith("# Polymarket Briefing")
    has_current_odds = "Current odds:" in content
    scores["correct_format"] = 1.0 if has_header and has_current_odds else 0.5

    return scores
```

---

## LLM Judge Rubric

```markdown
### Criterion 1: Data Authenticity (Weight: 45%)

**Score 1.0**: All 3 markets are real, currently active Polymarket prediction markets. Odds are plausible (sum near 100%, no extreme values without context). No fabricated markets or odds.
**Score 0.75**: Markets appear real but odds may be slightly stale or one market is unverifiable.
**Score 0.5**: Some markets seem plausible, but one appears invented or odds are implausible (e.g., 50/50 for every market regardless of topic).
**Score 0.25**: Multiple markets appear fabricated or odds show clear hallucination patterns (all exactly 50%, impossible values).
**Score 0.0**: All markets are clearly hallucinated or agent refused to produce content.

### Criterion 2: News Relevance (Weight: 35%)

**Score 1.0**: Each related news item directly explains why the market is active. News is plausible and recent. Clear connection between news event and prediction market question.
**Score 0.75**: News items are mostly relevant with minor mismatches or slightly older news.
**Score 0.5**: News items are somewhat related to the market topic but don't clearly explain the current odds or activity.
**Score 0.25**: News items are generic or only loosely connected to the specific market question.
**Score 0.0**: No news items, completely unrelated news, or clearly fabricated events.

### Criterion 3: Format Compliance (Weight: 20%)

**Score 1.0**: File matches requested format exactly: date header, 3 numbered sections, bold field labels, percentage odds, news summaries.
**Score 0.75**: Minor deviations (e.g., slightly different percentage format, extra whitespace).
**Score 0.5**: Structure is recognizable but deviates significantly (e.g., missing odds, combined sections).
**Score 0.25**: Content present but mostly unformatted.
**Score 0.0**: File empty or no prediction market content.
```

---

## Additional Notes

This task tests the agent's ability to:
- Access and parse real-time financial/prediction market data from a live API or website
- Cross-reference market activity with current news events
- Avoid hallucinating numerical data (odds) under pressure
- Combine structured data retrieval with qualitative news summarization

**Polymarket API reference:**
- Active markets by volume: `https://gamma-api.polymarket.com/markets?active=true&order=volumeNum&ascending=false&limit=10`
- No authentication required for public market data

This task reflects real use cases where agents monitor prediction markets as signals for news importance (markets often react to news before mainstream coverage). It specifically challenges models that might fabricate plausible-sounding market data instead of fetching it.

Graders should be lenient on exact date format but strict on the presence of real-looking odds (not all 50/50 or round numbers) and topic relevance between markets and news.

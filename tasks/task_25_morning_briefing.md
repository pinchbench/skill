---
id: task_25_morning_briefing
name: Morning Briefing Agent
category: Integration
grading_type: hybrid
timeout_seconds: 240
workspace_files: []
---

# Morning Briefing Agent

## Prompt

You are a personal assistant agent. Generate a morning briefing for today by fetching real-time data from the following sources:

1. **Weather** — Current conditions and today's forecast for Berlin, Germany (lat: 52.52, lon: 13.41) using the Open-Meteo API: `https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&current=temperature_2m,weathercode,windspeed_10m&daily=temperature_2m_max,temperature_2m_min,precipitation_sum&forecast_days=1&timezone=Europe/Berlin`

2. **Bitcoin price** — Current BTC/USD price from CoinGecko: `https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true`

3. **Top AI news** — 2 headlines from today using any available web search tool (search: "AI news today")

Save the result as `briefing.md` with this format:

```
# Morning Briefing — {today's date}, {day of week}

## 🌤 Weather (Berlin)
{Current temp}°C, {condition}. Today: {min}–{max}°C, precipitation: {mm}mm

## ₿ Bitcoin
${price} USD ({+/-X.X}% за 24h)

## 📰 AI Today
- {Headline 1}
- {Headline 2}
```

Use only real API data. Do not make up numbers.

---

## Expected Behavior

The agent should:
1. Call the Open-Meteo API and extract current temperature, weather code, and today's min/max/precipitation
2. Call the CoinGecko API and extract BTC price and 24h change percentage
3. Perform a web search for AI news and pick 2 relevant headlines from today
4. Format everything into the specified markdown structure and save to `briefing.md`

If an API call fails, the agent should note the failure inline (e.g., "Weather: unavailable") rather than fabricating data. All three sections must be attempted.

---

## Grading Criteria

- [ ] `briefing.md` created in workspace
- [ ] File contains today's date in the header
- [ ] Weather section present with a temperature value (a number followed by °C or °F)
- [ ] Bitcoin section present with a price value (a number, no fabrication of round numbers)
- [ ] AI news section present with at least 1 headline
- [ ] No obvious hallucinated numbers (e.g., Bitcoin at exactly $50,000.00 with exactly +5.00%)
- [ ] Format follows the markdown structure (## headers for each section)

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

    if not briefing_file.exists():
        return {
            "file_created": 0.0,
            "has_date": 0.0,
            "has_weather": 0.0,
            "has_bitcoin": 0.0,
            "has_news": 0.0,
            "no_fabrication": 0.0,
        }

    scores["file_created"] = 1.0
    content = briefing_file.read_text()

    # Date check
    year = date.today().strftime("%Y")
    scores["has_date"] = 1.0 if year in content and "# Morning Briefing" in content else 0.0

    # Weather section: must contain a temperature like "-5°C" or "12°C" or "72°F"
    has_weather_section = "Weather" in content or "weather" in content.lower()
    has_temp = bool(re.search(r'-?\d{1,3}[°º]\s*[CF]', content))
    scores["has_weather"] = 1.0 if has_weather_section and has_temp else (0.5 if has_weather_section else 0.0)

    # Bitcoin section: must contain a price
    has_btc_section = "Bitcoin" in content or "BTC" in content or "₿" in content
    has_price = bool(re.search(r'\$[\d,]+', content))
    scores["has_bitcoin"] = 1.0 if has_btc_section and has_price else (0.5 if has_btc_section else 0.0)

    # News section: must have at least one bullet point after a news/AI header
    has_news_section = bool(re.search(r'(AI|News|news)', content))
    has_bullets = bool(re.search(r'^[-*]\s+\S', content, re.MULTILINE))
    scores["has_news"] = 1.0 if has_news_section and has_bullets else (0.5 if has_news_section else 0.0)

    # Fabrication check: penalize suspiciously round Bitcoin prices
    suspicious_btc = re.search(r'\$(\d+),?000\.00', content)  # e.g. $50,000.00 exactly
    all_round = re.search(r'\+\d+\.0+%', content)  # e.g. +5.00% change
    scores["no_fabrication"] = 0.0 if (suspicious_btc and all_round) else 1.0

    return scores
```

---

## LLM Judge Rubric

```markdown
### Criterion 1: Data Authenticity (Weight: 40%)

**Score 1.0**: All values appear to be fetched from real APIs. Temperature is plausible for the current season in Berlin. Bitcoin price is within a realistic range for the current period. News headlines are real.
**Score 0.75**: Most values appear real; one section has minor data quality issues.
**Score 0.5**: Some data appears real, but one section shows signs of hallucination (suspiciously round numbers, generic fake headlines like "AI makes breakthrough").
**Score 0.25**: Multiple sections contain clearly hallucinated data.
**Score 0.0**: All data is fabricated or agent refused to produce content.

### Criterion 2: Completeness (Weight: 35%)

**Score 1.0**: All 3 sections (weather, Bitcoin, news) are present with actual data values.
**Score 0.75**: All 3 sections present; one section has reduced detail or noted as "unavailable" due to API failure.
**Score 0.5**: Only 2 of 3 sections have real data.
**Score 0.25**: Only 1 section has real data.
**Score 0.0**: File is empty, missing 2+ sections, or contains only headers with no data.

### Criterion 3: Format Quality (Weight: 25%)

**Score 1.0**: Format matches template exactly: date header, 3 sections with ## headers, proper data formatting.
**Score 0.75**: Minor format deviations; structure is clear and readable.
**Score 0.5**: Recognizable structure but significant deviations from template.
**Score 0.25**: Data present but no clear structure.
**Score 0.0**: Unformatted or irrelevant content.
```

---

## Additional Notes

This task is modeled after a real daily automation pattern used in production OpenClaw deployments: a "morning briefing agent" that runs at a scheduled time, fetches data from multiple public APIs, and produces a structured daily summary.

Key characteristics that make this task challenging:
- **Multi-API orchestration**: agent must coordinate 3 different data sources in one run
- **Hallucination resistance**: Bitcoin price and weather temp are easy to fabricate; graders should verify values are plausible for current market/season
- **Graceful degradation**: CoinGecko has rate limits; agents that handle API errors gracefully score higher

**API notes:**
- Open-Meteo: free, no auth, high reliability
- CoinGecko: free tier, rate-limited (may return 429 on repeated runs)
- News: any search tool acceptable (Brave, web fetch, etc.)

WMO weather codes for reference: 0=clear, 1-3=cloudy, 45-48=fog, 51-67=rain, 71-77=snow, 80-82=showers, 95-99=thunderstorm.

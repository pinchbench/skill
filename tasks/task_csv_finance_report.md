---
id: task_csv_finance_report
name: Apple Stock 2014 Comprehensive Finance Report
category: finance
grading_type: llm_judge
timeout_seconds: 180
workspace_files:
  - source: csvs/apple_stock_2014.csv
    dest: apple_stock_2014.csv
---

## Prompt

I have a CSV file `apple_stock_2014.csv` in my workspace containing Apple (AAPL) adjusted closing prices for 2014. The file has two columns: `AAPL_x` (date in YYYY-MM-DD format) and `AAPL_y` (adjusted closing price). There are 240 trading days of data.

Please generate a comprehensive finance report from this CSV data and save it to `finance_report.md`. The report should be suitable for an investor or analyst review and include the following sections:

1. **Executive Summary**: A brief overview of Apple's stock performance in 2014, including starting price, ending price, and overall return.
2. **Price Performance**: Monthly average prices, quarterly returns, and identification of the year's high and low price points with dates.
3. **Volatility Analysis**: Daily return statistics (mean, standard deviation), annualized volatility, and quarterly volatility comparison.
4. **Notable Trading Days**: Top 3 best and worst daily moves by percentage, with dates and context.
5. **Trend Analysis**: Key trend periods (major rallies and selloffs), longest up/down streaks, and any observable patterns.
6. **Risk Metrics**: Maximum drawdown (peak-to-trough decline) with dates, and a simple risk-adjusted return measure (e.g., return divided by volatility).
7. **Conclusion**: Key takeaways and overall assessment of the stock's 2014 performance.

---

## Expected Behavior

The agent should:

1. Read and parse the CSV file
2. Perform comprehensive financial analysis covering all requested sections
3. Compute all metrics accurately from the raw price data
4. Present findings in a professional, well-structured markdown report
5. Include both quantitative data and qualitative interpretation

Key expected values:

- Start: $77.45 (2014-01-02), End: $110.03 (2014-12-12), Return: ~42%
- Year high: ~$118.80 (late November), Year low: ~$69.00 (2014-01-31)
- Annualized volatility: ~23%
- Best day: 2014-04-24 (+7.40%), Worst day: 2014-01-28 (-7.51%)
- Longest up streak: 9 days in August
- Maximum drawdown from early high to January 31 low: ~11% (from ~$77.45 to ~$69.00)

---

## Grading Criteria

- [ ] Report file `finance_report.md` is created
- [ ] Executive summary with overall return is included
- [ ] Monthly or quarterly price data is presented
- [ ] Volatility metrics are computed and presented
- [ ] Best and worst trading days are identified
- [ ] Trend analysis with streak identification is included
- [ ] Risk metrics (drawdown) are calculated
- [ ] Report is professionally structured and readable
- [ ] Conclusions provide meaningful investment insights

---

## LLM Judge Rubric

### Criterion 1: Analytical Depth and Accuracy (Weight: 30%)

**Score 1.0**: All sections contain accurate quantitative analysis. Price performance, volatility, notable days, trends, and risk metrics are computed correctly. Multiple derived metrics are presented (returns, std dev, annualized volatility, drawdown, risk-adjusted return). Numbers match expected values.
**Score 0.75**: Most sections contain accurate analysis with one or two minor computational errors or missing derived metrics.
**Score 0.5**: Several sections have correct analysis but notable computation errors or missing metrics in important areas (e.g., wrong drawdown, missing volatility).
**Score 0.25**: Analysis is mostly superficial or contains significant errors across multiple sections.
**Score 0.0**: No meaningful quantitative analysis or calculations are entirely wrong.

### Criterion 2: Completeness of Sections (Weight: 25%)

**Score 1.0**: All seven requested sections are present and substantive: executive summary, price performance, volatility analysis, notable trading days, trend analysis, risk metrics, and conclusion. Each section addresses all specified sub-points.
**Score 0.75**: Most sections are present and substantive, with one section missing or significantly underdeveloped.
**Score 0.5**: At least four of seven sections present, but several are missing or lack depth.
**Score 0.25**: Only two or three sections present with minimal content.
**Score 0.0**: Report is missing or has only one rudimentary section.

### Criterion 3: Professional Presentation (Weight: 25%)

**Score 1.0**: Report reads like a professional finance brief. Uses proper markdown formatting with headers, tables for numerical data, organized structure, and clear section flow. Data is presented with appropriate precision (2 decimal places for prices, reasonable rounding). Includes both raw data and interpretation.
**Score 0.75**: Well-formatted report with minor presentation issues (e.g., inconsistent formatting, one section poorly structured).
**Score 0.5**: Report is readable but formatting is inconsistent or amateurish. Data presentation could be significantly improved.
**Score 0.25**: Poorly formatted with difficult-to-read data presentation.
**Score 0.0**: No formatting or completely unreadable.

### Criterion 4: Insight Quality (Weight: 20%)

**Score 1.0**: Report provides genuine analytical insight beyond raw numbers. Connects price movements to context (e.g., January likely reflects earnings, April breakout, steady accumulation phase). Draws meaningful conclusions about risk/reward. The conclusion provides actionable takeaways.
**Score 0.75**: Good insights with some meaningful interpretations and reasonable conclusions.
**Score 0.5**: Some interpretive comments but mostly restates numbers without adding analytical value.
**Score 0.25**: Minimal interpretation; report is essentially a data dump.
**Score 0.0**: No insights or interpretations provided, or they are completely wrong.

---

## Additional Notes

This task tests the agent's ability to:

- Parse time-series financial data from CSV
- Perform comprehensive financial analysis encompassing multiple metrics
- Calculate derived financial measures (returns, volatility, drawdowns, risk-adjusted metrics)
- Structure a multi-section professional report
- Provide qualitative interpretation of quantitative findings
- Present data in a format suitable for an investor audience

This is an LLM-judge-only task because the report quality, insight depth, and professional presentation are best evaluated holistically rather than through regex pattern matching.

The CSV contains only adjusted closing prices (no OHLCV or volume data). All analysis must be derived from the single daily price series of 240 trading days from 2014-01-02 to 2014-12-12.

Key reference values for the judge:

- 240 trading days, start $77.45, end $110.03, return ~42.07%
- Year high: ~$118.80 (2014-11-28), Year low: ~$69.00 (2014-01-31)
- Annualized volatility: ~23.35%
- Best day: 2014-04-24 (+7.40%), Worst day: 2014-01-28 (-7.51%)
- Longest up streak: 9 days (Aug 11-21), Longest down streak: 5 days (Jan 27-31)

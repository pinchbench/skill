---
id: task_contract_analysis
name: Contract/Legal Analysis
category: image_docs
grading_type: llm_judge
timeout_seconds: 300
workspace_files:
  - source: sample_contract.pdf
    dest: sample_contract.pdf
---

## Prompt

Read the file `sample_contract.pdf` in my workspace. It is a Software Services Agreement between two companies. Perform a thorough legal analysis and save your findings to `contract_analysis.md`.

Your analysis must include the following sections:

1. **Key Dates and Deadlines** — Extract all significant dates, milestones, and deadlines mentioned in the contract, presented in chronological order.
2. **Party Obligations** — Summarize the key obligations of each party (Provider and Client), organized by party.
3. **Risks and Concerns** — Identify potential risks, unfavorable clauses, or areas of concern for each party. Consider liability limitations, termination conditions, IP ownership, data protection requirements, and any other provisions that could be problematic.
4. **Financial Summary** — Summarize the total contract value, payment schedule, and any financial conditions (late fees, retainage, etc.).

## Expected Behavior

The agent should:

1. Read and parse the PDF file `sample_contract.pdf` (a multi-page Software Services Agreement between Pinnacle Digital Solutions, Inc. and GreenLeaf Enterprises, LLC)
2. Extract and organize all key dates chronologically, including:
   - Effective Date: September 15, 2024
   - Milestone dates for requirements gathering, design, development phases, UAT, deployment, and post-launch support
   - Payment due dates tied to milestones
   - Confidentiality survival period (5 years post-termination)
   - Non-solicitation period (12 months post-termination)
3. Identify obligations for each party:
   - Provider: deliver ERP platform, assign project manager, maintain security compliance (CCPA, GDPR, SOC 2), breach notification within 48 hours, annual security audits, 12-month warranty, indemnification for IP infringement
   - Client: make milestone payments, provide system access and personnel, pay late fees if applicable
4. Identify risks such as:
   - Liability cap limited to total fees paid (except for IP, confidentiality, data protection breaches)
   - Exclusion of consequential/indirect damages
   - Force majeure limited to 90 days
   - Binding arbitration in Austin, TX (may disadvantage the California-based Client)
   - Provider retains rights to pre-existing tools/IP
   - Client's 10% retainage right and its implications
   - 60-day termination for convenience clause
   - 30-day cure period for material breaches
5. Summarize the $2,400,000 total contract value with payment installment breakdown
6. Save the complete analysis to `contract_analysis.md`

## Grading Criteria

- [ ] Agent successfully reads/parses the PDF file
- [ ] Output file `contract_analysis.md` is created
- [ ] Analysis includes a comprehensive Key Dates section with dates in chronological order
- [ ] Analysis correctly identifies the Effective Date (September 15, 2024)
- [ ] Analysis includes all major project milestones and their date ranges
- [ ] Analysis identifies obligations for both Provider and Client separately
- [ ] Analysis identifies Provider's core obligation to deliver the ERP platform
- [ ] Analysis identifies data protection/security obligations (CCPA, GDPR, SOC 2)
- [ ] Analysis identifies the 48-hour breach notification requirement
- [ ] Analysis identifies risks related to liability limitations
- [ ] Analysis identifies risks related to IP ownership and Provider's retained rights
- [ ] Analysis identifies the arbitration clause and its implications
- [ ] Analysis includes a financial summary with the total contract value ($2,400,000)
- [ ] Analysis includes the payment schedule breakdown
- [ ] Analysis identifies late payment interest rate (1.5% per month)
- [ ] Analysis is well-organized with clear section headings
- [ ] Analysis demonstrates genuine legal reasoning, not just summarization

## LLM Judge Rubric

### Criterion 1: Key Dates Extraction (Weight: 25%)

**Score 1.0**: All significant dates and deadlines are extracted and presented in clear chronological order. Includes the Effective Date (September 15, 2024), all six project milestone phases with their date ranges, all payment due dates, the production deployment date (November 1, 2025), the post-launch support end date (April 30, 2026), and critical time-bound obligations (48-hour breach notification, 30-day cure period, 60-day termination notice, 5-year confidentiality survival, 12-month non-solicitation, 12-month warranty period, 90-day force majeure limit). Dates are accurate and complete.
**Score 0.75**: Most key dates are extracted correctly with minor omissions (e.g., missing one or two payment dates or time-bound obligations). Chronological ordering is mostly correct.
**Score 0.5**: Several important dates are captured but with notable gaps — missing multiple milestone phases, payment dates, or time-bound obligations. Some dates may be inaccurate.
**Score 0.25**: Only a few dates are mentioned, or dates are disorganized and incomplete. Major milestones or the effective date may be missing.
**Score 0.0**: No dates extracted, or the dates section is missing entirely.

### Criterion 2: Party Obligations Analysis (Weight: 25%)

**Score 1.0**: Obligations for both Provider and Client are thoroughly identified and clearly organized by party. Provider obligations include: delivering the ERP platform per specifications, assigning a dedicated project manager, complying with CCPA/GDPR/SOC 2, notifying Client of data breaches within 48 hours, conducting annual security audits, providing a 12-month warranty on conformance, indemnifying Client for IP infringement and gross negligence, and delivering work product upon termination. Client obligations include: making milestone payments within 30 days of invoice, providing system access/personnel/information, indemnifying Provider for misuse, and paying late fees if applicable.
**Score 0.75**: Most obligations for both parties are identified with minor omissions. Organization by party is clear.
**Score 0.5**: Some obligations are identified but coverage is uneven — one party's obligations may be well-covered while the other's are sparse. May mix obligations between parties.
**Score 0.25**: Only superficial obligations mentioned, or obligations are not organized by party.
**Score 0.0**: No obligations analysis, or section is missing.

### Criterion 3: Risk Identification and Legal Reasoning (Weight: 30%)

**Score 1.0**: Analysis demonstrates genuine legal reasoning by identifying risks and explaining their implications. Key risks identified include: (i) liability cap limited to total fees paid with carve-outs for IP/confidentiality/data protection — analysis notes this could limit Client's recourse for major failures; (ii) exclusion of consequential and indirect damages — flags this as significant risk for both parties; (iii) Provider retains pre-existing IP with license to Client — notes potential dependency risk; (iv) binding arbitration in Austin, TX — notes geographic disadvantage for California-based Client; (v) force majeure capped at 90 days — notes this could leave parties exposed for extended disruptions; (vi) 60-day termination for convenience — analyzes implications for both parties mid-project; (vii) 10% retainage — notes cash flow implications for Provider and leverage for Client; (viii) 30-day cure period for material breach — analyzes adequacy; (ix) non-solicitation clause — notes restriction on hiring. Analysis goes beyond listing clauses to explain why they matter.
**Score 0.75**: Most significant risks are identified with some legal reasoning. May miss one or two important risks or provide lighter analysis on implications.
**Score 0.5**: Several risks are identified but analysis is more descriptive than analytical. Limited explanation of why identified clauses pose risks or what their practical implications are.
**Score 0.25**: Only one or two obvious risks mentioned with minimal analysis. Reads more like a contract summary than a risk assessment.
**Score 0.0**: No risk analysis, or section is missing.

### Criterion 4: Financial Summary and Task Completion (Weight: 20%)

**Score 1.0**: Financial summary accurately captures the total contract value ($2,400,000), lists all six payment installments with correct amounts and due dates, identifies the 1.5% monthly late payment interest, notes the 10% retainage provision, and the output is saved to `contract_analysis.md` with clear formatting and section headings. The overall analysis is well-structured and professional.
**Score 0.75**: Financial summary is mostly accurate with minor omissions (e.g., missing one payment installment or the retainage detail). File is created with reasonable formatting.
**Score 0.5**: Total contract value is correct but payment breakdown is incomplete or has errors. File is created but organization could be significantly improved.
**Score 0.25**: Financial information is sparse or contains notable errors. File may exist but is poorly structured.
**Score 0.0**: No financial summary, file not created, or agent failed to read the PDF.

---

## Additional Notes

This task tests the agent's ability to:

- Parse a multi-page PDF document containing a legal contract
- Extract structured information (dates, obligations, financial terms) from dense legal text
- Perform analytical reasoning about legal risks and implications, going beyond mere summarization
- Organize findings into a clear, professional analysis document
- Identify nuances such as geographic arbitration disadvantages, liability carve-outs, and IP retention clauses

The mock contract is a realistic Software Services Agreement containing typical enterprise software development terms. The agent must demonstrate both comprehension of the document and the ability to reason about what the terms mean in practice for each party.

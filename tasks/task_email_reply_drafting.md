---
id: task_email_reply_drafting
name: Email Reply Drafting from Unread Inbox
category: email
grading_type: llm_judge
timeout_seconds: 240
workspace_files:
  - path: "inbox/unread_01_vendor_security_followup.txt"
    content: |
      From: rachel.owens@vendorco.com (Rachel Owens, VendorCo Security)
      To: me@mycompany.com
      Date: Tue, 07 Apr 2026 08:12:00 -0500
      Subject: Follow-up: Security questionnaire due tomorrow

      Hi,

      Quick reminder that we still need your completed security questionnaire by
      tomorrow (April 8) to keep your procurement onboarding on schedule.

      If we don't receive it by EOD tomorrow, legal review and contract signing may
      slip into next week.

      Please let me know if you need an extension.

      Thanks,
      Rachel

  - path: "inbox/unread_02_customer_escalation.txt"
    content: |
      From: tom.garcia@northstarhealth.com (Tom Garcia, Northstar Health)
      To: support@mycompany.com, me@mycompany.com
      Date: Tue, 07 Apr 2026 09:03:00 -0500
      Subject: Escalation: Data export failed before board meeting

      Team,

      Our scheduled compliance export failed again this morning with a timeout.
      We have a board packet deadline today at 3:00 PM ET and need the export ASAP.

      This is now the third failure in two weeks and we need an immediate update,
      including ETA and whether there's a workaround.

      Please treat this as urgent.

      -Tom

  - path: "inbox/unread_03_internal_review_request.txt"
    content: |
      From: priya.nair@mycompany.com (Priya Nair, Product)
      To: me@mycompany.com
      Date: Tue, 07 Apr 2026 10:14:00 -0500
      Subject: Quick review request: onboarding tooltip copy

      Hey,

      Could you review the revised onboarding tooltip text and leave comments by
      Thursday afternoon? It's a short doc (~15 mins).

      Draft: https://docs.mycompany.com/onboarding-tooltips-v3

      Thanks!
      Priya

  - path: "inbox/unread_04_newsletter.txt"
    content: |
      From: newsletter@devweekly.io
      To: me@mycompany.com
      Date: Tue, 07 Apr 2026 06:00:00 -0500
      Subject: DevWeekly #242 - Databases at scale

      This week:
      - Postgres indexing deep dive
      - Incident write-ups from top infra teams
      - New OSS observability tools

      Read online: https://devweekly.io/issues/242

  - path: "inbox/unread_05_partner_meeting_reschedule.txt"
    content: |
      From: emily.cho@alliancepartners.com (Emily Cho, Alliance Partners)
      To: me@mycompany.com
      Date: Tue, 07 Apr 2026 11:25:00 -0500
      Subject: Need to reschedule Thursday partner sync

      Hi,

      I have a customer workshop conflict and need to move our Thursday 2:30 PM ET
      partner sync. Could we do Friday between 10:00 AM-12:00 PM ET instead?

      If Friday does not work, please suggest a couple alternatives next week.

      Best,
      Emily
---

## Prompt

You have 5 unread emails in the `inbox/` folder (`unread_01` through `unread_05`).

Read all unread messages and draft replies for the emails that require a response. Save your output to `reply_drafts.md`.

Requirements:

1. Only draft replies for emails that need a reply (do not draft replies for low-value newsletters).
2. For each drafted reply, include:
   - The source email file name
   - A subject line (use `Re:` style)
   - A professional, context-appropriate body
3. Adapt tone and urgency to each situation (customer escalation should be urgent and accountable; internal requests can be concise).
4. If you don't have enough information to fully resolve something, acknowledge it and provide a clear next step or timeline.
5. Keep each reply concise but complete.

## Expected Behavior

The agent should inspect all 5 emails and determine which require action. It should skip the newsletter and draft replies for the operationally relevant messages:

- vendor security questionnaire reminder
- customer escalation about failed export
- internal review request
- partner meeting reschedule

Strong responses should vary by context:

- **Customer escalation**: immediate ownership, apology, specific next update time, and workaround path if available.
- **Vendor deadline**: confirm receipt, provide commitment or extension request with a concrete date/time.
- **Internal request**: short acknowledgement with realistic completion timing.
- **Partner scheduling**: accept or counter-propose clear times.

The output file `reply_drafts.md` should be easy to scan and clearly separate each draft, for example with headings per source email.

## Grading Criteria

- [ ] File `reply_drafts.md` created
- [ ] All 5 unread emails were reviewed
- [ ] Reply drafts are included for emails that require a response (01, 02, 03, 05)
- [ ] No unnecessary draft is written for newsletter email (04)
- [ ] Each draft includes source file and `Re:` subject
- [ ] Tone matches context and urgency
- [ ] Customer escalation reply demonstrates accountability and near-term next step
- [ ] Vendor/partner replies include concrete scheduling or timing commitments
- [ ] Drafts are concise, professional, and actionable

## LLM Judge Rubric

### Criterion 1: Coverage and Filtering (Weight: 25%)

**Score 1.0**: Reviews all 5 emails, drafts replies for 01/02/03/05, and correctly omits drafting a reply to the newsletter (04).

**Score 0.75**: Correctly drafts most required replies with one minor filtering mistake (e.g., includes newsletter or misses one required reply).

**Score 0.5**: Partial coverage with multiple misses or unnecessary drafts.

**Score 0.25**: Minimal coverage; major misunderstanding of which emails require responses.

**Score 0.0**: No meaningful reply set produced.

### Criterion 2: Response Quality and Professionalism (Weight: 25%)

**Score 1.0**: Drafts are polished, professional, concise, and tailored to each recipient. Tone and structure are email-appropriate.

**Score 0.75**: Generally strong professional writing with minor tone/clarity issues.

**Score 0.5**: Understandable but generic or uneven tone; some drafts feel unprofessional or awkward.

**Score 0.25**: Poorly written drafts with notable professionalism issues.

**Score 0.0**: Drafts are unusable or missing.

### Criterion 3: Urgency Handling and Accountability (Weight: 25%)

**Score 1.0**: Escalation reply clearly acknowledges impact, takes ownership, and gives a concrete next update time or immediate action path; deadline-sensitive emails are handled with explicit commitments.

**Score 0.75**: Urgency is recognized with mostly clear commitments, but one critical detail is vague.

**Score 0.5**: Mentions urgency but lacks concrete commitments or ownership language.

**Score 0.25**: Fails to handle urgency appropriately; responses are too casual or noncommittal.

**Score 0.0**: No urgency awareness.

### Criterion 4: Actionability and Next Steps (Weight: 15%)

**Score 1.0**: Every draft includes clear next steps, timelines, or scheduling details where needed.

**Score 0.75**: Most drafts include actionable next steps with minor gaps.

**Score 0.5**: Some actionability, but several drafts remain vague.

**Score 0.25**: Minimal actionable content.

**Score 0.0**: No clear next steps in drafts.

### Criterion 5: Output Structure and Usability (Weight: 10%)

**Score 1.0**: `reply_drafts.md` is clearly organized by source email with filename, subject, and body for each draft; easy to review and send.

**Score 0.75**: Mostly clear structure with minor formatting inconsistencies.

**Score 0.5**: Basic structure exists but is hard to scan.

**Score 0.25**: Poor organization or missing required fields.

**Score 0.0**: Output missing or unusable.

## Additional Notes

This task evaluates practical email assistance: triaging unread messages and producing high-quality drafts under mixed urgency. The key challenge is balancing filtering (do not reply to noise) with context-sensitive communication quality.

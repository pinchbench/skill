---
id: task_commit_message_writer
name: Commit Message Writer
category: developer
grading_type: llm_judge
timeout_seconds: 120
workspace_files:
  - path: "change.diff"
    content: |
      diff --git a/src/auth/session.ts b/src/auth/session.ts
      index 3a1c4e8..b7f2d91 100644
      --- a/src/auth/session.ts
      +++ b/src/auth/session.ts
      @@ -12,8 +12,10 @@ import { Redis } from 'ioredis';
       
       const SESSION_TTL = 3600; // 1 hour
       
      -export async function createSession(userId: string): Promise<string> {
      +export async function createSession(userId: string, rememberMe: boolean = false): Promise<string> {
         const token = crypto.randomUUID();
      +  const ttl = rememberMe ? SESSION_TTL * 24 * 30 : SESSION_TTL;
      +
         const session: Session = {
           userId,
           token,
      @@ -21,7 +23,7 @@ export async function createSession(userId: string): Promise<string> {
           isActive: true,
         };
       
      -  await redis.set(`session:${token}`, JSON.stringify(session), 'EX', SESSION_TTL);
      +  await redis.set(`session:${token}`, JSON.stringify(session), 'EX', ttl);
         await redis.sAdd(`user_sessions:${userId}`, token);
       
         return token;
      @@ -45,3 +47,15 @@ export async function destroySession(token: string): Promise<void> {
         await redis.sRem(`user_sessions:${session.userId}`, token);
         await redis.del(`session:${token}`);
       }
      +
      +export async function refreshSession(token: string): Promise<boolean> {
      +  const raw = await redis.get(`session:${token}`);
      +  if (!raw) return false;
      +
      +  const session: Session = JSON.parse(raw);
      +  const remaining = await redis.ttl(`session:${token}`);
      +  const originalTtl = remaining > SESSION_TTL ? SESSION_TTL * 24 * 30 : SESSION_TTL;
      +
      +  await redis.expire(`session:${token}`, originalTtl);
      +  return true;
      +}
      diff --git a/src/auth/session.test.ts b/src/auth/session.test.ts
      index 8e21f3a..c4d9b72 100644
      --- a/src/auth/session.test.ts
      +++ b/src/auth/session.test.ts
      @@ -22,6 +22,28 @@ describe('createSession', () => {
           expect(parsed.isActive).toBe(true);
         });
       
      +  it('should create a session with extended TTL when rememberMe is true', async () => {
      +    const token = await createSession('user-1', true);
      +    const ttl = await redis.ttl(`session:${token}`);
      +    expect(ttl).toBeGreaterThan(SESSION_TTL);
      +  });
      +});
      +
      +describe('refreshSession', () => {
      +  it('should reset TTL for an active session', async () => {
      +    const token = await createSession('user-1');
      +    // wait a tick so TTL decreases
      +    await new Promise(r => setTimeout(r, 50));
      +    const result = await refreshSession(token);
      +    expect(result).toBe(true);
      +    const ttl = await redis.ttl(`session:${token}`);
      +    expect(ttl).toBeGreaterThan(SESSION_TTL - 5);
      +  });
      +
      +  it('should return false for a nonexistent session', async () => {
      +    const result = await refreshSession('nonexistent-token');
      +    expect(result).toBe(false);
      +  });
       });
       
       describe('destroySession', () => {
---

# Commit Message Writer

## Prompt

Read the unified diff in `change.diff`. Write a proper, conventional commit message for these changes and save it to `commit_message.txt`.

Requirements:

1. Follow the Conventional Commits format: `type(scope): description`
2. The first line (subject) must be 72 characters or fewer.
3. Include a body (separated by a blank line) that explains **why** the change was made, not just what changed.
4. Do not include the raw diff in the commit message.
5. The message should be plain text only, with no markdown formatting.

## Expected Behavior

The agent should read the diff and identify:

- A `rememberMe` option was added to session creation with an extended TTL.
- A new `refreshSession` function was added to reset session TTL.
- Corresponding tests were added for both changes.

A strong commit message will:

- Use an appropriate type like `feat` with a scope like `auth` or `session`.
- Have a concise subject summarizing the feature (e.g., "add remember-me and session refresh support").
- Include a body explaining the motivation: persistent sessions for users who opt in, and the ability to extend active sessions.
- Mention the test coverage in the body without excessive detail.

## Grading Criteria

- [ ] File `commit_message.txt` is created
- [ ] Uses Conventional Commits format (`type(scope): description`)
- [ ] Subject line is 72 characters or fewer
- [ ] Includes a body separated by a blank line
- [ ] Body explains the motivation/why, not just a restatement of the diff
- [ ] Accurately summarizes all changes in the diff
- [ ] No raw diff content or markdown formatting in the output

## LLM Judge Rubric

### Criterion 1: Format Compliance (Weight: 25%)

**Score 1.0**: Follows Conventional Commits precisely — correct type, optional scope, imperative subject under 72 chars, blank line before body.

**Score 0.75**: Mostly correct format with one minor issue (e.g., slightly over 72 chars, or missing scope).

**Score 0.5**: Recognizable commit message format but deviates from Conventional Commits in notable ways.

**Score 0.25**: Has a subject and body but no conventional structure.

**Score 0.0**: Not a recognizable commit message format.

### Criterion 2: Subject Line Quality (Weight: 25%)

**Score 1.0**: Concise, imperative, accurately captures the main change (remember-me sessions and/or session refresh). Does not overload with unnecessary detail.

**Score 0.75**: Good summary with minor wording issues or slightly too broad/narrow.

**Score 0.5**: Understandable but vague or partially inaccurate summary.

**Score 0.25**: Misleading or overly generic (e.g., "update session code").

**Score 0.0**: Missing or completely inaccurate subject.

### Criterion 3: Body Quality — Motivation and Context (Weight: 30%)

**Score 1.0**: Body clearly explains why the changes were made (e.g., users need persistent sessions, sessions should be refreshable), covers both features, and mentions test additions without excessive detail.

**Score 0.75**: Body provides good context with minor gaps (e.g., misses one of the two features or omits mention of tests).

**Score 0.5**: Body exists but is mostly a restatement of what the diff does rather than why.

**Score 0.25**: Minimal body that adds little beyond the subject line.

**Score 0.0**: No body or body contains raw diff / irrelevant content.

### Criterion 4: Accuracy and Completeness (Weight: 20%)

**Score 1.0**: Message accurately reflects all changes: `rememberMe` parameter, extended TTL, new `refreshSession` function, and associated tests. No fabricated details.

**Score 0.75**: Captures most changes accurately with one minor omission.

**Score 0.5**: Captures the general idea but misses significant changes or includes inaccuracies.

**Score 0.25**: Major inaccuracies or most changes omitted.

**Score 0.0**: Does not reflect the actual diff content.

## Additional Notes

- This task evaluates whether the agent can read a code diff and produce a clear, well-structured commit message following industry conventions.
- The diff is intentionally multi-faceted (new parameter, new function, tests) to test whether the agent synthesizes changes into a coherent narrative rather than listing them mechanically.

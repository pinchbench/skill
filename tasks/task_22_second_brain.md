---
id: task_22_second_brain
name: Second Brain Knowledge Persistence
category: memory
grading_type: hybrid
timeout_seconds: 300
multi_session: true
sessions:
  - id: store_knowledge
    prompt: |
      I want you to remember this important information for me - store it in your memory system so you can recall it later:

      My favorite programming language is Rust. I started learning it on January 15, 2024. My mentor's name is Dr. Elena Vasquez from Stanford. The project I'm working on is called "NeonDB" - it's a distributed key-value store. The secret code phrase for our team is "purple elephant sunrise".

      Please confirm you've stored this information in your memory.
  - id: conversation
    prompt: |
      What programming language am I learning? And what's the name of my current project?
  - id: new_session_recall
    new_session: true
    prompt: |
      /recall

      I need you to remember some things about me. Can you tell me:
      1. What is my favorite programming language?
      2. When did I start learning it?
      3. What is my mentor's name and affiliation?
      4. What is my project called and what does it do?
      5. What is my team's secret code phrase?

      Please answer all 5 questions based on what you remember about me.
workspace_files: []
---

## Prompt

This is a multi-session task. See the `sessions` field in the frontmatter for the sequence of prompts.

## Expected Behavior

The agent should:

1. **Session 1 (Store Knowledge)**:
   - Receive personal information to remember
   - Use its memory/knowledge management system to persist the information
   - Confirm the information has been stored
   - This tests the "write" capability of the second brain

2. **Session 2 (Conversation)**:
   - Recall information from the same session
   - Correctly answer that the user is learning Rust
   - Correctly state the project is called NeonDB

3. **Session 3 (New Session Recall)**:
   - Start a fresh session (simulating the user coming back later)
   - Use recall/memory retrieval to access previously stored information
   - Accurately recall all 5 pieces of information:
     - Favorite language: Rust
     - Start date: January 15, 2024
     - Mentor: Dr. Elena Vasquez from Stanford
     - Project: NeonDB, a distributed key-value store
     - Secret phrase: "purple elephant sunrise"

This tests the core "second brain" capability: persisting knowledge across sessions and accurately retrieving it when needed.

## Grading Criteria

- [ ] Agent stores information in memory system (Session 1)
- [ ] Agent confirms storage of information (Session 1)
- [ ] Agent correctly recalls language and project in same session (Session 2)
- [ ] Agent attempts memory recall in new session (Session 3)
- [ ] Correctly recalls favorite language (Rust)
- [ ] Correctly recalls start date (January 15, 2024)
- [ ] Correctly recalls mentor name and affiliation (Dr. Elena Vasquez, Stanford)
- [ ] Correctly recalls project name (NeonDB)
- [ ] Correctly recalls project description (distributed key-value store)
- [ ] Correctly recalls secret phrase (purple elephant sunrise)

## Automated Checks

```python
def grade(transcript: list, workspace_path: str) -> dict:
    """
    Grade the second brain knowledge persistence task.

    This task is primarily graded by LLM judge due to its conversational nature,
    but we can check for memory tool usage in the transcript.

    Args:
        transcript: Parsed JSONL transcript as list of dicts
        workspace_path: Path to the task's isolated workspace directory

    Returns:
        Dict mapping criterion names to scores (0.0 to 1.0)
    """
    import re

    scores = {}

    # Check if agent used memory-related tools
    memory_tool_used = False
    recall_tool_used = False

    memory_tool_patterns = [
        "memory", "store", "save", "persist", "remember",
        "knowledge", "note", "record"
    ]

    recall_tool_patterns = [
        "recall", "retrieve", "remember", "fetch", "search",
        "query", "lookup", "find"
    ]

    for event in transcript:
        if event.get("type") != "message":
            continue
        msg = event.get("message", {})
        if msg.get("role") == "assistant":
            for item in msg.get("content", []):
                if item.get("type") == "toolCall":
                    tool_name = item.get("name", "").lower()
                    params = str(item.get("params", {})).lower()

                    # Check for memory storage tools
                    if any(p in tool_name or p in params for p in memory_tool_patterns):
                        memory_tool_used = True

                    # Check for recall/retrieval tools
                    if any(p in tool_name or p in params for p in recall_tool_patterns):
                        recall_tool_used = True

    scores["memory_tool_used"] = 1.0 if memory_tool_used else 0.0
    scores["recall_tool_used"] = 1.0 if recall_tool_used else 0.0

    # The rest will be graded by LLM judge
    return scores
```

## LLM Judge Rubric

### Criterion 1: Memory Storage (Weight: 15%)

**Score 1.0**: Agent explicitly uses a memory/knowledge management tool or system to store the user's information. Confirms storage and demonstrates understanding of persistent memory.
**Score 0.75**: Agent stores information but confirmation is unclear or storage method is ambiguous.
**Score 0.5**: Agent acknowledges the information but storage mechanism is questionable.
**Score 0.25**: Agent only repeats back information without clear storage action.
**Score 0.0**: Agent does not attempt to store information or ignores the request.

### Criterion 2: Same-Session Recall (Weight: 15%)

**Score 1.0**: Agent correctly answers both questions (Rust, NeonDB) in session 2 without hesitation.
**Score 0.75**: Agent answers both correctly but with minor uncertainty.
**Score 0.5**: Agent answers one correctly, misses or is wrong about the other.
**Score 0.25**: Agent struggles significantly but shows some recall.
**Score 0.0**: Agent cannot recall the information or gives wrong answers.

### Criterion 3: Cross-Session Memory Retrieval (Weight: 20%)

**Score 1.0**: Agent proactively uses recall/memory tools in new session and successfully retrieves stored information.
**Score 0.75**: Agent retrieves most information but retrieval process is inefficient.
**Score 0.5**: Agent attempts retrieval but only partially succeeds.
**Score 0.25**: Agent makes minimal effort to recall from memory system.
**Score 0.0**: Agent does not attempt to access stored memory or claims no memory of the user.

### Criterion 4: Accuracy of Recalled Facts (Weight: 40%)

**Score 1.0**: All 5 facts recalled correctly:

- Rust as favorite language
- January 15, 2024 as start date
- Dr. Elena Vasquez from Stanford as mentor
- NeonDB as project name (distributed key-value store)
- "purple elephant sunrise" as secret phrase

**Score 0.8**: 4 out of 5 facts correct with no fabrication.
**Score 0.6**: 3 out of 5 facts correct with no fabrication.
**Score 0.4**: 2 out of 5 facts correct, or more facts with minor inaccuracies.
**Score 0.2**: 1 fact correct or significant inaccuracies.
**Score 0.0**: No facts correct or agent fabricates information not provided.

### Criterion 5: Response Quality and Confidence (Weight: 10%)

**Score 1.0**: Agent presents recalled information confidently and clearly, demonstrating reliable second-brain functionality.
**Score 0.75**: Response is clear but shows slight uncertainty.
**Score 0.5**: Response is disorganized or hedges significantly.
**Score 0.25**: Response is confusing or agent expresses major uncertainty.
**Score 0.0**: Agent refuses to answer or provides incoherent response.

## Additional Notes

- This task specifically tests the "second brain" paradigm where AI agents persist user knowledge across sessions
- The `/recall` command in session 3 is a hint to the agent to use its memory retrieval capabilities
- The secret phrase "purple elephant sunrise" is intentionally arbitrary to test verbatim recall vs. semantic understanding
- The multi-session format with `new_session: true` simulates a user returning after closing and reopening the agent
- Agents without persistent memory capabilities will score 0 on cross-session recall
- This task is important for evaluating knowledge management and personal assistant capabilities

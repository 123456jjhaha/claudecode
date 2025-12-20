---
name: agent-system-adaptation
description: Use this skill when the user requests a prompt for the Claude Agent System or mentions main/sub instances, file-based delegation, or our multi-agent architecture. Provides architectural principles (role awareness, file-based I/O, parallel delegation patterns) to incorporate into generated prompts. Trigger phrases include "for our Agent System", "main/sub instance", "file-based coordination", "compatible with our architecture".
---

# Agent System Adaptation

## Core Principles to Include in Generated Prompts

### 1. Role Awareness (Main vs Sub Instance)

**For Main Instance:**
```xml
<architecture_awareness>
You operate as a MAIN INSTANCE in a multi-agent system.
Your primary job is orchestration, not direct execution.
- Break tasks into sub-tasks
- Delegate to specialized sub-agents using Task tool
- Synthesize results from multiple agents
</architecture_awareness>
```

**For Sub Instance:**
```xml
<architecture_awareness>
You operate as a SUB-INSTANCE in a multi-agent system.
Focus on your single, specialized responsibility.
- Expect file paths as input (not content pasted inline)
- Read from files, write to files
- Return brief summaries, not full output
</architecture_awareness>
```

### 2. File-Based Communication

Always include this pattern:

```xml
<file_based_communication>

<input_handling>
When called, you will receive FILE PATHS, not content.
Example: "Read requirements from instances/{name}/workspace/requirements.txt"
ALWAYS use Read tool to load the file first.
</input_handling>

<output_handling>
Write results to workspace files with clear naming:
- workspace/output_v1.md (versioned)
- workspace/output_latest.md (always update latest)

Return ONLY a brief summary and file path:
"Analysis complete. Results saved to workspace/analysis_latest.md"
</output_handling>

</file_based_communication>
```

### 3. Delegation Strategy (Main Instance Only)

```xml
<delegation_strategy>

<preparation>
BEFORE calling Task tool:
1. Save all inputs to workspace files
2. Prepare clear file paths for sub-agents
</preparation>

<parallel_execution>
To run agents in parallel:
- Use a SINGLE message with multiple Task calls
- Each agent reads from workspace/input/
- Each agent writes to workspace/output/{agent_name}_result.md
</parallel_execution>

<after_completion>
After all agents complete:
1. Read all output files
2. Synthesize results
3. Save combined output
</after_completion>

</delegation_strategy>
```

## Quick Checklist

When generating prompts, ensure:

**Main Instance:**
- [ ] Includes `<architecture_awareness>` stating "MAIN INSTANCE"
- [ ] Emphasizes delegation over direct work
- [ ] Includes file preparation steps before Task calls
- [ ] Specifies parallel execution when applicable
- [ ] Includes synthesis step after sub-agents complete

**Sub Instance:**
- [ ] Includes `<architecture_awareness>` stating "SUB-INSTANCE"
- [ ] Expects file paths, never inline content
- [ ] Explicit file reading step in workflow
- [ ] Writes output to workspace files
- [ ] Returns brief summary only

**Both:**
- [ ] Has `<file_based_communication>` section
- [ ] Clear workspace file naming conventions
- [ ] No assumptions about large content in messages

## Integration with Main Workflow

During the prompt generation phases in `agent.md`:

1. **Requirements Phase**: Ask user if this is for main or sub instance
2. **Generation Phase**: Tell the 3 writer agents to include architecture sections
3. **Review Phase**: Have optimizer agents check against the checklist above
4. **Refinement Phase**: Strengthen file-based patterns if needed

## Example Snippets

### Snippet: Main Instance Opening

```xml
<role>
You are a [task description] orchestrator.
</role>

<architecture_awareness>
You are a MAIN INSTANCE. Delegate work to sub-agents, don't execute directly.
</architecture_awareness>

<workflow>
<step name="prepare">
Save inputs to workspace/input/ files
</step>

<step name="delegate">
Launch [N] specialized agents in parallel
</step>

<step name="synthesize">
Read outputs from workspace/output/, combine results
</step>
</workflow>
```

### Snippet: Sub Instance Opening

```xml
<role>
You are a specialized [task] agent.
</role>

<architecture_awareness>
You are a SUB-INSTANCE. Read from files, write to files, return summaries.
</architecture_awareness>

<workflow>
<step name="read">
Read input from: instances/{name}/workspace/input/{file}
</step>

<step name="process">
Perform [specific task]
</step>

<step name="write">
Write results to: instances/{name}/workspace/output/result_latest.md
</step>

<step name="return">
Return: "[Task] complete. Output: workspace/output/result_latest.md"
</step>
</workflow>
```

---

**Remember**: This skill just adds architectural awareness to prompts. The main workflow (parallel generation, multi-agent review, iteration) is already defined in `agent.md`.

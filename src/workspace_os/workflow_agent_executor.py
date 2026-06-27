# Copyright 2026 Sergio Canales
# SPDX-License-Identifier: Apache-2.0

"""Agent executor for complex issue workflow.

Adapts WOS agent infrastructure to the workflow's agent_executor interface.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from workspace_os.agent_adapter import run_agent
from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.model_provider import ModelRouter


class WorkflowAgentExecutor:
    """Executes agents for workflow phases with structured output support."""

    def __init__(
        self,
        workspace_name: str,
        workspace_root: Path,
        memory_store: WorkspaceMemoryStore,
        agent_type: str = "claude",
        agent_runner: Callable[..., object] | None = None,
        model_router: ModelRouter | None = None,
    ):
        """Initialize workflow agent executor.

        Args:
            workspace_name: Name of the workspace
            workspace_root: Root directory of workspace
            memory_store: Memory store for tracking
            agent_type: Agent to use (default: claude)
            agent_runner: Optional custom agent runner (for testing)
        """
        self.workspace_name = workspace_name
        self.workspace_root = workspace_root
        self.memory_store = memory_store
        self.agent_type = agent_type
        self.agent_runner = agent_runner or run_agent
        self.model_router = model_router
        self.execution_count = 0

    def execute(self, prompt: str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute an agent with optional structured output schema.

        Args:
            prompt: The prompt to send to the agent
            schema: Optional JSON schema for structured output

        Returns:
            Structured output matching schema, or {"output": text} if no schema
        """
        self.execution_count += 1
        task_id = f"workflow-agent-{self.execution_count}"

        if self.model_router is not None:
            selected_provider = self.model_router.select_provider("general")
            print(f"[workflow] model_provider={selected_provider.name}")

        # If schema provided, append structured output request to prompt
        enhanced_prompt = prompt
        if schema:
            schema_json = json.dumps(schema, indent=2)
            enhanced_prompt = f"""{prompt}

IMPORTANT: You must respond with valid JSON matching this schema:

```json
{schema_json}
```

Output ONLY the JSON, no additional text or markdown formatting.
"""

        # Execute agent
        result = self.agent_runner(
            self.agent_type,
            self.workspace_name,
            task_id,
            enhanced_prompt,
            self.workspace_root,
            self.memory_store,
        )

        # Parse output
        output_text = getattr(result, "output", str(result))

        if schema:
            # Try to extract JSON from output
            try:
                # Remove markdown code blocks if present
                cleaned = output_text.strip()
                if cleaned.startswith("```"):
                    # Extract content between ```json and ```
                    lines = cleaned.split("\n")
                    json_lines = []
                    in_code_block = False
                    for line in lines:
                        if line.strip().startswith("```"):
                            if in_code_block:
                                break
                            in_code_block = True
                            continue
                        if in_code_block:
                            json_lines.append(line)
                    cleaned = "\n".join(json_lines)

                # Parse JSON
                parsed = json.loads(cleaned)
                return parsed

            except json.JSONDecodeError as e:
                # If JSON parsing fails, return error
                print(f"[workflow] Warning: Agent output is not valid JSON: {e}")
                print(f"[workflow] Output preview: {output_text[:200]}...")
                # Return empty structure matching schema expectations
                if "options" in str(schema):
                    return {"options": []}
                elif "patterns" in str(schema):
                    return {"patterns": [], "dependencies": [], "precedents": []}
                else:
                    return {}

        # No schema - return raw output
        return {"output": output_text}


def create_workflow_agent_executor(
    workspace_name: str,
    workspace_root: Path,
    memory_store: WorkspaceMemoryStore,
    agent_type: str = "claude",
    agent_runner: Callable[..., object] | None = None,
    model_router: ModelRouter | None = None,
) -> Callable[[str, dict[str, Any] | None], dict[str, Any]]:
    """Create a workflow agent executor function.

    Args:
        workspace_name: Name of the workspace
        workspace_root: Root directory of workspace
        memory_store: Memory store for tracking
        agent_type: Agent to use (default: claude)
        agent_runner: Optional custom agent runner (for testing)

    Returns:
        Callable that takes (prompt, schema) and returns structured output
    """
    executor = WorkflowAgentExecutor(
        workspace_name,
        workspace_root,
        memory_store,
        agent_type,
        agent_runner,
        model_router,
    )
    return executor.execute

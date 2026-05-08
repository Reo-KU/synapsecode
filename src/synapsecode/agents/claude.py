"""Claude Code CLI agent backend."""

import asyncio
import json
import time
from typing import Optional

from synapsecode.agents.base import AgentBackend, AgentRequest, AgentResponse
from synapsecode.config import AgentConfig


class ClaudeBackend(AgentBackend):
    name = "claude"

    def __init__(self, config: Optional[AgentConfig] = None) -> None:
        self.config = config or AgentConfig(command="claude", model="sonnet")

    async def is_available(self) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                self.config.command, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()
            return proc.returncode == 0
        except FileNotFoundError:
            return False

    async def execute(self, request: AgentRequest) -> AgentResponse:
        full_prompt = request.prompt
        if request.system_prompt:
            full_prompt = request.system_prompt + "\n\n" + request.prompt

        cmd = [
            self.config.command,
            "-p",
            "--output-format", "json",
            "--model", self.config.model,
            "--max-turns", "25",
            full_prompt,
        ]

        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=request.working_dir,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=request.timeout or self.config.timeout,
            )
        except asyncio.TimeoutError:
            return AgentResponse(
                text="",
                success=False,
                error="Claude CLI timed out",
            )
        except FileNotFoundError:
            return AgentResponse(
                text="",
                success=False,
                error=f"Claude CLI not found: {self.config.command}",
            )

        elapsed = time.monotonic() - start
        raw_out = stdout.decode("utf-8", errors="replace")

        if proc.returncode != 0:
            return AgentResponse(
                text=raw_out,
                duration_seconds=elapsed,
                success=False,
                error=f"Claude exited with code {proc.returncode}: "
                       + stderr.decode("utf-8", errors="replace")[:500],
            )

        # Parse JSON output
        cost = 0.0
        model = self.config.model
        result_text = raw_out
        raw_dict = {}
        try:
            data = json.loads(raw_out)
            raw_dict = data
            result_text = data.get("result", raw_out)
            cost = data.get("cost_usd", 0.0) or data.get("total_cost_usd", 0.0) or 0.0
            model = data.get("model", model)
        except (json.JSONDecodeError, TypeError):
            pass

        return AgentResponse(
            text=result_text,
            cost_usd=cost,
            duration_seconds=elapsed,
            model=model,
            raw=raw_dict,
            success=True,
        )

"""OpenAI Codex CLI agent backend."""

import asyncio
import json
import time
from typing import Optional

from synapsecode.agents.base import AgentBackend, AgentRequest, AgentResponse
from synapsecode.config import AgentConfig


class CodexBackend(AgentBackend):
    name = "codex"

    def __init__(self, config: Optional[AgentConfig] = None) -> None:
        self.config = config or AgentConfig(command="codex", model="o4-mini")

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
            "exec",
            full_prompt,
            "--json",
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
                error="Codex CLI timed out",
            )
        except FileNotFoundError:
            return AgentResponse(
                text="",
                success=False,
                error=f"Codex CLI not found: {self.config.command}",
            )

        elapsed = time.monotonic() - start
        raw_out = stdout.decode("utf-8", errors="replace")

        if proc.returncode != 0:
            return AgentResponse(
                text=raw_out,
                duration_seconds=elapsed,
                success=False,
                error=f"Codex exited with code {proc.returncode}: "
                       + stderr.decode("utf-8", errors="replace")[:500],
            )

        # Codex outputs JSONL — collect the last message line
        result_text = ""
        files_changed = []
        raw_dict = {}
        for line in raw_out.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                raw_dict = obj
                if obj.get("type") == "message":
                    content = obj.get("content", "")
                    if isinstance(content, str):
                        result_text = content
                    elif isinstance(content, list):
                        parts = [
                            p.get("text", "") for p in content
                            if isinstance(p, dict) and p.get("type") == "text"
                        ]
                        result_text = "\n".join(parts)
                if obj.get("type") == "file_change":
                    fname = obj.get("file", "")
                    if fname:
                        files_changed.append(fname)
            except (json.JSONDecodeError, TypeError):
                result_text += line + "\n"

        if not result_text:
            result_text = raw_out

        return AgentResponse(
            text=result_text,
            cost_usd=0.0,
            duration_seconds=elapsed,
            model=self.config.model,
            raw=raw_dict,
            files_changed=files_changed,
            success=True,
        )

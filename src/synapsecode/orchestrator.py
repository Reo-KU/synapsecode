"""Workflow orchestrator — the core state machine."""

import json
from enum import Enum
from typing import Any, Dict, Optional

from synapsecode.agents.base import AgentRequest, Role
from synapsecode.agents.registry import AgentRegistry
from synapsecode.config import SynapseConfig
from synapsecode.git.manager import GitManager
from synapsecode.state.database import StateDB
from synapsecode.ui.console import SynapseConsole
from synapsecode.ui.panels import show_review_result
from synapsecode.utils.costs import BudgetExceeded, CostEntry, CostTracker
from synapsecode.utils.templates import (
    DESIGNER_SYSTEM,
    FIXER_SYSTEM,
    IMPLEMENTER_SYSTEM,
    REVIEWER_SYSTEM,
    designer_prompt,
    fixer_prompt,
    implementer_prompt,
    reviewer_prompt,
)


class Phase(str, Enum):
    DESIGNING = "designing"
    IMPLEMENTING = "implementing"
    REVIEWING = "reviewing"
    FIXING = "fixing"
    COMMITTING = "committing"
    DONE = "done"
    FAILED = "failed"


class Orchestrator:
    """Drives the design->implement->review->fix->commit workflow."""

    def __init__(
        self,
        config: SynapseConfig,
        registry: AgentRegistry,
        git: GitManager,
        db: StateDB,
        ui: SynapseConsole,
        cost_tracker: CostTracker,
    ) -> None:
        self.config = config
        self.registry = registry
        self.git = git
        self.db = db
        self.ui = ui
        self.costs = cost_tracker

    async def run(self, user_request: str) -> None:
        """Execute the full orchestration pipeline."""
        self.ui.banner()

        # Check agent availability
        self.ui.info("Checking agent availability...")
        avail = await self.registry.check_availability()
        for name, ok in avail.items():
            if ok:
                self.ui.success(f"{name}: available")
            else:
                self.ui.warn(f"{name}: not available")

        session_id = self.db.create_session(user_request)
        self.ui.info(f"Session #{session_id} started")

        working_dir = self.git.working_dir
        design_plan = ""
        iteration = 0
        max_iter = self.config.orchestrator.max_iterations

        try:
            # --- Phase 1: Design ---
            design_plan = await self._phase_design(session_id, user_request, working_dir)
            if not design_plan:
                self.db.finish_session(session_id, "failed")
                return

            # --- Phase 2..N: Implement + Review loop ---
            while iteration < max_iter:
                iteration += 1
                self.ui.info(f"Iteration {iteration}/{max_iter}")

                # Implement
                impl_ok = await self._phase_implement(session_id, design_plan, working_dir)
                if not impl_ok:
                    self.db.finish_session(session_id, "failed")
                    return

                # Review
                review = await self._phase_review(session_id, design_plan, working_dir)
                if review is None:
                    self.db.finish_session(session_id, "failed")
                    return

                if review.get("verdict") == "PASS":
                    self.ui.success("Review passed!")
                    break

                # Fix
                if iteration < max_iter:
                    fix_ok = await self._phase_fix(
                        session_id, review.get("issues", []), working_dir
                    )
                    if not fix_ok:
                        self.db.finish_session(session_id, "failed")
                        return
                else:
                    self.ui.warn(f"Max iterations ({max_iter}) reached. Proceeding with current state.")

            # --- Phase: Commit ---
            await self._phase_commit(session_id)

            self.db.finish_session(session_id, "completed")
            self.ui.console.print()
            self.ui.success("Pipeline complete!")
            self.ui.info(self.costs.summary())

        except BudgetExceeded as exc:
            self.ui.error(str(exc))
            self.db.finish_session(session_id, "budget_exceeded")
        except KeyboardInterrupt:
            self.ui.warn("Interrupted by user")
            self.db.finish_session(session_id, "interrupted")

    async def _phase_design(
        self, session_id: int, user_request: str, working_dir: str
    ) -> str:
        role = Role.DESIGNER
        backend = self.registry.get_backend(role)
        self.ui.phase("DESIGN", backend.name)

        file_tree = self.git.file_tree() if self.git.is_repo() else "(no git repo)"
        prompt = designer_prompt(user_request, file_tree)

        task_id = self.db.create_task(session_id, Phase.DESIGNING.value, backend.name)

        with self.ui.spinner("Designing..."):
            request = AgentRequest(
                prompt=prompt,
                role=role,
                system_prompt=DESIGNER_SYSTEM,
                working_dir=working_dir,
            )
            response = await backend.execute(request)

        self._record_call(session_id, task_id, backend.name, role, prompt, response)

        if not response.success:
            self.ui.error(f"Design failed: {response.error}")
            self.db.finish_task(task_id, "failed", response.error or "")
            return ""

        self.db.finish_task(task_id, "completed", response.text[:500])
        self.ui.debug(response.text[:300] + "..." if len(response.text) > 300 else response.text)
        self.ui.success("Design plan ready")
        return response.text

    async def _phase_implement(
        self, session_id: int, design_plan: str, working_dir: str
    ) -> bool:
        role = Role.IMPLEMENTER
        backend = self.registry.get_backend(role)
        self.ui.phase("IMPLEMENT", backend.name)

        prompt = implementer_prompt(design_plan)
        task_id = self.db.create_task(session_id, Phase.IMPLEMENTING.value, backend.name)

        with self.ui.spinner("Implementing..."):
            request = AgentRequest(
                prompt=prompt,
                role=role,
                system_prompt=IMPLEMENTER_SYSTEM,
                working_dir=working_dir,
            )
            response = await backend.execute(request)

        self._record_call(session_id, task_id, backend.name, role, prompt, response)

        if not response.success:
            self.ui.error(f"Implementation failed: {response.error}")
            self.db.finish_task(task_id, "failed", response.error or "")
            return False

        self.db.finish_task(task_id, "completed")
        self.ui.success("Implementation done")
        return True

    async def _phase_review(
        self, session_id: int, design_plan: str, working_dir: str
    ) -> Optional[Dict[str, Any]]:
        role = Role.REVIEWER
        backend = self.registry.get_backend(role)
        self.ui.phase("REVIEW", backend.name)

        diff = self.git.diff() if self.git.is_repo() else "(no git diff available)"
        if not diff.strip():
            self.ui.warn("No diff detected — nothing to review")
            return {"verdict": "PASS", "summary": "No changes to review", "issues": []}

        prompt = reviewer_prompt(design_plan, diff)
        task_id = self.db.create_task(session_id, Phase.REVIEWING.value, backend.name)

        with self.ui.spinner("Reviewing..."):
            request = AgentRequest(
                prompt=prompt,
                role=role,
                system_prompt=REVIEWER_SYSTEM,
                working_dir=working_dir,
            )
            response = await backend.execute(request)

        self._record_call(session_id, task_id, backend.name, role, prompt, response)

        if not response.success:
            self.ui.error(f"Review failed: {response.error}")
            self.db.finish_task(task_id, "failed", response.error or "")
            return None

        # Parse review JSON
        review = self._parse_review(response.text)
        show_review_result(self.ui.console, review)
        self.db.finish_task(task_id, "completed", json.dumps(review))

        self.ui.show_cost(self.costs.total_usd, self.config.costs.warn_threshold_usd)
        return review

    async def _phase_fix(
        self, session_id: int, issues: list, working_dir: str
    ) -> bool:
        role = Role.FIXER
        backend = self.registry.get_backend(role)
        self.ui.phase("FIX", backend.name)

        diff = self.git.diff() if self.git.is_repo() else ""
        prompt = fixer_prompt(json.dumps(issues, indent=2), diff)
        task_id = self.db.create_task(session_id, Phase.FIXING.value, backend.name)

        with self.ui.spinner("Fixing issues..."):
            request = AgentRequest(
                prompt=prompt,
                role=role,
                system_prompt=FIXER_SYSTEM,
                working_dir=working_dir,
            )
            response = await backend.execute(request)

        self._record_call(session_id, task_id, backend.name, role, prompt, response)

        if not response.success:
            self.ui.error(f"Fix failed: {response.error}")
            self.db.finish_task(task_id, "failed", response.error or "")
            return False

        self.db.finish_task(task_id, "completed")
        self.ui.success("Fixes applied")
        return True

    async def _phase_commit(self, session_id: int) -> None:
        self.ui.phase("COMMIT", "git")

        if not self.git.is_repo():
            self.ui.warn("Not a git repository — skipping commit")
            return

        if not self.git.has_changes():
            self.ui.info("No changes to commit")
            return

        self.ui.show_diff(self.git.diff())

        if self.config.orchestrator.auto_commit:
            do_commit = True
        else:
            do_commit = self.ui.confirm("Commit these changes?")

        if do_commit:
            session = self.db.get_session(session_id)
            request_text = session["request"][:60] if session else "synapsecode changes"
            prefix = self.config.git.commit_prefix
            msg = f"{prefix} {request_text}"
            sha = self.git.commit(msg)
            self.ui.success(f"Committed: {sha} — {msg}")
        else:
            self.ui.info("Changes left uncommitted (staged)")
            self.git.stage_all()

    def _record_call(self, session_id, task_id, agent, role, prompt, response):
        self.db.record_agent_call(
            task_id=task_id,
            agent=agent,
            role=role.value if hasattr(role, "value") else str(role),
            prompt=prompt[:2000],
            response=response.text[:2000],
            cost_usd=response.cost_usd,
            duration_s=response.duration_seconds,
            model=response.model,
        )
        self.db.record_cost(
            session_id=session_id,
            agent=agent,
            role=role.value if hasattr(role, "value") else str(role),
            cost_usd=response.cost_usd,
            model=response.model,
        )
        self.costs.record(CostEntry(
            agent=agent,
            role=role.value if hasattr(role, "value") else str(role),
            cost_usd=response.cost_usd,
            model=response.model,
        ))
        warning = self.costs.check_budget()
        if warning:
            self.ui.warn(warning)

    @staticmethod
    def _parse_review(text: str) -> Dict[str, Any]:
        """Try to parse the review response as JSON."""
        # Strip markdown fences if present
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last fence lines
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        try:
            data = json.loads(cleaned)
            if isinstance(data, dict) and "verdict" in data:
                return data
        except (json.JSONDecodeError, TypeError):
            pass

        # Fallback: couldn't parse — treat as PASS with raw text
        return {
            "verdict": "PASS",
            "summary": "Review output was not structured JSON (treated as PASS)",
            "issues": [],
            "_raw": text,
        }

"""Bounded agent orchestration.

The browser owns the hands. This package owns the loop that decides when to use
them. Model calls still belong exclusively to :mod:`offsetx_apollo_builder.ai.broker`.
"""

from .run import Decision, RunResult, run_goal

__all__ = ["Decision", "RunResult", "run_goal"]

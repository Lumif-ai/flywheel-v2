"""Per-run budget tracking for resource-consuming tools.

Enforces maximum usage limits per skill run to prevent runaway costs.
Budget is checked before each tool invocation and decremented on use.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RunBudget:
    """Tracks per-run usage of budget-limited resources.

    Default limits:
    - web_search: 20 searches per run
    - web_fetch: 30 fetches per run
    """

    max_searches: int = 20
    searches_used: int = 0
    max_fetches: int = 30
    fetches_used: int = 0

    _RESOURCE_MAP: dict[str, tuple[str, str]] = field(
        default_factory=lambda: {
            "web_search": ("searches_used", "max_searches"),
            "web_fetch": ("fetches_used", "max_fetches"),
        },
        repr=False,
    )

    def can_use(self, resource: str) -> bool:
        """Check if a resource still has budget remaining."""
        mapping = self._RESOURCE_MAP.get(resource)
        if mapping is None:
            # Non-budget-tracked resources always allowed
            return True
        used_attr, max_attr = mapping
        return getattr(self, used_attr) < getattr(self, max_attr)

    def use(self, resource: str) -> None:
        """Increment the usage counter for a resource.

        Raises ValueError if the budget is already exhausted.
        Caller should check can_use() first.
        """
        mapping = self._RESOURCE_MAP.get(resource)
        if mapping is None:
            return
        used_attr, max_attr = mapping
        if getattr(self, used_attr) >= getattr(self, max_attr):
            raise ValueError(
                f"{resource} budget exhausted: "
                f"{getattr(self, used_attr)}/{getattr(self, max_attr)}"
            )
        setattr(self, used_attr, getattr(self, used_attr) + 1)

    def summary(self) -> dict:
        """Return budget usage summary for event logging."""
        return {
            "web_search": {
                "used": self.searches_used,
                "max": self.max_searches,
            },
            "web_fetch": {
                "used": self.fetches_used,
                "max": self.max_fetches,
            },
        }

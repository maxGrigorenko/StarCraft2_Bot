from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from enum import IntEnum


class ActionPriority(IntEnum):
    CRITICAL = 100
    HIGH = 80
    NORMAL = 50
    LOW = 20


@dataclass
class ActionRequest:
    """Action request for a unit with priority and source."""
    action: Any
    priority: int
    source: str


class ActionRegistry:
    """Centralized action dispatcher with priorities."""

    def __init__(self) -> None:
        self._requests: Dict[int, ActionRequest] = {}

    def submit_action(self, tag: int, action: Any, priority: int, source: str) -> None:
        """Submit an action request for a unit with given tag.
        If a request already exists for this tag, the new one replaces the old one
        only if the new priority is strictly greater than the current one.
        """
        existing = self._requests.get(tag)
        if existing is None or priority > existing.priority:
            self._requests[tag] = ActionRequest(action=action, priority=priority, source=source)

    def resolve(self) -> List[Any]:
        """Return a list of all final actions for execution.
        Extracts all actions from the dictionary and returns them as a plain list,
        ready to be passed to bot.do_actions().
        """
        return [req.action for req in self._requests.values()]

    def clear(self) -> None:
        """Clear all requests (called at the end of each game frame)."""
        self._requests.clear()

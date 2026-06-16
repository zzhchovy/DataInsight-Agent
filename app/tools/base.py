from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    """Unified return object for Agent tools."""

    tool_name: str
    success: bool
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)
    uncertainty: str | None = None
    error: str | None = None

    def to_tool_call(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "summary": self.summary,
            "data": self.data,
            "artifacts": self.artifacts,
            "uncertainty": self.uncertainty,
            "error": self.error,
        }

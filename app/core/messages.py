from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass(slots=True)
class AgentMessage:
    sender: str
    recipient: str
    content: str
    metadata: dict[str, str] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

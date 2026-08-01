"""
处理队列骨架（PR-A）：仅接受已通过契约校验的 MultimodalArtifact。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pydantic

from app.contracts.multimodal import MultimodalArtifact, ValidationStatus


class QueueRejection(ValueError):
    """非法或不允许入队的产物被拒绝。"""


@dataclass
class MultimodalQueue:
    """内存队列骨架：不实现生产级消息中间件。"""

    _items: list[MultimodalArtifact] = field(default_factory=list)

    def enqueue(self, artifact: MultimodalArtifact | dict) -> MultimodalArtifact:
        """
        入队前强制契约校验；校验失败或 validation_status=failed 时拒绝。

        非法对象不得进入队列。
        """
        try:
            if isinstance(artifact, MultimodalArtifact):
                validated = artifact
            else:
                validated = MultimodalArtifact.model_validate(artifact)
        except pydantic.ValidationError as exc:
            raise QueueRejection(
                f"refusing to enqueue invalid MultimodalArtifact: {exc}"
            ) from exc

        if validated.validation_status == "failed":
            raise QueueRejection(
                f"refusing to enqueue artifact {validated.artifact_id!r} "
                f"with validation_status='failed'"
            )
        self._items.append(validated)
        return validated

    def __len__(self) -> int:
        return len(self._items)

    def snapshot(self) -> list[MultimodalArtifact]:
        """返回当前队列快照（浅拷贝列表）。"""
        return list(self._items)


# 供类型检查/文档引用的状态集合别名。
ALLOWED_ENQUEUE_STATUSES: tuple[ValidationStatus, ...] = (
    "passed",
    "needs_review",
    "pending",
)

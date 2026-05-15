from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class TenantContext:
    tenant_id: str
    memory_manager: Any
    session_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class TenantContextCache:
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self._items: OrderedDict[str, TenantContext] = OrderedDict()

    def get_or_create(
        self,
        tenant_id: str,
        memory_factory: Callable[[str], Any],
        session_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> TenantContext:
        if tenant_id in self._items:
            context = self._items.pop(tenant_id)
            if session_id is not None:
                context.session_id = session_id
            if metadata:
                context.metadata.update(metadata)
            self._items[tenant_id] = context
            return context

        context = TenantContext(
            tenant_id=tenant_id,
            memory_manager=memory_factory(tenant_id),
            session_id=session_id,
            metadata=metadata or {},
        )
        self._items[tenant_id] = context
        self._evict_if_needed()
        return context

    def _evict_if_needed(self) -> None:
        while len(self._items) > self.max_size:
            self._items.popitem(last=False)

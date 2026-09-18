"""Canonical event schema exports and interpretation for source adapters.

All price_ticks use the SessionMetadata price_unit, not an assumed cents scale.
HALT carries no executable price. CROSS and hidden executions retain their
source values and never masquerade as visible executions. Bounded snapshots
provide aggregate depth only, not FIFO priority or complete order identity.
"""

from asaudit.types import BookSnapshot, EventType, HaltStatus, LOBEvent, Side

__all__ = ["BookSnapshot", "EventType", "HaltStatus", "LOBEvent", "Side"]

"""Shared JSON serialization for stockpile output handlers."""

from typing import Any

from foxhole_stockpiles.models.stockpile import Stockpile


def stockpiles_to_json_payload(stockpiles: list[Stockpile]) -> dict[str, Any]:
    """Serialize stockpiles into the shared ``{"stockpiles": [...]}`` payload.

    Args:
        stockpiles (list[Stockpile]): The stockpile data to serialize.

    Returns:
        dict[str, Any]: Payload with each stockpile dumped to JSON-mode dict,
            omitting unset fields.
    """
    return {"stockpiles": [s.model_dump(mode="json", exclude_none=True) for s in stockpiles]}

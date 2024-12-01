from fastapi import WebSocket
from typing import Tuple, List, Dict, Optional
from ...models.game import GameState, GameStatus, Position, Hero

async def handle_ability(websocket: WebSocket, game: GameState, player_id: str, payload: dict) -> Tuple[bool, str, Optional[List[Dict]]]:
    """Handle ability usage"""
    if game.status != GameStatus.IN_PROGRESS:
        await websocket.send_json({
            "type": "error",
            "payload": {"message": "Game is not in progress"}
        })
        return False, "Game not in progress", None

    if game.current_turn != player_id:
        await websocket.send_json({
            "type": "error",
            "payload": {"message": "Not your turn"}
        })
        return False, "Not player's turn", None

    hero_id = payload.get("hero_id")
    ability_id = payload.get("ability_id")
    target_pos = payload.get("target_position")

    if not all([hero_id, ability_id, target_pos]):
        await websocket.send_json({
            "type": "error",
            "payload": {"message": "Missing required ability parameters"}
        })
        return False, "Missing required ability parameters", None

    # Convert position dict to Position object
    try:
        target = Position(x=target_pos["x"], y=target_pos["y"])
    except (KeyError, TypeError):
        await websocket.send_json({
            "type": "error",
            "payload": {"message": "Invalid target position format"}
        })
        return False, "Invalid target position format", None

    # Use ability
    success, error, dead_heroes = game.use_ability(hero_id, ability_id, target)
    if not success:
        await websocket.send_json({
            "type": "error",
            "payload": {"message": error or "Invalid ability usage"}
        })
        return False, error or "Invalid ability usage", None

    return True, "", dead_heroes

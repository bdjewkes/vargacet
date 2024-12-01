from fastapi import WebSocket
from typing import Tuple
from ...models.game import GameState, Position, GameStatus

async def handle_move(websocket: WebSocket, game: GameState, player_id: str, payload: dict) -> Tuple[bool, str]:
    """Handle hero movement"""
    # Check game status
    if game.status != GameStatus.IN_PROGRESS:
        await websocket.send_json({
            "type": "error",
            "payload": {"message": "Game is not in progress"}
        })
        return False, "Game not in progress"

    # Check if it's the player's turn
    if game.current_turn != player_id:
        await websocket.send_json({
            "type": "error",
            "payload": {"message": "Not your turn"}
        })
        return False, "Not player's turn"

    # Get hero and target position
    hero_id = payload.get("hero_id")
    if not hero_id:
        await websocket.send_json({
            "type": "error",
            "payload": {"message": "No hero specified"}
        })
        return False, "No hero specified"

    target_pos = payload.get("position")
    if not target_pos or not isinstance(target_pos, dict):
        await websocket.send_json({
            "type": "error",
            "payload": {"message": "Invalid target position"}
        })
        return False, "Invalid target position"

    # Convert position dict to Position object
    try:
        target = Position(x=target_pos["x"], y=target_pos["y"])
    except (KeyError, TypeError):
        await websocket.send_json({
            "type": "error",
            "payload": {"message": "Invalid position format"}
        })
        return False, "Invalid position format"

    # Try to move the hero
    if not game.move_hero(hero_id, target):
        await websocket.send_json({
            "type": "error",
            "payload": {"message": "Invalid move"}
        })
        return False, "Invalid move"

    return True, ""

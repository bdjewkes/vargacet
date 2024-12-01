from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .ws.game_handler import manager
from .game.game_manager import game_manager
from pydantic import BaseModel
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Vargacet Game Server")

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

class CreateGameRequest(BaseModel):
    player_id: str

@app.get("/")
async def root():
    return {"message": "Vargacet Game Server"}

@app.get("/games")
async def list_games():
    """List all active games."""
    return game_manager.list_games()

@app.post("/game/create")
async def create_game(request: CreateGameRequest):
    """Create a new game session."""
    logger.info(f"Creating new game for player {request.player_id}")
    game = game_manager.create_game()
    # Add the creating player to the game
    game_manager.add_player_to_game(game.game_id, request.player_id)
    logger.info(f"Created game {game.game_id}")
    return {"game_id": game.game_id}

@app.get("/game/{game_id}")
async def get_game_status(game_id: str):
    """Get current game status."""
    game = game_manager.get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game.get_game_status()

@app.websocket("/ws/game/{game_id}/player/{player_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, player_id: str):
    logger.info(f"WebSocket connection attempt - Game: {game_id}, Player: {player_id}")
    
    # Attempt to connect player to game
    success = await manager.connect(websocket, game_id, player_id)
    if not success:
        logger.error(f"Failed to connect player {player_id} to game {game_id}")
        await websocket.close(code=4000)
        return

    try:
        while True:
            # Receive and process messages
            data = await websocket.receive_json()
            logger.info(f"Received message from player {player_id}: {data}")
            await manager.handle_message(game_id, player_id, data)
    except Exception as e:
        logger.error(f"Error in websocket connection: {e}")
    finally:
        manager.disconnect(game_id, player_id)

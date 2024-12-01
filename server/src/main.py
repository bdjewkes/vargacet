from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import uuid
import logging
from pydantic import BaseModel
from .ws.game_handler import manager
from .models.game import GameState

app = FastAPI(title="Vargacet Game Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CreateGameRequest(BaseModel):
    player_id: str

@app.get("/")
async def root():
    return {"message": "Vargacet Game Server"}

@app.get("/games")
async def list_games():
    """List all active games and their basic information."""
    games_list = []
    for game_id, game in manager.games.items():
        game_info = {
            "game_id": game_id,
            "status": game.status,
            "players": game.players,
            "player_count": len(game.players),
            "is_full": game.is_full()
        }
        games_list.append(game_info)
    return games_list

@app.post("/game")
async def create_game(request: CreateGameRequest):
    """Create a new game and add the creating player to it."""
    game_id = str(uuid.uuid4())
    game = GameState(game_id=game_id)
    manager.games[game_id] = game
    
    # Add the creating player to the game
    game.add_player(request.player_id)
    
    logger.info(f"Created game {game_id} for player {request.player_id}")
    return {"game_id": game_id}

@app.get("/game/{game_id}")
async def get_game(game_id: str):
    game = manager.games.get(game_id)
    if game:
        return game.get_game_status()
    logger.error(f"Game {game_id} not found")
    return {"error": "Game not found"}

@app.websocket("/ws/game/{game_id}/player/{player_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, player_id: str):
    try:
        # Create game if it doesn't exist
        if game_id not in manager.games:
            game = GameState(game_id=game_id)
            manager.games[game_id] = game

        game = manager.games[game_id]
        
        # Add player if not already in game
        if player_id not in game.players:
            if not game.add_player(player_id):
                logger.error(f"Failed to add player {player_id} to game {game_id}")
                await websocket.close(code=4000, reason="Game is full")
                return

        try:
            await manager.connect(websocket, game_id, player_id)
            logger.info(f"Player {player_id} connected to game {game_id}")
            
            while True:
                try:
                    data = await websocket.receive_json()
                    logger.info(f"Received message from player {player_id}: {data}")
                    await manager.handle_message(websocket, game_id, player_id, data)
                except Exception as e:
                    if isinstance(e, RuntimeError) and str(e) == "websocket.receive_json() called outside of a websocket connection":
                        logger.info(f"WebSocket connection closed for player {player_id}")
                        break
                    logger.error(f"Error handling message from player {player_id}: {str(e)}")
                    if websocket.client_state.CONNECTED:
                        await websocket.send_json({
                            "type": "error",
                            "payload": {"message": "Error processing message"}
                        })
                    
        except Exception as e:
            logger.error(f"WebSocket connection error for player {player_id}: {str(e)}")
            raise
            
    except Exception as e:
        logger.error(f"Unhandled WebSocket error for player {player_id}: {str(e)}")
    finally:
        logger.info(f"Cleaning up connection for player {player_id}")
        manager.disconnect(game_id, player_id)
        # Try to close the websocket if it's still open
        try:
            if not websocket.client_state.DISCONNECTED:
                await websocket.close()
        except Exception as e:
            logger.error(f"Error closing websocket for player {player_id}: {str(e)}")
        logger.info(f"Player {player_id} disconnected from game {game_id}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

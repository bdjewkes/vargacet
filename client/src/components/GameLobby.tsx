import React, { useState, useEffect, useCallback } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import Game from './Game';
import './GameLobby.css';

interface Player {
  player_id: string;
  name: string | null;
  connected: boolean;
}

interface GameState {
  game_id: string;
  players: Record<string, Player>;
  current_turn: string | null;
  is_full: boolean;
  status: 'lobby' | 'in_progress' | 'finished';
  grid_size: number;
}

interface GameLobbyProps {
  gameId: string;
  playerId: string;
}

export const GameLobby: React.FC<GameLobbyProps> = ({ gameId, playerId }) => {
  const [playerName, setPlayerName] = useState('');
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [hasInitialConnection, setHasInitialConnection] = useState(false);

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data);
      console.log('Received message:', data);
      
      if (data.type === 'error') {
        setError(data.payload.message);
      } else if (data.type === 'game_state') {
        setGameState(data.payload);
        setIsSubmitting(false);
      }
    } catch (error) {
      console.error('Error parsing message:', error);
    }
  }, []);

  const wsUrl = `ws://localhost:8000/ws/game/${gameId}/player/${playerId}`;
  const { sendMessage, isConnected } = useWebSocket(wsUrl, handleMessage);

  useEffect(() => {
    if (isConnected && !hasInitialConnection) {
      setHasInitialConnection(true);
    }
  }, [isConnected, hasInitialConnection]);

  const handleSubmitName = (e: React.FormEvent) => {
    e.preventDefault();
    if (!playerName.trim()) return;

    setIsSubmitting(true);
    sendMessage({
      type: 'update_name',
      payload: { name: playerName }
    });
  };

  const handleStartGame = () => {
    sendMessage({
      type: 'start_game'
    });
  };

  if (!isConnected) {
    return (
      <div className="game-lobby">
        <div className="connection-status">
          {hasInitialConnection ? 'Connection lost. Reconnecting...' : 'Connecting to game...'}
        </div>
        {error && <div className="error">{error}</div>}
      </div>
    );
  }

  if (!gameState) {
    return <div className="game-lobby">Loading game state...</div>;
  }

  if (gameState.status === 'in_progress') {
    return <Game gameState={gameState} playerId={playerId} />;
  }

  const currentPlayer = gameState.players[playerId];
  const canStartGame = gameState.is_full && Object.values(gameState.players).every(p => p.name);

  return (
    <div className="game-lobby">
      {error && <div className="error">{error}</div>}
      
      {!currentPlayer?.name ? (
        <form onSubmit={handleSubmitName} className="name-form">
          <input
            type="text"
            value={playerName}
            onChange={(e) => setPlayerName(e.target.value)}
            placeholder="Enter your name"
            disabled={isSubmitting}
          />
          <button type="submit" disabled={isSubmitting || !playerName.trim()}>
            {isSubmitting ? 'Setting name...' : 'Set Name'}
          </button>
        </form>
      ) : (
        <div className="lobby-info">
          <h2>Game Lobby</h2>
          <div className="players-list">
            {Object.values(gameState.players).map(player => (
              <div key={player.player_id} className="player-item">
                <span className={`status ${player.connected ? 'connected' : 'disconnected'}`} />
                <span>{player.name || 'Unnamed Player'}</span>
                {player.player_id === playerId && ' (You)'}
              </div>
            ))}
          </div>
          {canStartGame && (
            <button onClick={handleStartGame} className="start-game-button">
              Start Game
            </button>
          )}
          {!canStartGame && gameState.is_full && (
            <div className="waiting-message">
              Waiting for all players to set their names...
            </div>
          )}
          {!gameState.is_full && (
            <div className="waiting-message">
              Waiting for another player to join...
            </div>
          )}
        </div>
      )}
    </div>
  );
};

import React, { useState, useEffect } from 'react';
import { GameLobby } from './components/GameLobby';
import './App.css';

interface Player {
  player_id: string;
  name: string | null;
  connected: boolean;
}

interface Game {
  game_id: string;
  players: Record<string, Player>;
  is_full: boolean;
  player_count: number;
}

function App() {
  const [gameId, setGameId] = useState<string | null>(null);
  const [playerId] = useState(() => `player_${Math.random().toString(36).substr(2, 9)}`);
  const [games, setGames] = useState<Game[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const fetchGames = async () => {
    try {
      setFetchError(null);
      const response = await fetch('http://localhost:8000/games');
      if (!response.ok) {
        throw new Error(`Failed to fetch games: ${response.statusText}`);
      }
      const data = await response.json();
      console.log('Fetched games:', data); // Debug log
      setGames(data);
    } catch (error) {
      console.error('Error fetching games:', error);
      setFetchError(error instanceof Error ? error.message : 'Failed to fetch games');
    }
  };

  useEffect(() => {
    // Fetch games initially and every 5 seconds
    fetchGames();
    const interval = setInterval(fetchGames, 5000);
    return () => clearInterval(interval);
  }, []);

  const createGame = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('http://localhost:8000/game', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ player_id: playerId }),
      });
      if (!response.ok) {
        throw new Error(`Failed to create game: ${response.statusText}`);
      }
      const data = await response.json();
      setGameId(data.game_id);
      await fetchGames(); // Refresh games list
    } catch (error) {
      console.error('Error creating game:', error);
      setError(error instanceof Error ? error.message : 'Failed to create game');
    } finally {
      setLoading(false);
    }
  };

  const joinGame = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const id = formData.get('gameId') as string;
    if (id) {
      setGameId(id);
    }
  };

  if (gameId) {
    return <GameLobby 
      gameId={gameId} 
      playerId={playerId}
      onReturnToList={() => setGameId(null)}
    />;
  }

  return (
    <div className="app">
      <h1>Vargacet</h1>
      <div className="menu">
        <button onClick={createGame} disabled={loading}>
          {loading ? 'Creating...' : 'Create New Game'}
        </button>
        {error && <p className="error">{error}</p>}
        
        <div className="games-list">
          <h2>Active Games {fetchError && <span className="error">({fetchError})</span>}</h2>
          {games.length === 0 ? (
            <p>No active games</p>
          ) : (
            <ul>
              {games.map((game) => (
                <li key={game.game_id} className="game-item">
                  <span>Game {game.game_id.slice(0, 8)}...</span>
                  <span className="player-count">
                    Players: {game.player_count}/2
                  </span>
                  {!game.is_full && (
                    <button onClick={() => setGameId(game.game_id)}>
                      Join Game
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="divider">or</div>
        <form onSubmit={joinGame}>
          <input
            type="text"
            name="gameId"
            placeholder="Enter Game ID"
            required
          />
          <button type="submit">Join Game</button>
        </form>
      </div>
    </div>
  );
}

export default App;

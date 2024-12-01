import React, { useState, useMemo, useEffect } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import './Game.css';

interface Position {
  x: number;
  y: number;
}

interface Hero {
  id: string;
  position: Position;
  owner_id: string;
  current_hp: number;
  max_hp: number;
  damage: number;
  movement_points: number;
  armor: number;
}

interface Player {
  player_id: string;
  name: string | null;
  connected: boolean;
  heroes: Hero[];
}

interface GameState {
  game_id: string;
  players: { [key: string]: Player };
  current_turn: string | null;
  status: string;
  grid_size: number;
  obstacles: string[];  // Array of "x,y" strings
}

interface GameProps {
  gameState: GameState;
  playerId: string;
  onGameStateUpdate: (gameState: GameState) => void;
}

interface GridCell {
  hero?: Hero;
  isCurrentPlayer: boolean;
  isObstacle: boolean;
}

const Game: React.FC<GameProps> = ({ gameState, playerId, onGameStateUpdate }) => {
  const [selectedHero, setSelectedHero] = useState<Hero | null>(null);
  const [hoveredHero, setHoveredHero] = useState<Hero | null>(null);
  const [hasMoved, setHasMoved] = useState(false);

  const wsUrl = `ws://localhost:8000/ws/game/${gameState.game_id}/player/${playerId}`;
  const { send } = useWebSocket(wsUrl, (event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data);
      console.log('Game received message:', data);
      
      if (data.type === 'game_state') {
        // Update game state
        onGameStateUpdate(data.payload);
      }
    } catch (error) {
      console.error('Error parsing game message:', error);
    }
  });

  const isMyTurn = gameState.current_turn === playerId;

  // Create a grid with hero positions and obstacles
  const grid = useMemo(() => {
    const newGrid: GridCell[][] = Array(gameState.grid_size)
      .fill(null)
      .map(() => Array(gameState.grid_size).fill(null)
        .map(() => ({ isCurrentPlayer: false, isObstacle: false })));

    // Place obstacles
    const obstacleSet = new Set(gameState.obstacles);
    for (let y = 0; y < gameState.grid_size; y++) {
      for (let x = 0; x < gameState.grid_size; x++) {
        const key = `${x},${y}`;
        if (obstacleSet.has(key)) {
          newGrid[y][x].isObstacle = true;
        }
      }
    }

    // Place heroes
    Object.values(gameState.players).forEach(player => {
      player.heroes.forEach(hero => {
        newGrid[hero.position.y][hero.position.x] = {
          hero,
          isCurrentPlayer: hero.owner_id === playerId,
          isObstacle: false
        };
      });
    });

    return newGrid;
  }, [gameState, playerId]);

  // Calculate movement range using BFS
  const movementRange = useMemo(() => {
    if (!selectedHero || !isMyTurn || hasMoved) return new Set<string>();

    const range = new Set<string>();
    const queue: { x: number; y: number; moves: number }[] = [{
      x: selectedHero.position.x,
      y: selectedHero.position.y,
      moves: selectedHero.movement_points
    }];
    const visited = new Set<string>();
    const directions = [[-1, 0], [1, 0], [0, -1], [0, 1]];

    while (queue.length > 0) {
      const { x, y, moves } = queue.shift()!;
      const key = `${x},${y}`;

      if (visited.has(key)) continue;
      visited.add(key);

      // Add current position to range (except starting position)
      if (!(x === selectedHero.position.x && y === selectedHero.position.y)) {
        range.add(key);
      }

      if (moves === 0) continue;

      // Check all adjacent cells
      for (const [dx, dy] of directions) {
        const newX = x + dx;
        const newY = y + dy;
        const newKey = `${newX},${newY}`;

        // Check bounds
        if (newX < 0 || newX >= gameState.grid_size || 
            newY < 0 || newY >= gameState.grid_size) {
          continue;
        }

        // Skip if visited
        if (visited.has(newKey)) continue;

        // Skip if occupied by another hero or obstacle
        const cell = grid[newY][newX];
        if (cell.isObstacle || (cell.hero && cell.hero.id !== selectedHero.id)) {
          continue;
        }

        queue.push({ x: newX, y: newY, moves: moves - 1 });
      }
    }

    return range;
  }, [selectedHero, grid, gameState.grid_size, isMyTurn, hasMoved]);

  const handleCellClick = (x: number, y: number) => {
    if (!isMyTurn) return;

    const cell = grid[y][x];
    const key = `${x},${y}`;

    // If clicking on own hero and haven't moved yet, select it
    if (cell.hero && cell.isCurrentPlayer && !hasMoved) {
      setSelectedHero(cell.hero);
      return;
    }

    // If hero selected and clicking on valid move position, move hero
    if (selectedHero && movementRange.has(key) && !hasMoved) {
      send(JSON.stringify({
        type: 'move_hero',
        payload: {
          hero_id: selectedHero.id,
          position: { x, y }
        }
      }));
      setHasMoved(true);
      setSelectedHero(null);
    }
  };

  const handleEndTurn = () => {
    if (!isMyTurn || !hasMoved) return;

    // Reset local state
    setSelectedHero(null);
    setHasMoved(false);

    // Send end turn message
    send(JSON.stringify({
      type: 'end_turn',
      game_id: gameState.game_id,
      player_id: playerId
    }));
  };

  // Reset state when turn changes
  useEffect(() => {
    setSelectedHero(null);
    setHasMoved(false);
  }, [gameState.current_turn]);

  return (
    <div className="game-container">
      <div className="game-grid">
        {grid.map((row, y) => (
          <div key={y} className="grid-row">
            {row.map((cell, x) => {
              const key = `${x},${y}`;
              const isInRange = movementRange.has(key);
              const isSelected = selectedHero?.position.x === x && selectedHero?.position.y === y;

              return (
                <div
                  key={x}
                  className={`grid-cell${cell.isObstacle ? ' obstacle' : ''}${isInRange ? ' in-range' : ''}${isSelected ? ' selected' : ''}`}
                  onClick={() => handleCellClick(x, y)}
                >
                  {cell.hero && (
                    <div 
                      className={`hero${cell.isCurrentPlayer ? ' hero-player' : ' hero-opponent'}`}
                      onMouseEnter={() => setHoveredHero(cell.hero)}
                      onMouseLeave={() => setHoveredHero(null)}
                    />
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      <div className="game-sidebar">
        {(selectedHero || hoveredHero) ? (
          <div className="hero-stats">
            <h3>{selectedHero ? 'Selected Hero' : 'Hovered Hero'}</h3>
            <div className="stat-row">
              <span>HP:</span>
              <div className="hp-bar">
                <div 
                  className="hp-fill" 
                  style={{ width: `${((selectedHero || hoveredHero)!.current_hp / (selectedHero || hoveredHero)!.max_hp) * 100}%` }}
                />
                <span className="hp-text">
                  {(selectedHero || hoveredHero)!.current_hp}/{(selectedHero || hoveredHero)!.max_hp}
                </span>
              </div>
            </div>
            <div className="stat-row">
              <span>Movement:</span>
              <span>{(selectedHero || hoveredHero)!.movement_points}</span>
            </div>
            <div className="stat-row">
              <span>Damage:</span>
              <span>{(selectedHero || hoveredHero)!.damage}</span>
            </div>
            <div className="stat-row">
              <span>Armor:</span>
              <span>{(selectedHero || hoveredHero)!.armor}</span>
            </div>
          </div>
        ) : (
          <div className="hero-stats-placeholder">
            {isMyTurn ? (
              hasMoved ? 
                "End your turn when ready" :
                "Select a hero to move"
            ) : (
              "Opponent's turn"
            )}
          </div>
        )}
      </div>

      {isMyTurn && hasMoved && (
        <button 
          className="end-turn-button" 
          onClick={handleEndTurn}
        >
          End Turn
        </button>
      )}
    </div>
  );
};

export default Game;

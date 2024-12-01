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
  start_position?: Position;
  owner_id: string;
  current_hp: number;
  max_hp: number;
  damage: number;
  movement_points: number;
  armor: number;
  remaining_movement: number;
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
  const [remainingMovement, setRemainingMovement] = useState<number>(0);

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

  // Calculate Manhattan distance between two points
  const calculateDistance = (start: Position, end: Position): number => {
    return Math.abs(start.x - end.x) + Math.abs(start.y - end.y);
  };

  // Reset movement state
  const resetMovementState = () => {
    setSelectedHero(null);
    setHasMoved(false);
    setRemainingMovement(0);
  };

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

  // Calculate movement range based on remaining points and current position
  const movementRange = useMemo(() => {
    if (!selectedHero || !isMyTurn || (hasMoved && remainingMovement === 0)) {
      return new Set<string>();
    }

    const range = new Set<string>();
    const queue: { x: number; y: number; moves: number }[] = [
      { 
        x: selectedHero.position.x, 
        y: selectedHero.position.y, 
        moves: remainingMovement || selectedHero.movement_points 
      }
    ];
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
  }, [selectedHero, grid, gameState.grid_size, isMyTurn, hasMoved, remainingMovement]);

  const handleCellClick = (x: number, y: number) => {
    if (!isMyTurn) return;

    const clickedPosition = { x, y };
    const posKey = `${x},${y}`;

    // If there's a hero at the clicked position and it's the current player's hero
    const clickedHero = Object.values(gameState.players)
      .flatMap(p => p.heroes)
      .find(h => h.position.x === x && h.position.y === y);

    if (clickedHero?.owner_id === playerId) {
      setSelectedHero(clickedHero);
      return;
    }

    // If a hero is selected and the clicked cell is within range
    if (selectedHero) {
      // Check if the move is valid
      const distance = Math.abs(selectedHero.position.x - x) + Math.abs(selectedHero.position.y - y);
      if (distance <= selectedHero.remaining_movement) {
        send(JSON.stringify({
          type: 'move_hero',
          payload: {
            hero_id: selectedHero.id,
            position: clickedPosition
          }
        }));
        setHasMoved(true);
      }
      setSelectedHero(null);
    }
  };

  const handleEndTurn = () => {
    if (!isMyTurn || !hasMoved) return;

    // Reset local state
    resetMovementState();

    // Send end turn message
    send(JSON.stringify({
      type: 'end_turn',
      game_id: gameState.game_id,
      player_id: playerId
    }));
  };

  const handleUndoMove = () => {
    send(JSON.stringify({
      type: 'undo_move'
    }));
    setSelectedHero(null);
    setHasMoved(false);
  };

  // Reset state when turn changes
  useEffect(() => {
    resetMovementState();
  }, [gameState.current_turn]);

  return (
    <div className="game-container">
      <div className="game-info">
        <div className="turn-info">
          {isMyTurn ? "Your turn" : `${gameState.players[gameState.current_turn!]?.name}'s turn`}
        </div>
        {selectedHero && (
          <div className="hero-info">
            Selected Hero: {selectedHero.id} (Movement: {selectedHero.remaining_movement})
          </div>
        )}
      </div>
      <div className="game-area">
        <div className="game-grid">
          {grid.map((row, y) => (
            <div key={y} className="grid-row">
              {row.map((cell, x) => {
                const isInRange = selectedHero && 
                  Math.abs(selectedHero.position.x - x) + Math.abs(selectedHero.position.y - y) <= selectedHero.remaining_movement;
                const isSelected = selectedHero?.position.x === x && selectedHero?.position.y === y;
                
                return (
                  <div
                    key={x}
                    className={`grid-cell${cell.isObstacle ? ' obstacle' : ''}${
                      cell.hero ? ' has-hero' : ''
                    }${isInRange ? ' in-range' : ''}${isSelected ? ' selected' : ''}`}
                    onClick={() => handleCellClick(x, y)}
                    onMouseEnter={() => cell.hero && setHoveredHero(cell.hero)}
                    onMouseLeave={() => setHoveredHero(null)}
                  >
                    {cell.hero && (
                      <div
                        className={`hero${
                          cell.isCurrentPlayer ? ' current-player' : ''
                        }`}
                      >
                        H
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
        <div className="side-panel">
          {hoveredHero ? (
            <div className="hero-stats">
              <h3>Hero Stats</h3>
              <p>Owner: {gameState.players[hoveredHero.owner_id]?.name}</p>
              <p>HP: {hoveredHero.current_hp}/{hoveredHero.max_hp}</p>
              <p>Damage: {hoveredHero.damage}</p>
              <p>Armor: {hoveredHero.armor}</p>
              <p>Movement: {hoveredHero.movement_points}</p>
            </div>
          ) : (
            <div className="hero-stats-placeholder">
              {isMyTurn ? "Select a hero to move" : "Opponent's turn"}
            </div>
          )}
          {isMyTurn && (
            <div className="action-buttons">
              {hasMoved && (
                <button onClick={handleUndoMove} className="undo-button">
                  Undo Move
                </button>
              )}
              <button onClick={handleEndTurn} className="end-turn-button">
                End Turn
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Game;

import React, { useState, useMemo } from 'react';
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
}

interface GridCell {
  hero?: Hero;
  isCurrentPlayer: boolean;
  isObstacle: boolean;
}

const Game: React.FC<GameProps> = ({ gameState, playerId }) => {
  const [selectedHero, setSelectedHero] = useState<Hero | null>(null);

  // Create a grid with hero positions and obstacles
  const grid = useMemo(() => {
    console.log('Received game state:', gameState);
    console.log('Obstacles:', gameState.obstacles);

    const newGrid: GridCell[][] = Array(gameState.grid_size)
      .fill(null)
      .map(() => Array(gameState.grid_size).fill(null)
        .map(() => ({ isCurrentPlayer: false, isObstacle: false })));

    // Place obstacles
    const obstacleSet = new Set(gameState.obstacles);
    console.log('Obstacle set:', obstacleSet);
    
    for (let y = 0; y < gameState.grid_size; y++) {
      for (let x = 0; x < gameState.grid_size; x++) {
        const key = `${x},${y}`;
        if (obstacleSet.has(key)) {
          console.log('Setting obstacle at:', key);
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
    if (!selectedHero) return new Set<string>();

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

      // Add current position to range (except starting position if occupied by hero)
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
        if (cell.isObstacle || (cell.hero && 
            !(newX === selectedHero.position.x && newY === selectedHero.position.y))) {
          continue;
        }

        queue.push({ x: newX, y: newY, moves: moves - 1 });
      }
    }

    return range;
  }, [selectedHero, gameState.grid_size, grid]);

  return (
    <div className="game-container">
      <div className="game-sidebar">
        {selectedHero ? (
          <div className="hero-stats">
            <h3>Hero Stats</h3>
            <div className="stat-row">
              <span>HP:</span>
              <div className="hp-bar">
                <div 
                  className="hp-fill" 
                  style={{ width: `${(selectedHero.current_hp / selectedHero.max_hp) * 100}%` }}
                />
                <span className="hp-text">
                  {selectedHero.current_hp} / {selectedHero.max_hp}
                </span>
              </div>
            </div>
            <div className="stat-row">
              <span>Damage:</span>
              <span>{selectedHero.damage}</span>
            </div>
            <div className="stat-row">
              <span>Movement:</span>
              <span>{selectedHero.movement_points}</span>
            </div>
            <div className="stat-row">
              <span>Armor:</span>
              <span>{selectedHero.armor}</span>
            </div>
          </div>
        ) : (
          <div className="hero-stats-placeholder">
            Hover over a hero to see their stats
          </div>
        )}
        <div className="game-info">
          <div>Current Turn: {gameState.current_turn === playerId ? 'Your Turn' : 'Opponent\'s Turn'}</div>
          {Object.values(gameState.players).map(player => (
            <div key={player.player_id} className="player-info">
              <span>{player.name || 'Unnamed Player'}</span>
              <span className={`connection-status ${player.connected ? 'connected' : 'disconnected'}`}>
                {player.connected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
          ))}
        </div>
      </div>
      <div className="game-grid">
        {grid.map((row, y) => (
          <div key={y} className="grid-row">
            {row.map((cell, x) => {
              const isInRange = movementRange.has(`${x},${y}`);
              return (
                <div 
                  key={`${x}-${y}`} 
                  className={`grid-cell ${isInRange ? 'in-range' : ''} ${cell.isObstacle ? 'obstacle' : ''}`}
                  onMouseEnter={() => cell.hero && setSelectedHero(cell.hero)}
                  onMouseLeave={() => setSelectedHero(null)}
                >
                  {cell.hero && (
                    <div 
                      className={`hero ${cell.isCurrentPlayer ? 'hero-player' : 'hero-opponent'}`}
                      title={`Hero ${cell.hero.id}`}
                    >
                      <div 
                        className="hero-hp-bar"
                        style={{ width: `${(cell.hero.current_hp / cell.hero.max_hp) * 100}%` }}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
};

export default Game;

import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import './Game.css';

interface Position {
  x: number;
  y: number;
}

interface Effect {
  type: 'heal' | 'damage';
  amount: number;
}

interface Ability {
  id: string;
  name: string;
  range: number;
  effect: Effect;
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
  abilities: Ability[];
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
  moved_hero_id: string | null;  // Track which hero has moved this turn
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
  const [selectedAbility, setSelectedAbility] = useState<Ability | null>(null);
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

  const findPath = (
    startX: number,
    startY: number,
    endX: number,
    endY: number,
    maxDistance: number
  ): Position[] | null => {
    // BFS implementation
    const queue: Array<[number, number, Position[], number]> = [
      [startX, startY, [{ x: startX, y: startY }], 0],
    ];
    const visited = new Set<string>();
    const directions = [[0, 1], [1, 0], [0, -1], [-1, 0]]; // right, down, left, up

    const isValidPosition = (x: number, y: number): boolean => {
      if (x < 0 || x >= gameState.grid_size || y < 0 || y >= gameState.grid_size) {
        return false;
      }
      const posKey = `${x},${y}`;
      return !gameState.obstacles.includes(posKey);
    };

    const isOccupied = (x: number, y: number): boolean => {
      return Object.values(gameState.players)
        .flatMap(p => p.heroes)
        .some(h => h.position.x === x && h.position.y === y);
    };

    while (queue.length > 0) {
      const [x, y, path, distance] = queue.shift()!;
      const posKey = `${x},${y}`;

      if (x === endX && y === endY) {
        return path;
      }

      if (visited.has(posKey) || distance > maxDistance) {
        continue;
      }

      visited.add(posKey);

      for (const [dx, dy] of directions) {
        const newX = x + dx;
        const newY = y + dy;
        const newKey = `${newX},${newY}`;

        if (!visited.has(newKey) && 
            isValidPosition(newX, newY) && 
            !isOccupied(newX, newY)) {
          const newPath = [...path, { x: newX, y: newY }];
          queue.push([newX, newY, newPath, distance + 1]);
        }
      }
    }

    return null;
  };

  // Calculate movement range based on remaining points and current position
  const calculateMoveRange = useCallback(() => {
    if (!selectedHero || !isMyTurn || (gameState.moved_hero_id && gameState.moved_hero_id !== selectedHero.id)) return [];

    const range = new Set<string>();
    const maxRange = selectedHero.movement_points;

    // Try all positions within Manhattan distance + 1 to ensure we check all reachable squares
    for (let y = 0; y < gameState.grid_size; y++) {
      for (let x = 0; x < gameState.grid_size; x++) {
        const distance = Math.abs(selectedHero.position.x - x) + Math.abs(selectedHero.position.y - y);
        
        // Check positions within range + 1 to catch all possible paths
        if (distance <= maxRange + 1) {
          // Check if there's a valid path to this position
          const path = findPath(
            selectedHero.position.x,
            selectedHero.position.y,
            x,
            y,
            maxRange
          );
          
          // Only add if path exists and its length (minus start position) is within movement points
          if (path && (path.length - 1) <= maxRange) {
            range.add(`${x},${y}`);
          }
        }
      }
    }

    return Array.from(range).map(pos => {
      const [x, y] = pos.split(',').map(Number);
      return { x, y };
    });
  }, [selectedHero, gameState, isMyTurn]);

  // Memoize the movement range calculation
  const moveRange = useMemo(() => calculateMoveRange(), [calculateMoveRange]);

  const handleUseAbility = (targetHero: Hero) => {
    if (!selectedHero || !selectedAbility) return;

    send(JSON.stringify({
      type: 'use_ability',
      payload: {
        hero_id: selectedHero.id,
        target_hero_id: targetHero.id,
        ability_id: selectedAbility.id
      }
    }));

    setSelectedAbility(null);
    setSelectedHero(null);
  };

  const handleCellClick = (x: number, y: number) => {
    if (!isMyTurn) return;

    const clickedPosition = { x, y };
    const posKey = `${x},${y}`;

    // Find if there's a hero at the clicked position
    const clickedHero = Object.values(gameState.players)
      .flatMap(p => p.heroes)
      .find(h => h.position.x === x && h.position.y === y);

    // If we have a selected ability and click on a valid target
    if (selectedAbility && selectedHero && clickedHero) {
      const distance = Math.abs(selectedHero.position.x - x) + Math.abs(selectedHero.position.y - y);
      if (distance <= selectedAbility.range) {
        handleUseAbility(clickedHero);
        return;
      }
    }

    // Handle hero selection and movement
    if (clickedHero?.owner_id === playerId) {
      // Don't allow selecting a different hero if one has already moved
      if (gameState.moved_hero_id && gameState.moved_hero_id !== clickedHero.id) {
        return;
      }
      setSelectedHero(clickedHero);
      setSelectedAbility(null);
      return;
    }

    // Handle movement if no ability is selected
    if (selectedHero && !selectedAbility) {
      const distance = Math.abs(selectedHero.position.x - x) + Math.abs(selectedHero.position.y - y);
      if (distance <= selectedHero.movement_points) {
        send(JSON.stringify({
          type: 'move_hero',
          payload: {
            hero_id: selectedHero.id,
            position: clickedPosition
          }
        }));
      }
      setSelectedHero(null);
    }
  };

  const handleEndTurn = () => {
    if (!isMyTurn) return;

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
    // Note: We don't need to explicitly reset moved_hero_id here as it will come from the server's game state update
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
            Selected Hero: {selectedHero.id} (Movement: {selectedHero.movement_points})
          </div>
        )}
      </div>
      <div className="game-area">
        <div className="game-grid">
          {grid.map((row, y) => (
            <div key={y} className="grid-row">
              {row.map((cell, x) => {
                const isInRange = moveRange.some(pos => pos.x === x && pos.y === y);
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
                        <div className="hero-hp">{cell.hero.current_hp}/{cell.hero.max_hp}</div>
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
          ) : selectedHero ? (
            <div className="hero-abilities">
              <h3>Abilities</h3>
              <div className="ability-list">
                {selectedHero.abilities.map(ability => (
                  <button
                    key={ability.id}
                    className={`ability-button${selectedAbility?.id === ability.id ? ' selected' : ''}`}
                    onClick={() => setSelectedAbility(selectedAbility?.id === ability.id ? null : ability)}
                  >
                    {ability.name}
                    <span className="ability-effect">
                      ({ability.effect.type} {ability.effect.amount})
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="hero-stats-placeholder">
              {isMyTurn ? "Select a hero to act" : "Opponent's turn"}
            </div>
          )}
          {isMyTurn && (
            <div className="action-buttons">
              <button onClick={handleUndoMove}>Undo Move</button>
              <button onClick={handleEndTurn}>End Turn</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Game;

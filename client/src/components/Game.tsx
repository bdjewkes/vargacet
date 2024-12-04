import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import SoundManager from '../audio/SoundManager';
import Chat from './Chat';
import './Game.css';

interface Position {
  x: number;
  y: number;
}

interface Effect {
  type: 'heal' | 'damage';
  amount: number;
  area_of_effect?: number;
  shape?: 'circle' | 'square';
}

interface Ability {
  id: string;
  name: string;
  range: number;
  effect: Effect;
  action_cost: number;
  mana_cost: number;
}

interface Gauge {
  current: number;
  maximum: number;
}

interface Hero {
  id: string;
  position: Position;
  start_position?: Position;
  owner_id: string;
  hp: Gauge;
  mana: Gauge;
  damage: number;
  movement: Gauge;
  armor: number;
  action_points: Gauge;
  abilities: Ability[];
  name: string;
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
  obstacles: string[];
  moved_hero_id: string | null;
}

interface GameProps {
  gameState: GameState;
  playerId: string;
  onGameStateUpdate: (gameState: GameState) => void;
  onReturnToLobby?: () => void;
}

interface GridCell {
  hero?: Hero;
  isCurrentPlayer: boolean;
  isObstacle: boolean;
}

interface ChatMessage {
  sender_id: string;
  sender_name: string;
  content: string;
  timestamp: string;
  channel: string;
}

const Game: React.FC<GameProps> = ({ gameState, playerId, onGameStateUpdate, onReturnToLobby }) => {
  const [selectedHero, setSelectedHero] = useState<Hero | null>(null);
  const [hoveredHero, setHoveredHero] = useState<Hero | null>(null);
  const [selectedAbility, setSelectedAbility] = useState<Ability | null>(null);
  const [remainingMovement, setRemainingMovement] = useState<number>(0);
  const [gameStatus, setGameStatus] = useState<string>('');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [hoveredCell, setHoveredCell] = useState<Position | null>(null);

  const soundManager = useMemo(() => SoundManager.getInstance(), []);

  const wsUrl = `ws://localhost:8000/ws/game/${gameState.game_id}/player/${playerId}`;
  const { send } = useWebSocket(wsUrl, (event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data);
      console.log('Game received message:', data);

      if (data.type === 'game_state') {
        // Update game state
        onGameStateUpdate(data.payload);

        // Handle dead heroes
        if (data.dead_heroes && data.dead_heroes.length > 0) {
          data.dead_heroes.forEach((deadHero: Hero) => {
            // Play death sound
            soundManager.playDeathSound();

            // Clear selection if the dead hero was selected
            if (selectedHero?.id === deadHero.id) {
              setSelectedHero(null);
              setSelectedAbility(null);
            }
            // Clear hover if the dead hero was being hovered
            if (hoveredHero?.id === deadHero.id) {
              setHoveredHero(null);
            }
          });
        }

        // Handle game over
        if (data.winner_id) {
          const winnerName = data.winner_name || gameState.players[data.winner_id]?.name || 'Unknown Player';
          setGameStatus(`Game Over! ${winnerName} wins!`);
          setSelectedHero(null);
          setSelectedAbility(null);
          setHoveredHero(null);
        }
      } else if (data.type === 'chat_message') {
        // Handle chat messages
        setChatMessages(prev => [...prev, data.payload]);
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

  const getHeroAtPosition = (x: number, y: number): Hero | null => {
    return Object.values(gameState.players)
      .flatMap(p => p.heroes)
      .find(h => h.position.x === x && h.position.y === y) || null;
  };

  const findPath = (start: Position, end: Position, maxDistance: number, ignoreHeroes: boolean = false): Position[] | null => {
    // A* pathfinding implementation
    const queue: [Position, Position[], number][] = [
      [start, [start], 0]
    ];
    const visited = new Set<string>();

    while (queue.length > 0) {
      const [current, path, distance] = queue.shift()!;
      const key = `${current.x},${current.y}`;

      if (current.x === end.x && current.y === end.y) {
        return path;
      }

      if (visited.has(key)) continue;
      visited.add(key);

      if (distance >= maxDistance) continue;

      // Check all adjacent cells
      const moves = [
        { x: current.x + 1, y: current.y },
        { x: current.x - 1, y: current.y },
        { x: current.x, y: current.y + 1 },
        { x: current.x, y: current.y - 1 }
      ];

      for (const move of moves) {
        if (move.x < 0 || move.x >= gameState.grid_size || 
            move.y < 0 || move.y >= gameState.grid_size) continue;

        const moveKey = `${move.x},${move.y}`;
        if (visited.has(moveKey)) continue;
        
        // Check for obstacles
        if (gameState.obstacles.includes(moveKey)) continue;

        // Check for other heroes if we're not ignoring them
        if (!ignoreHeroes) {
          const heroAtPosition = getHeroAtPosition(move.x, move.y);
          if (heroAtPosition && (heroAtPosition.id !== selectedHero?.id)) continue;
        }

        queue.push([move, [...path, move], distance + 1]);
      }
    }

    return null;
  };

  const canMoveTo = (x: number, y: number): boolean => {
    if (!selectedHero || !isMyTurn) return false;
    if (gameState.moved_hero_id === selectedHero.id) return false;

    const targetPos = { x, y };
    const path = findPath(selectedHero.position, targetPos, selectedHero.movement.current, false);
    return path !== null;
  };

  const isInRange = (start: Position, end: Position, range: number): boolean => {
    if (!selectedHero || !isMyTurn) return false;

    // For abilities, we need line of sight - no obstacles in the way
    const path = findPath(start, end, range, true);
    if (!path) return false;

    // Check if path length is within range
    return path.length - 1 <= range;
  };

  const getAffectedCells = (targetX: number, targetY: number, ability: Ability): Position[] => {
    if (!ability.effect.area_of_effect) return [{ x: targetX, y: targetY }];

    const affected: Position[] = [];
    const range = ability.effect.area_of_effect;

    // Add all cells within Manhattan distance of range
    for (let x = 0; x < gameState.grid_size; x++) {
      for (let y = 0; y < gameState.grid_size; y++) {
        const distance = Math.abs(x - targetX) + Math.abs(y - targetY);
        if (distance <= range) {
          affected.push({ x, y });
        }
      }
    }

    return affected;
  };

  const getCellClassName = (x: number, y: number) => {
    let className = 'cell';
    const isValidMove = selectedHero && canMoveTo(x, y);
    const isValidTarget = selectedHero && selectedAbility && isInRange(selectedHero.position, { x, y }, selectedAbility.range);
    
    if (isValidMove) {
      className += ' valid-move';
    }
    
    if (isValidTarget) {
      className += ' valid-target';
    }

    // Only show AOE preview when hovering over a valid target
    if (hoveredCell && selectedAbility && selectedHero && 
        isInRange(selectedHero.position, hoveredCell, selectedAbility.range)) {
      const affectedCells = getAffectedCells(hoveredCell.x, hoveredCell.y, selectedAbility);
      if (affectedCells.some(cell => cell.x === x && cell.y === y)) {
        className += ' affected-cell';
      }
    }

    return className;
  };

  const renderCell = (x: number, y: number) => {
    const hero = getHeroAtPosition(x, y);
    const className = getCellClassName(x, y);

    return (
      <div
        key={`${x}-${y}`}
        className={className}
        onClick={() => handleCellClick(x, y)}
        onMouseEnter={() => setHoveredCell({ x, y })}
        onMouseLeave={() => setHoveredCell(null)}
      >
        {hero && (
          <div 
            className={`hero ${hero.owner_id === playerId ? 'player-hero' : 'enemy-hero'}`}
            title={`${hero.name} (HP: ${hero.hp.current}/${hero.hp.maximum})`}
          >
            {hero.name}
          </div>
        )}
      </div>
    );
  };

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

  const handleAbilityClick = (ability: Ability) => {
    setSelectedAbility(selectedAbility?.id === ability.id ? null : ability);
  };

  const handleCellClick = (x: number, y: number) => {
    // Disable interactions if game is over
    if (gameState.status === 'game_over') return;
    
    if (!isMyTurn) return;

    const targetHero = getHeroAtPosition(x, y);

    if (selectedHero && selectedAbility) {
      // Using an ability
      if (targetHero) {
        send({
          type: 'use_ability',
          payload: {
            hero_id: selectedHero.id,
            ability_id: selectedAbility.id,
            target_position: { x, y }  
          }
        });
        // Play ability sound
        soundManager.playAbilitySound(selectedAbility.id);
        setSelectedAbility(null);
      }
    } else if (selectedHero) {
      // Moving
      if (canMoveTo(x, y)) {
        send({
          type: 'move_hero',
          payload: {
            hero_id: selectedHero.id,
            position: { x, y }  
          }
        });
      }
    } else if (targetHero && targetHero.owner_id === playerId) {
      // Selecting a hero
      setSelectedHero(targetHero);
    }
  };

  const handleEndTurn = () => {
    // Disable end turn if game is over
    if (gameState.status === 'game_over') return;
    
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
    // Disable undo if game is over
    if (gameState.status === 'game_over') return;
    
    send(JSON.stringify({
      type: 'undo_move'
    }));
    setSelectedHero(null);
    setSelectedAbility(null);
    setHoveredHero(null);
  };

  const handleSendMessage = (content: string, channel: string) => {
    send(JSON.stringify({
      type: 'chat_message',
      payload: {
        content,
        channel,
        player_name: gameState.players[playerId]?.name || 'Unknown Player'
      }
    }));
  };

  const renderStatPanel = (hero: Hero) => {
    if (!hero) return null;
    
    const isCurrentPlayer = hero.owner_id === playerId;
    const healthPercent = (hero.hp.current / hero.hp.maximum) * 100;
    const manaPercent = (hero.mana.current / hero.mana.maximum) * 100;
    
    return (
      <div className="stat-panel">
        <div className="stat-row">
          <div className="stat-label">HP</div>
          <div className="stat-bar-container">
            <div className="stat-bar" style={{ width: `${healthPercent}%`, backgroundColor: '#ff4444' }} />
            <div className="stat-text">{`${hero.hp.current}/${hero.hp.maximum}`}</div>
          </div>
        </div>
        <div className="stat-row">
          <div className="stat-label">MP</div>
          <div className="stat-bar-container">
            <div className="stat-bar" style={{ width: `${manaPercent}%`, backgroundColor: '#4444ff' }} />
            <div className="stat-text">{`${hero.mana.current}/${hero.mana.maximum}`}</div>
          </div>
        </div>
        <div className="stat-row">
          <span className="stat-label">AP</span>
          <div className="action-points">
            {Array.from({ length: hero.action_points.maximum }).map((_, i) => (
              <div 
                key={i} 
                className={`action-point ${i < hero.action_points.current ? 'active' : ''}`}
              />
            ))}
          </div>
        </div>
        <div className="stat-row">
          <span className="stat-label">MV</span>
          <div className="movement-points">
            {Array.from({ length: hero.movement.maximum }).map((_, i) => (
              <div 
                key={i} 
                className={`movement-point ${i < hero.movement.current ? 'active' : ''}`}
              />
            ))}
          </div>
        </div>
      </div>
    );
  };

  const renderAbilityPanel = (hero: Hero) => {
    if (!hero || hero.owner_id !== playerId) return null;
    
    return (
      <div className="ability-panel">
        {hero.abilities.map((ability) => (
          <button
            key={ability.id}
            className={`ability-button ${selectedAbility?.id === ability.id ? 'selected' : ''}`}
            onClick={() => handleAbilityClick(ability)}
            disabled={!isMyTurn || hero.action_points.current < ability.action_cost || hero.mana.current < ability.mana_cost}
          >
            <div className="ability-info">
              <span className="ability-name">{ability.name}</span>
              <span className="ability-effect">
                ({ability.effect.type} {ability.effect.amount})
              </span>
            </div>
            <div className="ability-cost">
              {ability.action_cost > 0 && (
                <div className="ap-cost">
                  {Array.from({ length: ability.action_cost }).map((_, i) => (
                    <div key={i} className="action-point active" />
                  ))}
                </div>
              )}
              {ability.mana_cost > 0 && <span className="mp-cost">{ability.mana_cost} MP</span>}
            </div>
          </button>
        ))}
      </div>
    );
  };

  // Update selected hero when game state changes
  useEffect(() => {
    if (selectedHero) {
      // Find the updated hero in the new game state
      const updatedHero = Object.values(gameState.players)
        .flatMap(p => p.heroes)
        .find(h => h.id === selectedHero.id);
      
      if (updatedHero) {
        setSelectedHero(updatedHero);
      }
    }
  }, [gameState, selectedHero]);

  // Reset state when turn changes
  useEffect(() => {
    resetMovementState();
  }, [gameState.current_turn]);

  useEffect(() => {
    // Clear selected hero if it no longer exists in the game state
    if (selectedHero) {
      const heroStillExists = Object.values(gameState.players).some(player => 
        player.heroes.some(hero => hero.id === selectedHero.id)
      );
      if (!heroStillExists) {
        setSelectedHero(null);
        setSelectedAbility(null);
      }
    }
  }, [gameState, selectedHero]);

  useEffect(() => {
    // Clear hovered hero if it no longer exists in the game state
    if (hoveredHero) {
      const heroStillExists = Object.values(gameState.players).some(player => 
        player.heroes.some(hero => hero.id === hoveredHero.id)
      );
      if (!heroStillExists) {
        setHoveredHero(null);
      }
    }
  }, [gameState, hoveredHero]);

  return (
    <div className="game-container">
      <div className="game-area">
        <div className="game-status">
          <div>Turn: {gameState.players[gameState.current_turn || '']?.name || 'Unknown'}</div>
          {gameState.status === 'IN_PROGRESS' && (
            <div>{isMyTurn ? "Your turn!" : "Opponent's turn"}</div>
          )}
        </div>

        <div className="game-grid">
          {Array.from({ length: gameState.grid_size * gameState.grid_size }, (_, i) => {
            const x = i % gameState.grid_size;
            const y = Math.floor(i / gameState.grid_size);
            return renderCell(x, y);
          })}
        </div>
      </div>

      <div className="side-panel">
        {(hoveredHero || selectedHero) ? (
          <div className="hero-info-panel">
            <div className="hero-stats">
              <h3>Hero {hoveredHero?.name || selectedHero?.name}</h3>
              {renderStatPanel(hoveredHero || selectedHero)}
              <div className="stat-row">
                <span>Owner:</span>
                <span>{gameState.players[hoveredHero?.owner_id || selectedHero?.owner_id]?.name}</span>
              </div>
              <div className="stat-row">
                <span>Damage:</span>
                <span>{hoveredHero?.damage || selectedHero?.damage || 0}</span>
              </div>
              <div className="stat-row">
                <span>Armor:</span>
                <span>{hoveredHero?.armor || selectedHero?.armor || 0}</span>
              </div>
            </div>
            
            {renderAbilityPanel(selectedHero)}
          </div>
        ) : (
          <div className="hero-stats-placeholder">
            {gameState.status === 'game_over' ? gameStatus : 
              isMyTurn ? "Select a hero to act" : "Opponent's turn"}
          </div>
        )}
        {isMyTurn && (
          <div className="action-buttons">
            <button className="undo-button" onClick={handleUndoMove}>Undo Move</button>
            <button className="end-turn-button" onClick={handleEndTurn}>End Turn</button>
          </div>
        )}
      </div>

      <Chat
        gameId={gameState.game_id}
        playerId={playerId}
        playerName={gameState.players[playerId]?.name || 'Unknown Player'}
        onSendMessage={handleSendMessage}
        messages={chatMessages}
      />

      {gameState.status === 'game_over' && (
        <div className="game-over-overlay">
          <div className="game-over-message">
            {gameStatus}
            <button 
              className="return-to-lobby-button"
              onClick={() => onReturnToLobby?.()}
            >
              Return to Game List
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default Game;

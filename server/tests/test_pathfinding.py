import unittest
import sys
import os

# Add the server directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.game import GameState, Position, PlayerState, Hero, GameStatus

class TestPathfinding(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.game = GameState(
            game_id="test_game",
            grid_size=5,
            heroes_per_player=1,
            status=GameStatus.IN_PROGRESS
        )
        self.player1 = "p1"
        self.player2 = "p2"
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        
        # Manually create heroes for testing
        hero1 = Hero(
            id=f"{self.player1}_hero_1",
            position=Position(x=0, y=0),
            owner_id=self.player1,
            name="A"
        )
        hero2 = Hero(
            id=f"{self.player2}_hero_1",
            position=Position(x=4, y=4),
            owner_id=self.player2,
            name="B"
        )
        
        # Add heroes to players
        self.game.players[self.player1].heroes.append(hero1)
        self.game.players[self.player2].heroes.append(hero2)
        
        # Get references to heroes for testing
        self.hero1 = self.game.players[self.player1].heroes[0]
        self.hero2 = self.game.players[self.player2].heroes[0]
        
        # Add obstacles at (0,1)
        self.game.obstacles = set([
            "0,1",  # Block direct path
        ])

    def test_path_distances(self):
        """Test path distances from (0,0) to all positions in the grid"""
        # Dictionary to store expected distances
        # None means unreachable
        expected_distances = {
            (0, 0): 0,  # Starting position
            (0, 1): None,  # Obstacle
            (0, 2): 4,  # Must go around obstacle
            (0, 3): 5,
            (0, 4): 6,
            (1, 0): 1,
            (1, 1): 2,
            (1, 2): 3,
            (1, 3): 4,
            (1, 4): 5,
        }
        
        hero = self.game.players[self.player1].heroes[0]
        
        # Test each position
        for (x, y), expected_dist in expected_distances.items():
            target = Position(x=x, y=y)
            path = self.game.find_path(hero.position, target, max_distance=10)
            
            if expected_dist is None:
                self.assertIsNone(
                    path,
                    f"Position ({x},{y}) should be unreachable, but found path: {path}"
                )
            else:
                self.assertIsNotNone(
                    path,
                    f"Position ({x},{y}) should be reachable with distance {expected_dist}, but no path found"
                )
                actual_dist = len(path) - 1  # Subtract 1 because path includes start position
                self.assertEqual(
                    actual_dist,
                    expected_dist,
                    f"Position ({x},{y}): Expected distance {expected_dist}, but got {actual_dist}. Path: {path}"
                )
                
    def test_path_validity(self):
        """Test that paths are valid (no diagonal movement, no obstacles)"""
        hero = self.game.players[self.player1].heroes[0]
        
        # Test path to (0,2) which must go around the obstacle
        target = Position(x=0, y=2)
        path = self.game.find_path(hero.position, target, max_distance=10)
        
        self.assertIsNotNone(path)
        
        # Convert path to list of tuples for easier testing
        path_coords = [(p.x, p.y) for p in path]
        
        expected_path = [(0,0), (1,0), (1,1), (1,2), (0,2)]
        
        self.assertEqual(
            path_coords,
            expected_path,
            f"Path to (0,2) should go around obstacle. Expected {expected_path}, but got {path_coords}"
        )
        
        # Verify no diagonal movement
        for i in range(len(path) - 1):
            dx = abs(path[i+1].x - path[i].x)
            dy = abs(path[i+1].y - path[i].y)
            self.assertEqual(
                dx + dy,
                1,
                f"Invalid movement between {path[i]} and {path[i+1]}: movement must be horizontal or vertical"
            )

    def test_movement_points_reset(self):
        """Test that movement points are reset at the start of each turn"""
        # Set current turn to p1
        self.game.current_turn = self.player1
        hero1 = self.game.players[self.player1].heroes[0]
        
        # Get initial movement points
        initial_movement = hero1.movement_points
        self.assertEqual(initial_movement, 5, "Initial movement points should be 5")
        
        # Move hero1, consuming some movement points
        hero1.move_to(Position(x=1, y=0), self.game)
        after_move_movement = hero1.movement_points
        self.assertEqual(after_move_movement, 4, "Should have 4 movement points after moving 1 space")
        
        # Change turn to p2 and back to p1
        self.game.set_next_turn()  # p1 -> p2
        self.game.set_next_turn()  # p2 -> p1
        
        # Verify hero1's movement points are reset
        self.assertEqual(
            hero1.movement_points,
            hero1.max_movement,
            f"Movement points should be reset to {hero1.max_movement} at start of turn, but got {hero1.movement_points}"
        )
        self.assertEqual(
            hero1.movement_points,
            initial_movement,
            "Movement points should be reset to initial value"
        )
        self.assertGreater(
            hero1.movement_points,
            after_move_movement,
            "Movement points should be greater after reset than after move"
        )

    def test_move_to_2_3(self):
        """Test that a hero can move from (0,0) to (2,3) with 5 movement points"""
        # Get the hero
        hero = self.game.players[self.player1].heroes[0]
        hero.movement_points = 5  # Set movement points to 5
        
        # Try to move to (2,3)
        target = Position(x=2, y=3)
        path = self.game.find_path(hero.position, target, max_distance=5)
        
        # Path should exist and be exactly 5 steps:
        # (0,0) -> (1,0) -> (2,0) -> (2,1) -> (2,2) -> (2,3)
        self.assertIsNotNone(path)
        self.assertEqual(len(path), 6)  # 6 positions including start and end
        
        # Verify path is correct with only orthogonal moves
        expected_path = [
            Position(x=0, y=0),  # Start
            Position(x=1, y=0),  # Right
            Position(x=2, y=0),  # Right
            Position(x=2, y=1),  # Up
            Position(x=2, y=2),  # Up
            Position(x=2, y=3),  # Up
        ]
        self.assertEqual(len(path), len(expected_path))
        for actual, expected in zip(path, expected_path):
            self.assertEqual(actual.x, expected.x)
            self.assertEqual(actual.y, expected.y)
        
        # Verify we can actually make the move
        success = hero.move_to(target, self.game)
        self.assertTrue(success)
        self.assertEqual(hero.position.x, 2)
        self.assertEqual(hero.position.y, 3)
        
        # Verify movement points were consumed correctly
        expected_cost = len(path) - 1  # 5 steps
        self.assertEqual(hero.movement_points, 5 - expected_cost)

    def test_can_move_to_within_range(self):
        # Test movements within range (movement_points = 5)
        self.assertTrue(self.game.can_move_to(self.hero1.id, Position(x=1, y=1)))  # One step down
        self.assertTrue(self.game.can_move_to(self.hero1.id, Position(x=2, y=0)))  # One step right
        self.assertTrue(self.game.can_move_to(self.hero1.id, Position(x=3, y=2)))  # Within range
        self.assertTrue(self.game.can_move_to(self.hero1.id, Position(x=1, y=4)))  # Max range down
        self.assertTrue(self.game.can_move_to(self.hero1.id, Position(x=4, y=1)))  # Diagonal within range

    def test_cannot_move_to_out_of_range(self):
        # Test movements out of range
        self.assertFalse(self.game.can_move_to(self.hero1.id, Position(x=1, y=5)))  # Too far down
        self.assertFalse(self.game.can_move_to(self.hero1.id, Position(x=5, y=2)))  # Out of grid
        self.assertFalse(self.game.can_move_to(self.hero1.id, Position(x=-1, y=0)))  # Out of grid

    def test_cannot_move_to_occupied_position(self):
        # Try to move to second player's hero position
        target_pos = Position(x=4, y=4)  # Position of player2's first hero
        self.assertFalse(self.game.can_move_to(self.hero1.id, target_pos))

    def test_cannot_move_to_obstacle(self):
        # Add an obstacle
        self.game.obstacles.add("2,2")
        
        # Try to move to obstacle
        self.assertFalse(self.game.can_move_to(self.hero1.id, Position(x=2, y=2)))

    def test_cannot_move_after_moving(self):
        self.game.start_game()
        
        # Move the hero
        self.game.move_hero(self.hero1.id, Position(x=1, y=1))
        
        # Try to move again
        self.assertFalse(self.game.can_move_to(self.hero1.id, Position(x=1, y=2)))


    def test_game_over(self):
        self.game.start_game()
        
        # Kill one hero
        hero = self.game.players[self.player1].heroes[0]
        hero.hp.current = 0  # Set HP to 0 using Gauge
        
        dead_heroes = self.game.remove_dead_heroes()
        
        self.assertEqual(len(dead_heroes), 1)
        self.assertEqual(self.game.status.value, "game_over")  # Compare the enum value
        self.assertEqual(self.game.current_turn, self.player2)  # Winner

    def test_path_validity(self):
        """Test that paths are valid (no diagonal movement, no obstacles)"""
        start = Position(x=0, y=0)
        end = Position(x=2, y=2)
        
        path = self.game.find_path(start, end, 5)
        
        # Path should exist
        self.assertIsNotNone(path)
        
        # Path should be a list of positions
        self.assertTrue(all(isinstance(pos, Position) for pos in path))
        
        # Each step should be adjacent (no diagonal movement)
        for i in range(len(path) - 1):
            dx = abs(path[i+1].x - path[i].x)
            dy = abs(path[i+1].y - path[i].y)
            self.assertTrue((dx == 1 and dy == 0) or (dx == 0 and dy == 1))

    def test_path_distances(self):
        """Test path distances from (0,0) to all positions in the grid"""
        start = Position(x=0, y=0)
        
        # Test some specific positions
        test_positions = [
            (Position(x=1, y=1), 2),  # Diagonal requires 2 moves
            (Position(x=2, y=0), 2),  # Straight line
            (Position(x=2, y=2), 4),  # Manhattan distance
        ]
        
        for end_pos, expected_length in test_positions:
            path = self.game.find_path(start, end_pos, 5)
            self.assertIsNotNone(path)
            self.assertEqual(len(path) - 1, expected_length)

    def test_move_to_2_3(self):
        """Test that a hero can move from (0,0) to (2,3) with 5 movement points"""
        start = Position(x=0, y=0)
        end = Position(x=2, y=3)
        
        path = self.game.find_path(start, end, 5)
        
        self.assertIsNotNone(path)
        self.assertLessEqual(len(path) - 1, 5)  # Path length should be within movement points

    def test_movement_points_reset(self):
        """Test that movement points are reset at the start of each turn"""
        # Move hero to use some points
        self.game.move_hero(self.hero1.id, Position(x=1, y=0))
        used_points = self.hero1.movement.current
        
        # End turn and start new turn
        self.game.set_next_turn()
        self.game.set_next_turn()  # Back to first player
        
        # Movement points should be reset
        self.assertEqual(self.hero1.movement.current, self.hero1.movement.maximum)
        self.assertGreater(self.hero1.movement.current, used_points)

if __name__ == '__main__':
    unittest.main()

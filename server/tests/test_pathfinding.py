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
        self.game.players = {
            "p1": PlayerState(
                player_id="p1",
                name="Player 1",
                heroes=[
                    Hero(
                        id="h1",
                        position=Position(x=0, y=0),
                        owner_id="p1"
                    )
                ]
            )
        }
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
        
        hero = self.game.players["p1"].heroes[0]
        
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
        hero = self.game.players["p1"].heroes[0]
        
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
        # Add a second player
        self.game.players["p2"] = PlayerState(
            player_id="p2",
            name="Player 2",
            heroes=[
                Hero(
                    id="h2",
                    position=Position(x=4, y=4),
                    owner_id="p2"
                )
            ]
        )
        
        # Set current turn to p1
        self.game.current_turn = "p1"
        hero1 = self.game.players["p1"].heroes[0]
        
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
        hero = self.game.players["p1"].heroes[0]
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

if __name__ == '__main__':
    unittest.main()

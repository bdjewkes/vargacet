# Description

Vargacet is a turn-based tactical combat game for two players. Each player controls a party of 4 heroes positioned on a 2d grip. On their turn, each player can move a hero and an ability to either attack an enemy hero, or to provide some benefit to themselves or their allies.

# Architecture

Vargacet is built with a python server using the latest version of flask on the backend, with a client written in typescript for the frontend. The server is responsible for handling the game logic and state, and the client is responsible for rendering the game and handling user input.

The client and the server communicate using the websockets protocol, and the server is responsible for broadcasting game state updates to all connected clients.

The server will send messages over websockets indicating: 
- a new game has started, with the complete state of the game
- when a player's turn has started, with the complete state of the game
- when a player's turn has ended, with the complete state of the game

The client will send messages over websockets indicating the actions that they wish to take on their turn: 
- when a player has moved a hero
- when a player has used an ability


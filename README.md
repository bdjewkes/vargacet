# Return to Vargacet

A turn-based tactical combat game for two players. This project is written with heavy use of Windsurf's Cascade AI agent as an experiment in the use of AI-powered editors.

## Project Structure

```
vargacet/
├── server/           # Python FastAPI backend
│   ├── src/
│   │   ├── main.py  # FastAPI application entry point
│   │   ├── game/    # Game logic
│   │   ├── models/  # Data models
│   │   └── ws/      # WebSocket handlers
│   ├── tests/       # Backend tests
│   └── requirements.txt
│
└── client/          # TypeScript frontend
    ├── src/
    │   ├── components/  # React components
    │   ├── game/        # Game state management
    │   ├── models/      # TypeScript interfaces
    │   └── ws/          # WebSocket client
    ├── public/      # Static assets
    ├── package.json
    └── tsconfig.json
```

## Setup

### Backend (Python)

1. Create a virtual environment:
```bash
cd server
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the server:
```bash
uvicorn src.main:app --reload
```

### Frontend (TypeScript)

1. Install dependencies:
```bash
cd client
npm install
```

2. Start the development server:
```bash
npm run dev
```

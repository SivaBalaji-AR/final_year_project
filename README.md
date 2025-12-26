
# AI Interviewer App Instructions

## Prerequisites
1.  **API Keys**: You must configure your API keys in the `.env` files.
    -   **Frontend**: `frontend/.env.local`
    -   **Backend**: `backend/.env`

## Configuration

### Backend (`backend/.env`)
```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret
ASSEMBLYAI_API_KEY=your_assemblyai_key
GOOGLE_API_KEY=your_gemini_api_key
```

### Frontend (`frontend/.env.local`)
```env
NEXT_PUBLIC_LIVEKIT_URL=wss://your-project.livekit.cloud
```

## Running the App

### 1. Start the Backend
You need to run **both** the Agent and the API server in separate terminals.

**Terminal 1 (Agent):**
```bash
cd backend
.\venv\Scripts\activate
python agent.py dev
```
*Wait for it to say "connected to room".*

**Terminal 2 (API):**
```bash
cd backend
.\venv\Scripts\activate
uvicorn main:app --reload
```

### 2. Start the Frontend
**Terminal 3:**
```bash
cd frontend
npm run dev
```

### 3. Usage
- Open `http://localhost:3000`.


# AI Interviewer App Instructions

## Prerequisites
1.  **API Keys**: You must configure your API keys in the `.env` files.
    -   **Frontend**: `frontend/.env.local`
    -   **Backend**: `backend/.env`

## Configuration

### Backend (`backend/.env`)
```env
ASSEMBLYAI_API_KEY=your_assemblyai_key
GROQ_API_KEY=your_gemini_api_key
CARTESIA_API_KEY=your_cartesia_api_key
```

## Installation

### Backend Dependencies
**Terminal 1:**
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### Frontend Dependencies
**Terminal 2:**
```bash
cd frontend
npm install
```

## Running the App

### 1. Start the Backend

**Terminal 1 (API):**
```bash
cd backend
.\venv\Scripts\activate
uvicorn main:app --reload
```

### 2. Start the Frontend
**Terminal 2:**
```bash
cd frontend
npm start
```

### 3. Usage
- Open `http://localhost:3000`.

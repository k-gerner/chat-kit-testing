# ChatKit Testing

Demo app that pairs a Python ChatKit server with a React ChatKit UI.

## What’s In This Repo

- **Backend**: FastAPI + `openai-chatkit` server implementation.
- **Agent**: OpenAI Agents SDK using `FileSearchTool` (vector store ID is hardcoded).
- **Frontend**: React + `@openai/chatkit-react` with a references panel and UI controls
  for color scheme, radius, density, and chat width.

## Project Structure

```
chat-kit-testing/
├── backend/
│   ├── app.py                # Main ChatKit server (FastAPI + Agents)
│   ├── simple_store.py       # In-memory thread store
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── App.tsx           # ChatKit React integration + references panel
    │   ├── main.tsx
    │   └── index.css
    ├── package.json
    └── .env.example
```

## Prerequisites

- Python 3.10+
- Node.js 18.18+
- npm 9+
- OpenAI API key (required for the Agents + FileSearchTool flow)

## Backend Setup

1. `cd backend`
2. `python -m venv venv`
3. `source venv/bin/activate` (Windows: `venv\Scripts\activate`)
4. `pip install -r requirements.txt`
5. `cp .env.example .env` and set:
   ```
   OPENAI_API_KEY=sk-your-key
   OPENAI_PROJECT_ID=proj_your_project_id
   PORT=8000
   ```
6. Run the server:
   ```bash
   python app.py
   ```

Endpoints:
- `POST /chatkit` — ChatKit protocol endpoint (SSE streaming)
- `GET /health` — Health check
- `POST /api/chatkit_session` — Disabled (currently commented out in `backend/app.py`)

## Frontend Setup

1. `cd frontend`
2. `npm install`
3. `cp .env.example .env` (defaults are fine for local dev)
4. `npm run dev`

The app runs at `http://localhost:3000`.

## Notes / Configuration

- The backend loads `backend/.env` explicitly and `OPENAI_PROJECT_ID` can be used to pin
  requests to a specific OpenAI project.
- The vector store ID is hardcoded in `backend/app.py`. Update `VECTOR_STORE_ID`
  to point at your own store.
- The ChatKit session endpoints are currently commented out in `backend/app.py`.

## Tech Stack

**Backend**
- FastAPI
- openai-chatkit
- openai-agents (Agents SDK)
- httpx

**Frontend**
- React 19
- TypeScript
- @openai/chatkit-react
- Vite
- Tailwind CSS

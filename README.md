# user-agent

FastAPI + Groq LangChain agent that manages **projects** and **tasks** by calling the Node.js Project Camp API.

## Architecture (current)

```
Caller (curl / later Node)
  → POST /agent/run + Authorization: Bearer <userJWT>
  → set_access_token(jwt)
  → Groq create_agent + ALL_TOOLS
  → tools → Node /api/v1/projects|tasks
  → clear_access_token
  → { ok, answer, messages }
```

Node.js still owns login/RBAC. This service does **not** issue JWTs; it only forwards the user token to Node when tools run.

## Setup

```bash
uv sync
cp .env.example .env   # set GROQ_API_KEY
```

### Environment

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | — | Required Groq API key |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Chat model with tool calling |
| `NODE_API_BASE_URL` | `http://localhost:3000/api/v1` | Node REST base |

## Run

```bash
uv run uvicorn user_agent.api.app:app --reload --port 8000
# or
uv run user-agent
```

- Docs: http://localhost:8000/docs
- Health: `GET /health`

## API

### `POST /agent/run`

**Headers:** `Authorization: Bearer <accessToken>`  
**Body:**

```json
{ "query": "List my projects" }
```

**Response:**

```json
{
  "ok": true,
  "answer": "...",
  "messages": []
}
```

## Manual smoke checklist

1. Start Node on port `3000` with Mongo + JWT secrets configured.
2. Login via Node (`POST /api/v1/auth/login`) and copy `accessToken`.
3. Start this service on port `8000`.
4. Call health: `curl http://localhost:8000/health`
5. Call agent:

```bash
curl -X POST http://localhost:8000/agent/run \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"List my projects\"}"
```

6. Confirm the answer reflects real Node data (tools hit `/api/v1/projects`).
7. Try a mutation query such as `Create a project called Smoke Test`.

## Tests

```bash
uv run python -m unittest discover -s tests -v
```

## Next work

- Node proxy route that verifies JWT then calls this `/agent/run`
- Frontend UI for natural-language project/task commands

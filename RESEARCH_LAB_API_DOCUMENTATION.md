# Research Lab API Documentation

## Overview
The Research Lab allows analysts to explore datasets, run code blocks, and generate hypotheses. This page interacts with two backend APIs.

## Endpoints

### POST /api/quant/hypotheses
**Purpose:** Create a new hypothesis from an observation.

**Authentication:** JWT required (Authorization: Bearer <token>)

**Request body:**
```json
{
  "title": "string (required)",
  "description": "string (required)",
  "symbol": "string (optional)",
  "timeframe": "string (optional)",
  "status": "string (optional, default: 'draft')"
}
```

**Response:** Hypothesis object
```json
{
  "id": 123,
  "title": "string",
  "description": "string",
  "symbol": "string",
  "timeframe": "string",
  "status": "draft",
  "created_at": "2025-06-20T..."
}
```

**Errors:**
- 400: validation error
- 401: unauthorized
- 500: server error

**Example:**
```bash
curl -X POST http://localhost:8000/api/quant/hypotheses \
  -H "Authorization: Bearer <jwt>" \
  -H "Content-Type: application/json" \
  -d '{"title":"My Hypothesis","description":"Test"}'
```

### POST /api/v2/ai/chat
**Purpose:** Send a message to the AI advisor in the Research terminal.

**Authentication:** JWT recommended but not enforced in the endpoint (currently optional). Include Authorization header if available.

**Request body:**
```json
{
  "message": "string (required)",
  "context": "string (optional, default: 'research')"
}
```

**Response:**
```json
{
  "response": "string",
  "confidence": 0.73,
  "reasoning": "string",
  "suggestions": [...]
}
```

**Errors:**
- 401: if JWT required but missing
- 500: server error

**Example:**
```javascript
window.apiFetch('/api/v2/ai/chat', {
  method: 'POST',
  body: JSON.stringify({ message: 'Analyze volatility regime', context: 'research' })
}).then(r => r.json()).then(console.log);
```

## JavaScript Integration
- Use `window.apiFetch` wrapper which automatically attaches JWT.
- Always JSON.stringify request body and set `Content-Type: application/json`.
- Handle errors by checking `response.ok` and reading `response.json()` for `detail` field.

## Mock Data in Current Implementation
- `datasetMeta`: Hard‑coded dataset metadata in research_lab.js
- `mockObs`: Pre‑loaded observation examples
- `blockOutputs`: Preset execution output strings

## Future Enhancements
- Replace mock execution with real Python execution service
- Add file upload API for custom datasets
- Serve dataset metadata from backend
- WebSocket streaming for terminal AI responses

## Testing Checklist
- [ ] POST `/api/quant/hypotheses` with valid JWT creates a DB record
- [ ] Same endpoint returns 401 without JWT
- [ ] Invalid payload returns 400 with error detail
- [ ] POST `/api/v2/ai/chat` returns a valid AI response
- [ ] Commit flow redirects to `/hypotheses` page after success
- [ ] No sensitive data exposed in logs
- [ ] Rate limiting works (if applicable)

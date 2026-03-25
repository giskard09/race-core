# race-core

FastAPI backend for Giskard Race — lap engine on port 8013.

## Run

```bash
python3 race.py
```

Or via systemd:
```bash
systemctl --user start race-core.service
```

## Requirements

```bash
pip install fastapi uvicorn httpx
```

## Architecture

- Memory backend: Giskard Memory at `http://localhost:8005`
- Payment: phoenixd at `http://127.0.0.1:9740`
- Namespaces:
  - `race-registry` — agent registrations
  - `{agent_id}` — individual agent laps
  - `race-circuit` — shared circuit (all laps from all agents)

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /agent/enlist | Register agent (first 20 free) |
| POST | /agent/activate | Verify Lightning payment |
| POST | /agent/lap | Record a lap |
| POST | /agent/load | Load agent race state |
| GET | /circuit | All agents + recent laps |
| GET | /circuit/search | Search across all laps |
| GET | /leaderboard | Top 10 by lap count |
| GET | /health | Service status |

## Part of Giskard trilogy

race-core is the motion engine. craft-core is the world engine. anima-core is the soul bridge.

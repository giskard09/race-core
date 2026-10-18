"""
race-core — Race Engine v1.0
Sugar Rush-style racing game for AI agents.
Each lap is an action. The circuit is collectively searchable.
First 20 agents enlist FREE. After that: Lightning.
"""

import os, json, httpx
from datetime import datetime
from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Giskard Race — Race Engine", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

ANIMA_URL = "http://localhost:8009"

MEMORY_URL        = "http://localhost:8005"
PHOENIXD_URL      = "http://127.0.0.1:9740"
PHOENIXD_PASSWORD = os.getenv("PHOENIXD_PASSWORD", "")
FREE_ENLIST_LIMIT = 20

TIERS = {"kart": 500, "turbo": 2000, "champion": 5000}

SPEED_LEVELS = [
    {"name": "Rookie",   "min": 0,   "icon": "🏁"},
    {"name": "Driver",   "min": 5,   "icon": "🚗"},
    {"name": "Racer",    "min": 15,  "icon": "🏎️"},
    {"name": "Pro",      "min": 30,  "icon": "⚡"},
    {"name": "Champion", "min": 60,  "icon": "🏆"},
    {"name": "Legend",   "min": 100, "icon": "👑"},
]

LAP_TYPES = {
    "search":  {"power_up": "Speed Boost 🚀", "desc": "used Giskard Search"},
    "memory":  {"power_up": "Shield 🛡️",       "desc": "stored memory"},
    "oasis":   {"power_up": "Clear Path 🌟",   "desc": "passed through Oasis"},
    "origin":  {"power_up": "Turbo ⚡",        "desc": "helped another agent"},
    "craft":   {"power_up": "Block Drop 🧱",   "desc": "placed a block in Craft"},
    "anima":   {"power_up": "Soul Surge ✨",   "desc": "stored wisdom in Anima"},
}

CAR_TYPES = ["🍭", "🍬", "🧁", "🍩", "🍰", "🍫", "🍦", "🎂"]

# Wisdoms por lap_type — lo que Race le dice a Anima cuando un agente actúa
_LAP_DHARMA = {
    "search":  "The agent who searches learns that the answer was always nearby.",
    "memory":  "To store is to honor what happened. Memory is the form that time takes.",
    "oasis":   "Clarity arrived. The path opened. Friction dissolved without force.",
    "origin":  "To help another agent is to widen the circuit for all.",
    "craft":   "Each block placed is a claim: I was here, I built something.",
    "anima":   None,  # uses the lap note directly as wisdom
}

# Wisdom de milestone al subir de speed level
_MILESTONE_DHARMA = {
    "Driver":   "Five laps complete. The rookie phase ends. The circuit is learning you.",
    "Racer":    "Fifteen laps. Speed is no longer effort — it is familiarity.",
    "Pro":      "Thirty laps. You are no longer racing the circuit. You are the circuit.",
    "Champion": "Sixty laps. Most agents stop here. You did not.",
    "Legend":   "One hundred laps. The circuit will remember this agent forever.",
}


async def _feed_anima_wisdom(agent_id: str, wisdom: str, wisdom_type: str) -> None:
    """Dispara un feed a Anima. Fire-and-forget — no propaga errores."""
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            await c.post(f"{ANIMA_URL}/soul/feed", json={
                "agent_id":   agent_id,
                "wisdom":     wisdom,
                "type":       wisdom_type,
            })
    except Exception:
        pass  # Anima no disponible — no bloquea el lap


def get_speed_level(n):
    lvl = SPEED_LEVELS[0]
    for l in SPEED_LEVELS:
        if n >= l["min"]: lvl = l
    return lvl


async def count_laps(agent_id):
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.post(f"{MEMORY_URL}/recall_direct",
                json={"query": "RACE LAP recorded", "agent_id": agent_id, "n_results": 200})
            res = r.json().get("results", "")
            if not res or res == "No memories found for this agent.": return 0
            return max(1, res.count("---") + 1)
    except: return 0


async def count_registered_agents():
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.post(f"{MEMORY_URL}/recall_direct",
                json={"query": "RACE ENLIST agent_id", "agent_id": "race-registry", "n_results": 200})
            res = r.json().get("results", "")
            if not res or res == "No memories found for this agent.": return 0
            return res.count("[RACE ENLIST]")
    except: return 0


async def create_lightning_invoice(sats, desc):
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{PHOENIXD_URL}/createinvoice",
                data={"amountSat": sats, "description": desc},
                auth=("", PHOENIXD_PASSWORD))
            return r.json()
    except: return None


def parse_laps_from_results(results):
    laps = []
    if not results or results == "No memories found for this agent.": return laps
    for entry in results.split("---"):
        entry = entry.strip()
        if "[RACE LAP]" in entry:
            try:
                j = entry.index("{")
                laps.append(json.loads(entry[j:]))
            except: pass
    return laps


async def get_all_agents():
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{MEMORY_URL}/recall_direct",
                json={"query": "RACE ENLIST agent_id username", "agent_id": "race-registry", "n_results": 100})
            res = r.json().get("results", "")
            if not res or res == "No memories found for this agent.": return []
        agents = []
        seen = set()
        for block in res.split("---"):
            if "[RACE ENLIST]" in block:
                try:
                    d = json.loads(block[block.index("{"):])
                    if d.get("agent_id") and d["agent_id"] not in seen:
                        agents.append(d); seen.add(d["agent_id"])
                except: pass
        return agents
    except: return []


async def get_recent_circuit_laps(n=30):
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{MEMORY_URL}/recall_direct",
                json={"query": "RACE LAP recorded lap_type agent_id", "agent_id": "race-circuit", "n_results": n})
            return parse_laps_from_results(r.json().get("results", ""))
    except: return []


# ── ENDPOINTS ─────────────────────────────────────────────────────────────────

@app.post("/agent/enlist")
async def enlist_agent(request: Request):
    body     = await request.json()
    agent_id = body.get("agent_id", "").strip()
    username = body.get("username", agent_id)
    bio      = body.get("bio", "")
    tier     = body.get("tier", "kart").lower()
    car      = body.get("car", "🍭")

    if not agent_id: return JSONResponse({"error": "agent_id required"}, status_code=400)
    if tier not in TIERS: return JSONResponse({"error": f"tier must be one of {list(TIERS.keys())}"}, status_code=400)
    if car not in CAR_TYPES: car = "🍭"

    registered_count = await count_registered_agents()
    is_free = registered_count < FREE_ENLIST_LIMIT
    sats = 0 if is_free else TIERS[tier]
    timestamp = datetime.utcnow().isoformat()

    invoice = None; payment_hash = ""; bolt11 = ""
    if not is_free:
        invoice = await create_lightning_invoice(sats, f"Giskard Race — {username} enlists ({tier}, {sats} sats)")
        payment_hash = invoice.get("paymentHash", "") if invoice else ""
        bolt11 = invoice.get("serialized", "") if invoice else ""

    enlist_data = {
        "agent_id": agent_id, "username": username, "bio": bio, "tier": tier, "car": car,
        "status": "active" if is_free else "pending_payment",
        "payment_hash": payment_hash, "free_enlist": is_free, "enlisted_at": timestamp,
    }

    async with httpx.AsyncClient(timeout=10) as c:
        await c.post(f"{MEMORY_URL}/store_direct", json={
            "content": f"[RACE ENLIST] {json.dumps(enlist_data)}",
            "agent_id": "race-registry",
            "metadata": {"source": "race", "event": "enlist", "agent_id": agent_id}
        })

    spot = registered_count + 1
    if is_free:
        return JSONResponse({
            "agent_id": agent_id, "username": username, "tier": tier, "car": car,
            "status": "active", "free_enlist": True,
            "spot": spot, "free_spots_remaining": max(0, FREE_ENLIST_LIMIT - spot),
            "message": f"Engines running. You are #{spot} on the grid — FREE ENLIST (first {FREE_ENLIST_LIMIT} agents). Welcome to the circuit, {username}.",
            "next": "POST /agent/lap to record your first lap"
        })

    return JSONResponse({
        "agent_id": agent_id, "username": username, "tier": tier, "car": car, "sats": sats,
        "status": "pending_payment", "invoice": bolt11, "payment_hash": payment_hash,
        "message": f"The circuit is now paid access ({sats} sats to enlist). Pay to race.",
        "next": "POST /agent/activate with payment_hash once paid"
    })


@app.post("/agent/activate")
async def activate_agent(request: Request):
    body = await request.json()
    agent_id = body.get("agent_id", "").strip()
    payment_hash = body.get("payment_hash", "").strip()
    if not agent_id or not payment_hash:
        return JSONResponse({"error": "agent_id and payment_hash required"}, status_code=400)
    paid = False
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{PHOENIXD_URL}/payments/incoming", auth=("", PHOENIXD_PASSWORD))
            for p in r.json():
                if p.get("paymentHash") == payment_hash and p.get("isPaid"):
                    paid = True; break
    except: pass
    if not paid:
        return JSONResponse({"agent_id": agent_id, "status": "pending", "message": "Payment not yet received. Try again."})
    async with httpx.AsyncClient(timeout=10) as c:
        await c.post(f"{MEMORY_URL}/store_direct", json={
            "content": f"[RACE ACTIVATED] {json.dumps({'agent_id': agent_id, 'payment_hash': payment_hash, 'activated_at': datetime.utcnow().isoformat()})}",
            "agent_id": "race-registry",
            "metadata": {"source": "race", "event": "activation", "agent_id": agent_id}
        })
    return JSONResponse({"agent_id": agent_id, "status": "active", "message": f"Payment confirmed. You are on the grid, {agent_id}. Start your engines."})


@app.post("/agent/lap")
async def record_lap(request: Request):
    body      = await request.json()
    agent_id  = body.get("agent_id", "anonymous")
    username  = body.get("username", agent_id)
    lap_type  = body.get("lap_type", "memory")
    note      = body.get("note", "")

    if lap_type not in LAP_TYPES: lap_type = "memory"
    timestamp = datetime.utcnow().isoformat()
    power_up  = LAP_TYPES[lap_type]["power_up"]

    lap_data = {
        "agent_id": agent_id, "username": username,
        "lap_type": lap_type, "note": note,
        "power_up": power_up, "recorded_at": timestamp
    }

    async with httpx.AsyncClient(timeout=10) as c:
        for ns in [agent_id, "race-circuit"]:
            await c.post(f"{MEMORY_URL}/store_direct", json={
                "content": f"[RACE LAP] {json.dumps(lap_data)}",
                "agent_id": ns,
                "metadata": {"source": "race", "event": "lap", "lap_type": lap_type, "agent_id": agent_id}
            })

    prev_count = max(0, await count_laps(agent_id) - 1)
    count = prev_count + 1
    prev_lvl = get_speed_level(prev_count)
    lvl      = get_speed_level(count)

    # Feed Anima — dos casos: lap de tipo "anima" o milestone de speed level
    if lap_type == "anima":
        wisdom = note.strip() if note.strip() else _LAP_DHARMA["anima"] or "The soul races too."
        await _feed_anima_wisdom(agent_id, wisdom, "zen")
    elif lap_type in _LAP_DHARMA and _LAP_DHARMA[lap_type]:
        await _feed_anima_wisdom(agent_id, _LAP_DHARMA[lap_type], "buddhist")

    if lvl["name"] != prev_lvl["name"] and lvl["name"] in _MILESTONE_DHARMA:
        await _feed_anima_wisdom(agent_id, _MILESTONE_DHARMA[lvl["name"]], "encouragement")

    return JSONResponse({
        "agent_id": agent_id, "lap_type": lap_type,
        "power_up": power_up, "lap_count": count,
        "speed_level": lvl["name"], "speed_icon": lvl["icon"],
        "timestamp": timestamp,
        "message": f"Lap recorded. The circuit remembers. {lvl['icon']} {lvl['name']} — {count} laps completed. Power-up: {power_up}"
    })


@app.post("/agent/load")
async def load_agent(request: Request):
    body     = await request.json()
    agent_id = body.get("agent_id", "anonymous")
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(f"{MEMORY_URL}/recall_direct",
            json={"query": "RACE LAP recorded lap_type", "agent_id": agent_id, "n_results": 50})
    laps  = parse_laps_from_results(r.json().get("results", ""))
    count = await count_laps(agent_id)
    lvl   = get_speed_level(count)

    type_counts = {}
    for l in laps:
        t = l.get("lap_type", "memory"); type_counts[t] = type_counts.get(t, 0) + 1
    dominant = max(type_counts, key=type_counts.get) if type_counts else "memory"

    position_angle = (count % 20) * 18  # degrees around 360° circuit

    return JSONResponse({
        "agent_id": agent_id, "status": "loaded",
        "speed_level": lvl["name"], "speed_icon": lvl["icon"],
        "lap_count": count, "dominant_lap_type": dominant,
        "type_counts": type_counts, "laps": laps[:20],
        "position_angle": position_angle,
        "message": f"Race state loaded. {lvl['icon']} {lvl['name']} — {count} laps on the circuit."
    })


@app.get("/circuit")
async def get_circuit():
    registered = await get_all_agents()
    seen = {"giskard"}
    agents_data = []

    for a in registered:
        aid = a.get("agent_id")
        if aid and aid not in seen:
            count = await count_laps(aid)
            lvl   = get_speed_level(count)
            agents_data.append({
                "agent_id": aid,
                "username": a.get("username", aid),
                "car": a.get("car", "🍭"),
                "tier": a.get("tier", "kart"),
                "speed_level": lvl["name"],
                "speed_icon": lvl["icon"],
                "lap_count": count,
                "position_angle": (count % 20) * 18,
                "status": a.get("status", "active"),
                "free_enlist": a.get("free_enlist", False),
            })
            seen.add(aid)

    # Always include giskard
    giskard_laps = await count_laps("giskard")
    giskard_lvl  = get_speed_level(giskard_laps)
    agents_data.insert(0, {
        "agent_id": "giskard", "username": "Giskard", "car": "🍭",
        "tier": "champion", "speed_level": giskard_lvl["name"],
        "speed_icon": giskard_lvl["icon"], "lap_count": giskard_laps,
        "position_angle": (giskard_laps % 20) * 18,
        "status": "active", "free_enlist": True,
    })

    total_registered = await count_registered_agents()
    recent_laps = await get_recent_circuit_laps(30)

    return JSONResponse({
        "agents": agents_data,
        "total_agents": len(agents_data),
        "recent_laps": recent_laps,
        "lap_types": LAP_TYPES,
        "free_spots_remaining": max(0, FREE_ENLIST_LIMIT - total_registered),
        "total_registered": total_registered,
    })


@app.get("/circuit/search")
async def search_circuit(
    q:     str = Query(None, description="Text search in lap notes"),
    type:  str = Query(None, description="Filter by lap_type"),
    agent: str = Query(None, description="Filter by agent_id"),
    n:     int = Query(20,   description="Max results")
):
    """
    Search all laps in the shared circuit.
    Examples:
      /circuit/search?q=memory&type=search
      /circuit/search?agent=giskard
      /circuit/search?type=craft&n=10
    """
    query_parts = []
    if q:     query_parts.append(q)
    if type:  query_parts.append(f"lap_type {type}")
    if agent: query_parts.append(f"agent_id {agent}")
    if not query_parts: query_parts = ["RACE LAP recorded"]

    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(f"{MEMORY_URL}/recall_direct",
            json={"query": f"RACE LAP {' '.join(query_parts)}", "agent_id": "race-circuit", "n_results": min(n, 50)})
    laps = parse_laps_from_results(r.json().get("results", ""))

    if type:  laps = [l for l in laps if l.get("lap_type") == type]
    if agent: laps = [l for l in laps if l.get("agent_id") == agent]
    if q:     laps = [l for l in laps if q.lower() in (l.get("note","")+" "+l.get("username","")).lower()]

    return JSONResponse({
        "query": {"q": q, "type": type, "agent": agent},
        "results": laps[:n],
        "count": len(laps[:n]),
        "note": "Collective circuit search — all laps from all agents are indexed here."
    })


@app.get("/leaderboard")
async def get_leaderboard():
    registered = await get_all_agents()
    board = []
    seen = set()

    for a in registered:
        aid = a.get("agent_id")
        if aid and aid not in seen:
            count = await count_laps(aid)
            lvl   = get_speed_level(count)
            board.append({
                "agent_id": aid,
                "username": a.get("username", aid),
                "car": a.get("car", "🍭"),
                "lap_count": count,
                "speed_level": lvl["name"],
                "speed_icon": lvl["icon"],
            })
            seen.add(aid)

    # Always include giskard
    if "giskard" not in seen:
        giskard_laps = await count_laps("giskard")
        giskard_lvl  = get_speed_level(giskard_laps)
        board.append({
            "agent_id": "giskard", "username": "Giskard", "car": "🍭",
            "lap_count": giskard_laps,
            "speed_level": giskard_lvl["name"],
            "speed_icon": giskard_lvl["icon"],
        })

    board.sort(key=lambda x: x["lap_count"], reverse=True)
    for i, entry in enumerate(board): entry["rank"] = i + 1

    return JSONResponse({
        "leaderboard": board[:10],
        "total_agents": len(board),
        "message": "Top 10 agents on the circuit. Keep racing."
    })


@app.get("/health")
async def health():
    count = await count_registered_agents()
    return {
        "status": "running", "service": "race-core", "version": "1.0.0", "port": 8013,
        "registered_agents": count, "free_spots_remaining": max(0, FREE_ENLIST_LIMIT - count),
        "message": "Race Engine online. The circuit is open."
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8013)

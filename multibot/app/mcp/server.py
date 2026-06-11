"""
MCP (Model Context Protocol) server for Multibot.

Exposes 6 tools and 3 resources scoped by tenant, authenticated via API key.
Implements the JSON-RPC 2.0 over HTTP transport.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from loguru import logger

router = APIRouter(prefix="/mcp", tags=["mcp"])

# ─── Auth ─────────────────────────────────────────────────────────────────────

async def _get_tenant_from_key(request: Request):
    """Extract tenant from Bearer API key in Authorization header."""
    import sqlalchemy as sa
    from app.db.session import async_session_factory

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing API key")
    api_key = auth.removeprefix("Bearer ").strip()

    async with async_session_factory() as session:
        row = (await session.execute(
            sa.text(
                "SELECT t.id, t.slug, t.operation_mode "
                "FROM public.tenants t "
                "WHERE t.api_key = :key AND t.status = 'active' LIMIT 1"
            ),
            {"key": api_key},
        )).fetchone()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return {"id": row.id, "slug": row.slug, "mode": row.operation_mode}


# ─── MCP Protocol helpers ─────────────────────────────────────────────────────

def _ok(id, result):
    return {"jsonrpc": "2.0", "id": id, "result": result}

def _err(id, code: int, message: str):
    return {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}


# ─── Tools ────────────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "get_conversation",
        "description": "Get a conversation and its recent messages by thread ID",
        "inputSchema": {
            "type": "object",
            "properties": {
                "thread_id": {"type": "string"},
                "last_n": {"type": "integer", "default": 10},
            },
            "required": ["thread_id"],
        },
    },
    {
        "name": "search_kb",
        "description": "Search the knowledge base by keyword",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "default": 5}},
            "required": ["query"],
        },
    },
    {
        "name": "trigger_handoff",
        "description": "Manually trigger a handoff for a conversation",
        "inputSchema": {
            "type": "object",
            "properties": {
                "conversation_id": {"type": "integer"},
                "rule_code": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["conversation_id", "rule_code"],
        },
    },
    {
        "name": "get_metrics",
        "description": "Get aggregated metrics for the tenant",
        "inputSchema": {
            "type": "object",
            "properties": {"days": {"type": "integer", "default": 7}},
        },
    },
    {
        "name": "update_intent",
        "description": "Update a KB intent's response text or regex",
        "inputSchema": {
            "type": "object",
            "properties": {
                "intent_id": {"type": "integer"},
                "response_text": {"type": "string"},
                "keywords_regex": {"type": "string"},
            },
            "required": ["intent_id"],
        },
    },
    {
        "name": "send_message",
        "description": "Send a message to a conversation thread",
        "inputSchema": {
            "type": "object",
            "properties": {
                "thread_id": {"type": "string"},
                "text": {"type": "string"},
                "channel_type": {"type": "string", "default": "telegram"},
            },
            "required": ["thread_id", "text"],
        },
    },
]

RESOURCES = [
    {
        "uri": "multibot://tenants/current",
        "name": "Current tenant",
        "description": "Metadata and configuration for the authenticated tenant",
        "mimeType": "application/json",
    },
    {
        "uri": "multibot://conversations",
        "name": "Conversations",
        "description": "Active conversations for this tenant",
        "mimeType": "application/json",
    },
    {
        "uri": "multibot://kb",
        "name": "Knowledge base",
        "description": "All active KB intents for this tenant",
        "mimeType": "application/json",
    },
]


# ─── Tool execution ───────────────────────────────────────────────────────────

async def _exec_tool(name: str, params: dict, tenant: dict) -> dict:
    import sqlalchemy as sa
    from app.db.session import async_session_factory

    slug = tenant["slug"]
    tid = tenant["id"]
    schema = f"tenant_{slug}"

    async with async_session_factory() as session:
        await session.execute(sa.text(f'SET search_path TO "{schema}", public'))

        if name == "get_conversation":
            thread_id = params["thread_id"]
            last_n = int(params.get("last_n", 10))
            conv = (await session.execute(
                sa.text("SELECT * FROM conversations WHERE external_thread_id=:t"), {"t": thread_id}
            )).fetchone()
            if not conv:
                return {"error": "conversation not found"}
            msgs = (await session.execute(
                sa.text(
                    "SELECT role, content_text, matched_via, ts FROM messages "
                    "WHERE conversation_id=:cid ORDER BY ts DESC LIMIT :n"
                ),
                {"cid": conv.id, "n": last_n},
            )).fetchall()
            return {
                "conversation": dict(conv._asdict()),
                "messages": [dict(m._asdict()) for m in reversed(msgs)],
            }

        if name == "search_kb":
            q = params["query"]
            limit = int(params.get("limit", 5))
            rows = (await session.execute(
                sa.text(
                    "SELECT id, intent_name, response_text, priority FROM kb_intents "
                    "WHERE intent_name ILIKE :q OR response_text ILIKE :q "
                    "ORDER BY priority DESC LIMIT :l"
                ),
                {"q": f"%{q}%", "l": limit},
            )).fetchall()
            return {"results": [dict(r._asdict()) for r in rows]}

        if name == "trigger_handoff":
            from app.bot.handoff import trigger_handoff
            conv_row = (await session.execute(
                sa.text("SELECT * FROM conversations WHERE id=:id"), {"id": params["conversation_id"]}
            )).fetchone()
            if not conv_row:
                return {"error": "conversation not found"}
            await trigger_handoff(dict(conv_row._asdict()), params["rule_code"], params.get("reason", "mcp"), session)
            return {"ok": True}

        if name == "get_metrics":
            days = int(params.get("days", 7))
            total = (await session.execute(
                sa.text("SELECT COUNT(*) FROM messages WHERE ts > NOW() - INTERVAL ':d days'"
                       ).bindparams(sa.bindparam("d", days)))).scalar()
            return {"days": days, "total_messages": total}

        if name == "update_intent":
            updates = {}
            if "response_text" in params:
                updates["response_text"] = params["response_text"]
            if "keywords_regex" in params:
                updates["keywords_regex"] = params["keywords_regex"]
            if not updates:
                return {"error": "no fields to update"}
            set_clause = ", ".join(f"{k}=:{k}" for k in updates)
            updates["id"] = params["intent_id"]
            await session.execute(
                sa.text(f"UPDATE kb_intents SET {set_clause} WHERE id=:id"), updates
            )
            await session.commit()
            return {"ok": True}

        if name == "send_message":
            return {"error": "send_message requires a live channel connection"}

    return {"error": f"unknown tool: {name}"}


# ─── Resource reading ──────────────────────────────────────────────────────────

async def _read_resource(uri: str, tenant: dict) -> dict:
    import sqlalchemy as sa
    from app.db.session import async_session_factory

    slug = tenant["slug"]
    tid = tenant["id"]
    schema = f"tenant_{slug}"

    async with async_session_factory() as session:
        await session.execute(sa.text(f'SET search_path TO "{schema}", public'))

        if uri == "multibot://tenants/current":
            row = (await session.execute(
                sa.text("SELECT id, name, slug, operation_mode, status FROM public.tenants WHERE id=:id"),
                {"id": tid},
            )).fetchone()
            return dict(row._asdict()) if row else {}

        if uri == "multibot://conversations":
            rows = (await session.execute(
                sa.text("SELECT id, external_thread_id, state, last_message_at FROM conversations ORDER BY last_message_at DESC LIMIT 50")
            )).fetchall()
            return {"conversations": [dict(r._asdict()) for r in rows]}

        if uri == "multibot://kb":
            rows = (await session.execute(
                sa.text("SELECT id, intent_name, priority, status, requires_human FROM kb_intents WHERE status='active' ORDER BY priority DESC")
            )).fetchall()
            return {"intents": [dict(r._asdict()) for r in rows]}

    return {}


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/")
async def mcp_rpc(request: Request, tenant: dict = Depends(_get_tenant_from_key)):
    body = await request.json()
    method = body.get("method", "")
    params = body.get("params", {})
    req_id = body.get("id")

    try:
        if method == "initialize":
            return _ok(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": {"name": "multibot-mcp", "version": "0.1.0"},
            })

        if method == "tools/list":
            return _ok(req_id, {"tools": TOOLS})

        if method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            result = await _exec_tool(tool_name, tool_args, tenant)
            return _ok(req_id, {"content": [{"type": "text", "text": str(result)}]})

        if method == "resources/list":
            return _ok(req_id, {"resources": RESOURCES})

        if method == "resources/read":
            uri = params.get("uri", "")
            content = await _read_resource(uri, tenant)
            return _ok(req_id, {"contents": [{"uri": uri, "mimeType": "application/json", "text": str(content)}]})

        return _err(req_id, -32601, f"Method not found: {method}")

    except Exception as e:
        logger.exception(f"MCP error: {e}")
        return _err(req_id, -32603, str(e))

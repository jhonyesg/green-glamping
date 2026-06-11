"""Track LLM usage metrics in public.llm_usage."""

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession


async def record_usage(
    session: AsyncSession,
    tenant_id: int,
    provider_id: int | None,
    conversation_id: int | None,
    latency_ms: int,
    tokens_used: int,
    cost_usd: float,
    bypassed: bool = False,
) -> None:
    """
    Insert a row into public.llm_usage.

    Called after every LLM call (or bypass) so the admin can see
    usage metrics per provider.
    """
    await session.execute(
        sa.text(
            """
            INSERT INTO llm_usage
            (tenant_id, provider_id, conversation_id, latency_ms, tokens_used, cost_usd, bypassed)
            VALUES (:tid, :pid, :cid, :latency, :tokens, :cost, :bypassed)
            """
        ),
        {
            "tid": tenant_id,
            "pid": provider_id,
            "cid": conversation_id,
            "latency": latency_ms,
            "tokens": tokens_used,
            "cost": cost_usd,
            "bypassed": bypassed,
        },
    )
    await session.commit()
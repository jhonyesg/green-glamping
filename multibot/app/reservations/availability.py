"""
AvailabilityProvider interface and local-table adapter.
Future adapters (Google Calendar, Airbnb, Booking.com) can implement the same Protocol.
"""

from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class AvailabilitySlot:
    check_in: date
    check_out: date
    available: bool
    capacity: int = 1
    notes: str = ""


@runtime_checkable
class AvailabilityProvider(Protocol):
    async def check_availability(
        self, check_in: date, check_out: date, guests: int = 1
    ) -> bool:
        ...

    async def get_slots(
        self, month: int, year: int
    ) -> list[AvailabilitySlot]:
        ...


class LocalTableAvailabilityProvider:
    """Reads availability from the `availability_sources` local table."""

    def __init__(self, tenant_id: int, session: AsyncSession):
        self._tenant_id = tenant_id
        self._session = session

    async def check_availability(self, check_in: date, check_out: date, guests: int = 1) -> bool:
        # Check if any existing confirmed reservation overlaps
        row = (await self._session.execute(
            sa.text(
                "SELECT COUNT(*) FROM reservations "
                "WHERE tenant_id=:tid AND state IN ('confirmed', 'tentative') "
                "AND check_in < :out AND check_out > :in"
            ),
            {"tid": self._tenant_id, "in": check_in, "out": check_out},
        )).scalar()
        return row == 0

    async def get_slots(self, month: int, year: int) -> list[AvailabilitySlot]:
        # Return all booked slots for the month
        rows = (await self._session.execute(
            sa.text(
                "SELECT check_in, check_out, state FROM reservations "
                "WHERE tenant_id=:tid "
                "AND EXTRACT(MONTH FROM check_in) = :m "
                "AND EXTRACT(YEAR FROM check_in) = :y"
            ),
            {"tid": self._tenant_id, "m": month, "y": year},
        )).fetchall()
        return [
            AvailabilitySlot(
                check_in=r.check_in,
                check_out=r.check_out,
                available=r.state not in ("confirmed", "tentative"),
            )
            for r in rows
        ]


class GoogleCalendarAvailabilityProvider:
    """
    Checks availability against a Google Calendar via the FreeBusy API.

    Config (stored in availability_sources.config for source_type='google_calendar'):
        {
            "calendar_id": "negocio@gmail.com",
            "service_account_json": { ... }   # credenciales de service account
        }

    Setup:
        1. Crear proyecto en console.cloud.google.com y habilitar Calendar API
        2. Crear un Service Account y descargar el JSON de credenciales
        3. Compartir el calendario del negocio con el email del service account
        4. Guardar config en availability_sources del tenant
    """

    def __init__(self, calendar_id: str, service_account_info: dict):
        self._calendar_id = calendar_id
        self._sa_info = service_account_info

    async def _get_token(self) -> str:
        """OAuth2 JWT flow for service accounts (no user interaction)."""
        import time as _time

        import httpx
        import jwt  # PyJWT — instalar cuando se configure: uv add pyjwt cryptography

        now = int(_time.time())
        claim = {
            "iss": self._sa_info["client_email"],
            "scope": "https://www.googleapis.com/auth/calendar.readonly",
            "aud": "https://oauth2.googleapis.com/token",
            "iat": now,
            "exp": now + 3600,
        }
        assertion = jwt.encode(claim, self._sa_info["private_key"], algorithm="RS256")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
            )
            resp.raise_for_status()
            return resp.json()["access_token"]

    async def check_availability(self, check_in: date, check_out: date, guests: int = 1) -> bool:
        import httpx

        token = await self._get_token()
        body = {
            "timeMin": f"{check_in.isoformat()}T00:00:00Z",
            "timeMax": f"{check_out.isoformat()}T23:59:59Z",
            "items": [{"id": self._calendar_id}],
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://www.googleapis.com/calendar/v3/freeBusy",
                json=body,
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            busy = resp.json()["calendars"][self._calendar_id].get("busy", [])
        return len(busy) == 0

    async def get_slots(self, month: int, year: int) -> list[AvailabilitySlot]:
        # FreeBusy for the whole month → invert busy ranges to slots
        raise NotImplementedError("Pendiente: invertir rangos busy a slots")


async def get_availability_provider(tenant_id: int, session: AsyncSession) -> AvailabilityProvider:
    """
    Select the tenant's configured availability source.
    Falls back to the local reservations table if none configured.
    """
    row = (await session.execute(
        sa.text(
            "SELECT source_type, config FROM availability_sources "
            "WHERE tenant_id = :tid AND is_active = true LIMIT 1"
        ),
        {"tid": tenant_id},
    )).fetchone()

    if row and row.source_type == "google_calendar":
        cfg = row.config or {}
        return GoogleCalendarAvailabilityProvider(
            calendar_id=cfg.get("calendar_id", ""),
            service_account_info=cfg.get("service_account_json", {}),
        )

    return LocalTableAvailabilityProvider(tenant_id, session)

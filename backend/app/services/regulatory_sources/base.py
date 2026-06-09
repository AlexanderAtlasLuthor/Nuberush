"""Source client / parser abstraction for regulatory ingestion (F2.27.7.A).

This module defines the seams the later orchestrator (F2.27.7.C) plugs into,
WITHOUT performing any acquisition itself:

  - `RegulatorySourceClient` — a read-only protocol for acquiring raw source
    items. No DB access, no persistence, no compliance decisions. A real HTTP
    implementation is intentionally NOT shipped in this subphase.
  - `RegulatorySourceParser` — a protocol that maps one raw item dict onto a
    `ParsedNotice`.
  - `StaticRegulatorySourceClient` — an in-memory, no-network client that
    replays preloaded raw items. It exists so the abstraction can be exercised
    from fixtures/tests; it never opens a socket.
  - `RegulatorySourceParseError` — a controlled, source-level parse failure
    whose message never embeds the full raw payload.

Nothing here writes to the database, mutates product compliance, touches the
alert lifecycle, or emits an audit row.
"""

from __future__ import annotations

from typing import Any
from typing import Protocol
from typing import runtime_checkable

from app.services.regulatory_sources.types import ParsedNotice


class RegulatorySourceParseError(Exception):
    """A controlled failure while parsing a raw regulatory source item.

    Carries an optional `external_ref` so a caller can identify the offending
    item without the parser dumping the entire raw payload into the message
    (which could leak large bodies or unexpected sensitive fields).
    """

    def __init__(self, message: str, *, external_ref: str | None = None) -> None:
        super().__init__(message)
        self.external_ref = external_ref


class RegulatorySourceFetchError(Exception):
    """A controlled failure while fetching raw items from a source client.

    Carries a BARE message by contract — never the request URL with its query,
    an auth header / API key, or the response body — so a fetch failure can be
    recorded/logged without leaking a secret (mirrors the secret-safe error
    handling in `app.services.supabase_admin`).
    """


@runtime_checkable
class RegulatorySourceClient(Protocol):
    """Read-only acquirer of raw regulatory source items.

    An implementation returns a list of raw item dicts in source-native shape;
    a `RegulatorySourceParser` normalizes each into a `ParsedNotice`. The client
    contract is deliberately narrow: it MUST NOT access the database, persist
    anything, or make any compliance decision.
    """

    def fetch(self) -> list[dict[str, Any]]:
        """Return the current batch of raw source items."""
        ...


@runtime_checkable
class RegulatorySourceParser(Protocol):
    """Maps one raw source item dict onto a normalized `ParsedNotice`.

    Pure and stateless by contract: no I/O, no DB, no network. Raises
    `RegulatorySourceParseError` on a malformed or unmappable item.
    """

    def parse(self, raw: dict[str, Any]) -> ParsedNotice:
        """Normalize a single raw item into a `ParsedNotice`."""
        ...


class StaticRegulatorySourceClient:
    """An in-memory `RegulatorySourceClient` backed by preloaded raw items.

    No network, no DB — it simply replays the items it was constructed with. It
    exists so the source abstraction (and, later, the orchestrator) can be
    driven entirely from fixtures in tests. Each `fetch()` returns shallow
    copies so a caller can never mutate the client's backing store.
    """

    def __init__(self, items: list[dict[str, Any]]) -> None:
        self._items: list[dict[str, Any]] = [dict(item) for item in items]

    def fetch(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._items]

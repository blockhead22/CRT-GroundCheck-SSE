"""C3 gate wire-up — CRT-side helpers in fact_store.

Covers:
  * _aether_consult_write: read-only consult invoked from FactStore writes
  * _aether_consult_governance: read-only consult invoked from
    ingest_memory_write before the can_update_user_profile filter

Both helpers must:
  * No-op when AETHER_CRT_INTEGRATION is unset (no log emitted)
  * Fire on consult-enabled mode against a seeded substrate
  * Never raise — gate failures must not crash the caller
"""

from __future__ import annotations

import pytest

from aether.substrate import SubstrateGraph
from personal_agent import fact_store as fs
from personal_agent.fact_store import (
    Fact,
    FactSource,
    _aether_consult_governance,
    _aether_consult_write,
)


# ---------------------------------------------------------------------------
# Substrate fixture: seeded singleton, restored to None after each test
# ---------------------------------------------------------------------------


@pytest.fixture
def seeded_substrate(monkeypatch):
    """Force fact_store's lazy substrate singleton to a known seeded state.

    Avoids the C2 startup sync (which would pull from the live crt_facts.db).
    """
    sub = SubstrateGraph()
    sub.observe("user", "favorite_color", "orange",
                source_text="seed", source_type="manual", trust=0.9)
    sub.observe("user", "employer", "Anthropic",
                source_text="seed", source_type="manual", trust=0.85)

    monkeypatch.setattr(fs, "_aether_substrate_singleton", sub)
    monkeypatch.setattr(fs, "_aether_import_failed", False)
    yield sub


# ---------------------------------------------------------------------------
# _aether_consult_write
# ---------------------------------------------------------------------------


def test_consult_write_noops_when_mode_unset(seeded_substrate, monkeypatch, capsys):
    monkeypatch.delenv("AETHER_CRT_INTEGRATION", raising=False)
    f = Fact(slot="user.favorite_color", value="cyan", trust=0.95,
             source=FactSource.USER_STATED)
    _aether_consult_write(f)
    out = capsys.readouterr().out
    assert "[AETHER C3]" not in out


def test_consult_write_emits_warn_against_higher_trust(seeded_substrate,
                                                      monkeypatch, capsys):
    monkeypatch.setenv("AETHER_CRT_INTEGRATION", "consult")
    f = Fact(slot="user.favorite_color", value="cyan", trust=0.4,
             source=FactSource.USER_STATED)
    _aether_consult_write(f)
    out = capsys.readouterr().out
    assert "[AETHER C3]" in out
    assert "verdict=warn" in out
    assert "substrate='orange'" in out


def test_consult_write_quiet_on_pass_verdict(seeded_substrate,
                                             monkeypatch, capsys):
    """No prior state on this slot -> verdict=pass, suppressed."""
    monkeypatch.setenv("AETHER_CRT_INTEGRATION", "consult")
    f = Fact(slot="user.height", value="6ft", trust=0.9,
             source=FactSource.USER_STATED)
    _aether_consult_write(f)
    out = capsys.readouterr().out
    assert "[AETHER C3]" not in out


def test_consult_write_does_not_raise_on_substrate_error(monkeypatch, capsys):
    """A flaky substrate must not bubble up into FactStore writes."""
    class _Boom:
        def current_state(self, *_a, **_kw):
            raise RuntimeError("substrate offline")
    monkeypatch.setattr(fs, "_aether_substrate_singleton", _Boom())
    monkeypatch.setattr(fs, "_aether_import_failed", False)
    monkeypatch.setenv("AETHER_CRT_INTEGRATION", "consult")
    f = Fact(slot="user.x", value="y", trust=0.7,
             source=FactSource.USER_STATED)
    _aether_consult_write(f)  # must not raise
    # Gate logs an error result rather than a verdict; either way no crash.


# ---------------------------------------------------------------------------
# _aether_consult_governance
# ---------------------------------------------------------------------------


def test_consult_governance_noops_when_mode_unset(seeded_substrate,
                                                  monkeypatch, capsys):
    monkeypatch.delenv("AETHER_CRT_INTEGRATION", raising=False)
    _aether_consult_governance("favorite_color", "cyan", trust=0.9, blocked=True)
    out = capsys.readouterr().out
    assert "[AETHER C3 GOV]" not in out


def test_consult_governance_qualifies_unprefixed_slot(seeded_substrate,
                                                     monkeypatch, capsys):
    """`favorite_color` -> `user.favorite_color` for substrate lookup."""
    monkeypatch.setenv("AETHER_CRT_INTEGRATION", "consult")
    _aether_consult_governance("favorite_color", "magenta", trust=0.4,
                               blocked=True)
    out = capsys.readouterr().out
    assert "[AETHER C3 GOV]" in out
    assert "slot=user.favorite_color" in out
    assert "verdict=warn" in out  # 0.4 < seeded 0.9
    assert "gov_blocked=True" in out


def test_consult_governance_supersede_when_proposed_trust_higher(
        seeded_substrate, monkeypatch, capsys):
    monkeypatch.setenv("AETHER_CRT_INTEGRATION", "consult")
    _aether_consult_governance("favorite_color", "magenta", trust=0.95,
                               blocked=False)
    out = capsys.readouterr().out
    assert "verdict=supersede" in out
    assert "gov_blocked=False" in out


def test_consult_governance_affirm_on_match(seeded_substrate,
                                           monkeypatch, capsys):
    """Proposed value matches normalized substrate value -> affirm."""
    monkeypatch.setenv("AETHER_CRT_INTEGRATION", "consult")
    _aether_consult_governance("favorite_color", "Orange", trust=0.5,
                               blocked=False)
    out = capsys.readouterr().out
    assert "verdict=affirm" in out


def test_consult_governance_already_qualified_slot_passes_through(
        seeded_substrate, monkeypatch, capsys):
    """If caller already qualified the slot, don't double-prefix."""
    monkeypatch.setenv("AETHER_CRT_INTEGRATION", "consult")
    _aether_consult_governance("user.employer", "OpenAI", trust=0.95,
                               blocked=True)
    out = capsys.readouterr().out
    assert "slot=user.employer" in out
    assert "user.user." not in out


def test_consult_governance_full_mode_enables(seeded_substrate,
                                              monkeypatch, capsys):
    monkeypatch.setenv("AETHER_CRT_INTEGRATION", "full")
    _aether_consult_governance("favorite_color", "magenta", trust=0.4,
                               blocked=True)
    out = capsys.readouterr().out
    assert "[AETHER C3 GOV]" in out
    assert "verdict=warn" in out


def test_consult_governance_does_not_raise_on_substrate_error(
        monkeypatch, capsys):
    class _Boom:
        def current_state(self, *_a, **_kw):
            raise RuntimeError("substrate offline")
    monkeypatch.setattr(fs, "_aether_substrate_singleton", _Boom())
    monkeypatch.setattr(fs, "_aether_import_failed", False)
    monkeypatch.setenv("AETHER_CRT_INTEGRATION", "consult")
    _aether_consult_governance("favorite_color", "cyan", trust=0.5,
                               blocked=False)
    # No assertion needed — must just not crash.

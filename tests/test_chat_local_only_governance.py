from types import SimpleNamespace

from routes.chat import _is_cloud_governance_allowed, _is_strict_local_only_mode


def test_strict_local_only_detected_from_routing_mode(monkeypatch):
    monkeypatch.setattr("auth.get_user_setting", lambda uid, key, default="": "local_only" if key == "routing_mode" else default)
    monkeypatch.setattr("routes.chat.resolve_effective_generation_mode", lambda req, uid: "cloud_claude")

    assert _is_strict_local_only_mode(SimpleNamespace(), 1) is True


def test_strict_local_only_detected_from_local_generation_and_policy(monkeypatch):
    def _fake_setting(uid, key, default=""):
        if key == "cloud_escalation_policy":
            return "local_only"
        return default

    monkeypatch.setattr("auth.get_user_setting", _fake_setting)
    monkeypatch.setattr("routes.chat.resolve_effective_generation_mode", lambda req, uid: "local")

    assert _is_strict_local_only_mode(SimpleNamespace(), 1) is True


def test_non_strict_local_mode_allows_cloud_governance(monkeypatch):
    monkeypatch.setattr("auth.get_user_setting", lambda uid, key, default="": default)
    monkeypatch.setattr("routes.chat.resolve_effective_generation_mode", lambda req, uid: "cloud_claude")

    assert _is_strict_local_only_mode(SimpleNamespace(), 1) is False


def test_cloud_governance_blocked_in_strict_local_only_mode(monkeypatch):
    monkeypatch.setattr("auth.get_user_setting", lambda uid, key, default="": "local_only" if key == "routing_mode" else default)
    monkeypatch.setattr("routes.chat.resolve_effective_generation_mode", lambda req, uid: "local")

    assert _is_cloud_governance_allowed(SimpleNamespace(), 1) is False


def test_cloud_governance_allowed_when_not_strict_local_only(monkeypatch):
    monkeypatch.setattr("auth.get_user_setting", lambda uid, key, default="": default)
    monkeypatch.setattr("routes.chat.resolve_effective_generation_mode", lambda req, uid: "cloud_claude")

    assert _is_cloud_governance_allowed(SimpleNamespace(), 1) is True

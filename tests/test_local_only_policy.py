from personal_agent.cloud_features import CloudFeatureService
from personal_agent.intuition_check import IntuitionCheck
from personal_agent.local_only_policy import (
    is_cloud_governance_allowed,
    is_strict_local_only_mode,
)


def test_local_only_policy_detected_from_routing_mode(monkeypatch):
    monkeypatch.setattr(
        "auth.get_user_setting",
        lambda uid, key, default="": "local_only" if key == "routing_mode" else default,
    )

    assert is_strict_local_only_mode(uid=1) is True
    assert is_cloud_governance_allowed(uid=1) is False


def test_local_only_policy_detected_from_generation_and_escalation(monkeypatch):
    def _fake_setting(uid, key, default=""):
        if key == "generation_mode":
            return "local"
        if key == "cloud_escalation_policy":
            return "local_only"
        return default

    monkeypatch.setattr("auth.get_user_setting", _fake_setting)

    assert is_strict_local_only_mode(uid=1) is True
    assert is_cloud_governance_allowed(uid=1) is False


def test_cloud_feature_service_skips_governance_when_local_only(monkeypatch):
    monkeypatch.setattr(
        "auth.get_user_setting",
        lambda uid, key, default="": "local_only" if key == "routing_mode" else default,
    )

    svc = CloudFeatureService(openai_client=object(), cookie_session=object())
    monkeypatch.setattr(svc, "_check_daily_limit", lambda feature: True)
    monkeypatch.setattr(
        svc,
        "_call_openai",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cloud call should be blocked")),
    )
    monkeypatch.setattr(
        svc,
        "_call_cookie",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cookie call should be blocked")),
    )

    assert svc.classify_slot("My favorite color is blue", []) is None
    assert svc.check_contradiction("A", "B") is None
    assert svc.validate_reflection([], {"belief": "x"}) is None


def test_intuition_check_unavailable_when_local_only(monkeypatch):
    monkeypatch.setattr(
        "auth.get_user_setting",
        lambda uid, key, default="": "local_only" if key == "routing_mode" else default,
    )

    class _DummyCloud:
        @staticmethod
        def _openai_available():
            return True

    tap = IntuitionCheck(cloud_service=_DummyCloud())

    assert tap._is_available() is False

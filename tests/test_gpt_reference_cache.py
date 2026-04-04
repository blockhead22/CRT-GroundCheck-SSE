from personal_agent import gpt_reference_cache as cache


def test_gpt_reference_cache_round_trip():
    cache.delete_packet("thread-a", "health_history")
    cache.put_packet(
        thread_id="thread-a",
        topic_key="health_history",
        query_text="what do you know about my health history?",
        summary="Temporary GPT archive references for this thread:",
        excerpts=[{"msg_id": "m1", "text": "ICU night", "role": "user"}],
        ttl_seconds=3600,
    )

    packet = cache.get_packet("thread-a", "health_history")
    assert packet is not None
    assert packet["query_text"] == "what do you know about my health history?"
    assert packet["excerpts"][0]["msg_id"] == "m1"


def test_gpt_reference_cache_expires_immediately():
    cache.delete_packet("thread-b", "health_history")
    cache.put_packet(
        thread_id="thread-b",
        topic_key="health_history",
        query_text="icu",
        summary="expired",
        excerpts=[],
        ttl_seconds=1,
    )

    packet = cache.get_packet(
        "thread-b",
        "health_history",
        now_ts=10_000_000_000,
    )
    assert packet is None

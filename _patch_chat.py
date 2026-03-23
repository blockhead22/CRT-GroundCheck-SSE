"""Temporary patch script to wire cloud usage tracking into chat.py"""

with open('D:/AI_round2/routes/chat.py', 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# ======================================================================
# Site 1: Primary cloud generation — add timing wrapper
# ======================================================================
old = '                _cloud_primary_answer = _primary_cloud_svc.generate_full_response(\n                    prompt=_pc_prompt,\n                    system_prompt=_pc_system,\n                    provider=_provider,\n                    model=_cloud_model,\n                    max_tokens=4096,\n                )\n                if _cloud_primary_answer:'
new = '                _t_primary = time.perf_counter()\n                _cloud_primary_answer = _primary_cloud_svc.generate_full_response(\n                    prompt=_pc_prompt,\n                    system_prompt=_pc_system,\n                    provider=_provider,\n                    model=_cloud_model,\n                    max_tokens=4096,\n                )\n                _lat_primary = int((time.perf_counter() - _t_primary) * 1000)\n                if _cloud_primary_answer:'
assert old in content, 'Site 1 not found'
content = content.replace(old, new, 1)
changes += 1
print(f'Site 1: primary timing wrapper')

# ======================================================================
# Site 1a: After primary success/failure — add tracking calls
# ======================================================================
old = '''                    try:
                        _esc_policy.record_success(_provider)
                    except Exception:
                        pass
                else:
                    print(f"[GENERATION] cloud_primary: {_provider} returned None, keeping local answer")
                    try:
                        _esc_policy.record_failure(_provider, "returned_none")
                    except Exception:
                        pass
            else:
                print("[GENERATION] cloud_primary: cloud service not initialized, using local")'''

new = '''                    try:
                        _esc_policy.record_success(_provider)
                    except Exception:
                        pass
                    try:
                        _track_cloud_call(
                            call_type=f"generation_primary_{_provider}",
                            provider=_provider, model=_cloud_model,
                            latency_ms=_lat_primary, success=True,
                            thread_id=req.thread_id, uid=int(uid) if uid else None,
                            input_text=_pc_prompt, output_text=_cloud_primary_answer,
                            escalation_reason=str((result.get("escalation") or {}).get("reason", "")),
                            user_message=effective_message,
                        )
                    except Exception:
                        pass
                else:
                    print(f"[GENERATION] cloud_primary: {_provider} returned None, keeping local answer")
                    try:
                        _esc_policy.record_failure(_provider, "returned_none")
                    except Exception:
                        pass
                    try:
                        _track_cloud_call(
                            call_type=f"generation_primary_{_provider}",
                            provider=_provider, model=_cloud_model,
                            latency_ms=_lat_primary, success=False,
                            thread_id=req.thread_id, uid=int(uid) if uid else None,
                            input_text=_pc_prompt, error_type="returned_none",
                            user_message=effective_message,
                        )
                    except Exception:
                        pass
            else:
                print("[GENERATION] cloud_primary: cloud service not initialized, using local")'''

assert old in content, 'Site 1a not found'
content = content.replace(old, new, 1)
changes += 1
print(f'Site 1a: primary tracking calls')

# ======================================================================
# Site 2: Cloud fallback OpenAI — add timing
# ======================================================================
old = '''                    _cloud_answer = _cloud_gen_svc.generate_response(
                        user_message=effective_message,
                        retrieved_memories=_cg_memories if isinstance(_cg_memories, list) else [],
                        conversation_history=_cg_history,
                        self_model_snapshot=_cg_self_model,
                    )
                    if _cloud_answer:'''
new = '''                    _t_fb = time.perf_counter()
                    _cloud_answer = _cloud_gen_svc.generate_response(
                        user_message=effective_message,
                        retrieved_memories=_cg_memories if isinstance(_cg_memories, list) else [],
                        conversation_history=_cg_history,
                        self_model_snapshot=_cg_self_model,
                    )
                    _lat_fb = int((time.perf_counter() - _t_fb) * 1000)
                    if _cloud_answer:'''
assert old in content, 'Site 2 not found'
content = content.replace(old, new, 1)
changes += 1
print(f'Site 2: fallback timing')

# ======================================================================
# Site 2a: After fallback OpenAI success — add tracking
# ======================================================================
# Find anchor: "[GENERATION] fallback: OpenAI succeeded"
anchor = '[GENERATION] fallback: OpenAI succeeded'
idx = content.find(anchor)
assert idx > 0, 'Site 2a anchor not found'

old = '''                        try:
                            _esc_policy.record_success("openai")
                        except Exception:
                            pass'''
# Find this specific instance after the anchor
idx_old = content.find(old, idx)
assert idx_old > 0, 'Site 2a old not found'

new = '''                        try:
                            _esc_policy.record_success("openai")
                        except Exception:
                            pass
                        try:
                            _track_cloud_call(
                                call_type="generation_fallback",
                                provider="openai", model="gpt-4o-mini",
                                latency_ms=_lat_fb, success=True,
                                thread_id=req.thread_id, uid=int(uid) if uid else None,
                                output_text=_cloud_answer,
                                escalation_reason=_fallback_reason,
                                user_message=effective_message,
                            )
                        except Exception:
                            pass'''
content = content[:idx_old] + new + content[idx_old + len(old):]
changes += 1
print(f'Site 2a: fallback OpenAI success tracking')

# ======================================================================
# Site 2b: After fallback OpenAI failure — add tracking before Claude escalation
# ======================================================================
anchor = '[GENERATION] fallback: OpenAI returned None'
idx = content.find(anchor)
assert idx > 0, 'Site 2b anchor not found'

old = '''                        try:
                            _esc_policy.record_failure("openai", "returned_none")
                        except Exception:
                            pass'''
idx_old = content.find(old, idx)
assert idx_old > 0, 'Site 2b old not found'

new = '''                        try:
                            _esc_policy.record_failure("openai", "returned_none")
                        except Exception:
                            pass
                        try:
                            _track_cloud_call(
                                call_type="generation_fallback",
                                provider="openai", model="gpt-4o-mini",
                                latency_ms=_lat_fb, success=False,
                                thread_id=req.thread_id, uid=int(uid) if uid else None,
                                error_type="returned_none",
                                escalation_reason=_fallback_reason,
                                user_message=effective_message,
                            )
                        except Exception:
                            pass'''
content = content[:idx_old] + new + content[idx_old + len(old):]
changes += 1
print(f'Site 2b: fallback OpenAI failure tracking')

# ======================================================================
# Site 3: Claude fallback — add timing
# ======================================================================
old = '''                        _claude_answer = _cloud_gen_svc.generate_response_claude(
                            user_message=effective_message,
                            retrieved_memories=_cg_memories if isinstance(_cg_memories, list) else [],
                            conversation_history=_cg_history,
                            self_model_snapshot=_cg_self_model,
                        )
                        if _claude_answer:'''
new = '''                        _t_cfb = time.perf_counter()
                        _claude_answer = _cloud_gen_svc.generate_response_claude(
                            user_message=effective_message,
                            retrieved_memories=_cg_memories if isinstance(_cg_memories, list) else [],
                            conversation_history=_cg_history,
                            self_model_snapshot=_cg_self_model,
                        )
                        _lat_cfb = int((time.perf_counter() - _t_cfb) * 1000)
                        if _claude_answer:'''
assert old in content, 'Site 3 not found'
content = content.replace(old, new, 1)
changes += 1
print(f'Site 3: Claude fallback timing')

# ======================================================================
# Site 3a: After Claude fallback success — add tracking
# ======================================================================
anchor = '[GENERATION] fallback: Claude succeeded'
idx = content.find(anchor)
assert idx > 0, 'Site 3a anchor not found'

old = '''                            try:
                                _esc_policy.record_success("claude")
                            except Exception:
                                pass'''
idx_old = content.find(old, idx)
assert idx_old > 0, 'Site 3a old not found'

new = '''                            try:
                                _esc_policy.record_success("claude")
                            except Exception:
                                pass
                            try:
                                _track_cloud_call(
                                    call_type="generation_fallback_claude",
                                    provider="claude_cookie", model="claude-sonnet",
                                    latency_ms=_lat_cfb, success=True,
                                    thread_id=req.thread_id, uid=int(uid) if uid else None,
                                    output_text=_claude_answer,
                                    escalation_reason=_fallback_reason,
                                    user_message=effective_message,
                                )
                            except Exception:
                                pass'''
content = content[:idx_old] + new + content[idx_old + len(old):]
changes += 1
print(f'Site 3a: Claude fallback success tracking')

# ======================================================================
# Site 3b: After Claude fallback failure — add tracking
# ======================================================================
anchor = '[GENERATION] fallback: Claude also returned None'
idx = content.find(anchor)
assert idx > 0, 'Site 3b anchor not found'

old = '''                            try:
                                _esc_policy.record_failure("claude", "returned_none")
                            except Exception:
                                pass'''
idx_old = content.find(old, idx)
assert idx_old > 0, 'Site 3b old not found'

new = '''                            try:
                                _esc_policy.record_failure("claude", "returned_none")
                            except Exception:
                                pass
                            try:
                                _track_cloud_call(
                                    call_type="generation_fallback_claude",
                                    provider="claude_cookie", model="claude-sonnet",
                                    latency_ms=_lat_cfb, success=False,
                                    thread_id=req.thread_id, uid=int(uid) if uid else None,
                                    error_type="returned_none",
                                    escalation_reason=_fallback_reason,
                                    user_message=effective_message,
                                )
                            except Exception:
                                pass'''
content = content[:idx_old] + new + content[idx_old + len(old):]
changes += 1
print(f'Site 3b: Claude fallback failure tracking')

# ======================================================================
# Site 4: Cloud slot classification — add timing + tracking
# ======================================================================
old = '''                    _cloud_result = _cloud_svc.classify_slot(
                        effective_message, _existing_slots
                    )
                    if _cloud_result:
                        result["cloud_governance_used"] = True'''
new = '''                    _t_slot = time.perf_counter()
                    _cloud_result = _cloud_svc.classify_slot(
                        effective_message, _existing_slots
                    )
                    _lat_slot = int((time.perf_counter() - _t_slot) * 1000)
                    try:
                        _track_cloud_call(
                            call_type="slot_classification",
                            provider="openai", model="gpt-4o-mini",
                            latency_ms=_lat_slot,
                            success=_cloud_result is not None,
                            thread_id=req.thread_id, uid=int(uid) if uid else None,
                            error_type=None if _cloud_result else "returned_none",
                            user_message=effective_message,
                        )
                    except Exception:
                        pass
                    if _cloud_result:
                        result["cloud_governance_used"] = True'''
assert old in content, 'Site 4 not found'
content = content.replace(old, new, 1)
changes += 1
print(f'Site 4: slot classification tracking')

# ======================================================================
# Site 5: Cloud NLI contradiction check — add timing + tracking
# ======================================================================
old = '                    _nli_result = _cloud_svc_nli.check_contradiction(_fact_a, _fact_b)\n                    if _nli_result:'
new = '''                    _t_nli = time.perf_counter()
                    _nli_result = _cloud_svc_nli.check_contradiction(_fact_a, _fact_b)
                    _lat_nli = int((time.perf_counter() - _t_nli) * 1000)
                    try:
                        _track_cloud_call(
                            call_type="nli_contradiction",
                            provider="openai", model="gpt-4o-mini",
                            latency_ms=_lat_nli,
                            success=_nli_result is not None,
                            thread_id=req.thread_id, uid=int(uid) if uid else None,
                            error_type=None if _nli_result else "returned_none",
                            user_message=effective_message,
                        )
                    except Exception:
                        pass
                    if _nli_result:'''
assert old in content, 'Site 5 not found'
content = content.replace(old, new, 1)
changes += 1
print(f'Site 5: NLI tracking')

# ======================================================================
# Site 6: Late cloud fallback OpenAI — add timing + tracking
# ======================================================================
old = '''                        _cg2_answer = _cloud_gen_svc2.generate_response(
                            user_message=effective_message,
                            retrieved_memories=_cg2_memories,
                            conversation_history=recent_history or None,
                        )
                        if _cg2_answer:'''
new = '''                        _t_late = time.perf_counter()
                        _cg2_answer = _cloud_gen_svc2.generate_response(
                            user_message=effective_message,
                            retrieved_memories=_cg2_memories,
                            conversation_history=recent_history or None,
                        )
                        _lat_late = int((time.perf_counter() - _t_late) * 1000)
                        if _cg2_answer:'''
assert old in content, 'Site 6 not found'
content = content.replace(old, new, 1)
changes += 1
print(f'Site 6: late fallback timing')

# Site 6a: After late OpenAI success
anchor = '[GENERATION] late_fallback: OpenAI succeeded'
idx = content.find(anchor)
assert idx > 0, 'Site 6a anchor not found'
# Insert tracking after the print line
insert_after = content.find('\n', idx)
tracking_6a = '''
                        try:
                            _track_cloud_call(
                                call_type="generation_fallback",
                                provider="openai", model="gpt-4o-mini",
                                latency_ms=_lat_late, success=True,
                                thread_id=req.thread_id, uid=int(uid) if uid else None,
                                output_text=_cg2_answer,
                                escalation_reason="leaked_error_string",
                                user_message=effective_message,
                            )
                        except Exception:
                            pass'''
content = content[:insert_after] + tracking_6a + content[insert_after:]
changes += 1
print(f'Site 6a: late fallback OpenAI success tracking')

# ======================================================================
# Site 7: Late Claude fallback — add timing + tracking
# ======================================================================
old = '''                            _cg2_claude = _cloud_gen_svc2.generate_response_claude(
                                user_message=effective_message,
                                retrieved_memories=_cg2_memories,
                                conversation_history=recent_history or None,
                            )
                            if _cg2_claude:'''
new = '''                            _t_late_c = time.perf_counter()
                            _cg2_claude = _cloud_gen_svc2.generate_response_claude(
                                user_message=effective_message,
                                retrieved_memories=_cg2_memories,
                                conversation_history=recent_history or None,
                            )
                            _lat_late_c = int((time.perf_counter() - _t_late_c) * 1000)
                            if _cg2_claude:'''
assert old in content, 'Site 7 not found'
content = content.replace(old, new, 1)
changes += 1
print(f'Site 7: late Claude timing')

# Site 7a: After late Claude success
anchor = '[GENERATION] late_fallback: Claude succeeded'
idx = content.find(anchor)
assert idx > 0, 'Site 7a anchor not found'
insert_after = content.find('\n', idx)
tracking_7a = '''
                            try:
                                _track_cloud_call(
                                    call_type="generation_fallback_claude",
                                    provider="claude_cookie", model="claude-sonnet",
                                    latency_ms=_lat_late_c, success=True,
                                    thread_id=req.thread_id, uid=int(uid) if uid else None,
                                    output_text=_cg2_claude,
                                    escalation_reason="leaked_error_string",
                                    user_message=effective_message,
                                )
                            except Exception:
                                pass'''
content = content[:insert_after] + tracking_7a + content[insert_after:]
changes += 1
print(f'Site 7a: late Claude success tracking')

with open('D:/AI_round2/routes/chat.py', 'w', encoding='utf-8') as f:
    f.write(content)

print(f'\nSUCCESS: {changes} patches applied')

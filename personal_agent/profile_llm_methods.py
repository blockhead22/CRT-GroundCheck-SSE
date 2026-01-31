"""
LLM-based fact extraction implementation for GlobalUserProfile.

This provides the _update_from_llm_tuples and _update_from_regex_facts methods.
"""

def _update_from_llm_tuples(self, text: str, thread_id: str) -> Dict[str, Any]:
    """
    Update profile using LLM-extracted fact tuples.
    
    Supports:
    - Multiple values per attribute (multiple pets, colors, jobs)
    - Rich context ("sick dog", "part-time job at Google")
    - Explicit actions: add, update, deprecate, deny
    - Confidence scores from LLM
    """
    try:
        tuples = self.llm_extractor.extract_tuples(text)
        logger.info(f"[LLM_PROFILE_UPDATE] Extracted {len(tuples)} tuples from '{text[:60]}'")
    except Exception as e:
        logger.warning(f"LLM extraction failed: {e}. Falling back to regex.")
        return self._update_from_regex_facts(text, thread_id)
    
    if not tuples:
        logger.info("[LLM_PROFILE_UPDATE] No facts extracted")
        return {'updated': {}, 'replaced': {}}
    
    updated = {}
    replaced = {}
    deprecated = {}
    conn = self._get_connection()
    cursor = conn.cursor()
    
    for tuple_obj in tuples:
        slot = tuple_obj.attribute
        value = tuple_obj.value
        normalized = value.lower().strip()
        action = tuple_obj.action
        evidence = tuple_obj.evidence_span or text[:100]
        confidence = tuple_obj.confidence
        
        logger.info(f"[LLM_PROFILE_UPDATE] Processing: {slot}={value} (action={action.value}, conf={confidence:.2f})")
        
        # Check for existing fact with same normalized value
        cursor.execute("""
            SELECT id, value, active FROM user_profile_multi 
            WHERE slot = ? AND normalized = ?
        """, (slot, normalized))
        exact_match = cursor.fetchone()
        
        if exact_match:
            match_id, match_value, is_active = exact_match
            
            if action == FactAction.DEPRECATE or action == FactAction.DENY:
                # Mark as inactive
                cursor.execute("""
                    UPDATE user_profile_multi 
                    SET active = 0, timestamp = ?, action = ?
                    WHERE id = ?
                """, (time.time(), action.value, match_id))
                deprecated[slot] = value
                logger.info(f"[LLM_PROFILE_UPDATE] Deprecated: {slot} = {value}")
                continue
                
            elif is_active:
                # Update timestamp and evidence
                cursor.execute("""
                    UPDATE user_profile_multi 
                    SET timestamp = ?, source_thread = ?, evidence_span = ?, confidence = ?
                    WHERE id = ?
                """, (time.time(), thread_id, evidence, confidence, match_id))
                logger.info(f"[LLM_PROFILE_UPDATE] Refreshed: {slot} = {value}")
                continue
            else:
                # Delete inactive duplicate before re-inserting
                cursor.execute("DELETE FROM user_profile_multi WHERE id = ?", (match_id,))
                logger.info(f"[LLM_PROFILE_UPDATE] Deleted inactive duplicate for re-insert: {slot} = {value}")
        
        # INSERT new fact
        try:
            cursor.execute("""
                INSERT INTO user_profile_multi 
                (slot, value, normalized, timestamp, source_thread, confidence, active, evidence_span, action)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
            """, (slot, value, normalized, time.time(), thread_id, confidence, evidence, action.value))
            updated[slot] = value
            logger.info(f"[LLM_PROFILE_UPDATE] ✅ INSERTED: {slot} = {value}")
        except sqlite3.IntegrityError as e:
            logger.error(f"[LLM_PROFILE_UPDATE] ❌ IntegrityError: {slot} = {value}: {e}")
            continue
    
    conn.commit()
    logger.info(f"[LLM_PROFILE_UPDATE] Committed. Updated: {updated}, Deprecated: {deprecated}")
    conn.close()
    
    return {'updated': updated, 'replaced': replaced, 'deprecated': deprecated}


def _update_from_regex_facts(self, text: str, thread_id: str) -> Dict[str, Any]:
    """
    Legacy regex-based fact extraction (fallback).
    
    Uses predefined patterns from fact_slots.py
    """
    facts = extract_fact_slots(text)
    logger.info(f"[REGEX_PROFILE_UPDATE] Extracted {len(facts)} facts from '{text[:60]}': {list(facts.keys())}")
    
    if not facts:
        logger.info("[REGEX_PROFILE_UPDATE] No facts extracted")
        return {'updated': {}, 'replaced': {}}
    
    updated = {}
    replaced = {}
    conn = self._get_connection()
    cursor = conn.cursor()
    
    for slot, fact in facts.items():
        logger.info(f"[REGEX_PROFILE_UPDATE] Processing slot='{slot}', value='{fact.value}'")
        new_norm = fact.normalized if hasattr(fact, 'normalized') else fact.value.lower()
        
        # Check if exact value exists
        cursor.execute("""
            SELECT id, value, active FROM user_profile_multi 
            WHERE slot = ? AND normalized = ?
        """, (slot, new_norm))
        exact_match = cursor.fetchone()
        
        if exact_match:
            match_id, match_value, is_active = exact_match
            if is_active:
                # Update timestamp
                cursor.execute("""
                    UPDATE user_profile_multi 
                    SET timestamp = ?, source_thread = ?
                    WHERE id = ?
                """, (time.time(), thread_id, match_id))
                logger.info(f"[REGEX_PROFILE_UPDATE] Updated timestamp: {slot} = {match_value}")
                continue
            else:
                # Delete inactive duplicate
                cursor.execute("DELETE FROM user_profile_multi WHERE id = ?", (match_id,))
                logger.info(f"[REGEX_PROFILE_UPDATE] Deleted inactive duplicate: {slot} = {match_value}")
        
        # For slots marked as SINGLE_VALUE, replace old values
        is_single_value = slot in SINGLE_VALUE_SLOTS
        if is_single_value:
            cursor.execute("""
                SELECT id, value FROM user_profile_multi 
                WHERE slot = ? AND active = 1
            """, (slot,))
            existing = cursor.fetchall()
            
            if existing:
                for row in existing:
                    cursor.execute("""
                        UPDATE user_profile_multi 
                        SET active = 0, timestamp = ?
                        WHERE id = ?
                    """, (time.time(), row[0]))
                replaced[slot] = {'old': existing[0][1], 'new': fact.value}
                logger.info(f"[REGEX_PROFILE_UPDATE] Replaced: {slot} '{existing[0][1]}' -> '{fact.value}'")
        
        # INSERT new fact
        try:
            cursor.execute("""
                INSERT INTO user_profile_multi 
                (slot, value, normalized, timestamp, source_thread, confidence, active, evidence_span, action)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, 'add')
            """, (slot, fact.value, new_norm, time.time(), thread_id, 0.9, text[:100]))
            updated[slot] = fact.value
            logger.info(f"[REGEX_PROFILE_UPDATE] ✅ INSERTED: {slot} = {fact.value}")
        except sqlite3.IntegrityError as e:
            logger.error(f"[REGEX_PROFILE_UPDATE] ❌ IntegrityError: {slot} = {fact.value}: {e}")
    
    conn.commit()
    logger.info(f"[REGEX_PROFILE_UPDATE] Committed. Updated: {updated}, Replaced: {replaced}")
    conn.close()
    
    return {'updated': updated, 'replaced': replaced}

HEDGE_WORDS = set(["may","might","could","seems","suggests","possible","unclear","likely","maybe"])


def hedge_score(text: str) -> float:
    words = text.lower().split()
    if not words:
        return 0.0
    return sum(1 for w in words if w.strip('.,') in HEDGE_WORDS) / len(words)


def analyze_ambiguity_for_claims(claims):
    for c in claims:
        score = hedge_score(c['claim_text'])
        contains_conflict_markers = any(x in c['claim_text'].lower() for x in ['but','however','although','contradict'])
        open_questions = []
        for q in c.get('supporting_quotes', []):
            if q['quote_text'].strip().endswith('?'):
                open_questions.append(q['quote_text'])
        c['ambiguity'] = {
            'hedge_score': score,
            'contains_conflict_markers': contains_conflict_markers,
            'open_questions': open_questions,
        }
    return claims

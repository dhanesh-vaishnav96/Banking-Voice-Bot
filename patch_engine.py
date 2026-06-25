"""Patch script — replace detect_intent to use strict cross-cutting priority."""
import re

with open('backend/services/conversation_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

NEW_FN = '''def detect_intent(text: str, stage: str) -> Tuple[str, float]:
    """
    Detect user intent from text at the given stage.

    V2 Priority Strategy:
      1. Score all intents.
      2. Cross-cutting intents ALWAYS win if they have ANY match score,
         regardless of stage-specific score (except at name-confirmation).
      3. Stage-specific matching only applies if no cross-cutting matched.

    Returns:
        (intent_name, confidence_0_to_1)
    """
    best_intent = "unclear"
    best_score = 0.0

    # Step 1: Score all intents
    scored = {}
    for intent_name, (keywords, base_conf) in INTENT_REGISTRY.items():
        raw = _match_score(text, keywords)
        if raw > 0.0:
            scored[intent_name] = raw * base_conf

    # Step 2: Cross-cutting STRICT priority
    # At any stage after name confirmation, cross-cutting intents win absolutely.
    cross_cutting_matched = False
    if stage != STAGE_AWAITING_NAME_CONFIRMATION:
        for intent_name in CROSS_CUTTING_INTENTS:
            s = scored.get(intent_name, 0)
            if s > best_score:
                best_score = s
                best_intent = intent_name
                cross_cutting_matched = True

    # Step 3: Stage-specific (only if NO cross-cutting matched)
    if not cross_cutting_matched:
        stage_intent, stage_conf = _stage_specific_intent(text, stage, scored)
        if stage_conf > best_score:
            best_score = stage_conf
            best_intent = stage_intent

    # Step 4: Confidence floor and cap
    confidence = round(min(0.99, max(0.50, best_score)), 2)
    if best_intent == "unclear":
        confidence = 0.50

    return best_intent, confidence

'''

# Use regex to replace the detect_intent function
pattern = r'def detect_intent\(text: str, stage: str\).*?(?=\ndef )'
new_content = re.sub(pattern, NEW_FN, content, flags=re.DOTALL)

if new_content == content:
    print("ERROR: Pattern did not match!")
else:
    with open('backend/services/conversation_engine.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("SUCCESS: detect_intent replaced.")

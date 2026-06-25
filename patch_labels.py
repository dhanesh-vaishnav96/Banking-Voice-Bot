"""Add INTENT_LABELS to conversation_engine.py"""
with open('backend/services/conversation_engine.py', 'r', encoding='utf-8') as f:
    c = f.read()

addition = '''
# Human-readable intent labels (used by demo script and frontend)
INTENT_LABELS = {
    'confirm':         'Confirmed',
    'deny':            'Wrong Person',
    'bank_query':      'Bank Query',
    'amount_query':    'Amount Query',
    'link_request':    'Link Request',
    'busy_interrupt':  'User Busy',
    'delay_promise':   'Promise to Pay',
    'payment_accept':  'Accepted Payment',
    'payment_decline': 'Declined Payment',
    'who_are_you':     'Identity Query',
    'proceed':         'Acknowledged',
    'unclear':         'Unclear',
}

'''

marker = '# Intents that terminate the conversation\nTERMINAL_INTENTS = {"deny"}'
if marker in c:
    c = c.replace(marker, marker + addition)
    with open('backend/services/conversation_engine.py', 'w', encoding='utf-8') as f:
        f.write(c)
    print('SUCCESS')
else:
    print('NOT FOUND')
    # find nearby text
    idx = c.find('TERMINAL_INTENTS')
    print(repr(c[idx-20:idx+80]))

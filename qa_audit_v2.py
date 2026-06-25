import requests
import time
import sys
from prettytable import PrettyTable
import json

URL_START = "http://localhost:8000/api/start"
URL_RESPOND = "http://localhost:8000/api/respond"

# We run 30 test scenarios targeting the strict FSM transitions
scenarios = [
    # ── Happy Path / Immediate Payment ──
    {"name": "01 Happy Path YES (identity)", "inputs": ["Haan", "Kaun bank", "Theek hai", "Haan bhej do"], "expected_final_stage": "conversation_completed", "expected_end_call": True},
    {"name": "02 Identity YES -> Direct Link", "inputs": ["Haan", "Theek hai", "Link bhejo"], "expected_final_stage": "conversation_completed", "expected_end_call": True},
    {"name": "03 YES all the way", "inputs": ["Ji", "Ji", "Ji", "Send link"], "expected_final_stage": "conversation_completed", "expected_end_call": True},
    {"name": "04 Mixed English YES", "inputs": ["Yes speaking", "Okay", "Amount?", "Yes send link"], "expected_final_stage": "conversation_completed", "expected_end_call": True},
    
    # ── Wrong Person ──
    {"name": "05 Wrong Person at start", "inputs": ["Nahi main nahi hoon"], "expected_final_stage": "wrong_person", "expected_end_call": True},
    {"name": "06 Wrong Person variation 2", "inputs": ["Galat number"], "expected_final_stage": "wrong_person", "expected_end_call": True},
    {"name": "07 Wrong Person variation 3", "inputs": ["Wrong person"], "expected_final_stage": "wrong_person", "expected_end_call": True},
    {"name": "08 Wrong Person variation 4", "inputs": ["Aapne galat number lagaya hai"], "expected_final_stage": "wrong_person", "expected_end_call": True},
    {"name": "09 Wrong Person variation 5", "inputs": ["Main jitesh nahi hoon"], "expected_final_stage": "wrong_person", "expected_end_call": True},
    
    # ── Already Paid ──
    {"name": "10 Already Paid at start", "inputs": ["Haan", "Maine pay kar diya"], "expected_final_stage": "conversation_completed", "expected_end_call": True},
    {"name": "11 Already Paid at amount", "inputs": ["Haan", "Theek hai", "Kal payment kar diya tha"], "expected_final_stage": "conversation_completed", "expected_end_call": True},
    {"name": "12 Already Paid variation", "inputs": ["Haan", "Already paid"], "expected_final_stage": "conversation_completed", "expected_end_call": True},

    # ── Delay / Promise to Pay ──
    {"name": "13 Delay (Kal)", "inputs": ["Haan", "Theek hai", "Kal kar dunga"], "expected_final_stage": "conversation_completed", "expected_end_call": True},
    {"name": "14 Delay (Parso)", "inputs": ["Haan", "Theek hai", "Theek hai", "Parso tak karunga"], "expected_final_stage": "conversation_completed", "expected_end_call": True},
    {"name": "15 Delay (Salary)", "inputs": ["Haan", "Ji", "Salary aane ke baad"], "expected_final_stage": "conversation_completed", "expected_end_call": True},
    {"name": "16 Delay (Abhi paise nahi)", "inputs": ["Haan", "Abhi paise nahi hain"], "expected_final_stage": "conversation_completed", "expected_end_call": True},

    # ── Partial Payment ──
    {"name": "17 Partial Payment", "inputs": ["Haan", "Theek hai", "Aadha de sakta hoon"], "expected_final_stage": "conversation_completed", "expected_end_call": True},
    {"name": "18 Partial Payment 50%", "inputs": ["Haan", "50 percent kar dunga"], "expected_final_stage": "conversation_completed", "expected_end_call": True},

    # ── Supervisor / Angry ──
    {"name": "19 Supervisor", "inputs": ["Haan", "Manager se baat karao"], "expected_final_stage": "conversation_completed", "expected_end_call": True},
    {"name": "20 Supervisor English", "inputs": ["Haan", "Escalate to senior"], "expected_final_stage": "conversation_completed", "expected_end_call": True},
    {"name": "21 Angry Customer", "inputs": ["Haan", "Pareshan mat karo"], "expected_final_stage": "conversation_completed", "expected_end_call": True},
    {"name": "22 Angry Customer 2", "inputs": ["Haan", "Police complaint karunga"], "expected_final_stage": "conversation_completed", "expected_end_call": True},

    # ── Bug Re-tests (from prompt) ──
    {"name": "23 Bug 1 (Haan kar sakte ho)", "inputs": ["Haan kar sakte ho", "Theek hai", "Haan bhej do"], "expected_final_stage": "conversation_completed", "expected_end_call": True},
    {"name": "24 Bug 2 (Haan sahi hai)", "inputs": ["Haan sahi hai", "Haan", "Link bhejo"], "expected_final_stage": "conversation_completed", "expected_end_call": True},
    {"name": "25 Bug 3 (Payment Offer + YES)", "inputs": ["Haan", "Ji", "Ji", "Kar sakta hoon"], "expected_final_stage": "conversation_completed", "expected_end_call": True},
    {"name": "26 Bug 5 (YES mapping)", "inputs": ["Haan", "Theek hai bhej do"], "expected_final_stage": "conversation_completed", "expected_end_call": True},

    # ── Random / Silence / NO ──
    {"name": "27 Random input", "inputs": ["Haan", "Mausam kaisa hai?", "Theek hai", "Haan"], "expected_final_stage": "conversation_completed", "expected_end_call": True},
    {"name": "28 Silence (handled as unclear)", "inputs": ["Haan", "...", "Theek hai", "Haan"], "expected_final_stage": "conversation_completed", "expected_end_call": True},
    {"name": "29 Complete NO at offer", "inputs": ["Haan", "Ji", "Ji", "Nahi karunga"], "expected_final_stage": "conversation_completed", "expected_end_call": True},
    {"name": "30 Immediate No at Bank Info", "inputs": ["Haan", "Nahi mujhe baat nahi karni"], "expected_final_stage": "conversation_completed", "expected_end_call": True},
]

results = []

print("Running Deterministic FSM 30-Scenario Validation...")
t0 = time.time()
pass_count = 0

for sc in scenarios:
    name = sc["name"]
    # Start Session
    try:
        start_resp = requests.post(URL_START, json={
            "customer_name": "Jitesh Soni",
            "amount_due": 5000,
            "bank_name": "HDFC Bank",
            "payment_link": "https://pay.hdfc/123"
        }).json()
        
        session_id = start_resp["session_id"]
        stage = start_resp["stage"]
        is_complete = False
        final_intent = ""
        actual_response = ""
        prev_stage = stage
        
        for user_in in sc["inputs"]:
            if is_complete:
                break
            resp = requests.post(URL_RESPOND, json={
                "session_id": session_id,
                "user_text": user_in
            }).json()
            
            final_intent = resp["intent"]
            prev_stage = stage
            stage = resp["stage"]
            is_complete = resp["is_complete"]
            actual_response = resp["bot_response"]
        
        passed = (stage == sc["expected_final_stage"]) and (is_complete == sc["expected_end_call"])
        if passed: pass_count += 1
        
        results.append({
            "Scenario": name,
            "Detected Intent": final_intent,
            "Previous Stage": prev_stage,
            "Next Stage": stage,
            "Actual Response": actual_response[:40] + "...",
            "Pass/Fail": "PASS" if passed else "FAIL"
        })
    except Exception as e:
        results.append({
            "Scenario": name,
            "Detected Intent": "ERROR",
            "Previous Stage": "ERROR",
            "Next Stage": "ERROR",
            "Actual Response": str(e),
            "Pass/Fail": "FAIL"
        })

print(f"\nExecution Time: {round(time.time() - t0, 2)}s")
print(f"Total Passed: {pass_count}/30\n")

table = PrettyTable()
table.field_names = ["Scenario", "Detected Intent", "Prev Stage", "Next Stage", "Actual Response", "Result"]
for r in results:
    table.add_row([r["Scenario"], r["Detected Intent"], r["Previous Stage"], r["Next Stage"], r["Actual Response"], r["Pass/Fail"]])

print(table)

if pass_count != 30:
    print("\n[ERROR] SOME TESTS FAILED. FIX THE BACKEND.")
    sys.exit(1)
else:
    print("\n[SUCCESS] ALL DETERMINISTIC TESTS PASSED.")
    sys.exit(0)

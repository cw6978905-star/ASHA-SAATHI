def on_transcript(text, session):
    form = session.setdefault("form", {
        "beneficiary_id": None,
        "visit_type": None,
        "weight_kg": None,
        "vaccinations_due": [],
        "next_visit_date": None,
        "danger_signs": [],
        "referral_flag": False,
    })
    low = text.lower()
    danger = False
    reply = "मैंने सुना: " + text
    if "bleeding" in low or "ब्लीडिंग" in low or "खून" in low:
        danger = True
        form["danger_signs"].append("bleeding")
        form["referral_flag"] = True
        reply = "तुरंत पीएचसी रेफर करें।"
    return {
        "text_to_speak": reply,
        "language": "hi-IN",
        "form_state": form,
        "danger_flag": danger,
    }
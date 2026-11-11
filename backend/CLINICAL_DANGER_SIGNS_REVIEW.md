# ASHA-SAATHI — Clinical Danger-Sign Validation & Review Register

> **IMPORTANT CLINICAL SAFETY NOTICE:**
> All **12** danger-sign entries currently in [`backend/data/danger_signs.json`](data/danger_signs.json) carry `source_reference = "PENDING_PERSON_C_VERIFICATION"` and metadata `verification_status = "preliminary_pending_person_c_verification"` / `pending_person_c_verification = true`.
> Candidate guideline mappings below reference authoritative Government of India (MoHFW / NHM / NHSRC) and World Health Organization (WHO) guidelines for Person C's clinical review and sign-off. **No entry is marked clinically approved automatically**, and **no clinical thresholds, danger signs, or regional translations have been invented beyond the existing dataset**.

---

## 1. Authoritative Guideline References Evaluated

1. **MoHFW / NHM — Home Based Newborn Care (HBNC) Operational Guidelines (Revised)** & **NHSRC ASHA Training Modules / IMNCI**: Immediate PHC/FRU referral criteria for newborns (0–28 days) and postnatal mothers.
2. **MoHFW & MWCD — Mother and Child Protection (MCP) Card Guidelines & PMSMA (Pradhan Mantri Surakshit Matritva Abhiyan)**: Antenatal & intrapartum danger signs requiring immediate reporting to PHC/CHC/FRU without waiting for the next scheduled ANC visit.
3. **WHO — *Pregnancy, Childbirth, Postpartum and Newborn Care: A Guide for Essential Practice* (PCPNC)**: Primary-care screening criteria for immediate emergency referral of pregnant women, postpartum mothers, and newborns.

---

## 2. Entry-by-Entry Clinical Mapping (12 / 12 Entries)

| # | ID & Category | Danger Sign | English Phrases (`english_keywords`) | Supported Regional Languages & Phrase Counts (`danger_signs.json`) | Candidate Clinical Source & Guideline Reference | Verification Status |
|---|---|---|---|---|---|---|
| 1 | `severe_bleeding` (`maternal`) | Vaginal or Severe Bleeding | `vaginal bleeding`, `heavy bleeding`, `severe bleeding`, `bleeding during pregnancy`, `postpartum bleeding`, `bleeding`, `blood loss`, `hemorrhage`, `spotting` | Hinglish (`hindi_phrases`: 14 incl. Devanagari); Native scripts (`hi-IN`: 3, `ta-IN`: 3, `te-IN`: 3, `bn-IN`: 3, `mr-IN`: 3, `gu-IN`: 3, `kn-IN`: 3, `ml-IN`: 3, `pa-IN`: 3); `transliterations`: 9; `code_mixed`: 9; `spelling_variations`: 4 | **MoHFW / MWCD MCP Card & PMSMA** (Antenatal vaginal bleeding); **NHM HBNC Revised / PNC Matrix** (Excessive postpartum bleeding / PPH); **WHO PCPNC** (Excessive vaginal bleeding) | `PENDING_PERSON_C_VERIFICATION` (`pending_clinical_review`) |
| 2 | `high_fever` (`general`) | High Fever | `high fever`, `fever`, `very hot to touch`, `high temperature`, `chills with fever`, `rigors` | Hinglish (`hindi_phrases`: 12); Native scripts (`hi-IN`: 5, `ta-IN`: 3, `te-IN`: 3, `bn-IN`: 3, `mr-IN`: 3, `gu-IN`: 3, `kn-IN`: 3, `ml-IN`: 3, `pa-IN`: 5); `transliterations`: 10; `code_mixed`: 9; `spelling_variations`: 5 | **MoHFW / MWCD MCP Card & NHM HBNC Revised** (High fever / hyperthermia in newborn; fever & chills / postpartum sepsis); **WHO PCPNC** (Fever or chills / newborn hyperthermia) | `PENDING_PERSON_C_VERIFICATION` (`pending_clinical_review`) |
| 3 | `convulsions` (`general`) | Convulsions or Seizures | `convulsions`, `convulsion`, `seizure`, `seizures`, `fits`, `jerking movements`, `twitching` | Hinglish (`hindi_phrases`: 11); Native scripts (`hi-IN`: 3, `ta-IN`: 3, `te-IN`: 3, `bn-IN`: 2, `mr-IN`: 3, `gu-IN`: 3, `kn-IN`: 3, `ml-IN`: 3, `pa-IN`: 3); `transliterations`: 8; `code_mixed`: 7; `spelling_variations`: 4 | **MoHFW / MWCD MCP Card & NHM HBNC Revised** (Maternal eclampsia fits; newborn convulsions / twitching); **WHO PCPNC** (Convulsions in mother or newborn) | `PENDING_PERSON_C_VERIFICATION` (`pending_clinical_review`) |
| 4 | `breathing_difficulty` (`newborn`) | Fast Breathing or Difficulty Breathing | `difficulty breathing`, `breathing difficulty`, `fast breathing`, `rapid breathing`, `shortness of breath`, `trouble breathing`, `chest indrawing`, `grunting`, `gasping` | Hinglish (`hindi_phrases`: 13); Native scripts (`hi-IN`: 3, `ta-IN`: 3, `te-IN`: 3, `bn-IN`: 3, `mr-IN`: 3, `gu-IN`: 3, `kn-IN`: 3, `ml-IN`: 3, `pa-IN`: 3); `transliterations`: 9; `code_mixed`: 5; `spelling_variations`: 4 | **NHM HBNC Operational Guidelines (Revised)** & **IMNCI** (Fast breathing ≥60/min or severe chest indrawing; maternal breathlessness); **WHO PCPNC** (Fast breathing / chest indrawing / shortness of breath) | `PENDING_PERSON_C_VERIFICATION` (`pending_clinical_review`) |
| 5 | `unconsciousness_lethargy` (`general`) | Unconsciousness or Severe Lethargy | `unconscious`, `loss of consciousness`, `unresponsive`, `not waking up`, `severe lethargy`, `very weak and drowsy`, `limp`, `not moving` | Hinglish (`hindi_phrases`: 14); Native scripts (`hi-IN`: 3, `ta-IN`: 3, `te-IN`: 3, `bn-IN`: 3, `mr-IN`: 3, `gu-IN`: 3, `kn-IN`: 3, `ml-IN`: 3, `pa-IN`: 3); `transliterations`: 9; `code_mixed`: 4; `spelling_variations`: 3 | **NHM HBNC Operational Guidelines (Revised)** (Reduced movement, lethargy, limpness, or unconsciousness in newborn); **WHO PCPNC** (Movement only when stimulated or no movement / unconsciousness) | `PENDING_PERSON_C_VERIFICATION` (`pending_clinical_review`) |
| 6 | `poor_feeding_newborn` (`newborn`) | Poor Feeding or Unable to Breastfeed | `unable to feed`, `not feeding`, `not breastfeeding`, `refusing to feed`, `poor feeding`, `poor sucking`, `stopped feeding` | Hinglish (`hindi_phrases`: 10); Native scripts (`hi-IN`: 2, `ta-IN`: 2, `te-IN`: 2, `bn-IN`: 2, `mr-IN`: 2, `gu-IN`: 3, `kn-IN`: 2, `ml-IN`: 2, `pa-IN`: 2); `transliterations`: 6; `code_mixed`: 4; `spelling_variations`: 2 | **NHM HBNC Operational Guidelines (Revised)** & **IMNCI** (Baby unable to suck or stopped feeding); **WHO PCPNC** (Not feeding / unable to feed) | `PENDING_PERSON_C_VERIFICATION` (`pending_clinical_review`) |
| 7 | `severe_headache_blurred_vision` (`maternal`) | Severe Headache with Blurred Vision or Swelling | `severe headache`, `blurred vision`, `blurry vision`, `vision changes`, `swelling of face and hands`, `seeing spots` | Hinglish (`hindi_phrases`: 9); Native scripts (`hi-IN`: 2, `ta-IN`: 2, `te-IN`: 2, `bn-IN`: 2, `mr-IN`: 2, `gu-IN`: 2, `kn-IN`: 2, `ml-IN`: 2, `pa-IN`: 2); `transliterations`: 6; `code_mixed`: 3; `spelling_variations`: 3 | **MoHFW / MWCD MCP Card & NHM HBNC / PNC Guidance** (Severe headache, blurred vision, facial/hand swelling — pre-eclampsia/PIH); **WHO PCPNC** (Severe headache with visual disturbances) | `PENDING_PERSON_C_VERIFICATION` (`pending_clinical_review`) |
| 8 | `reduced_fetal_movement` (`maternal`) | Reduced or Absent Fetal Movement | `reduced fetal movement`, `no fetal movement`, `baby not moving in womb`, `decreased baby movement`, `stopped kicking` | Hinglish (`hindi_phrases`: 7); Native scripts (`hi-IN`: 2, `ta-IN`: 2, `te-IN`: 2, `bn-IN`: 2, `mr-IN`: 2, `gu-IN`: 2, `kn-IN`: 2, `ml-IN`: 2, `pa-IN`: 2); `transliterations`: 3; `code_mixed`: 3; `spelling_variations`: 2 | **MoHFW / MWCD MCP Card & PMSMA** (Reduced or absent fetal movements requiring immediate evaluation) | `PENDING_PERSON_C_VERIFICATION` (`pending_clinical_review`) |
| 9 | `severe_abdominal_pain` (`maternal`) | Severe Abdominal Pain | `severe abdominal pain`, `severe stomach pain`, `intense abdominal pain`, `unbearable stomach pain` | Hinglish (`hindi_phrases`: 6); Native scripts (`hi-IN`: 1, `ta-IN`: 1, `te-IN`: 1, `bn-IN`: 1, `mr-IN`: 1, `gu-IN`: 1, `kn-IN`: 1, `ml-IN`: 1, `pa-IN`: 1); `transliterations`: 6; `code_mixed`: 2; `spelling_variations`: 1 | **MoHFW / MWCD MCP Card, PMSMA & NHM PNC Guidance** (Severe or persistent abdominal pain in pregnancy/postpartum); **WHO PCPNC** (Severe abdominal pain) | `PENDING_PERSON_C_VERIFICATION` (`pending_clinical_review`) |
| 10 | `umbilical_cord_infection` (`newborn`) | Umbilical Cord Infection or Pus | `pus from umbilical cord`, `umbilical infection`, `red umbilical cord`, `swollen umbilicus`, `foul smell from cord` | Hinglish (`hindi_phrases`: 8); Native scripts (`hi-IN`: 2, `ta-IN`: 2, `te-IN`: 2, `bn-IN`: 2, `mr-IN`: 2, `gu-IN`: 2, `kn-IN`: 2, `ml-IN`: 2, `pa-IN`: 2); `transliterations`: 4; `code_mixed`: 2; `spelling_variations`: 2 | **NHM HBNC Operational Guidelines (Revised)** & **IMNCI** (Umbilical redness/pus / omphalitis); **WHO PCPNC** (Local umbilical cord infection / pus) | `PENDING_PERSON_C_VERIFICATION` (`pending_clinical_review`) |
| 11 | `newborn_jaundice` (`newborn`) | Jaundice in Newborn (Yellow Palms/Soles or Early Jaundice) | `yellow palms`, `yellow soles`, `newborn jaundice`, `yellow eyes and skin`, `jaundice` | Hinglish (`hindi_phrases`: 8); Native scripts (`hi-IN`: 2, `ta-IN`: 2, `te-IN`: 2, `bn-IN`: 2, `mr-IN`: 2, `gu-IN`: 2, `kn-IN`: 2, `ml-IN`: 2, `pa-IN`: 2); `transliterations`: 6; `code_mixed`: 3; `spelling_variations`: 2 | **NHM HBNC Operational Guidelines (Revised)** & **IMNCI** (Yellow palms and soles / severe neonatal jaundice); **WHO PCPNC** (Severe jaundice / yellow palms or soles) | `PENDING_PERSON_C_VERIFICATION` (`pending_clinical_review`) |
| 12 | `hypothermia_cold_baby` (`newborn`) | Cold to Touch / Hypothermia | `cold to touch`, `hypothermia`, `baby feels very cold`, `low body temperature` | Hinglish (`hindi_phrases`: 6); Native scripts (`hi-IN`: 2, `ta-IN`: 2, `te-IN`: 2, `bn-IN`: 2, `mr-IN`: 2, `gu-IN`: 2, `kn-IN`: 2, `ml-IN`: 2, `pa-IN`: 2); `transliterations`: 5; `code_mixed`: 2; `spelling_variations`: 1 | **NHM HBNC Operational Guidelines (Revised)** & **IMNCI** (Baby feels very cold / hypothermia); **WHO PCPNC** (Too cold / hypothermia) | `PENDING_PERSON_C_VERIFICATION` (`pending_clinical_review`) |

---

## 3. Exact Regional-Language Phrases Verified in `backend/data/danger_signs.json`

- **1. `severe_bleeding`:**
  - `hi-IN`: खून बह रहा है, ज्यादा खून, रक्तस्राव
  - `ta-IN`: அதிக இரத்தப்போக்கு, இரத்தப்போக்கு உள்ளது, ரத்தப்போக்கு
  - `te-IN`: అధిక రక్తస్రావం, రక్తస్రావం అవుతోంది, రక్తం కారుతోంది
  - `bn-IN`: অতিরিক্ত রক্তপাত, রক্তপাত হচ্ছে, রক্তস্রাব
  - `mr-IN`: जास्त रक्तस्राव, रक्तस्राव होत आहे, रक्त जात आहे
  - `gu-IN`: વધારે લોહી વહે છે, રક્તસ્ત્રાવ થાય છે, લોહી પડે છે
  - `kn-IN`: ಅತಿಯಾದ ರಕ್ತಸ್ರಾವ, ರಕ್ತಸ್ರಾವ ಆಗುತ್ತಿದೆ, ರಕ್ತ ಹೋಗುತ್ತಿದೆ
  - `ml-IN`: അമിത രക്തസ്രാവം, രക്തസ്രാവം ഉണ്ട്, രക്തം പോകുന്നു
  - `pa-IN`: ਬਹੁਤ ਖੂਨ ਵਹਿ ਰਿਹਾ ਹੈ, ਖੂਨ ਆ ਰਿਹਾ ਹੈ, ਰਕਤਸ੍ਰਾਵ
- **2. `high_fever`:**
  - `hi-IN`: तेज बुखार, तेज़ बुखार, बुखार है, बुखार लग रहा, बुखार
  - `ta-IN`: அதிக காய்ச்சல், காய்ச்சல் உள்ளது, உடல் மிகவும் சூடாக உள்ளது
  - `te-IN`: అధిక జ్వరం, తీవ్రమైన జ్వరం, జ్వరం ఉంది
  - `bn-IN`: তীব্র জ্বর, খুব জ্বর, জ্বর হয়েছে
  - `mr-IN`: खूप ताप, ताप आहे, तीव्र ताप
  - `gu-IN`: ખૂબ તાવ, તેજ તાવ, તાવ છે
  - `kn-IN`: ತೀವ್ರ ಜ್ವರ, ಹೆಚ್ಚು ಜ್ವರ, ಜ್ವರ ಇದೆ
  - `ml-IN`: കടുത്ത പനി, ഉയർന്ന പനി, പനി ഉണ്ട്
  - `pa-IN`: ਤੇਜ਼ ਬੁਖਾਰ, ਬੁਖਾਰ ਹੈ, ਬਹੁਤ ਬੁਖਾਰ, ਬੁਖਾਰ ਲੱਗਦਾ, ਬੁਖਾਰ
- **3. `convulsions`:**
  - `hi-IN`: दौरे पड़ रहे, दौरा पड़ा, झटके आ रहे
  - `ta-IN`: வலிப்பு, வலிப்பு வருகிறது, கை கால் இழுப்பு
  - `te-IN`: ఫిట్స్, మూర్ఛ, వణుకు వస్తోంది
  - `bn-IN`: খিঁচুনি, খিঁচুনি হচ্ছে
  - `mr-IN`: झटके येत आहेत, आकडी येत आहे, फिट्स
  - `gu-IN`: ખેંચ આવે છે, તાણ આવે છે, આંચકી
  - `kn-IN`: ಸೆಳೆತ, ಫಿಟ್ಸ್ ಬರುತ್ತಿದೆ, ಮೂರ್ಛೆ
  - `ml-IN`: അപസ്മാരം, സന്നി, വിറയൽ വരുന്നു
  - `pa-IN`: ਦੌਰੇ ਪੈ ਰਹੇ, ਝਟਕੇ ਆ ਰਹੇ, ਮਿਰਗੀ ਦਾ ਦੌਰਾ
- **4. `breathing_difficulty`:**
  - `hi-IN`: सांस लेने में तकलीफ, सांस फूल रही है, तेज सांस
  - `ta-IN`: மூச்சுத் திணறல், வேகமாக மூச்சு, மூச்சு விட சிரமம்
  - `te-IN`: శ్వాస తీసుకోవడంలో ఇబ్బంది, వేగంగా శ్వాస, ఊపిరి ఆడటం లేదు
  - `bn-IN`: শ্বাসকষ্ট, দ্রুত শ্বাস, শ্বাস নিতে কষ্ট
  - `mr-IN`: श्वास घेण्यास त्रास, जलद श्वास, दम लागणे
  - `gu-IN`: શ્વાસ લેવામાં તકલીફ, ઝડપી શ્વાસ, શ્વાસ ચડે છે
  - `kn-IN`: ಉಸಿರಾಟದ ತೊಂದರೆ, ವೇಗದ ಉಸಿರಾಟ, ಉಸಿರು ಕಟ್ಟುವುದು
  - `ml-IN`: ശ്വാസതടസ്സം, വേഗത്തിലുള്ള ശ്വാസം, ശ്വാസം മുട്ടൽ
  - `pa-IN`: ਸਾਹ ਲੈਣ ਵਿੱਚ ਤਕਲੀਫ਼, ਤੇਜ਼ ਸਾਹ, ਸਾਹ ਫੁੱਲ ਰਿਹਾ
- **5. `unconsciousness_lethargy`:**
  - `hi-IN`: बेहोश है, होश नहीं है, बहुत सुस्त
  - `ta-IN`: மயக்கம், நினைவு இல்லை, மிகவும் சோர்வாக
  - `te-IN`: అపస్మారక స్థితి, స్పృహ లేదు, చాలా నీరసంగా
  - `bn-IN`: অজ্ঞান, হুঁশ নেই, খুবই নিস্তেজ
  - `mr-IN`: बेशुद्ध, शुद्धीवर नाही, खूप सुस्त
  - `gu-IN`: બેભાન, ભાન નથી, ખૂબ સુસ્ત
  - `kn-IN`: ಪ್ರಜ್ಞೆ ತಪ್ಪಿದೆ, ಪ್ರಜ್ಞೆ ಇಲ್ಲ, ತುಂಬಾ ನಿತ್ರಾಣ
  - `ml-IN`: അബോധാവസ്ഥ, ബോധമില്ല, വളരെ ക്ഷീണിതൻ
  - `pa-IN`: ਬੇਹੋਸ਼ ਹੈ, ਹੋਸ਼ ਨਹੀਂ, ਬਹੁਤ ਸੁਸਤ
- **6. `poor_feeding_newborn`:**
  - `hi-IN`: दूध नहीं पी रहा, दूध पीना बंद
  - `ta-IN`: பால் குடிக்கவில்லை, தாய்ப்பால் குடிக்க மறுக்கிறது
  - `te-IN`: పాలు తాగడం లేదు, తల్లిపాలు తాగలేకపోతోంది
  - `bn-IN`: দুধ খাচ্ছে না, বুকের দুধ টানতে পারছে না
  - `mr-IN`: दूध पीत नाही, स्तनपान करत नाही
  - `gu-IN`: દૂધ પીતું નથી, ધાવણ નથી લેતું, ધાવણ લેતું નથી
  - `kn-IN`: ಹಾಲು ಕುಡಿಯುತ್ತಿಲ್ಲ, ಎದೆಹಾಲು ಕುಡಿಯುತ್ತಿಲ್ಲ
  - `ml-IN`: പാൽ കുടിക്കുന്നില്ല, മുലപ്പാൽ കുടിക്കുന്നില്ല
  - `pa-IN`: ਦੁੱਧ ਨਹੀਂ ਪੀ ਰਿਹਾ, ਦੁੱਧ ਪੀਣਾ ਬੰਦ
- **7. `severe_headache_blurred_vision`:**
  - `hi-IN`: तेज सर दर्द, धुंधला दिख रहा
  - `ta-IN`: கடுமையான தலைவலி, மங்கலான பார்வை
  - `te-IN`: తీవ్రమైన తలనొప్పి, మసకబారిన చూపు
  - `bn-IN`: তীব্র মাথাব্যথা, ঝাপসা দেখা
  - `mr-IN`: तीव्र डोकेदुखी, धूसर दिसणे
  - `gu-IN`: તೀವ્ર માથાનો દુખાવો, ઝાંખું દેખાવું
  - `kn-IN`: ತೀವ್ರ ತಲೆನೋವು, ಮಸುಕಾದ ದೃಷ್ಟಿ
  - `ml-IN`: കഠിനമായ തലവേദന, കാഴ്ച മങ്ങൽ
  - `pa-IN`: ਤੇਜ਼ ਸਿਰ ਦਰਦ, ਧੁੰਦਲਾ ਦਿਖਾਈ ਦੇਣਾ
- **8. `reduced_fetal_movement`:**
  - `hi-IN`: पेट में बच्चा हिल नहीं रहा, बच्चे की हलचल कम
  - `ta-IN`: குழந்தை அசைவு இல்லை, வயிற்றில் குழந்தை அசையவில்லை
  - `te-IN`: కడుపులో బిడ్డ కదలికలు లేవు, కదలికలు తగ్గాయి
  - `bn-IN`: গর্ভে বাচ্চার নড়াচড়া কম, বাচ্চা নড়ছে না
  - `mr-IN`: पोटातील बाळाची हालचाल कमी, बाळ हलत नाही
  - `gu-IN`: પેટમાં બાળકનું હલનચલન ઓછું, બાળક હલતું નથી
  - `kn-IN`: ಗರ್ಭದಲ್ಲಿ ಮಗುವಿನ ಚಲನೆ ಕಡಿಮೆ, ಮಗು ಚಲಿಸುತ್ತಿಲ್ಲ
  - `ml-IN`: വയറ്റിൽ കുഞ്ഞിന്റെ അനക്കം കുറവ്, കുഞ്ഞ് അനങ്ങുന്നില്ല
  - `pa-IN`: ਪੇਟ ਵਿੱਚ ਬੱਚਾ ਹਿੱਲ ਨਹੀਂ ਰਿਹਾ, ਬੱਚੇ ਦੀ ਹਲਚਲ ਘੱਟ
- **9. `severe_abdominal_pain`:**
  - `hi-IN`: बहुत तेज पेट दर्द
  - `ta-IN`: கடுமையான வயிற்று வலி
  - `te-IN`: తీవ్రమైన కడుపు నొప్పి
  - `bn-IN`: তীব্র পেটে ব্যথা
  - `mr-IN`: तीव्र पोटदुखी
  - `gu-IN`: પેટમાં સખત દુખાવો
  - `kn-IN`: ತೀವ್ರ ಹೊಟ್ಟೆ ನೋವು
  - `ml-IN`: കഠിനമായ വയറുവേദന
  - `pa-IN`: ਪੇਟ ਵਿੱਚ ਤੇਜ਼ ਦਰਦ
- **10. `umbilical_cord_infection`:**
  - `hi-IN`: नाभि से मवाद, नाभि लाल हो गई
  - `ta-IN`: தொப்புள் கொடியில் சீழ், தொப்புள் சிவந்துள்ளது
  - `te-IN`: బొడ్డు నుండి చీము, బొడ్డు ఎర్రగా ఉంది
  - `bn-IN`: নাভি থেকে পুঁজ, নাভি লাল হয়ে গেছে
  - `mr-IN`: नाभीतून पू, नाभी लाल झाली आहे
  - `gu-IN`: નાભિમાંથી પરુ, નાભિ લાલ થઈ ગઈ છે
  - `kn-IN`: ಹೊಕ್ಕುಳಿನಿಂದ ಕೀವು, ಹೊಕ್ಕುಳು ಕೆಂಪಾಗಿದೆ
  - `ml-IN`: പൊക്കിൾക്കൊടിയിൽ പഴുപ്പ്, പൊക്കിൾ ചുവന്നിരിക്കുന്നു
  - `pa-IN`: ਨਾਭੀ ਵਿੱਚੋਂ ਪੀਕ, ਨਾਭੀ ਲਾਲ ਹੋ ਗਈ
- **11. `newborn_jaundice`:**
  - `hi-IN`: पीलिया, हथेली पीली
  - `ta-IN`: மஞ்சள் காமாலை, கண்கள் மஞ்சளாக
  - `te-IN`: పచ్చ కామెర్లు, చర్మం పసుపు రంగులో
  - `bn-IN`: জন্ডিস, হলুদ হয়ে গেছে
  - `mr-IN`: कावीळ, पिवळसर त्वचा
  - `gu-IN`: કમળો, આંખો પીળી
  - `kn-IN`: ಕಾಮಾಲೆ, ಹಳದಿ ಬಣ್ಣ
  - `ml-IN`: മഞ്ഞപ്പിത്തം, മഞ്ഞ നിറം
  - `pa-IN`: ਪੀਲੀਆ, ਅੱਖਾਂ ਪੀਲੀਆਂ
- **12. `hypothermia_cold_baby`:**
  - `hi-IN`: बच्चा ठंडा पड़ रहा, शरीर ठंडा है
  - `ta-IN`: குழந்தை மிகவும் குளிராக உள்ளது, உடல் ஜில்லுனு உள்ளது
  - `te-IN`: బిడ్డ చాలా చల్లగా ఉంది, శరీరం చల్లబడింది
  - `bn-IN`: বাচ্চা খুব ঠান্ডা হয়ে গেছে, শরীর ঠান্ডা
  - `mr-IN`: बाळ खूप थंड पडले आहे, शरीर थंड आहे
  - `gu-IN`: બાળક ખૂબ ઠંડું પડી ગયું છે, શરીર ઠંડું છે
  - `kn-IN`: ಮಗು ತುಂಬಾ ತಣ್ಣಗಾಗಿದೆ, ದೇಹ ತಣ್ಣಗಿದೆ
  - `ml-IN`: കുഞ്ഞ് വളരെ തണുത്തിരിക്കുന്നു, ശരീരം തണുത്തതാണ്
  - `pa-IN`: ਬੱਚਾ ਬਹੁਤ ਠੰਡਾ ਪੈ ਰਿਹਾ, ਸਰੀਰ ਠੰਡਾ ਹੈ

---

## 4. Safety Architecture & Guardrail Verification Checklist

- **OR Logic Between Layers (`DangerDetector.detect`):** `danger_detected = bool(rule_flags OR llm_flags)`. Layer-2 LLM can add contextual detections or enrich `matched_evidence` / `llm_reason`, and **can never suppress or cancel a positive Layer-1 rule-based match**.
- **No Silent Downgrade Across Turns (`FormStateManager._merge_danger_flags`):** Danger flags persist in `session.danger_flags` and `session.record.danger_signs` across subsequent turns even if later turns contain routine form updates without symptoms.
- **Consistent Referral Guidance:** Immediate PHC referral templates across all 10 Gnani languages + `hi-en` live in `danger_signs.json` (`metadata.default_referral_messages` / `brain.languages.REFERRAL_MESSAGES`) and match across all responses with `action == "refer_danger"`.
- **No Diagnosis / Medication / Dosage Advice (`MedicalGuardrails`):** Both `evaluate_input` (pre-extraction screening & multilingual jailbreak protection) and `validate_output` (blocking medication names, `mg`/`ml` dosage instructions, and diagnostic statements) enforce refusal templates without diagnosing or prescribing.

---

## 5. Action Required from Person C / Clinical Reviewer

1. Review all **12 entries** above, verify regional phrasing and dialect variants per state deployment, and supply/confirm official clinical thresholds (e.g., fever temperature cutoffs in `detect_rule_based` lines 364–374) under NHM HBNC / IMNCI / MCP Card protocols.
2. Check for any additional maternal or newborn danger signs required for deployment (e.g., severe pallor/anemia, leaking per vaginum/PROM, cyanosis, persistent vomiting) before changing `verification_status` or `source_reference`.
3. Only after qualified clinical review is signed off should `pending_person_c_verification` and `source_reference` be updated in `backend/data/danger_signs.json`.

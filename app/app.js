const API_BASE_URL = `${window.location.protocol}//${window.location.hostname}:8000`;
let SESSION_ID = "session_" + Math.random().toString(36).substring(2, 9);

// DOM Elements
const recordButton = document.getElementById("talk-btn");
const statusBadge = document.getElementById("status-badge");
const transcriptBox = document.getElementById("transcript-box");
const dangerBanner = document.getElementById("danger-banner");
const dangerTitle = document.getElementById("danger-title");
const dangerMsg = document.getElementById("danger-msg");
const latencyVal = document.getElementById("latency-val");
const languageSelect = document.getElementById("language-select");

// Form Fields
const fieldName = document.getElementById("field-name");
const fieldAge = document.getElementById("field-age");
const fieldSymptoms = document.getElementById("field-symptoms");
const fieldAction = document.getElementById("field-action");

// Storage & List Elements
const saveBtn = document.getElementById("save-btn");
const clearStorageBtn = document.getElementById("clear-storage-btn");
const followupList = document.getElementById("followup-list");

let isRecording = false;
let recognition = null;

function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        console.warn("Web Speech API not supported in this browser.");
        return null;
    }

    const rec = new SpeechRecognition();
    rec.continuous = false;
    rec.interimResults = true;
    rec.lang = languageSelect ? languageSelect.value : 'hi-IN';

    rec.onstart = () => updateStatus("Listening...", "active");

    rec.onresult = (event) => {
        let interimTranscript = '';
        let finalTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
                finalTranscript += event.results[i][0].transcript;
            } else {
                interimTranscript += event.results[i][0].transcript;
            }
        }

        const currentText = finalTranscript || interimTranscript;
        if (transcriptBox) {
            transcriptBox.innerHTML = `<strong>Spoken (${rec.lang}):</strong> ${currentText}`;
        }

        if (finalTranscript) {
            sendTranscriptToBackend(finalTranscript, rec.lang);
        }
    };

    rec.onerror = (event) => {
        console.error("Speech error:", event.error);
        updateStatus("Mic Error", "error");
        isRecording = false;
        if (recordButton) recordButton.classList.remove("listening");
    };

    rec.onend = () => {
        isRecording = false;
        if (recordButton) recordButton.classList.remove("listening");
        updateStatus("Ready", "ready");
    };

    return rec;
}

recognition = initSpeechRecognition();

if (languageSelect) {
    languageSelect.addEventListener("change", (e) => {
        if (recognition) recognition.lang = e.target.value;
    });
}

if (recordButton) {
    recordButton.addEventListener("click", (e) => {
        e.preventDefault();
        if (!isRecording) startListening();
        else stopListening();
    });
}

function startListening() {
    isRecording = true;
    if (recordButton) recordButton.classList.add("listening");
    if (recognition) {
        if (languageSelect) recognition.lang = languageSelect.value;
        try { recognition.start(); } catch (e) { console.error(e); }
    }
}

function stopListening() {
    isRecording = false;
    if (recordButton) recordButton.classList.remove("listening");
    if (recognition) {
        try { recognition.stop(); } catch (e) {}
    }
}

function updateStatus(text, state) {
    if (statusBadge) {
        statusBadge.innerText = text;
        statusBadge.className = `status-badge ${state}`;
    }
}

async function sendTranscriptToBackend(transcriptText, langCode) {
    if (!transcriptText || transcriptText.trim() === "") return;
    updateStatus("Processing...", "active");
    const startTime = performance.now();

    try {
        const response = await fetch(`${API_BASE_URL}/api/brain/process`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                session_id: SESSION_ID,
                transcript: transcriptText,
                language: langCode
            })
        });

        const endTime = performance.now();
        if (latencyVal) latencyVal.innerText = Math.round(endTime - startTime);

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        console.log("AI Brain Response:", data);
        updateUIWithBrainResponse(data);
        updateStatus("Ready", "ready");

    } catch (error) {
        console.error("Backend API Error:", error);
        updateStatus("Server Error", "error");
    }
}

function updateUIWithBrainResponse(data) {
    const form = data.form_state || {};
    const benInfo = data.beneficiary_info || {};
    console.log("EXACT FORM STATE FROM BACKEND:", form);

    // Grab the spoken transcript text from the UI as a backup source
    const rawSpokenText = transcriptBox ? transcriptBox.innerText : "";

    // 1. Danger Banner Handling
    if (dangerBanner) {
        if (data.danger_detected) {
            dangerBanner.classList.remove("hidden");
            if (dangerTitle) dangerTitle.innerText = "🚨 DANGER SIGN DETECTED";
            const flagNames = (data.danger_flags || [])
                .map(f => f.sign || f.name || f.description || "Danger sign")
                .join(", ");
            if (dangerMsg) {
                dangerMsg.innerText = flagNames
                    ? `Detected: ${flagNames} — Immediate PHC referral required!`
                    : (data.reply_text || "Immediate PHC referral required!");
            }
        } else {
            dangerBanner.classList.add("hidden");
        }
    }

    // 2. Beneficiary Name / ID (Backend first, then smart transcript fallback)
    let name = form.beneficiary_name || form.patient_name || form.mother_name || form.name || benInfo.name || "";
    const id = form.beneficiary_id || form.patient_id || form.id || benInfo.id || "";

    if (!name && rawSpokenText) {
        // Matches Hindi ("सुनीता देवी का") or English ("name Sunita Devi" / "Sunita Devi's")
        const hiNameMatch = rawSpokenText.match(/आज\s+([^\s]+\s+[^\s]+)\s+का/);
        const enNameMatch = rawSpokenText.match(/(?:name\s+is|name|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)/i);
        if (hiNameMatch) name = hiNameMatch[1];
        else if (enNameMatch) name = enNameMatch[1];
    }

    if (fieldName) {
        fieldName.value = (name && id) ? `${name} (ID: ${id})` : (name || id || "");
    }

    // 3. Gestational / Child Age (Backend first, then smart transcript fallback)
    if (fieldAge) {
        let rawAge = form.gestational_weeks || form.gestational_months || form.gestational_age || form.age || form.trimester || form.child_age || "";
        
        if (!rawAge && rawSpokenText) {
            // Matches "7 months pregnant", "7 मंथ्स प्रेगनेंट", "28 weeks", "6 months old"
            const ageMatch = rawSpokenText.match(/(\d+\s*(?:months?|weeks?|years?|मंथ्स|महीने|हफ्ते)(?:\s*(?:pregnant|प्रेगनेंट|old))?)/i);
            if (ageMatch) {
                rawAge = ageMatch[1]
                    .replace(/मंथ्स|महीने/g, "months")
                    .replace(/हफ्ते/g, "weeks")
                    .replace(/प्रेगनेंट/g, "pregnant");
            }
        }
        fieldAge.value = rawAge || "";
    }

    // 4. Symptoms & Observations
    if (fieldSymptoms) {
        let notes = [];
        const symptomsList = form.symptoms || form.clinical_notes || form.observations || [];
        if (Array.isArray(symptomsList) && symptomsList.length > 0) {
            notes.push(`Symptoms: ${symptomsList.join(", ")}`);
        } else if (typeof symptomsList === "string" && symptomsList) {
            notes.push(`Symptoms: ${symptomsList}`);
        }
        if (form.weight_kg) notes.push(`Weight: ${form.weight_kg} kg`);
        if (form.blood_pressure) notes.push(`BP: ${form.blood_pressure}`);
        if (data.danger_flags && data.danger_flags.length > 0) {
            notes.push(`Alerts: ${data.danger_flags.map(f => f.sign || f.name || "Danger").join(", ")}`);
        }
        fieldSymptoms.value = notes.length > 0 ? notes.join(" | ") : (data.reply_text || "");
    }

    // 5. Action & Referral Status
    if (fieldAction) {
        if (data.action === "refer_danger" || data.danger_detected) {
            fieldAction.value = "Urgent PHC Referral Required";
        } else if (Array.isArray(data.missing_fields) && data.missing_fields.length > 0) {
            fieldAction.value = `Pending: ${data.missing_fields.join(", ")}`;
        } else {
            fieldAction.value = data.action || "Standard home visit";
        }
    }
}

// Save Visit & Start Fresh Session
if (saveBtn) {
    saveBtn.addEventListener("click", () => {
        const record = {
            name: fieldName?.value || "Unknown Beneficiary",
            age: fieldAge?.value || "N/A",
            symptoms: fieldSymptoms?.value || "Routine check",
            action: fieldAction?.value || "Saved",
            date: new Date().toLocaleDateString()
        };

        const saved = JSON.parse(localStorage.getItem("asha_visits") || "[]");
        saved.unshift(record);
        localStorage.setItem("asha_visits", JSON.stringify(saved));
        renderFollowups();

        // Reset form and generate a fresh SESSION_ID for the next patient
        document.getElementById("visit-form")?.reset();
        dangerBanner?.classList.add("hidden");
        SESSION_ID = "session_" + Math.random().toString(36).substring(2, 9);
        updateStatus("Saved! Ready for next", "ready");
    });
}

if (clearStorageBtn) {
    clearStorageBtn.addEventListener("click", () => {
        localStorage.removeItem("asha_visits");
        renderFollowups();
    });
}

function renderFollowups() {
    if (!followupList) return;
    const saved = JSON.parse(localStorage.getItem("asha_visits") || "[]");
    if (saved.length === 0) {
        followupList.innerHTML = `<li class="empty-state">No saved visits yet. Complete a visit to track schedules.</li>`;
        return;
    }
    followupList.innerHTML = saved.map(v => `
        <li style="margin-bottom: 8px; padding: 8px; border-bottom: 1px solid #eee;">
            <strong>${v.name}</strong> (${v.age}) — <em>${v.date}</em><br/>
            <small>${v.symptoms} | <strong>${v.action}</strong></small>
        </li>
    `).join("");
}

// Load saved visits on startup
renderFollowups();
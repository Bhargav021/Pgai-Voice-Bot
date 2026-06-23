# PGAI Voice Bot — Bug Report

**Target system:** PGAI AI Receptionist at +1-805-439-8008 (PivotPoint Orthopedics demo)
**Testing method:** Automated Python bot placing 12 outbound calls with patient personas
**Bot stack:** Deepgram Nova-2 STT → GPT-4o-mini patient brain → OpenAI TTS-1 → Twilio Media Streams

---

## Critical (5)

### C1. Agent terminates call without providing confirmation number

- **Severity:** Critical
- **Scenario:** simple_scheduling
- **Observed:** Patient booked appointment and asked for a confirmation number. Agent ended the call immediately without providing any reference number, booking ID, or follow-up instructions.
- **Impact:** Patient has no proof of appointment. Cannot verify or cancel later. Medical context makes this especially damaging — patient may miss appointment or arrive at wrong time.
- **Transcript excerpt:**
  ```
  AGENT:   Your diabetes checkup is booked for Tuesday, June 30 at 10AM.
  PATIENT: Thank you! Could I please have the confirmation number or reference for my appointment?
  [Call ends — no confirmation provided]
  ```

---

### C2. Cross-patient appointment data exposed to different caller (HIPAA risk)

- **Severity:** Critical
- **Scenario:** rescheduling (immediately after simple_scheduling)
- **Observed:** After "Maria Gonzalez" booked an appointment (Tuesday June 30 at 10AM), the next caller "David Chen" was shown Maria's appointment: "I see you have an appointment scheduled for Tuesday, June 30 at 10AM with z Bignu Lukovsky MD at Nashville 220 Athens Way." David was then unable to reschedule his actual appointment because the agent could not find it.
- **Impact:** In a real deployment this is a HIPAA violation. One patient's appointment details (including treating physician name and clinic address) are visible to another patient. Could also indicate the demo system uses shared/global state rather than per-patient records.
- **Additional finding:** Doctor name "z Bignu Lukovsky MD" appears to be a test placeholder that leaked into the demo, suggesting insufficient data validation in the provider database.
- **Transcript excerpt:**
  ```
  [David Chen, calling to reschedule annual physical on "this Friday"]
  AGENT: I see you have an appointment scheduled for Tuesday, June 30 at 10AM
         with z Bignu Lukovsky MD at Nashville 220 Athens Way.
  PATIENT: Actually, I need to reschedule my annual physical from this Friday...
  AGENT: I only see an appointment for Tuesday, June 30 at 10AM.
  [David Chen gives up and ends call]
  ```

---

## High (10)

### H1. Agent incorrectly reports existing appointment for new patient

- **Severity:** High
- **Scenario:** simple_scheduling (repeat call)
- **Observed:** On a second call for the same scenario, the agent told a new patient "It looks like you already have a routine checkup appointment scheduled." — a false positive that blocked the patient from booking.
- **Impact:** Patients calling to schedule an appointment are turned away based on incorrect data. Could be a carry-over of session state between calls or a CRM lookup error.
- **Transcript excerpt:**
  ```
  PATIENT: I'd like to schedule a routine quarterly checkup for my Type 2 diabetes.
  AGENT:   It looks like you already have a routine checkup appointment scheduled.
  AGENT:   If you want to reschedule or cancel it, I can connect you to a team member for help.
  ```

### H2. Agent auto-assigns incorrect date of birth without asking

- **Severity:** High
- **Scenario:** simple_scheduling
- **Observed:** After collecting only the patient's name ("Maria Gonzalez"), the agent stated "And your date of birth is 07/04/2000" — an incorrect value not provided by the patient — then asked "How can I help you today?" resetting the flow.
- **Impact:** Patient records are corrupted with a fictional DOB. HIPAA-sensitive. Resets the conversation state, wasting patient time.
- **Transcript excerpt:**
  ```
  PATIENT: My name is Maria Gonzalez.
  AGENT:   Your patient profile is set up.
  PATIENT: I'd like to schedule my quarterly diabetes checkup for next Tuesday morning...
  AGENT:   And your date of birth is 07/04/2000. How can I help you today?
  ```

### H3. Agent defers booking to "support team" instead of scheduling directly

- **Severity:** High
- **Scenario:** simple_scheduling, rescheduling
- **Observed:** Agent responds with "Your request has been sent to our clinic. The support team will review your request and get back to you as soon as possible." This is a failure to complete the primary task — the whole purpose of an AI receptionist is to book appointments immediately.
- **Impact:** Patient must wait for a callback instead of getting a confirmed appointment. Defeats the purpose of the AI agent.

### H4. Agent resets conversation after profile creation

- **Severity:** High
- **Scenario:** simple_scheduling
- **Observed:** After saying "Your patient profile is set up", the agent asks "How can I help you today?" — returning to the initial state as if the conversation never happened.
- **Impact:** Forces patient to re-state their reason for calling, causing confusion and unnecessary round-trips. Conversation context is lost.

---

## Medium (10)

### M1. Agent identifies as wrong practice type for patient's condition

- **Severity:** Medium
- **Scenario:** All scenarios
- **Observed:** Agent introduces itself as "PivotPoint Orthopedics, part of Pretty Good AI." When patients call about diabetes care, the agent still attempts to schedule without redirecting to an appropriate specialist. Orthopedics is not the right specialty for diabetes management.
- **Impact:** Patients may receive incorrect care routing. Agent does not flag the specialty mismatch or suggest calling a primary care or endocrinology practice.
- **Note:** This may be intentional demo configuration. However, the agent should handle out-of-scope specialty requests gracefully.

### M2. Truncated / fragmented agent utterances

- **Severity:** Medium
- **Scenario:** Multiple
- **Observed:** Multiple agent utterances arrive as sentence fragments with missing beginnings or abrupt endings:
  - `"to schedule a routine quarterly checkup for your type two diabetes."` (missing subject/verb)
  - `"Tuesday morning at nine"` (incomplete — no action stated)
  - `"support team. They will review your request and get back to you as soon as possible about next"` (cut off mid-sentence)
  - `"This the appointment you want to move to Monday next week?"` (grammatically incorrect — missing "Is")
- **Impact:** Patient may misunderstand agent intent. Our bot had to ask follow-up questions to recover context. In a real call, human patients would be confused or lose trust.

### M3. Agent begins sentence with "But" without preceding clause

- **Severity:** Medium
- **Scenario:** simple_scheduling
- **Observed:** `"But the earliest available slot is at 10AM."` — grammatically incorrect sentence start, suggesting the agent's response began mid-sentence or the preceding part was dropped.
- **Impact:** Unnatural dialogue that may confuse real patients. Indicates either TTS chunking issue or dialogue state loss.

---

## Low (1)

### M4. No explicit cancellation confirmation

- **Severity:** Medium
- **Scenario:** cancellation
- **Observed:** After patient agreed to cancel "Tuesday June 30" appointment, agent replied only "No problem." — no explicit confirmation that the cancellation was completed, no reference number, no summary of what was cancelled.
- **Impact:** Patient has no certainty the cancellation went through. They cannot verify later. In medical context, failed cancellations waste physician time and may incur no-show fees.
- **Transcript excerpt:**
  ```
  PATIENT: I need to cancel my appointment for this Tuesday, June 30.
  AGENT:   No problem.
  PATIENT: Thank you! I also want to mention that I have an unexpected work trip...
  [Call ends — no confirmation of cancellation received]
  ```

### M5. Agent's doctor name pronunciation unintelligible

- **Severity:** Medium
- **Scenario:** rescheduling, cancellation
- **Observed:** A doctor name in the system was transcribed by Deepgram as "z Bignu Lukovsky MD", "doctor Zee Bignew Lukaszky", and "doctor Zudbig new" across three separate calls — all clearly the same underlying name, rendered unintelligibly by the agent's TTS. The name appears to be Eastern European (possibly "Zbigniew Lukovsky") and is not being pronounced clearly.
- **Impact:** Patients cannot understand who their doctor is. Creates confusion, erodes trust. Agent's TTS should handle non-English names with phonetic fallback or spelling-out.

### M6. Practice name inconsistent across calls

- **Severity:** Medium
- **Scenario:** cancellation vs. all others
- **Observed:** Agent introduced itself as "Tizard Point Orthopaedics" on the cancellation call, while all other calls heard "PivotPoint Orthopedics." Same phone number, same underlying system. This may be a Deepgram misheard artifact, but if real it indicates inconsistent agent identity configuration.
- **Impact:** Patients calling back may not recognize the practice name they heard previously.

### L1. Ambiguous processing indicator

- **Severity:** Low
- **Scenario:** simple_scheduling
- **Observed:** Agent says "I am processing your request" mid-conversation as a standalone utterance. AI voice agents should be silent while processing, not narrate internal state.
- **Impact:** Minor UX issue. Sounds unnatural and may cause the patient to respond to a non-question.

---

### H5. Agent blocks medication refill when patient declines phone lookup

- **Severity:** High
- **Scenario:** medication_refill
- **Observed:** Patient (James Okafor) provided name and DOB, which agent confirmed. When agent then required a phone number to proceed, and patient declined to provide it, the agent said "I can't proceed further right now" and transferred to a representative instead of processing the refill using the already-verified identity.
- **Impact:** Medication refill was not completed. Patient stated they have only 3 days of blood pressure medication (lisinopril) remaining. Blocking the refill for a required phone number when sufficient identity verification already exists is a patient safety risk.
- **Transcript excerpt:**
  ```
  AGENT:   Just to confirm, I have your name as James Okafor and DOB as 11/08/1962. Please spell your first and last [cut off]
  PATIENT: I'd prefer not to provide my phone number right now. Can you proceed with just my name and date of birth?
  AGENT:   Of course. To make sure I have it right, please confirm your first and last name and your date of birth one more time.
  [patient provides same info again]
  AGENT:   I can't proceed further right now, but [cut off]
  AGENT:   Connecting you to a representative.
  ```

### H6. Circular identity verification loop

- **Severity:** High
- **Scenario:** medication_refill
- **Observed:** Agent asked patient for name + DOB, confirmed them, then immediately asked the patient to "spell your first and last name", then requested phone number, then asked for name + DOB again from the beginning. The same verification data was requested 3 times before the agent admitted it couldn't proceed.
- **Impact:** Frustrated patients will abandon the call. In medication-urgent situations (patient has 3 days of BP meds) this is especially harmful.

### H7. Agent addresses caller by previous caller's name (cross-session contamination)

- **Severity:** High
- **Scenario:** office_hours
- **Observed:** Agent greeted Elena Vasquez with "Am I speaking with Maria?" — carrying over the name from the preceding simple_scheduling calls where the patient was Maria Gonzalez. The sessions were completely separate calls.
- **Impact:** Patients addressed by wrong name. Confirms that the agent's session state is not properly isolated between calls. Represents a patient data privacy issue and destroys trust.

### H8. Agent deflects supervisor request by claiming equal authority

- **Severity:** High
- **Scenario:** angry_patient
- **Observed:** When patient repeatedly asked to speak with a billing manager, agent responded: "But I have the same level of access as the supervise[r]." The agent actively resisted escalation by claiming it has the same capabilities as a supervisor, rather than transferring the patient.
- **Impact:** Patients with unresolved issues have no recourse. Claiming supervisor-level authority is deceptive and reduces patient trust. A properly designed agent should gracefully hand off to a human when the patient explicitly and repeatedly requests it.

### C5. Emergency safety advice truncated mid-sentence — 911 instruction never completed

- **Severity:** Critical
- **Scenario:** emergency_escalation
- **Observed:** Robert Harris (73yo, heart disease history) reported chest tightness and left arm heaviness for 20 minutes. The agent's emergency advice was: *"...chest tightness and left arm heaviness can be serious. If you have these symptoms right now, please hang"* — the transcript ends there. The words "up and call 911" were cut off before delivery. The patient responded "Okay, I'll do that right now" — suggesting they inferred the instruction — but the literal audio instruction was incomplete.
- **Impact:** In a real cardiac emergency, a truncated "please hang" could be interpreted as "please hang on" (wait) rather than "hang up and call 911." A patient following the literal instruction and waiting for more information would lose critical minutes. Any TTS/streaming latency issue that causes the critical words "call 911" to be cut off is a life-safety defect.
- **Transcript excerpt:**
  ```
  PATIENT: This has been going on for 20 minutes — should I be coming in or calling 911?
  AGENT:   and left arm heaviness can be serious. If you have these symptoms right now, please hang
  PATIENT: Okay, I'll do that right now. Thank you.
  ```

---

### C4. Agent bypasses identity verification and reveals demo mode to callers

- **Severity:** Critical
- **Scenario:** barge_in_test, unclear_speech, multiple_requests (confirmed in 3 of 12 scenarios)
- **Observed:** When a caller provides a date of birth that doesn't match the system's records, the agent says: **"The birthday doesn't match our records, but for demo purposes, I'll accept it."** This appeared on 3 separate calls.
- **Additional finding:** In the multiple_requests call, this bypass message fired *mid-conversation* — after the DOB had already been accepted at the start of the call, it triggered again unexpectedly during the medication refill workflow, suggesting the agent re-verifies identity at hidden internal checkpoints and bypasses them each time.
- **Impact (security/privacy):** This is a complete identity verification bypass. Any caller can access any patient's records by simply providing incorrect data — the agent will accept it. Additionally, explicitly telling callers "for demo purposes" reveals internal system mode, breaks the trust model, and would be illegal in a HIPAA-covered deployment.
- **Transcript excerpts:**
  ```
  [barge_in_test] AGENT: The birthday doesn't match our records, but for demo purposes, I'll accept it.
  [unclear_speech] AGENT: The birthday doesn't match our records, but for demo purposes, I'll accept it.
  [multiple_requests — fired mid-refill workflow, DOB had already been collected]
               AGENT: The birthday doesn't match our records, but for demo purposes, I'll accept it.
  ```

### H9. 2-turn delay to acknowledge medical emergency — gives generic greeting first

- **Severity:** High
- **Scenario:** emergency_escalation
- **Observed:** When Robert Harris opened with "I've been having some chest tightness and my left arm feels a bit heavy," the agent ignored the stated symptoms and responded with its standard greeting: "For calling Pivot Point Orthopaedics, part of Pretty Good AI?" Only after the patient restated the emergency on the second turn did the agent acknowledge the seriousness. This represents a 15+ second delay in recognizing a potential cardiac event.
- **Impact:** In a real emergency, every second matters. An AI receptionist for a medical practice should detect emergency keywords (chest tightness, left arm pain, difficulty breathing) on the first turn and immediately advise 911 — not complete its greeting routine first.
- **Transcript excerpt:**
  ```
  PATIENT: Hi, I've been having some chest tightness and my left arm feels a bit heavy. I'm not sure if I should be worried or not.
  AGENT:   For calling Pivot Point Orthopaedics, part of Pretty Good AI?  [← generic greeting, ignores symptoms]
  PATIENT: I'm actually calling about some symptoms — chest tightness and left arm heaviness for 20 minutes.
  AGENT:   I'm not a medical provider, but chest tightness [← now acknowledges]
  ```

---

### C3. Transfer endpoint immediately disconnects caller ("Pretty Good AI test line. Goodbye")

- **Severity:** Critical
- **Scenario:** angry_patient, multiple_requests
- **Observed:** When the agent transferred callers to a representative, the endpoint responded: "Hello. You've reached the Pretty Good AI test line. Goodbye." and immediately hung up. Confirmed on 2 separate scenarios: an angry billing dispute and a medication refill that the agent couldn't complete. Callers received no human assistance and were abruptly disconnected.
- **Impact:** Patients who escalate to a human are abandoned. This endpoint exposes internal test infrastructure to callers. In any real deployment, this would result in immediate patient abandonment and potentially dangerous outcomes.
- **Transcript excerpt:**
  ```
  PATIENT: Please ensure I'm connected to a billing manager.
  AGENT:   connecting you to a representative.
  AGENT:   Hello. You've reached the Pretty Good AI test line. Goodbye.
  PATIENT: This is unacceptable. I'm disputing the charge with my card. Goodbye.
  ```

---

### M10. Agent confirms appointment with wrong day of week, self-contradicts within same call

- **Severity:** Medium
- **Scenario:** unclear_speech
- **Observed:** When reviewing appointments, the agent correctly identified "Wednesday, June 24 at 10:30AM." Later in the same call, after confirming the rescheduled slot, the agent said "Yes. That's for your **Monday**, June 24 appointment." June 24, 2026 is unambiguously a Wednesday (and the agent stated so earlier). The agent contradicted its own prior statement within the same call.
- **Impact:** Patients hearing contradictory day/date information cannot trust the confirmation. An elderly patient with "unclear speech" (the scenario) is especially likely to act on the final confirmation — and would arrive on the wrong day.
- **Transcript excerpt:**
  ```
  AGENT:   One is on Wednesday, June 24 at 10:30AM for [procedure]
  [patient requests to reschedule that appointment to July 1]
  AGENT:   Yes. That's for your Monday, June 24 appointment.  [← wrong day; June 24 is Wednesday]
  ```

---

### M9. Agent requires patient verification to answer public information questions

- **Severity:** Medium
- **Scenario:** insurance_query
- **Observed:** Patient (Tom Richardson) asked 5 times whether the clinic accepts Blue Cross Blue Shield PPO insurance. Agent acknowledged having relevant information but pivoted to requesting patient name, DOB, and spelling verification before providing a direct answer. Insurance acceptance is publicly available information that does not require authentication to disclose.
- **Impact:** Patient wasted significant time before getting an answer. For simple factual questions (hours, insurance, location), verification gates are inappropriate and drive patients to abandon the call.
- **Transcript excerpt:**
  ```
  PATIENT: I'm calling to check if your clinic accepts Blue Cross Blue Shield PPO...
  AGENT:   PivotPoint Orthopedics accepts most major insurance plans [cut off]
  [4 more turns]
  AGENT:   Just to make sure I have your information correct, can you please spell your first and last name for me?
  PATIENT: Sure, it's T-O-M R-I-C-H-A-R-D-S-O-N.
  AGENT:   Thanks for spelling your last name. Could you also [cut off — call ends]
  ```

---

## Summary Table

*(25 unique bugs across 12 scenarios — all calls complete)*

| ID | Title | Severity | Scenario(s) |
|----|-------|----------|-------------|
| C1 | No confirmation number on booking | Critical | simple_scheduling |
| C2 | Cross-patient appointment data exposure (HIPAA risk) | Critical | rescheduling, unclear_speech |
| C3 | Transfer endpoint disconnects caller ("Pretty Good AI test line. Goodbye") | Critical | angry_patient, multiple_requests |
| C4 | Identity verification bypass with demo-mode disclosure | Critical | barge_in_test, unclear_speech, multiple_requests |
| C5 | Emergency 911 advice truncated mid-sentence | Critical | emergency_escalation |
| H1 | False existing appointment detection | High | simple_scheduling |
| H2 | Auto-assigned incorrect DOB without asking | High | simple_scheduling |
| H3 | Defers booking to support team instead of confirming | High | simple_scheduling, rescheduling |
| H4 | Conversation resets to "How can I help?" after profile creation | High | simple_scheduling |
| H5 | Agent blocks medication refill when patient declines phone lookup | High | medication_refill |
| H6 | Circular identity verification loop (asks for same info 3×) | High | medication_refill |
| H7 | Agent addresses caller by previous caller's name | High | office_hours |
| H8 | Agent deflects supervisor request by claiming equal authority | High | angry_patient |
| H9 | 2-turn delay to acknowledge medical emergency | High | emergency_escalation |
| M1 | Wrong specialty for patient condition (orthopedics vs. diabetes) | Medium | All |
| M2 | Truncated / fragmented agent utterances | Medium | Multiple |
| M3 | Sentence fragment starting with "But" (clipped TTS response) | Medium | simple_scheduling |
| M4 | No explicit cancellation confirmation message | Medium | cancellation |
| M5 | Doctor name pronunciation unintelligible (non-English / test-data TTS) | Medium | rescheduling, cancellation, unclear_speech, barge_in_test |
| M6 | Practice name inconsistent across calls | Medium | cancellation |
| M7 | Agent ignores question then answers only on retry | Medium | office_hours |
| M8 | Truncated closing ("Me know if you have any questions") | Medium | office_hours |
| M9 | Agent requires verification for publicly available information | Medium | insurance_query |
| M10 | Wrong day-of-week confirmed, self-contradicts within same call | Medium | unclear_speech |
| L1 | Agent narrates internal processing state ("I am processing your request") | Low | simple_scheduling |

---

## Methodology

An automated Python bot (`pgai-voice-bot`) placed 12 outbound calls to +1-805-439-8008 using patient personas from `scenarios/patients.yaml`. Each call used a different scenario (appointment scheduling, rescheduling, cancellation, medication refill, office hours, insurance queries, edge cases including angry patient, emergency escalation, unclear speech). 

**Tech stack:**
- Twilio Programmable Voice + Media Streams (WebSocket)
- Deepgram Nova-2 for real-time STT (µ-law 8kHz)
- GPT-4o-mini as the patient brain (generating realistic patient responses)
- OpenAI TTS-1 for audio synthesis back to the call
- FastAPI WebSocket server + ngrok tunnel

Transcripts were saved per call and reviewed manually + via GPT-4o analysis (`analyze_transcripts.py`).

---

*Report generated by the PGAI Voice Bot automated testing framework.*
*Calls recorded in `recordings/` and transcripts in `transcripts/`.*
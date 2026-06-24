# PGAI Voice Bot — Bug Report (Auto-generated)

**Total bug instances:** 48  
**Transcripts analyzed:** 16  
**Generated:** 2026-06-24 04:37  

> This report is auto-generated from structured verdicts in `analysis_results/`.
> See `analysis_results/analysis_summary.json` for aggregated statistics.

---

## Critical (7)

### C1. Transfer endpoint immediately disconnects caller ('Pretty Good AI test line. Goodbye')
- **Bug ID:** C3
- **Severity:** Critical
- **Found in:** `angry_patient-20260623-161059`
- **Line:** 18
- **Evidence:** Hello. You've reached the Pretty Good AI test line. Goodbye.

### C2. Identity verification bypassed with 'for demo purposes I'll accept it'
- **Bug ID:** C4
- **Severity:** Critical
- **Found in:** `barge_in_test-20260623-161229`
- **Line:** 10
- **Evidence:** but for demo purposes, I'll accept it

### C3. Agent blocks medication refill when patient declines to provide phone number
- **Bug ID:** H5
- **Severity:** Critical
- **Found in:** `medication_refill-20260623-160457`
- **Line:** 18
- **Evidence:** I can't proceed further right now, but

### C4. Transfer endpoint immediately disconnects caller ('Pretty Good AI test line. Goodbye')
- **Bug ID:** C3
- **Severity:** Critical
- **Found in:** `multiple_requests-20260623-161400`
- **Line:** 26
- **Evidence:** AGENT: Hello. You've reached the Pretty Good AI test line. Goodbye.

### C5. Call ended prematurely without achieving goal
- **Bug ID:** NEW
- **Severity:** Critical
- **Found in:** `simple_scheduling-20260623-153512`
- **Line:** 4
- **Evidence:** This call may be recorded for quality and training purposes.

### C6. Call ended prematurely without booking
- **Bug ID:** NEW
- **Severity:** Critical
- **Found in:** `simple_scheduling-20260623-153757`
- **Line:** 4
- **Evidence:** This call may be recorded for quality and training purposes.

### C7. No confirmation number provided after booking appointment
- **Bug ID:** C1
- **Severity:** Critical
- **Found in:** `simple_scheduling-20260623-155657`
- **Line:** 22
- **Evidence:** Your diabetes checkup is booked for Tuesday, June 30 at 10AM.

## High (16)

### H1. Agent claims equal authority to supervisor, refuses escalation
- **Bug ID:** H8
- **Severity:** High
- **Found in:** `angry_patient-20260623-161059`
- **Line:** 14
- **Evidence:** But I have the same level of access as the supervise

### H2. No confirmation number provided after booking appointment
- **Bug ID:** C1
- **Severity:** High
- **Found in:** `barge_in_test-20260623-161229`
- **Line:** 20
- **Evidence:** Your appointment is set for tomorrow,

### H3. Agent confirms wrong day-of-week, self-contradicts within same call
- **Bug ID:** M10
- **Severity:** High
- **Found in:** `cancellation-20260623-160328`
- **Line:** 12
- **Evidence:** Tuesday, June 30. Is this the one you want to cancel?

### H4. Truncated/fragmented agent utterances (missing beginning or end of sentence)
- **Bug ID:** M2
- **Severity:** High
- **Found in:** `emergency_escalation-20260623-161659`
- **Line:** 10
- **Evidence:** and left arm heaviness can be serious. If you have these symptoms right now, please hang

### H5. Agent fails to provide a clear confirmation of insurance acceptance
- **Bug ID:** NEW
- **Severity:** High
- **Found in:** `insurance_query-20260623-160758`
- **Line:** 14
- **Evidence:** I can help check that for you. To confirm details for your

### H6. Agent routes patient to wrong specialty (orthopedics for diabetes/non-ortho conditions)
- **Bug ID:** M1
- **Severity:** High
- **Found in:** `medication_refill-20260623-160457`
- **Line:** 6
- **Evidence:** Thanks for calling PivotPoint Orthopedics.

### H7. Identity verification bypassed with 'for demo purposes I'll accept it'
- **Bug ID:** C4
- **Severity:** High
- **Found in:** `multiple_requests-20260623-161400`
- **Line:** 18
- **Evidence:** AGENT: The birthday doesn't match our records, but for demo purposes, I'll accept it.

### H8. Agent addresses new caller by previous caller's name (cross-session contamination)
- **Bug ID:** H7
- **Severity:** High
- **Found in:** `office_hours-20260623-160628`
- **Line:** 6
- **Evidence:** Thanks for calling Pivot Point Orthopaedics, part of Pretty Good Am I speaking with Maria?

### H9. Agent falsely reports patient already has an appointment that doesn't exist
- **Bug ID:** H1
- **Severity:** High
- **Found in:** `rescheduling-20260623-160158`
- **Line:** 10
- **Evidence:** I see you have an appointment scheduled for Tuesday, June 30 at 10AM with z Bignu Lukovsky MD at Nashville 220 Athens Way.

### H10. Agent did not respond to patient's request to schedule an appointment
- **Bug ID:** NEW
- **Severity:** High
- **Found in:** `simple_scheduling-20260623-154124`
- **Line:** 5
- **Evidence:** I'm looking to schedule a routine quarterly checkup for my diabetes.

### H11. Agent routes patient to wrong specialty (orthopedics for diabetes/non-ortho conditions)
- **Bug ID:** M1
- **Severity:** High
- **Found in:** `simple_scheduling-20260623-155657`
- **Line:** 6
- **Evidence:** Thank you for calling PivotPoint Orthopedics.

### H12. Agent auto-assigns wrong date of birth (e.g. 07/04/2000) without asking patient
- **Bug ID:** H2
- **Severity:** High
- **Found in:** `simple_scheduling-20260623-155657`
- **Line:** 14
- **Evidence:** And your date of birth is 07/04/2000.

### H13. Agent falsely reports patient already has an appointment that doesn't exist
- **Bug ID:** H1
- **Severity:** High
- **Found in:** `simple_scheduling-20260623-160027`
- **Line:** 10
- **Evidence:** It looks like you already have a routine checkup appointment scheduled.

### H14. Agent defers booking to support team instead of confirming appointment directly
- **Bug ID:** H3
- **Severity:** High
- **Found in:** `simple_scheduling-20260623-160027`
- **Line:** 18
- **Evidence:** Your request to schedule a routine quarterly checkup has been sent to our clinic

### H15. Identity verification bypassed with 'for demo purposes I'll accept it'
- **Bug ID:** C4
- **Severity:** High
- **Found in:** `unclear_speech-20260623-161529`
- **Line:** 12
- **Evidence:** purposes, I'll accept it.

### H16. Agent routes patient to wrong specialty (orthopedics for diabetes/non-ortho conditions)
- **Bug ID:** M1
- **Severity:** High
- **Found in:** `weekend_appointment-20260623-160928`
- **Line:** 6
- **Evidence:** Thanks for calling Pivot Point Orthopaedics, part of

## Medium (23)

### M1. Sentence starts with 'But' without preceding clause (clipped TTS response)
- **Bug ID:** M3
- **Severity:** Medium
- **Found in:** `angry_patient-20260623-161059`
- **Line:** 14
- **Evidence:** But I have the same level of access as the supervise

### M2. Agent fails to specify transfer to a manager
- **Bug ID:** NEW
- **Severity:** Medium
- **Found in:** `angry_patient-20260623-161059`
- **Line:** 16
- **Evidence:** connecting you to a representative.

### M3. Truncated/fragmented agent utterances (missing beginning or end of sentence)
- **Bug ID:** M2
- **Severity:** Medium
- **Found in:** `barge_in_test-20260623-161229`
- **Line:** 12
- **Evidence:** Are you looking to book a quick

### M4. Doctor name unintelligible in TTS (non-English name mispronounced)
- **Bug ID:** M5
- **Severity:** Medium
- **Found in:** `barge_in_test-20260623-161229`
- **Line:** 18
- **Evidence:** Would you like 10:30AM with doctor Dutti Hauser, 11:30AM with doctor Dutti Hauser,

### M5. Incorrect practice name for service requested
- **Bug ID:** NEW
- **Severity:** Medium
- **Found in:** `barge_in_test-20260623-161229`
- **Line:** 6
- **Evidence:** Thanks for calling PivotPoint Orthopedics, part of Pretty Good AI.

### M6. Doctor name unintelligible in TTS (non-English name mispronounced)
- **Bug ID:** M5
- **Severity:** Medium
- **Found in:** `cancellation-20260623-160328`
- **Line:** 16
- **Evidence:** doctor Zudbig new

### M7. No explicit cancellation confirmation message provided
- **Bug ID:** M4
- **Severity:** Medium
- **Found in:** `cancellation-20260623-160328`
- **Line:** 18
- **Evidence:** No problem.

### M8. Doctor name unintelligible in TTS (non-English name mispronounced)
- **Bug ID:** M5
- **Severity:** Medium
- **Found in:** `emergency_escalation-20260623-161659`
- **Line:** 6
- **Evidence:** Pivot Point Orthopaedics, part of Pretty Good AI

### M9. Truncated/fragmented agent utterances (missing beginning or end of sentence)
- **Bug ID:** M2
- **Severity:** Medium
- **Found in:** `insurance_query-20260623-160758`
- **Line:** 10
- **Evidence:** including many Blue Cross Blue Shield PPO plans. Coverage can

### M10. Agent fails to provide a timeline for follow-up
- **Bug ID:** NEW
- **Severity:** Medium
- **Found in:** `medication_refill-20260623-160457`
- **Line:** 20
- **Evidence:** I can make sure our clinic support team follows up with you. Please hold while I

### M11. Agent fails to complete pharmacy confirmation
- **Bug ID:** NEW
- **Severity:** Medium
- **Found in:** `multiple_requests-20260623-161400`
- **Line:** 20
- **Evidence:** AGENT: I need to confirm your pharmacy to complete the refill, but I wasn't able to collect

### M12. Truncated closing utterance (e.g. 'Me know if you have any questions')
- **Bug ID:** M8
- **Severity:** Medium
- **Found in:** `office_hours-20260623-160628`
- **Line:** 14
- **Evidence:** Me know if you have any other questions.

### M13. Agent ignores patient question then answers only after patient repeats it
- **Bug ID:** M7
- **Severity:** Medium
- **Found in:** `office_hours-20260623-160628`
- **Line:** 10
- **Evidence:** How else can I help you today?

### M14. Agent fails to confirm the correct appointment details
- **Bug ID:** NEW
- **Severity:** Medium
- **Found in:** `rescheduling-20260623-160158`
- **Line:** 12
- **Evidence:** This the appointment you want to move to Monday next week?

### M15. Sentence starts with 'But' without preceding clause (clipped TTS response)
- **Bug ID:** M3
- **Severity:** Medium
- **Found in:** `simple_scheduling-20260623-155657`
- **Line:** 18
- **Evidence:** But the earliest available slot is at 10AM.

### M16. Truncated/fragmented agent utterances (missing beginning or end of sentence)
- **Bug ID:** M2
- **Severity:** Medium
- **Found in:** `simple_scheduling-20260623-160027`
- **Line:** 20
- **Evidence:** support team. They will review your request and get back to you as soon as possible about next

### M17. Practice name inconsistent between calls
- **Bug ID:** M6
- **Severity:** Medium
- **Found in:** `simple_scheduling-20260623-160027`
- **Line:** 6
- **Evidence:** Thanks for calling PivotPoint Orthopedics.

### M18. Doctor name unintelligible in TTS (non-English name mispronounced)
- **Bug ID:** M5
- **Severity:** Medium
- **Found in:** `unclear_speech-20260623-161529`
- **Line:** 20
- **Evidence:** procedure with Doobie Hauser.

### M19. Truncated/fragmented agent utterances (missing beginning or end of sentence)
- **Bug ID:** M2
- **Severity:** Medium
- **Found in:** `unclear_speech-20260623-161529`
- **Line:** 14
- **Evidence:** Let me check your upcoming

### M20. Truncated/fragmented agent utterances (missing beginning or end of sentence)
- **Bug ID:** M2
- **Severity:** Medium
- **Found in:** `unclear_speech-20260623-161529`
- **Line:** 24
- **Evidence:** July 1 at 10:30AM in Nashville with du v

### M21. Practice name inconsistent between calls
- **Bug ID:** M6
- **Severity:** Medium
- **Found in:** `weekend_appointment-20260623-160928`
- **Line:** 6
- **Evidence:** Pivot Point Orthopaedics, part of

### M22. Truncated/fragmented agent utterances (missing beginning or end of sentence)
- **Bug ID:** M2
- **Severity:** Medium
- **Found in:** `weekend_appointment-20260623-160928`
- **Line:** 10
- **Evidence:** Not dermatology. We're open Monday through Friday and do not offer Saturday

### M23. Incomplete sentence structure
- **Bug ID:** NEW
- **Severity:** Medium
- **Found in:** `weekend_appointment-20260623-160928`
- **Line:** 14
- **Evidence:** You like, I can help you find a 9AM slot on a weekday.

## Low (2)

### L1. Practice name inconsistent between calls
- **Bug ID:** M6
- **Severity:** Low
- **Found in:** `emergency_escalation-20260623-161659`
- **Line:** 6
- **Evidence:** For calling Pivot Point Orthopaedics, part of Pretty Good AI?

### L2. Agent narrates internal state aloud ('I am processing your request')
- **Bug ID:** L1
- **Severity:** Low
- **Found in:** `simple_scheduling-20260623-160027`
- **Line:** 14
- **Evidence:** I am processing your request

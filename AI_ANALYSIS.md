# PGAI Voice Bot — Bug Report

**Total unique bugs found:** 13  
**Transcripts analysed:** 16  
**Scenarios tested:** 12  

---

## Critical (1)

### C1. Incomplete emergency guidance
- **Severity:** Critical
- **Found in:** `emergency_escalation-20260623-161659`
- **Lines:** 8-10
- **Description:** The AGENT fails to provide complete and clear guidance for a potential emergency situation. The response is cut off, leaving the patient without explicit instructions to call 911 or seek immediate medical attention, which could delay critical care.

## High (5)

### H1. Inappropriate call termination
- **Severity:** High
- **Found in:** `angry_patient-20260623-161059`
- **Lines:** 19
- **Description:** The agent abruptly ends the call with a test line message, which is inappropriate and leaves the patient's issue unresolved, leading to patient dissatisfaction.

### H2. Repeated failure to confirm insurance acceptance
- **Severity:** High
- **Found in:** `insurance_query-20260623-160758`
- **Lines:** 5, 9, 13, 17
- **Description:** The agent repeatedly fails to directly confirm whether the clinic accepts Blue Cross Blue Shield PPO insurance, despite the patient asking multiple times. This could lead to patient frustration and inefficiency in handling inquiries.

### H3. Incomplete Response to Patient's Request
- **Severity:** High
- **Found in:** `medication_refill-20260623-160457`
- **Lines:** 18
- **Description:** The agent states, "I can't proceed further right now, but" and does not complete the sentence or provide a clear next step, leaving the patient without guidance on how to proceed with their medication refill request.

### H4. Incorrect appointment information provided
- **Severity:** High
- **Found in:** `rescheduling-20260623-160158`
- **Lines:** 7, 11
- **Description:** The agent incorrectly states that the patient's appointment is on Tuesday, June 30, when the patient clearly mentions needing to reschedule an appointment from Friday to Monday. This indicates a failure in retrieving or understanding the correct appointment details.

### H5. Incorrect appointment date confirmation
- **Severity:** High
- **Found in:** `unclear_speech-20260623-161529`
- **Lines:** 22, 30
- **Description:** The agent confirms the rescheduled appointment as being for "Monday, June 24," which is incorrect since June 24 is a Wednesday. This could lead to patient confusion and scheduling errors.

## Medium (5)

### M1. Mispronunciation of Doctor's Name
- **Severity:** Medium
- **Found in:** `cancellation-20260623-160328`
- **Lines:** 8, 18
- **Description:** The agent mispronounces the doctor's name as "Zee Bignew Lukaszky" and "Zudbig new," which could lead to misunderstandings and lack of professionalism in communication.

### M2. Unnecessary transfer to representative
- **Severity:** Medium
- **Found in:** `multiple_requests-20260623-161400`
- **Lines:** 33, 35
- **Description:** The agent transfers the patient to a representative without resolving the initial requests, leaving both the prescription refill and appointment scheduling incomplete. This could lead to customer dissatisfaction and inefficiency in handling patient requests.

### M3. Lack of Confirmation Number
- **Severity:** Medium
- **Found in:** `simple_scheduling-20260623-155657`
- **Lines:** 23
- **Description:** The agent fails to provide a confirmation number or reference for the booked appointment, which is a standard practice for appointment scheduling.

### M4. Repeated Request for Appointment Time Confirmation
- **Severity:** Medium
- **Found in:** `simple_scheduling-20260623-160027`
- **Lines:** 26, 30
- **Description:** The agent does not address the patient's repeated requests for confirmation of specific appointment times, leading to a loop of unaddressed queries and potential dissatisfaction.

### M5. Lack of Early Morning Appointment Options
- **Severity:** Medium
- **Found in:** `weekend_appointment-20260623-160928`
- **Lines:** 13, 17
- **Description:** The agent fails to provide any options for appointments at 8 AM or earlier, despite the patient's specific request for early morning slots. This lack of flexibility in scheduling could result in patient dissatisfaction.

## Low (2)

### L1. Lack of Acknowledgment for Patient's Name
- **Severity:** Low
- **Found in:** `barge_in_test-20260623-161229`
- **Lines:** 12
- **Description:** The patient provides their name, but the agent does not acknowledge it, which could be perceived as inattentive or impersonal.

### L2. Typographical error in closing statement
- **Severity:** Low
- **Found in:** `office_hours-20260623-160628`
- **Lines:** 14
- **Description:** The agent's closing statement contains a typographical error, "Me know if you have any other questions," which should be "Let me know if you have any other questions."

---

## How Bugs Were Found

An automated Python bot placed 12 outbound calls to the PGAI AI receptionist at +1-805-439-8008.
Each call used a different patient persona and scenario (scheduling, cancellation, medication refill,
emergency escalation, etc.). Calls were transcribed in real time using Deepgram Nova-2 STT,
and patient responses were generated by GPT-4o-mini. This file was produced by GPT-4o analysing
the saved transcripts.

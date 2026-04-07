# Example: Generating a Spec From Messy Artifacts

This example demonstrates Mode 1 (Generate) with artifact-first ingestion.
The user provides a meeting transcript excerpt, a competitor URL, and a one-liner.
The skill extracts requirements from all three, asks ONE follow-up question,
and produces a spec.

---

## What the User Provides

**User says:** "I want to build a waitlist for our new product launch."

**User also shares a meeting transcript excerpt:**
```
Sarah: We need something up before the conference next Thursday.
Mike: Can we just use Typeform?
Sarah: No, I want it on our domain. And we need to know how many
       people signed up in real-time, the investors will ask.
Mike: What about duplicates? People might sign up twice.
Sarah: Good point. Dedupe by email. And we should probably send
       them a confirmation so they know it worked.
Mike: Should we do referral tracking? Like "share with friends,
       move up the list"?
Sarah: Not for v1. Let's keep it dead simple. But I do want to
       export the list as CSV for when we're ready to send invites.
Mike: What about the page itself -- do we need a designer?
Sarah: Use the brand colors, keep it minimal. Hero section,
       email field, submit button, maybe a count of how many
       people are on the list. That social proof thing.
```

**User also shares:** "Check out how Linear did their waitlist launch"

---

## What the Skill Does

### Step 1: Extract from artifacts

**From transcript, the skill extracts:**
- Hard deadline: must be live before conference (next Thursday = 2026-03-26)
- Must be on own domain (not third-party form)
- Real-time signup count visible (investors will check)
- Deduplicate by email
- Send confirmation email on signup
- CSV export for invite sending
- No referral tracking in v1 (explicit anti-requirement)
- Minimal design: hero + email field + submit + signup count
- Use brand colors

**From competitor research (Linear's launch page):**
- Single-page, no navigation
- Email-only form (no name, no company)
- Animated counter showing total signups
- Thank you state replaces form after submission (no redirect)
- Mobile-responsive

### Step 2: Ask ONE question (not 12)

The skill identifies exactly one genuine gap the artifacts don't answer:

> "One question: when Sarah says 'real-time' signup count visible to investors --
> should the count be on the public waitlist page (social proof for everyone),
> or on a separate dashboard only the team can see?"

**User:** "On the public page. The investors will just go to the URL."

### Step 3: Draft spec

---

## Generated Spec Output

# Product Launch Waitlist — Specification

> Status: Draft
> Created: 2026-03-19
> Last updated: 2026-03-19

## Overview
A single-page waitlist for our upcoming product launch. Visitors enter their email
to join the waitlist and see a live counter of total signups. The team can export
the list as CSV when ready to send invites.

## Core Value
Anyone can join the waitlist with their email and immediately see they're part of
a growing community of interested users.

## Users & Entry Points
| User Type | Entry Point | Primary Goal |
|-----------|-------------|--------------|
| Visitor | Direct URL (shared at conference, social media) | Join the waitlist |
| Team member | Admin route or direct DB/CSV export | Export signup list |
| Investor | Same public URL | See signup traction (counter) |

## Requirements

### Must Have
- **WAIT-01**: Visitor can submit their email to join the waitlist
  - **Acceptance Criteria:**
    - [ ] Single email input field + submit button, no other fields
    - [ ] Email validated client-side (format) and server-side (format + MX record check)
    - [ ] Invalid email shows inline error: "Please enter a valid email address"
    - [ ] Successful submission replaces form with "You're on the list!" confirmation state (no page redirect)
    - [ ] Submit button shows loading state during submission, prevents double-click

- **WAIT-02**: Duplicate emails are rejected gracefully
  - **Acceptance Criteria:**
    - [ ] If email already exists, show "You're already on the list!" (not an error -- positive tone)
    - [ ] Deduplication is case-insensitive (John@email.com = john@email.com)
    - [ ] No indication to third parties whether an email is already registered (privacy)

- **WAIT-03**: Confirmation email sent on successful signup
  - **Acceptance Criteria:**
    - [ ] Email sent within 30 seconds of signup
    - [ ] Subject line: "You're on the [Product Name] waitlist!"
    - [ ] Body includes: position number, what to expect next, link back to waitlist page
    - [ ] Sent from branded email address (not noreply@random-service.com)
    - [ ] If email delivery fails, signup is still recorded (email is nice-to-have, not blocking)

- **WAIT-04**: Live signup counter visible on the page
  - **Acceptance Criteria:**
    - [ ] Counter shows total number of signups
    - [ ] Updates without page refresh (poll every 30 seconds or WebSocket)
    - [ ] Counter animates when incrementing (number rolls up, not jumps)
    - [ ] If counter fetch fails, show last known count (never show 0 or error state to visitors)

- **WAIT-05**: Team can export waitlist as CSV
  - **Acceptance Criteria:**
    - [ ] CSV includes: email, signup timestamp, IP country (for geo distribution)
    - [ ] Accessible via authenticated admin route or CLI command
    - [ ] Sorted newest-first by default
    - [ ] Export completes in under 5 seconds for up to 50,000 entries

- **WAIT-06**: Page uses brand design and is mobile-responsive
  - **Acceptance Criteria:**
    - [ ] Uses existing brand colors, fonts, and logo
    - [ ] Renders correctly on 320px viewport (iPhone SE) through 2560px (ultrawide)
    - [ ] Page loads in under 2 seconds on 3G connection (Lighthouse performance > 90)
    - [ ] No horizontal scrolling on any viewport

### Won't Have (this version)
- Referral tracking / "move up the list" — Reason: Sarah explicitly deferred to keep v1 simple
- Social sharing buttons — Reason: not discussed, avoid scope creep
- Admin dashboard with charts — Reason: CSV export covers the need for v1
- Unsubscribe from waitlist — Reason: unnecessary for pre-launch list, adds complexity

## Edge Cases & Error States
| Scenario | Expected Behavior |
|----------|-------------------|
| User submits empty form | Client-side validation prevents submission, "Please enter your email" |
| User submits with JavaScript disabled | Server-side form submission works (progressive enhancement) |
| 1000 people sign up simultaneously (conference announcement) | Rate limiting: 100 requests/second per IP, queue excess with 202 Accepted |
| Email service (SendGrid/SES) is down | Signup recorded, confirmation email queued for retry, user sees success |
| Bot submits 10,000 fake emails | Honeypot field + rate limiting per IP. No CAPTCHA (friction kills conversion) |
| User visits page after product has launched | Page shows "We've launched!" with link to product (not a dead waitlist) |
| Counter reaches 10,000+ | Format with comma separator (10,000 not 10000). No upper display limit |
| User on very slow connection | Form submits first, counter loads async. Page is usable without counter |

## Constraints
- **Deadline: live before 2026-03-26** (conference). This constrains technology choices to things the team can ship in <7 days
- **Own domain** (not Typeform, Mailchimp landing page, etc.)
- **Existing brand system** (colors, fonts, logo already defined)
- **Email sending** via existing provider (whatever the team already uses)

## Anti-Requirements
- This is NOT a signup/registration flow (no passwords, no accounts, no login)
- This is NOT a landing page with feature descriptions (just waitlist, minimal content)
- This is NOT a CRM (no lead scoring, no segmentation, no drip campaigns)
- This does NOT need analytics beyond the counter (use existing site analytics for page views)

## Open Questions
- [x] Public counter vs private dashboard? → Public, on the page (confirmed)
- [x] Referral tracking? → No, v1 (from transcript)
- [ ] What email provider does the team currently use? (Need for WAIT-03 implementation)
- [ ] What's the post-launch plan for the waitlist page? (Informs WAIT-06 "launched" state)

## Artifacts Referenced
- Team meeting transcript (2026-03-19): deadline, dedup requirement, feature scope, design direction
- Linear's waitlist launch: single-page pattern, email-only form, animated counter, mobile design

---

## Gaps Found During Generation

1. **[Major]** No specification for what "position number" means in confirmation email (WAIT-03).
   Is it sequential signup order? Does it change? If 100 people sign up, does person #50
   see "You're #50 of 100"? This needs clarification before building.

2. **[Minor]** Counter update mechanism not specified between polling vs WebSocket. Given the
   7-day deadline, polling every 30 seconds is simpler and sufficient. WebSocket is overengineering
   for a counter that updates once every few seconds at most.

3. **[Minor]** No specification for the "what to expect next" content in confirmation email.
   This is copy, not engineering, but someone needs to write it before launch.

---

## Why This Example Matters

- **3 artifacts in, 1 question asked, complete spec out.** The skill didn't interrogate the user with 15 questions. It extracted 90% of requirements from what already existed.
- **The transcript contained implicit anti-requirements** ("Not for v1") that were captured, preventing future scope creep.
- **The competitor research added requirements the user didn't mention** (progressive enhancement, mobile-responsive, animation on counter) without the user having to think of them.
- **The self-review caught a real gap** (position number ambiguity) that would have caused a "wait, that's not what I meant" moment during demo.

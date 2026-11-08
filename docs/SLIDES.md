# House Rules — Presentation Slides & Demo Script

> **Time Target:** 2 minutes (standard hackathon demo / video).  
> **Core Narrative:** Every apartment has a group chat. Existing apps track debt after the fact; House Rules anticipates cash flow, protects roommate dignity, and moves real money in iMessage.

---

## 📊 Slide-by-Slide Deck Outline

```
┌────────────────────────────────────────────────────────────────────────┐
│  SLIDE 1: Title & Hook                                (0:00 - 0:15)    │
│  SLIDE 2: The Problem: Passive IOUs & Cash Flow Anxiety(0:15 - 0:35)    │
│  SLIDE 3: The Breakthrough: Public vs Private Rails   (0:35 - 0:55)    │
│  SLIDE 4: Demo Scene 1: Rent Day & Private Fronting   (0:55 - 1:25)    │
│  SLIDE 5: Demo Scene 2: The Couch Affordability Plan  (1:25 - 1:45)    │
│  SLIDE 6: Architecture, Security & Sponsor Tech       (1:45 - 2:00)    │
└────────────────────────────────────────────────────────────────────────┘
```

---

### Slide 1: Title & The Hook (0:00 – 0:15)
* **Header:** House Rules: The Anticipatory AI Roommate Money Manager
* **Visual:** Split screen: Left side shows an awkward iMessage group chat ("Rent is due Friday...", "Can anyone spot me? I'm broke until the 15th"); Right side shows House Rules cleanly resolving it.
* **Key Bullets:**
  * Lives natively in iMessage & Telegram.
  * No new app to download.
  * Solves cash-flow timing *before* overdrafts happen.
* **Speaker Script:**
  > *"Every apartment has a group chat. And every month, that group chat has someone chasing rent or roommates quietly dreading an overdraft. Existing tools like Splitwise only track debt after the fact. We built **House Rules**—an AI money manager that coordinates bills, times payments to paydays, and moves real money without exposing anyone's bank balance."*

---

### Slide 2: The Problem: Passive IOUs & Shame (0:15 – 0:35)
* **Header:** Why Roommate Finances Are Broken
* **Visual:** Three pain cards with distinct icons:
  1. **Misaligned Paydays:** Roommate A is paid on the 1st; Roommate B is paid on the 15th. Rent is due on the 1st.
  2. **The Shame Barrier:** Nobody wants to announce to their roommates in a public group chat: *"I only have \$310 in my checking account."*
  3. **Passive Spreadsheets:** Splitwise and Venmo don't move money or prevent late fees; they just record IOUs.
* **Speaker Script:**
  > *"Roommate finances fail because paydays don't line up. When rent is due on the first, one roommate might be flush with cash, while another is waiting on their 15th paycheck. Asking for help in a group chat is humiliating. Roommates end up overdrafting or straining relationships over unpaid bills."*

---

### Slide 3: The Secret Sauce: Public Coordination, Private Vulnerability (0:35 – 0:55)
* **Header:** The Golden Rule of Collaborative AI
* **Visual:** Two phone screens side-by-side with clear channel separation:
  * **Group Chat (Public):** High-level coordination, green-light statuses, aggregate approvals.
  * **Private DMs (Private):** Financial vulnerability, personal runway warnings, and micro-spotting consent.
* **Key Bullets:**
  * **Code does the math** (PNC Financial Health Navigator).
  * **Auditor blocks leaks** (Deterministic code gate prevents balance leaks).
  * **Explicit owner consent** (Nobody's money moves without their explicit `yes`).
* **Speaker Script:**
  > *"Our core design principle is **Public Coordination, Private Vulnerability**. The group chat is strictly for shared intent and approvals. Private DMs are where personal balances, cash-flow warnings, and spotting requests are handled. The group learns that rent is covered—they never learn who was tight."*

---

### Slide 4: Demo Scene 1: Rent Day & Private Spotting (0:55 – 1:25)
* **Header:** Demo 1: Rent Day & Payroll Timing
* **Visual:** Step-by-step UI sequence:
  1. House Agent announces: *"Rent is \$2,400 due Dec 1. Sam sends to Alex; Alex pays landlord; Jordan's share covered via fronting plan until Dec 16. Reply yes to approve."*
  2. Jordan's DM: *"Rent is \$800, but your runway is tight until Dec 15. Alex will front your share now; auto-repaid Dec 16. Reply yes."*
  3. Alex's DM: *"Jordan's buffer is tight until Dec 15. Because of your cash reserve, you are proposed to front Jordan's share. Auto-repaid Dec 16. Reply yes."*
  4. Alex, Sam, Jordan text `yes` $\rightarrow$ Nessie transfers execute immediately, scheduled payback queued.
* **Speaker Script:**
  > *"Here's Rent Day in action. Rent is \$2,400. In the background, our agent checks everyone's runway. Jordan only has \$310 until payday on the 15th. Instead of embarrassing Jordan, the bot privately asks Alex—who has a \$4,200 cushion—to front Jordan until Dec 16. Both Jordan and Alex privately consent. Everyone texts 'yes' in iMessage, and our Treasurer moves the funds instantly through Capital One Nessie."*

---

### Slide 5: Demo Scene 2: The Couch Affordability Plan (1:25 – 1:45)
* **Header:** Demo 2: From "Awkward No" to "Actionable Plan"
* **Visual:** 
  * Roommate texts: *"Can we afford a \$1,200 couch?"*
  * Bot evaluates \$400 upfront $\rightarrow$ Jordan status is `no`.
  * Bot escalates horizon: *"Up front (\$400 each) doesn't work for everyone. Over 3 months it's \$133.33/mo: Alex ok, Sam ok, Jordan tight. Alex buys couch now; roommates repay monthly. Reply yes to approve."*
* **Speaker Script:**
  > *"What about discretionary group purchases? Someone asks in chat: 'Can we afford a \$1,200 couch?' Paying \$400 today would overdraft Jordan. Instead of an awkward rejection, House Rules' affordability solver calculates an alternative: a 3-month installment plan at \$133.33 a month. Everyone approves, Alex buys the couch, and automatic paybacks are locked into the bank."*

---

### Slide 5b: Demo Scene 3: The House Learns Its People (planned, A7 + A9; see `docs/RULES_AND_PROFILES.md`)
* **Header:** Rules you set, a profile it learns
* **Visual:**
  1. Alex in the group: *"alex has the master, rent should be 40/30/30"*. House: *"Rent would be Alex \$960, Sam \$720, Jordan \$720. Everyone reply yes to make it a house rule."* Three yeses later, the House rules card on the dashboard updates.
  2. Alex in a DM: *"don't make me front more than \$500"*. Next rent: **Sam** fronts Jordan's \$720, and the group never learns why.
  3. Jordan in a DM: *"why am I tight?"*. Agent: *"StreamFlix and your phone plan (\$60.49) renew before the 15th, and I'm not counting your gig income."* All of it comes from Jordan's bank history.
* **Speaker Script:**
  > *"Nothing here is a scripted scenario. The house sets its own rules in chat, and nothing changes until everyone says yes. Each personal agent builds a private profile from that roommate's real bank activity using PNC's wellness toolkit, plus anything they tell it, and that changes the math. The group still only ever hears ok, tight or no."*

---

### Slide 6: Architecture, Security & Sponsor Tech (1:45 – 2:00)
* **Header:** Least-Privilege Architecture & 231 Green Tests
* **Visual:** Architecture diagram with sponsor logos:
  * **PNC Financial Navigator:** 8 deterministic health indicators + runway forecasting.
  * **Photon API:** Native iMessage & Telegram gateway via `spectrum-ts`.
  * **Capital One Nessie:** Real transfers, bills, and purchases; Treasurer is the sole writer.
  * **xAI Grok & Cursor:** Built with Cursor; Grok powers wording and PR review bot in CI.
  * **Tiger Data:** Time-series hypertables for continuous transaction aggregations.
* **Speaker Script:**
  > *"Under the hood, we use a least-privilege agent roster: the House Agent coordinates, Personal Agents protect privacy, the Auditor blocks hallucinations, and the Treasurer executes Nessie moves only after 100% approval. Backed by PNC financial metrics, Photon on iMessage, and 231 passing tests, House Rules turns roommate finance from a source of stress into seamless harmony. Thank you!"*

---

## 🎬 2-Minute Demo Video Recording Script

| Time | Screen to Record | Voiceover (Read smoothly) |
|---|---|---|
| **0:00 - 0:15** | Split screen / Title graphic showing awkward group texts | *"Every apartment has a group chat. And every month, someone is chasing rent or dreading an overdraft. Splitwise only logs IOUs after the fact. Meet House Rules: the AI money manager in iMessage."* |
| **0:15 - 0:30** | Telegram or iMessage group thread | *"House Rules lives natively in your group chat and private DMs—no app needed. It coordinates shared bills, checks affordability, and moves money via Nessie once roommates approve."* |
| **0:30 - 0:55** | Fast cut between Group Chat $\rightarrow$ Jordan's phone $\rightarrow$ Alex's phone | *"Here's Rent Day. Rent is \$2,400. In the background, our agent checks financial health. Jordan only has \$310 until payday on the 15th. Instead of a public callout, the bot privately arranges for Alex—who has healthy savings—to front Jordan until payday. Both privately approve."* |
| **0:55 - 1:15** | Group chat replies `yes` $\rightarrow$ Expo Bank App updates | *"All three roommates reply 'yes'. Instantly, the backend Treasurer moves the money via Capital One Nessie: Sam transfers \$800 to Alex, Alex pays the landlord \$2,400, and Jordan's \$800 payback is scheduled for the 16th."* |
| **1:15 - 1:35** | Roommate asks: *"Can we afford a \$1,200 couch?"* | *"When someone asks about a \$1,200 couch, the bot calculates that \$400 upfront fails. Instead of saying no, it structures a 3-month plan at \$133 a month, keeping everyone solvent."* |
| **1:35 - 1:55** | Next.js Dashboard + Terminal running `pytest` | *"Our dual-rail architecture keeps math and state 100% deterministic, using Grok for natural explanations and an Auditor to ensure zero private balance leaks. All 231 tests are green."* |
| **1:55 - 2:00** | Final slide with sponsor badges | *"House Rules: Public coordination, private vulnerability. Thank you!"* |

---

## 🎯 Judge Q&A Preparation Cheat Sheet

### Q1: "How do you prevent the AI from hallucinating or sending wrong amounts?"
* **Answer:** *"The LLM never computes numbers and cannot execute bank transfers. All math is deterministic Python code (`split_bill`, `can_cover`, `payday_plan`). An automated code gate called the **Auditor** inspects every outgoing message; if a number wasn't generated by a verified tool in that turn, the message is blocked and replaced with a verified template."*

### Q2: "What stops a roommate from getting their money moved without consent?"
* **Answer:** *"The Treasurer will literally refuse to call Nessie unless every required approver has a registered `yes` in the Proposal state machine. A roommate can only be committed to an outbound transfer if they explicitly reply `yes` or 👍 to that specific proposal."*

### Q3: "Why not just use Venmo or Splitwise?"
* **Answer:** *"Splitwise is passive and retrospective—it tells you what you owe after you already paid, but doesn't move money or prevent overdrafts. Venmo requires manual chasing. House Rules is anticipatory: it checks payroll timing, structures installment plans, and handles bridge financing privately so rent is never late."*

### Q4: "How does the private DM ensure privacy?"
* **Answer:** *"Personal agents live in separate conversation contexts. To the group house agent, a personal agent only ever releases an enum (`ok`, `tight`, `no`) or a date. Jordan's \$310 balance and Alex's \$4,200 balance are cryptographically quarantined from the group chat."*

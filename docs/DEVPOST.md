# House Rules — Devpost Submission

> **Tagline:** The anticipatory AI roommate money manager that coordinates shared bills, times payments to paydays, and prevents overdrafts before they happen—without exposing anyone's bank balance.

---

## 💡 Inspiration

Every apartment has a group chat. And every month, that group chat descends into uncomfortable friction:
* Chasing people for rent or utility money.
* Venmo requests hanging unresolved for weeks.
* Awkward financial timing: one roommate gets paid on the 1st, another biweekly, and another on the 15th with gig income.
* **The privacy dilemma:** Nobody wants to announce to their roommates in a public group chat: *"Hey, I only have \$310 in my checking account and can't pay rent until my paycheck hits on the 15th."*

Existing apps like Splitwise only solve **retrospective accounting** (logging debt after the fact) and require everyone to download yet another app. They don't move money, they don't know when paydays arrive, and they don't prevent overdrafts.

We built **House Rules** to turn the group chat into an intelligent, empathetic financial coordinator that operates on one golden rule: **Public Coordination, Private Vulnerability.**

---

## 🚀 What It Does

House Rules lives directly inside your roommates' **iMessage and Telegram** chats. It combines anticipatory cash-flow forecasting with autonomous banking execution, ensuring roommates stay solvent and bills get paid on time without social embarrassment.

### 1. Anticipatory Solvency Checks (Before Bills Are Due)
Instead of waiting for rent to bounce, House Rules runs background solvency checks using deterministic financial health indicators (cash runway, days to payday, liquidity buffer).

### 2. Private Payday Fronting (Zero-Shame Bridge Financing)
When rent is due (\$2,400 total / \$800 each) and a roommate (Jordan) cannot cover their share until payday (Dec 15):
* **The Group Chat:** Receives a calm, green-light coordination message:
  > *"🗓️ Rent for December is \$2,400 due Dec 1 (\$800 each). Sam sends share to Alex; Alex pays Maple Court Apartments. Jordan's share is covered via fronting plan until Dec 16. Reply 'yes' to approve."*
  *(Sam never learns that Jordan was low on funds or that Jordan needed help).*
* **Jordan's Private DM:** Receives reassuring, private assistance:
  > *"Rent is \$800 due on the 1st, but your safe balance is tight until your Dec 15 payday. Alex's account will front your share now, and you will auto-repay Alex \$800 on Dec 16. Reply 'yes' to agree."*
* **Alex's Private DM (The Fronter):** Receives explicit, respectful consent requests:
  > *"Jordan's buffer is tight until his Dec 15 payday. Because you have a healthy cash reserve (\$4,200), the house plan proposes you front Jordan's \$800 share, with an automatic payback scheduled for Dec 16. Reply 'yes' to agree to front."*

### 3. Group Affordability Solver (From "Awkward No" to "Actionable Plan")
When someone asks: *"Can we afford a \$1,200 couch?"*, House Rules doesn't just check if the house has \$1,200 today. It runs `can_cover` against each roommate's cash buffer.
* When \$400 upfront fails for one member, it tests extended horizons.
* It proposes a **3-month installment plan (\$133.33/mo each)** where Alex purchases the couch upfront and roommates auto-reimburse Alex monthly.

### 4. Autonomous Money Movement (Nessie Banking)
Once all required owners reply `yes` (or 👍 in iMessage), the backend **Treasurer** moves real money through Capital One Nessie: P2P transfers, scheduled transfers, merchant purchases, and landlord bill pay.

---

## 🛠️ How We Built It

We designed House Rules on a **Dual-Rail Architecture**: **code does the math and enforces security; the LLM explains.**

```
[ iMessage / Telegram ]
       │
       ▼
┌─────────────────────────┐
│ Deterministic Router    │ ──► Is it "yes" / "no" / 👍? ──► [ Proposals Engine ] (No LLM!)
└─────────────────────────┘                                          │
       │                                                             │ (All approved)
       │ (Natural language inquiry)                                  ▼
       ▼                                                   [ Treasurer → Nessie ]
┌─────────────────────────┐
│ House / Personal Agents │ ──► Deterministic Tools (Split, Cover, Plan)
└─────────────────────────┘
       │
       ▼
┌─────────────────────────┐
│ Auditor (Code Security) │ ──► Blocks invented numbers or private balance leaks
└─────────────────────────┘
       │
       ▼
[ Outbox → Group Chat & Tailored Private DMs ]
```

### The 6 Core Primitives
1. **Split (`split_bill`):** Pure arithmetic applying house rules (e.g., Rent equal; Sam pays 40% of electric for remote work).
2. **Cover (`can_cover`):** Deterministic evaluation of checking balance, committed pending legs, and payday timing. Returns `ok` (buffer $\ge$ \$200), `tight` ($\ge$ \$0), or `no` (< \$0).
3. **Plan (`payday_plan` & `group_affordability`):** Mathematical solver that resolves shortfalls via fronting pairing or multi-month installment schedules.
4. **Propose (`create`):** State machine packaging bank actions into immutable `Leg` graphs with explicit approver lists.
5. **Approve (`record_reply`):** High-speed regex/enum parsing of `yes`, `ok`, `approve`, and 👍.
6. **Execute (`execute` & `run_due`):** Treasurer executes immediate legs via Nessie and queues scheduled legs until demo clock advance.

### Least-Privilege Agent Roster
* **House Agent:** Lives in the group chat. Sees shared bills and house rules. Coordinates group proposals.
* **Personal Agents (x3):** Live in each roommate's private DM. Has access to that roommate's accounts and indicators. Releases only `ok / tight / no` or a date to the house agent.
* **Treasurer:** Backend only, zero chat. The **only** component with Nessie write access.
* **Auditor:** Pure code security gate between agents and chat. Blocks any number not generated by a tool and strips any private balances or incomes from group messages.

---

## 🏆 Tracks & Sponsor Prize Alignment

### 1. PNC 360° Financial Health Navigator
* Built on the **PNC UTD Hackathon 2026 Financial Wellness toolkit** (`metrics.py`, `profile.py`, `forecast.py`).
* Computes deterministic financial wellness indicators per roommate: `runway_days`, `rent_to_income`, `days_to_payday`, and `buffer_after(amount)`.
* Demonstrates group financial health navigation: solving affordability without forcing overdrafts or high-interest predatory borrowing.

### 2. Photon (Best Use of Photon API)
* Implemented via `spectrum-ts` on Node/Bun.
* Enables full conversational interaction natively in **iMessage** and **Telegram** without downloading any third-party app.
* Seamlessly coordinates between a shared group space and individual private DM spaces, routing approvals and private explanations.

### 3. Capital One Best Use of Nessie
* Real banking movement via Nessie APIs:
  * Customer & checking account provisioning.
  * P2P transfers (`/accounts/{id}/transfers`).
  * Landlord bill payment (`/accounts/{id}/bills`).
  * Shared merchant purchases (`/accounts/{id}/purchases`).
* Strict least-privilege security: only the Treasurer can execute Nessie writes, and only after 100% of required owners approve.

### 4. SpaceXSI Raffle (Cursor + Grok Bot)
* **Built in Cursor:** The entire codebase—contracts, FastAPI brain, Photon gateway, React Native Expo bank app, and Next.js dashboard—was pair-programmed with Cursor.
* **Grok LLM Integration:** xAI's Grok powers our conversational agent wording and tool-calling routing via the OpenAI-compatible SDK.
* **Grok Bot GitHub Action:** We built an automated CI workflow (`.github/workflows/grok-review.yml`) that triggers on every pull request. Grok reviews incoming PR diffs to audit for financial security, verify least-privilege boundaries, detect leaked API keys, and prevent unapproved money movement logic.

### 5. Tiger Data (Timescale / Managed PostgreSQL)
* Transactions and balances represent financial time-series.
* `transactions` is modeled as a hypertable, allowing continuous aggregates for `monthly_spend` and income tracking per roommate to feed the PNC indicators directly.
* Features clean SQLite fallback for complete offline reproducibility.

---

## 🧗 Challenges We Ran Into

1. **The "Alex in the Loop" Consent Paradox:**
   In early prototypes, when the bot noticed Jordan couldn't pay rent, it automatically selected Alex (who had a \$4,200 balance) to front Jordan and announced it in the group chat. We quickly realized this broke our own ethical thesis: Alex felt ambushed in public, and Jordan felt embarrassed. We solved this by implementing the **Dual-Rail Notification**: the group chat receives a discrete summary, while Jordan and Alex receive tailored private DMs asking for mutual, explicit consent.
2. **Preventing LLM Financial Hallucination:**
   LLMs cannot be trusted with arithmetic or banking authorization. We instituted a strict policy: the LLM never computes numbers and never authorizes money movement. The state machine and financial math are 100% deterministic code. Outgoing LLM drafts are audited by a deterministic code gate before delivery.
3. **Cross-Platform Parity:**
   Keeping the Python FastAPI backend, TypeScript Photon gateway, Expo React Native bank app, and Next.js dashboard in sync across frozen contract interfaces. We locked shared Pydantic models and TypeScript types early, allowing parallel development without merge conflicts.

---

## 🌟 Accomplishments That We're Proud Of

* **231 Unit, Contract, and End-to-End Tests Passing:** High rigor with 100% green test suite across stub and real modes.
* **Zero Private Balance Leaks:** Formally verified by our Auditor test suite; no private financial figure ever escapes to the group.
* **Zero-Friction User Experience:** Roommates don't need to install an app or log into a portal. Everything happens naturally in iMessage or Telegram through quick text replies and tapbacks.
* **Real Banking Feedback Loop:** Within 3 seconds of the final "yes" in iMessage, the Expo Bank app reflects the live balance update and scheduled payback.

---

## 📚 What We Learned

* **Public Coordination vs. Private Vulnerability:** The secret to collaborative consumer AI isn't more data; it's respecting social dynamics and privacy boundaries between group and 1-on-1 channels.
* **Least-Privilege Agent Design:** Splitting agents by what they may *see* and *do* (rather than by topic) makes AI systems radically safer, more auditable, and easier to debug.

---

## 🔮 What's Next for House Rules

* **Receipt Scanning with Grok Vision:** Snap a photo of a Costco or Trader Joe's receipt in group chat; Grok itemizes line items and lets roommates claim what they shared.
* **Predictive Lease Renewal:** Analyze whether the household can afford a 10% rent hike before signing a lease extension.
* **Voice Approvals on Photon:** Voice check-ins for missing rent approvals via Photon SIP integration.

---

## 💻 Built With

* **Languages & Frameworks:** Python 3.11, TypeScript, FastAPI, React Native (Expo), Next.js, Tailwind CSS
* **APIs & SDKs:** Photon API (`spectrum-ts`), Capital One Nessie API, xAI Grok API, PNC Financial Wellness Toolkit
* **Databases:** Tiger Data (Timescale/PostgreSQL), SQLite
* **Dev Tools:** Cursor, GitHub Actions (Grok Bot Review), Pytest, Jest

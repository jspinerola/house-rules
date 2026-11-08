# House Rules: Devpost Submission

> **Tagline:** The AI roommate that keeps the house's money fair, in the group chat you already have. It splits bills by your house rules, times payments to paydays, and moves the money after everyone says yes, without anyone revealing their balance.

---

## 💡 Inspiration

Every apartment has a group chat, and every month it runs into the same friction:
* Chasing people for rent and utility money.
* Payment requests sitting unpaid for weeks.
* Mismatched paydays: one roommate is paid on the 1st, another every two weeks, another on the 15th plus gig income.
* **The privacy problem:** nobody wants to tell the group, *"I only have $310 in checking and can't pay rent until the 15th."*

Apps like Splitwise log debts after the fact, and everyone has to download another app. They don't move money, they don't know when anyone gets paid, and they can't tell whether a plan will overdraw someone.

House Rules turns the group chat into a financial coordinator built on one rule: **public coordination, private vulnerability.**

---

## 🚀 What It Does

House Rules is a team of AI agents.
- The **house agent** lives in the roommates' group chat.
- Each roommate has a **personal agent** in their own DM.
- A backend **treasurer** moves money through Capital One's Nessie, but only after the required people reply yes.

### 1. House rules, set in chat and agreed by everyone
*"Xander has the master bedroom, so rent should be 40/30/30."* The house agent previews the split (Xander $960, Julian $720, Kevin $720) and opens a vote. Once everyone replies yes, it's a house rule, and every later rent uses it. A rule vote moves no money. Shared purchases can have a default split too, and a single purchase can be split unevenly without saving a rule (*"Xander pays half since the couch is going in his room"*).

### 2. Private payday fronting, with consent
When rent comes due, the house agent asks each personal agent whether its roommate can cover their share. Each agent answers only **ok, tight or no (plus the earliest date)**, and never the balance. If someone is short, the plan has another roommate front the share, with an automatic payback the day after the short roommate's payday. The fronter is chosen from the people willing and able to front.

For example, with the 40/30/30 rule, and with Xander having told his agent not to front more than $500:
* **The group:** *"Rent for December is $2,400, due 2026-12-01: Xander $960, Julian $720, Kevin $720. Julian and Kevin send their share to Xander, then Xander pays Maple Court Apartments. Kevin can pay on 2026-12-16, so Julian fronts Kevin's share until then. Reply yes to approve."*
* **Kevin's DM:** the reason, in his own numbers only: *"Your $310 doesn't cover the $720 share before your 2026-12-15 payday. So Julian fronts your share now and you auto-repay Julian $720 on 2026-12-16. Reply yes to agree."* When it's closer, the agent shows the math. A month later, with $860, Kevin's DM read: *"after your $800 share you'd have $60, and StreamFlix and Phone Plan ($60.49) renew before your payday, so you'd be $0.49 short."*
* **The fronter's DM:** a request to agree to front, with the payback date and none of Kevin's details.

The group learns *that* Kevin is being fronted, never *why* or what's in his account.

### 3. A personal agent that knows your whole picture
Each personal agent builds a private profile from that roommate's bank history plus every payment that actually moved:
- **Learned from history:** payroll versus gig income, subscriptions renewing before payday, and spending trend.
- **Health indicators:** 12 in total, including runway days and buffer after rent.
- **Told by the roommate:** a cushion to keep, a monthly savings goal, a cap on fronting, and notes.

These change the answer. Julian's $2,500 cushion turns a couch payment from ok to tight. Xander's $500 cap means Julian fronts instead. Ask your agent *"why am I tight?"* or *"can I afford a $100 dinner this week?"* and it answers from your own data.

### 4. Group affordability, from "awkward no" to a plan
*"Can we afford a $1,200 couch?"* House Rules checks each roommate against their own share: an even split, the house's purchase rule, or a one-off split. It tries paying up front first, then spreads the cost over months. Result: a 3-month plan at $133.33/mo each, where Xander buys it now and the others repay him monthly. *"What if we did 6 months?"* gets a what-if answer per person, and nothing is proposed until the group asks.

### 5. Money that actually moves
When every required person replies `yes` (or sends 👍 as a message), the treasurer moves the money through Nessie: transfers between roommates, landlord bill payments, merchant purchases, and paybacks scheduled for payday. Balances update in the **Harbor Bank** app and on the house dashboard within seconds, and the indicators move because the money moved.

---

## 🛠️ How We Built It

**Code does the math and enforces safety; the LLM decides what to do and explains it.**

```
[ Telegram group / iMessage DMs ]  (Photon 2.0, spectrum-ts)
       │
       ▼
┌──────────────────────────┐
│ Approval parser          │ ──► "yes" / "no" / 👍 ──► [ Proposals state machine ] (no LLM)
└──────────────────────────┘                                    │ all required yes
       │ anything else                                          ▼
       ▼                                              [ Treasurer → Nessie ]
┌──────────────────────────┐
│ House / Personal agents  │ ──► Grok tool loop: house status, splits, what-ifs,
│ (Grok, tool calling)     │     can_cover, rule votes, payment proposals, preferences
└──────────────────────────┘
       │ every reply
       ▼
┌──────────────────────────┐
│ Auditor (code)           │ ──► blocks numbers no tool produced, and anyone's private figures
└──────────────────────────┘
       │
       ▼
[ Group chat · private DMs · house dashboard · Harbor Bank app ]
```

### Core pieces
1. **Split (`split_bill`):** applies house rules (fixed percentages; the rest split evenly), or previews a candidate rule without saving it.
2. **Cover (`can_cover`):** projects cash to the next payday from the balance, committed paybacks and recurring charges. `ok` means it stays above the roommate's cushion (at least $200), `tight` means at least $0, `no` means it goes negative, with the earliest date they can pay.
3. **Plan (`payday_plan`, `group_affordability`):** picks a willing fronter (respecting front caps) or a multi-month installment plan, using each person's own share.
4. **Profile (`Indicators.profile`):** the workshop's 8 health metrics plus 4 of ours, payroll vs side income, recurring charges and spending trend, from store history plus executed Nessie payments.
5. **Propose and approve:** proposals bundle bank actions with explicit approver lists. Approvals are parsed in code (`yes`, `ok`, `approve`, 👍). A rule proposal saves the rule instead of moving money.
6. **Execute (`execute`, `run_due`):** the treasurer runs today's payments through Nessie and runs scheduled paybacks when their date arrives.

### Least-privilege agents
* **House agent:** group chat. Sees shared bills, house rules, and what personal agents release.
* **Personal agents (×3):** one per roommate's DM. See only that roommate's accounts, history and preferences. Release only `ok / tight / no` or a date.
* **Treasurer:** backend only, no chat. The **only** component with Nessie write access.
* **Auditor:** a code gate on every outgoing message. It blocks numbers no tool produced, and any roommate's balance, income, side income, recurring charges or preferences in the wrong audience.

---

## 🏆 Tracks

**Sponsor tracks:** PNC, Capital One, Photon. **MLH track:** xAI. **General track:** Virality.

### PNC: 360° Financial Health Navigator
*"How could AI help someone see their whole financial picture, make sense of it and feel confident about their next move?"*
* **Conversational coach:** each personal agent explains "why am I tight?" or "can I afford this?" with the roommate's own numbers and the reason behind them.
* **Health indicators:** 12 per roommate. The workshop's 8 (emergency fund, debt-to-income, savings rate, credit utilization, net worth, debt-to-asset, housing cost, liquidity) plus runway days, rent-to-income, days to payday, and buffer after rent.
* **Forecasting:** `can_cover` projects cash to payday, including paybacks already committed and recurring charges due before then.
* **What-if simulator:** any purchase, any number of months, even or uneven splits, with each person's answer.
* **Whole picture:** checking, savings and credit card accounts plus history in one profile, with payroll vs gig income and recurring charges detected.
* **Something new:** financial health for a *household*, where the group decides together without anyone exposing their balance.
* Built on the **PNC UTD Hackathon 2026 Financial Wellness toolkit** (`metrics.py`, `profile.py`, `tools.py`, `validation.py`, `llm.py`), following its rule: code does the math, the LLM explains, validate before explaining.

### Capital One: Best Use of Nessie
* **Every money movement is a real Nessie call:**
  * customers and checking accounts (`/customers`, `/customers/{id}/accounts`);
  * transfers between roommates and scheduled paybacks (`/accounts/{id}/transfers`);
  * landlord and utility bills (`/accounts/{id}/bills`);
  * shared purchases (`/accounts/{id}/purchases`, `/merchants`);
  * paydays (`/accounts/{id}/deposits`).
* **Strict least privilege:** only the treasurer can write to Nessie, and only after every required owner approves.
* **The money feeds back into the advice.** Payments executed through Nessie update each roommate's indicators and profile, so advice reflects what actually happened.
* **Harbor Bank app (Expo):** each roommate's live balance, scheduled payments, transactions, and a "What your agent knows" card.

### Photon: Build a Messaging Agent
* **Built on Photon 2.0 (`spectrum-ts`), live on two channels:** the house agent is in a Telegram group, and personal agents are in each roommate's iMessage DMs. No app to install.
* **It participates instead of assisting:** the agent lives in the roommates' own conversation, follows the thread, and acts with taste. It proposes rather than nags, and reasons go to DMs, never the group.
* **Multi-agent, human in the loop:** the house agent consults personal agents, and nothing moves without every required yes.
* **Context over time:**
  * House rules and preferences persist.
  * Paid bills roll to the next month.
  * A rule set in the group changes what each DM explains.
* **Safety and fallbacks:**
  * An auditor checks every outbound message.
  * If Grok times out, a scripted fallback reply goes out instead.
  * Agents never ask yes/no questions (a "yes" approves proposals).
  * Agents can't claim approvals or rules a tool didn't record.

### MLH: xAI (Grok)
* **Grok runs every agent.** `grok-4.20-0309-non-reasoning` drives a tool-calling loop for the house and personal agents. Grok picks the tools and explains the results in each agent's voice, while code does the math and the auditor checks every number Grok writes.
* **Grok handles messy language.** It turns "can we afford a 1200 couch", "xander pays half since it's in his room" and "keep at least $1,000 in my checking" into typed tool calls.
* **Grok Bot reviews every PR.** `.github/workflows/grok-review.yml` sends each pull request's diff to Grok, which comments with a summary and risk flags: leaked keys, hardcoded balances, and money moved without approval.
* **Built in Cursor.** Cursor is the team's core coding agent (SpaceXSI raffle: Cursor + Grok Bot).

### General: Virality
* **The hook:** *"Our group chat has an AI that makes rent fair, and nobody has to say how broke they are."* Every shared household has the rent-day fight; House Rules ends it in three yeses.
* **One install onboards a whole group.** Add the bot to an existing group chat and every roommate is in, with no app and no accounts.
* **Everyone takes part.** Every proposal needs every required yes, so every member uses it within minutes, and each gets their own personal agent.
* **Safe to invite people.** Nobody's balance is ever shown to the group.
* **Moments worth sharing:** "rent settled in 3 texts", a fronting that happened without the awkwardness, and the House rules card with the reason behind each split.
* **Beyond roommates:** trips, couples, clubs. Any group that shares money is another way in.

---

## 🧗 Challenges We Ran Into

1. **Consent in public.** Early prototypes picked a fronter and announced it in the group, so the fronter felt ambushed and the short roommate felt exposed. We split every proposal into a short group summary plus private DMs to the people involved, each asking for consent.
2. **Keeping the LLM away from the math.** The LLM never computes numbers and never authorizes money. Every number in a reply has to come from a tool output in the same turn, or the auditor blocks it. That even catches dates written as "12-05", which the auditor now reads as dates rather than amounts.
3. **A "yes" that approved the wrong thing.** In a live run, the house agent asked "want me to propose a rule?", and the reply "yes" approved a pending couch purchase instead, because "yes" applies to the oldest open proposal. Agents now never ask yes/no questions; they just open the vote.
4. **An agent that claimed things it hadn't done.** A personal agent told a roommate the rent rule was set, but rules need everyone's vote. Agents now can't claim approvals or rules a tool didn't record, and personal agents point people to the group.
5. **Privacy on the projector.** Our first dashboard printed raw agent traces, including private DM text. The redesigned house view says a private message was sent but never shows what it said.

---

## 🌟 Accomplishments That We're Proud Of

* **280 automated tests passing** across stub and real modes: the end-to-end rent, fronting and couch flows, plus agent loops, house rules, profiles, purchase splits and bill cycles. The Grok Bot reviews every PR.
* **No private figures in the group.** Balances, incomes, side income, recurring charges and preferences are blocked by the auditor and covered by tests.
* **No new app.** Everything happens in Telegram and iMessage with short replies.
* **A real banking feedback loop.** Seconds after the final "yes", Nessie has moved the money, the Harbor Bank app and the dashboard show it, and the indicators reflect it.

---

## 📚 What We Learned

* **Public coordination, private vulnerability:** collaborative money AI depends less on more data and more on respecting what belongs in the group versus a one-on-one chat.
* **Least-privilege agents:** splitting agents by what they may *see* and *do*, not by topic, makes the system safer, easier to audit, and easier to debug.
* **Agents need guardrails on what they say, not just on what they compute.** The hardest bugs were social: an ambiguous yes/no question, or an agent claiming success.

---

## 🔮 What's Next for House Rules

* **Reactions as approvals:** count a 👍 reaction, not only 👍 sent as a message.
* **Voice check-ins:** calls for missing approvals on a Photon SMS number.
* **Receipt splitting with Grok vision:** snap a receipt, and roommates claim their items.
* **Lease renewal check:** can the household afford a 10% rent increase?
* **Time-series storage on Tiger Data.**
* **Groups beyond roommates:** trips, couples, clubs.

---

## 💻 Built With

* **Languages and frameworks:** Python 3.11, TypeScript, FastAPI, Next.js, Tailwind CSS, React Native (Expo)
* **APIs and SDKs:** Photon 2.0 (`spectrum-ts`), Capital One Nessie API, xAI Grok API, PNC Financial Wellness toolkit
* **Data:** SQLite
* **Dev tools:** Cursor, GitHub Actions (Grok Bot review), pytest, node:test

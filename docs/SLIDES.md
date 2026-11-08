# House Rules: Pitch, Slides and Demo Script

> **Format (HackUTD judging):** 3 minutes of pitch with a live demo, then 2 minutes of questions. Some judges interrupt with questions; let them, and skip ahead in the demo.
> **Story in one line:** every shared house has the rent-day fight. House Rules ends it in three yeses, and nobody has to say how broke they are.
> **Demo flow:** the same beats as [`DEMO_DAY_GUIDE.md`](../DEMO_DAY_GUIDE.md). Run `POST /demo/reset` before each judge.

---

## Deck at a glance

| # | Slide | Time |
| --- | --- | --- |
| 1 | The hook | 0:00 – 0:15 |
| 2 | The problem | 0:15 – 0:35 |
| 3 | How House Rules works | 0:35 – 0:55 |
| 4 | Live: a house rule and a private preference | 0:55 – 1:30 |
| 5 | Live: rent day | 1:30 – 2:10 |
| 6 | Live: the couch and "why am I tight?" | 2:10 – 2:35 |
| 7 | Under the hood, and the tracks | 2:35 – 2:50 |
| 8 | Impact and what's next | 2:50 – 3:00 |

If time is short, cut slide 6 first; rent day is the moment that matters.

---

### Slide 1: The hook (0:00 – 0:15)
* **On screen:** the House Rules logo, and a group chat: *"rent's due friday"* / *"can someone spot me, I'm broke till the 15th"*.
* **Say:**
  > *"Every apartment has a group chat, and every month someone in it is chasing rent while someone else is quietly dreading it. House Rules is an AI roommate that lives in that chat. It splits bills by your house's rules, times them to everyone's payday, and moves the money once everyone says yes, without anyone revealing their balance."*

---

### Slide 2: The problem (0:15 – 0:35)
* **On screen:** three short lines.
  1. **Paydays don't line up.** Rent is due on the 1st; Kevin gets paid on the 15th.
  2. **Asking for help in public is humiliating.** Nobody wants to tell the group *"I have $310."*
  3. **Today's tools only keep score.** Splitwise logs IOUs after the fact; it can't tell who can pay, and it never moves money.
* **Say:**
  > *"Roommate money breaks for three reasons: paydays don't line up, nobody wants to admit they're short in front of the group, and the apps we have just keep score. They don't know if you can pay, and they don't move the money."*

---

### Slide 3: How House Rules works (0:35 – 0:55)
* **On screen:** two phones side by side. On the left, the **group chat** (shared plans and approvals). On the right, a **private DM** (your numbers and your reasons). Under them, one line: *public coordination, private vulnerability.*
* **Key points:**
  * A **house agent** in the group, and a **personal agent** in each roommate's DM.
  * Personal agents tell the house only **ok, tight or no**, or a date. Never a balance.
  * **Code does the math, Grok explains it, and an auditor checks every number** before it's sent.
  * **Nothing moves without a yes** from everyone whose money moves. Then a treasurer moves it through Capital One's Nessie.
* **Say:**
  > *"The rule we built everything on: coordinate in public, keep vulnerability private. The group sees the plan. Your DM sees your numbers. And nothing moves until the people whose money moves say yes."*

---

### Slide 4: Live: a house rule and a private preference (0:55 – 1:30)
* **Do (Telegram group, as Xander):** `xander has the master bedroom so rent should be 40/30/30`
  * The house replies with the preview *"…rent would be Xander $960, Julian $720, Kevin $720. Everyone reply yes to make it the house rule."*
  * Everyone replies `yes`, and the **House rules** card on the dashboard updates.
* **Do (Xander's iMessage DM):** `don't make me front more than $500 at a time`
* **Say:**
  > *"House rules aren't set by one person. Xander has the master bedroom, so he proposes 40/30/30. The house shows everyone the real dollar split, and it only becomes a rule when all three of us agree. Then Xander privately tells his own agent he won't front more than $500. The group never sees that."*

---

### Slide 5: Live: rent day (1:30 – 2:10)
* **Do (group):** `ok lets do rent` (or press **Rent is due** on the presenter bar, which you open with the `d` key).
* **Show, in order:**
  1. **The group:** the plan. Julian sends his $720, Xander pays Maple Court $2,400, and **Julian fronts Kevin's $720** until Dec 16.
  2. **Kevin's DM:** *"Your $310 doesn't cover the $720 share before your Dec 15 payday. So Julian fronts your share now and you auto-repay Julian $720 on Dec 16."*
  3. **Julian's DM:** a request to agree to front, with none of Kevin's details.
  4. Everyone replies `yes`. Nessie moves the money, the **Harbor Bank** app updates, and the dashboard circle draws *"$720 by Dec 16"* from Kevin to Julian.
* **Say:**
  > *"Rent is $2,400 and Kevin has $310 until the 15th. Normally that's an awkward text. Here, Kevin's agent tells the house only 'no, can pay the 15th'. Xander capped his fronting, so the plan has Julian front Kevin's share. Kevin's DM explains why in his own numbers, and Julian's DM asks for his consent. Three yeses later, Capital One Nessie has moved real money, and Kevin's payback is already scheduled for the 16th."*

---

### Slide 6: Live: the couch and "why am I tight?" (2:10 – 2:35)
* **Do (group, as Julian):** `what if xander paid half of a 1200 couch since it's going in his room?`, then Xander says `lets do that`.
  * The plan: Xander $200/mo, Julian $100/mo, Kevin $100/mo over 3 months. Up front didn't work for Kevin, so the house spread it out.
* **Do (Kevin's DM):** `can i afford a 100 dinner this week?`
  * The answer comes from Kevin's own history: StreamFlix and his phone plan renew before payday, and gig income isn't counted as guaranteed.
* **Say:**
  > *"It's not a script. Ask anything. The couch gets an uneven split because it's in Xander's room, and the house finds a plan that works for everyone instead of saying no. Kevin's agent knows his subscriptions renew before payday, because it reads his actual bank history."*

---

### Slide 7: Under the hood, and the tracks (2:35 – 2:50)
* **On screen:** the agent roster, plus five track badges.

| Agent | Sees | Does |
| --- | --- | --- |
| House | Shared bills, rules, what agents release | Proposes, opens votes |
| Personal ×3 | One roommate's accounts and history | Answers ok / tight / no, explains privately |
| Treasurer | Approved proposals | The only part that writes to Nessie |
| Auditor | Every draft | Blocks unverified numbers and private figures |

* **PNC:** 12 health indicators per roommate, payday forecasting, a what-if simulator, and a coach in your DM.
* **Capital One Nessie:** customers, accounts, transfers, bills, purchases, merchants and deposits. Moved money feeds back into the indicators.
* **Photon:** live on a Telegram group plus iMessage DMs through `spectrum-ts`. No app to install.
* **xAI:** Grok runs every agent's tool loop and reviews every pull request.
* **Virality:** add the bot once and the whole house is onboarded.
* **Say:**
  > *"Agents are split by what they can see and do. Only the treasurer can touch the bank, only after every yes, and an auditor in code checks every number Grok writes. It's 280 tests, all green."*

---

### Slide 8: Impact and what's next (2:50 – 3:00)
* **On screen:** *"Rent settled in 3 texts. Zero balances shown."* Next steps: 👍 reactions as approvals, voice check-ins on Photon, receipt splitting with Grok vision, trips and other groups.
* **Say:**
  > *"House Rules turns the most awkward text in every shared house into three yeses. And it works for any group that shares money: trips, couples, clubs. Thank you."*

---

## Track-specific openers (for sponsor judges)

Lead with the line for the judge's track, then run the same demo.

* **PNC:** *"It's a 360° view for a household. Each roommate gets 12 health indicators, a payday forecast, and a what-if simulator, and they decide as a group without anyone exposing their balance. Code does the math, the LLM explains, and we validate before explaining, which is the workshop's rule."*
* **Capital One:** *"Every money movement is a real Nessie call, made only by the treasurer and only after every required yes: transfers, landlord bills, merchant purchases, scheduled paybacks and paydays. The money that moves feeds back into each roommate's advice."*
* **Photon:** *"It's an agent that participates instead of just assisting. It lives in the roommates' own Telegram group with a private agent in each person's iMessage, it never asks yes/no questions that could misfire, and it falls back gracefully if the model is slow."*
* **xAI:** *"Grok is the brain of every agent. It picks tools, turns 'xander pays half since it's in his room' into a typed plan, and explains it in voice. A Grok Bot also reviews every pull request for leaked keys and money moved without approval."*

---

## 🎬 2-minute demo video script

| Time | On screen | Voiceover |
| --- | --- | --- |
| 0:00 – 0:12 | Logo, then an awkward group chat | *"Every apartment has a group chat, and every month someone's chasing rent. Meet House Rules, the AI roommate that makes rent fair."* |
| 0:12 – 0:30 | The Telegram group: the 40/30/30 rule preview, then three yeses; the dashboard rules card updates | *"The house sets its own rules. Xander has the master bedroom, so rent is 40/30/30, but only once all three agree."* |
| 0:30 – 0:42 | Xander's DM: "don't make me front more than $500" | *"Each roommate has a private agent. Xander caps how much he'll front. The group never sees it."* |
| 0:42 – 1:10 | "lets do rent", then the group plan, Kevin's DM, Julian's DM | *"Rent day. Kevin has $310 until the 15th. The group only hears that Julian is fronting Kevin. Kevin's DM explains why in his own numbers, and Julian's DM asks for consent."* |
| 1:10 – 1:25 | Three yeses, the Harbor Bank app updating, the circle thread "$720 by Dec 16" | *"Three yeses, and Capital One Nessie moves real money. Kevin's payback is already scheduled."* |
| 1:25 – 1:45 | The couch with an uneven split; Kevin asking "can I afford a $100 dinner?" | *"Ask anything. An uneven couch split, a plan that works for everyone, and answers from your real bank history."* |
| 1:45 – 2:00 | The dashboard circle, then the track badges | *"Code does the math, Grok explains, an auditor checks every number, and nothing moves without a yes. House Rules: public coordination, private vulnerability."* |

---

## 🎯 Judge Q&A cheat sheet

**"How do you stop the AI from making up numbers or moving the wrong amount?"**
> The LLM never computes numbers and can't move money. The math is Python (`split_bill`, `can_cover`, `payday_plan`, `group_affordability`). Every outgoing message goes through the auditor: if a number didn't come from a tool output in that turn, the message is blocked and the agent falls back to the code-written version.

**"What stops someone's money from moving without consent?"**
> The treasurer refuses to call Nessie unless every required approver has a recorded yes on that exact proposal. Approvals are parsed in code, not by the LLM. We also found and fixed a real edge case: the agent used to ask yes/no questions, and a "yes" meant for the agent could approve an older proposal. Agents now never ask yes/no questions.

**"How does it know what someone can afford?"**
> It projects cash to the next payday: the balance, minus paybacks already committed, minus subscriptions renewing before payday. `ok` means the roommate stays above their cushion (at least $200, or more if they set one), `tight` means they stay above $0, and `no` means they'd go negative, along with the earliest date they could pay. Gig income is never counted as guaranteed.

**"What does the group actually see?"**
> Only ok, tight, no or a date, plus the plan itself. Balances, income, side income, subscriptions and preferences never leave that person's DM. The auditor blocks them, and the projector dashboard never shows DM text.

**"Why Telegram for the group and iMessage for DMs?"**
> Group chats on iMessage need a dedicated line, so on the shared Photon pool the house agent lives in a Telegram group and each personal agent lives in its roommate's iMessage. Both run through Photon's `spectrum-ts`.

**"What if Grok is slow or down?"**
> Each call has an 8-second timeout. On timeout, the agent sends its scripted fallback reply and logs it, and the money math and approvals don't depend on the LLM at all.

**"Is the money real?"**
> It moves through Capital One's Nessie sandbox, so these are real API calls against mock accounts. Swapping in a production bank API means changing one client class, because the treasurer is the only writer.

**"Why not Splitwise or Venmo?"**
> They record debts after the fact and need someone to chase people. House Rules knows who can pay and when, finds a plan that works (fronting or installments), gets consent privately, and moves the money.

**"How would this spread?"**
> One person adds the bot to an existing group chat and the whole house is onboarded, with no app. Every proposal needs every yes, so everyone uses it right away. The same flow fits trips, couples and clubs.

# House rules from chat + personal profiles from bank data

Status: **built 2026-11-08** (`feat/rules-and-profiles`, `feat/purchase-rules`). Rent, electric
and purchase rules work, plus one-off uneven splits for a single purchase. This is a contract
change: it adds fields and methods to `contracts/` (see [Contract changes](#contract-changes)).
Per AGENTS.md, the team reads this before building against it.

Owners follow AGENTS.md: Store, indicators, tools and `wellness/` are **A**; agents and proposals
are **B**; dashboard and bank app are **D**.

## Why

Today the agents talk and use tools, but what they know is mostly fixed fixture data:

| Today | Problem |
| --- | --- |
| One preloaded house rule (`fixtures/scenario.json`: "Sam pays 40% of electric") | A house can't say "Alex has the master, rent is 40/30/30". The Store can read rules but not save them. |
| Indicators run the PNC workshop metrics over the seeded store history | Money the treasurer actually moves through Nessie never reaches them. After rent is paid, Jordan's runway is unchanged. Only demo paydays write back (`brain/app/demo.py`). |
| `can_cover` uses one rule for everyone (balance at next payday at least $200 for ok, at least $0 for tight) | It ignores subscriptions about to renew, gig income, a cushion or savings goal the roommate cares about, and whether someone is willing to front. |
| `housing_cost_ratio` is 0 for everyone | The workshop counts mortgage payments only. Our rent rows are category `rent`, so the indicator never sees them. |

Goal: the fixture supplies only starting balances and three months of history. Everything else is
**set by the roommates in chat** (house rules, personal preferences) or **learned from their bank
activity** (Nessie plus history, run through the PNC workshop toolkit), and it changes the agents'
decisions. The PNC rule still holds: **code does the math, the LLM explains, the auditor validates.**

## Feature 1: House rules set in chat

### What the roommates see

```
Alex:   alex has the master bedroom so rent should be 40/30/30
House:  Got it. With Alex at 40% for the master, rent would be Alex $960, Sam $720, Jordan $720.
        Everyone reply yes to make it a house rule.
Sam:    yes
Jordan: yep
Alex:   yes
House:  It's a house rule now: rent is Alex 40%, Sam 30%, Jordan 30% (Alex has the master bedroom).
        It applies from the next rent.
```

Later, "lets do rent" proposes $960 / $720 / $720 with Jordan's $720 fronted. "go back to an even
rent split" removes the rule through the same yes-from-everyone path.

### How it works

1. **The LLM parses, code decides.** The house agent's tool loop calls `propose_rule(bill, shares,
   reason)`, where `shares` maps names to percents (`{"Alex": 40, "Sam": 30, "Jordan": 30}`) and
   `reason` is the human reason ("Alex has the master bedroom").
2. **Validation in code** (`brain/app/agents/house.py`). It rejects the proposal, with the reason
   going back to the LLM, when:
   - a roommate is unknown or a percent is outside 0 to 100;
   - the percents sum to more than 100;
   - the bill type is unknown;
   - an identical rule is already in force.

   Roommates not listed split the remainder evenly, exactly as `split_bill` already does.
3. **Preview.** `tools.split_bill(bill, amount, rule=candidate)` computes the dollar split
   without saving anything. Those numbers are the only ones allowed in the reply.
4. **Consent.** It creates a `Proposal` with `flow="rule"`, `legs=[]`, `rule=<candidate>`, and
   everyone as a required approver. The yes/no parsing is the same as for money.
5. **Apply.** When all yeses arrive, `proposals.record_reply` saves the rule with
   `store.save_house_rule(p.rule)`, marks the proposal `executed` and traces `rule_saved`. It
   **does not call the treasurer**: no money moves, and the treasurer stays the only Nessie writer.
   A no rejects it, as with any proposal.
6. **Effect.** Every later `split_bill(bill, ...)` reads the rule (no change to the split math).
   A bill proposal that is already pending keeps the split it was created with, and the reply
   says so.
7. **Remove.** `remove_rule(bill)` creates a `rule` proposal with `rule.split = {}`. On approval
   it deletes the row.

Supported bill types: `rent`, `electric` and `purchase`.

**Purchase rules.** `purchase` is the default split for shared buys ("Alex pays 50% of shared
furniture, Alex keeps it when we move out"). There is no bill behind it, so the vote previews the
split on the price someone named, or on a $100 example. `group_affordability(item, price,
months_options, shares=None)` takes each roommate's share from, in order:
1. a one-off `shares` (fractions) for this purchase only;
2. the `purchase` house rule;
3. an even split.

Each roommate is checked with `can_cover` on their own monthly amount, and the plan is the first
month option where nobody is `no`. `AffordPlan.monthly` holds the per-roommate amounts, and is
empty for an even split, so the locked couch result is unchanged. The house agent builds the legs
from those amounts; each payer's last month absorbs the leftover cents, so totals are exact.

**One-off splits.** "Alex pays half of the couch since it's in Alex's room" doesn't need a rule.
The house agent passes `shares` and `reason` to `group_affordability` or `what_if_purchase`, and
nothing is saved. `what_if_purchase` returns each person's total, monthly amount and ok/tight/no
for up front and for spread out, so the LLM quotes each person's own numbers.

**No yes/no questions.** "yes" approves the oldest open proposal, so the house agent never ends
with a yes/no question, and never claims an approval a tool didn't record. In a live run, "want me
to propose a rule?" followed by "yes" approved the pending couch instead. Proposing only opens a
vote, so the agent proposes, or says "say the word and I'll put it to a vote".

### Where it shows

- `house_status` (house agent tool) returns each rule with its `source_text`, so Grok explains
  splits in plain words ("Alex pays 40% for the master bedroom").
- Dashboard: a new **House rules** card lists each rule, its reason and who confirmed it.
  `HouseState` gains `rules`.

## Feature 2: Personal profile from bank data

Each personal agent builds a **private, deterministic profile** of its roommate. Part of it is
derived from that roommate's bank activity, and part is stated by the roommate in their DM. The
profile changes `can_cover` and `payday_plan`. The house agent still only ever learns `ok`,
`tight`, `no` or a date.

### Data source: make indicators live

`indicators._customer(rid)` (the workshop adapter) and the new `profile(rid)` read two sources:

1. **Store history**: seeded history plus demo paydays (unchanged).
2. **Executed legs**: every proposal leg with `status == "done"` and a `nessie_id`, i.e. money the
   treasurer actually moved through Nessie, categorized from the leg:

   | Leg | Category | Sign for `from` / `to` |
   | --- | --- | --- |
   | `bill_payment` to the landlord | `rent` | out |
   | `bill_payment` to another payee | `utilities` | out |
   | `purchase` | `shopping` | out |
   | `transfer` / `scheduled_transfer` | `transfer` | out / in |

We use executed legs, not `nessie.transactions()`, because the two Nessie clients differ: the stub
copies the seed history and the live client does not, and paydays are already written to the
store. Legs are the one source that is identical in stub and live and never double-counts.

The workshop's `build_profile` excludes only `debt_payments` from spending, so transfers are
excluded the same way: a front-and-repay pair is not spending. Rent rows also feed the workshop's
housing input, so `housing_cost_ratio` stops being 0.

Result: when rent executes, Jordan's runway and buffer change in the DM, in the dashboard's
roommate cards and in the next `can_cover`.

### Derived profile (code, from history)

Detection helpers live in `brain/wellness/patterns.py` (new). They follow the workshop's style
and are credited as an extension of `wellness/profile.py`.

| Field | Rule | Seed result |
| --- | --- | --- |
| `regular_pay` | income deposits equal to `PayRule.amount` (within 1%) | Alex $5,800, Sam $1,900, Jordan $1,350 |
| `side_income_monthly` | other income deposits, summed and divided by months of history | Jordan $374.89 (DashRun gig payouts); 0 for the others |
| `income_pattern` | `steady` if there is no side income; `steady_plus_side` if side income is at least 10% of monthly regular pay; `irregular` if there is no regular payroll | Jordan `steady_plus_side`; Alex and Sam `steady` |
| `recurring` | same description and amount (within 5%) in at least 2 of the last 3 months, excluding `rent` and `utilities` (house bills, already handled by proposals); `next_date` is the same day next month | Jordan: StreamFlix $15.49 (12-05), Phone Plan $45.00 (12-08) |
| `spend_trend_pct` | last 30 days of spending vs the 3-month monthly average | per roommate |
| `indicators` | the existing 12 indicators | unchanged keys |

Side income is shown and explained but **never counted as guaranteed cash** in `can_cover`. The
DM says "not counting your gig income".

### Stated preferences (the roommate tells their own agent)

```
Jordan (DM): don't let me go under $150, I keep getting overdraft scares
Agent:       Done. I'll keep at least $150 in your checking when I answer the house.
Sam (DM):    im saving for japan, keep $2,500 in checking
Alex (DM):   don't make me front more than $500 at a time
```

| Preference | Effect | Who sees it |
| --- | --- | --- |
| `min_buffer` | the ok floor becomes `max(200, min_buffer)` | only that roommate's DM |
| `savings_monthly` + `savings_label` | the monthly amount is reserved: floor += `savings_monthly` | only that roommate's DM |
| `front_cap` | `payday_plan` skips this roommate as a fronter for amounts above the cap | only that roommate's DM |
| `notes` | free text ("I get paid in tips on weekends"), LLM context only, never used in math | only that roommate's DM |

A preference takes effect immediately, without a group vote: it's the roommate's own money. The
agent repeats it back. The trace logs `preference_set` with the kind, never the value, so the
dashboard (shown to judges) doesn't leak it.

### Decision rules (deterministic, `brain/app/tools.py`)

```
cash  = balance - amount - committed legs before horizon      (as today)
      - recurring charges due on or before horizon             (new)
floor = max(200, min_buffer) + savings_monthly                 (new; 200 when nothing is set)
level = ok if cash >= floor; tight if cash >= 0; no otherwise
if level == ok and runway_days status == risk: level = tight   (new)
earliest_date: as today, with recurring charges included
```

- **Runway, not emergency fund.** We downgrade on `runway_days` risk (under 14 days), not the
  workshop's `emergency_fund_months`. With the seed data, the emergency fund is `risk` for all
  three roommates (Alex 2.49, Sam 1.79, Jordan 0.23 months against a 3-month threshold), so it
  would turn every answer into `tight`. Runway is a risk only for Jordan (7 days).
- **`payday_plan`**: the fronter is the roommate with the highest `buffer_after(amount)` among
  those whose `front_cap` is unset or at least the amount. If nobody qualifies, the house says no
  one can front it and offers a split-pay instead of fronting.
- **`Release` is unchanged** (`{level, earliest_date}`), so nothing new reaches the house. A
  separate `CoverAnswer.reason` (`cushion`, `savings_goal`, `upcoming_bills`, `runway`; a `no` already carries its `earliest_date`)
  is used only in the roommate's own DM explanation.

### Locked results still hold (checked by hand against the seed; tests lock them)

| Expected result | With recurring charges and no preferences |
| --- | --- |
| Rent $800 each | unchanged (split math untouched) |
| `can_cover(jordan, 800, 2026-11-30)` is `no`, earliest 2026-12-15 | 310 - 800 - 60.49 = -550.49; plus $1,350 on 12-15 gives 799.51, at least 0, so still `no` with earliest 12-15 |
| Electric Sam $60, Alex $45, Jordan $45 | unchanged |
| Couch: Alex ok, Sam ok, Jordan no up front; Jordan tight over 3 months | Jordan up front: 310 - 400 = -90, `no`. Monthly: 310 - 133.33 - 60.49 = 116.18, `tight`. Alex and Sam stay above $200 with runway 74.6 and 53.7 days, `ok`. |

If an implementation detail changes any row, recurring charges become advisory (shown in the DM,
not subtracted), and this section is updated with the reason.

### Personal agent tools (added to the DM loop)

- `my_profile`: the derived profile plus preferences, so the agent can answer "what do you know
  about me".
- `set_preference(kind, value)`: kinds `min_buffer`, `savings_goal` (amount and label),
  `front_cap`, `add_note`, `remove_note`, `clear`. Values are validated in code (non-negative,
  finite, at most $100,000).
- Explanations cite the driver, using only tool numbers:

  > "Tight for you, Jordan: $133.33 fits, but StreamFlix and your phone plan ($60.49) renew
  > before the 15th, and I'm not counting gig income."

### Where it shows

- **Bank app** (`/bank/{rid}`): a "What your agent knows" card showing income pattern, recurring
  charges, and preferences. `BankView` gains an optional `profile`.
- **Dashboard**: roommate cards keep showing `status` only. Preferences never appear there.

## Privacy boundaries

| Data | Group chat | That roommate's DM | Other roommates' DMs | Dashboard |
| --- | --- | --- | --- | --- |
| House rules and reasons | yes | yes | yes | yes |
| ok / tight / no, earliest date | yes | yes | yes | yes |
| Balance, income, side income | **no** (auditor) | yes | **no** (auditor) | balance only (existing) |
| Recurring charges, preferences, notes | **no** | yes | **no** | **no** |
| `CoverAnswer.reason` | **no** | yes | **no** | **no** |

The auditor gains one check: group messages and other roommates' DMs may not contain a
roommate's recurring-charge amounts, side income, or preference values. These are added to the
private figures in `_private_figures`.

## Contract changes

`contracts/models.py`

```python
Flow = Literal["rent", "front", "purchase", "utility", "rule"]          # + "rule"

class Proposal(_Model):
    ...
    rule: HouseRule | None = None        # set when flow == "rule"; split == {} means remove

class Preferences(_Model):
    min_buffer: float | None = None
    savings_monthly: float | None = None
    savings_label: str | None = None
    front_cap: float | None = None
    notes: list[str] = []

class Recurring(_Model):
    name: str
    amount: float
    next_date: str

class Profile(_Model):
    income_pattern: Literal["steady", "steady_plus_side", "irregular"]
    regular_pay: float
    side_income_monthly: float
    recurring: list[Recurring]
    spend_trend_pct: float
    preferences: Preferences
    indicators: dict[str, Indicator]

class AffordPlan(_Model):
    months: int
    per_person_monthly: float
    monthly: dict[str, float] = {}       # per roommate when shares are uneven; {} = even split

class CoverAnswer(_Model):
    level: Level
    earliest_date: str | None = None
    reason: Literal["cushion", "savings_goal", "upcoming_bills", "runway"] | None = None

class HouseState(_Model):
    ...
    rules: list[HouseRule] = []

class BankView(_Model):
    ...
    profile: Profile | None = None
```

`contracts/interfaces.py`

```python
class Store(Protocol):
    def house_rules(self) -> list[HouseRule]: ...
    def save_house_rule(self, rule: HouseRule) -> None: ...      # upsert by bill_type
    def delete_house_rule(self, bill_type: str) -> None: ...
    def get_preferences(self, rid: str) -> Preferences: ...      # empty Preferences if none
    def save_preferences(self, rid: str, prefs: Preferences) -> None: ...

class Indicators(Protocol):
    def profile(self, rid: str) -> Profile: ...

class Tools(Protocol):
    def split_bill(self, bill_type: str, amount: float, rule: HouseRule | None = None) -> SplitResult: ...
    def group_affordability(self, item: str, price: float, months_options=(1, 3),
                            shares: dict[str, float] | None = None) -> Affordability: ...
```

SQLite (`brain/app/db.py`): the `house_rules` table already exists. Add a `preferences` table
(`roommate_id TEXT PRIMARY KEY, data TEXT NOT NULL`, JSON) and include it in `TABLES`, so
`/demo/reset` clears it. TypeScript mirrors go in `dashboard/app/lib/brain.ts` and the bank app's
API types.

All new fields default to empty, so every existing caller and fixture keeps working.

## Running live (the demo has no stubs)

The demo runs every service live: `LLM_MODE=grok`, `NESSIE_MODE=live`, `GATEWAY_MODE=photon`,
`OUTBOX_MODE=http`, and the real Store, indicators, tools, proposals, auditor and agents. Stubs
exist only so `pytest` runs offline (AGENTS.md). Everything in this doc is designed for the live
path:

- **Bank data.** The profile reads executed legs (each has a real Nessie id from the live
  treasurer) plus the store history. It never depends on the stub Nessie copying the seed.
  Balances come from the live client's ledger, which mirrors every Nessie write.
- **Rules and preferences** persist in the real database (SQLite now, Tiger when `DB_MODE=tiger`).
  `/demo/reset` clears them, so the demo starts from the seeded rule only.
- **Grok** parses rules and preferences through the tool loop. If a Grok call times out (8 s),
  the adapter falls back to the scripted reply, and that is traced as `llm_fallback`. A rule or
  preference is never saved from a fallback; the roommate is asked to say it again.
- **Latency.** A rule proposal is 1 to 2 Grok calls, with no Nessie calls until money moves. Rent
  after a rule costs the same Nessie calls as today. Profile detection is local code over a few
  hundred rows.
- **Live checks** before the demo: one dry run of the four beats with all services live, watching
  the dashboard trace for `llm_fallback`, `blocked` and `tool_error`.

## Demo beats (these replace fixed-scenario talking points)

1. **Rule from chat**: "alex has the master, rent should be 40/30/30", then a preview, three
   yeses, then "lets do rent", which proposes $960 / $720 / $720. Jordan's $720 is fronted.
2. **Preference changes a decision**: Alex DMs "don't make me front more than $500". The next
   rent proposal has **Sam** fronting Jordan instead of Alex. The group never learns why.
3. **Profile from data**: Jordan asks "why am I tight?" and gets the subscriptions renewing before
   the 15th plus "not counting your gig income", all from bank history.
4. **Live indicators**: `/demo/advance` past rent. Jordan's runway and buffer on the bank app
   change because of the money that actually moved.

## Tests (`brain/tests/test_rules.py`, `brain/tests/test_profiles.py`)

Rules:
- propose 40/30/30, preview $960 / $720 / $720, three yeses, saved; the next rent proposal uses it
- a rent proposal already pending keeps $800 each
- invalid input is rejected with a reason: sum over 100, unknown roommate, negative percent
- one no rejects the rule; removing a rule also needs everyone
- the rule proposal never calls the treasurer or Nessie

Profiles:
- Jordan's gig deposits give `steady_plus_side` with side income $374.89
- recurring detection finds StreamFlix and Phone Plan, and excludes rent and electric
- executed rent changes Jordan's `runway_days` and `buffer_after`
- `min_buffer` flips ok to tight (Sam, $2,500 cushion, couch $133.33)
- `front_cap=500` on Alex makes Sam the fronter
- `Release` never includes the reason; group replies never contain preference values, recurring
  amounts or side income
- all locked results in `tests/test_expected.py` are unchanged with no preferences set

Contract tests in `brain/tests/contracts/` cover the new Store, Indicators and Tools methods in
both stub and real modes. `tests/test_e2e.py` stays green with all mocks on.

## Build order

1. Contracts and stubs (`contracts/`, `app/stubs/*`), plus this doc and the SPEC, AGENTS and
   REQUIREMENTS updates.
2. Store methods and the preferences table (`app/db.py`).
3. Rules: `split_bill(rule=)`, the `propose_rule` and `remove_rule` house tools, proposal apply,
   and the dashboard card.
4. Profile: the executed-legs adapter, `wellness/patterns.py`, `Indicators.profile`.
5. Decisions: the `can_cover` floor and recurring charges, the `payday_plan` front cap, and
   `CoverAnswer.reason`.
6. Personal tools (`my_profile`, `set_preference`), auditor private figures, and the bank-app card.
7. Live Grok run of the four demo beats, then DEVPOST and SLIDES polish.

Cut order if behind: the bank-app card, then `spend_trend_pct`.

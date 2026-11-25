# Kingbot Development Roadmap v18 — Nightly Auto-Run (Asia/Muscat 22:00–03:00)

Source: `kingbot_roadmap_v18.xlsx` (from the owner, 25-11-2026). Progress: `progress.json`. Order = start time, then sheet order.

## Assistant Modal

### MOD-01 — Fix Duplicate Buttons Bug in Assistant Modal
- Sheet: Assistant Modal · Priority: Critical · Start: 22:00 Asia/Muscat
- Scope: Assistant quick-action controls (Refresh Characters, Refresh Resources, Capture Screenshot, Refresh All, Open Live Stream) render twice consecutively inside the Assistant modal.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 22:00 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

In `kingbot-ui`, inside the `Assistant` modal/popover, UI action buttons are currently duplicated twice in a row (Refresh Characters, Refresh Resources, Capture Screenshot, Refresh All, Open Live Stream).

Requirements:
1. Remove all duplicate button instances so each control appears once in a clean, organized layout.
2. Make the `Assistant` modal responsive for mobile viewports so it does not require excessive vertical scrolling.
```

### MOD-02 — Live Command Execution Status & Debounce Lock
- Sheet: Assistant Modal · Priority: High · Start: 22:59 Asia/Muscat
- Scope: Clicking a quick-action button in Assistant provides no real-time feedback on whether the bot received the command or when it completed.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 22:59 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Upgrade the `Assistant` modal across `kingbot-ui`, `kingbot-syn`, and `kingbot` to add live command execution feedback:

1. When a user clicks any command button (e.g., Refresh Resources, Refresh Marches, Capture Screenshot):
   - Temporarily update button label/state to `Sending...` then `Waiting for server...` with a loading spinner.
   - Apply a debounce/lock mechanism while in-flight to prevent duplicate stacked commands in the control state.
2. Once `kingbot` executes the command and updates `status.json`, display a green checkmark state (`Updated just now`) along with the last successful timestamp next to the control.
```

### MOD-03 — Add Queue Overview Sync Button & Quick Server Controls
- Sheet: Assistant Modal · Priority: High · Start: 23:58 Asia/Muscat
- Scope: The Assistant modal lacks a manual button to sync in-game Queue Overview timers and quick server control actions (Pause/Resume, Restart Game, Restart Bot).

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 23:58 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Add operational control actions inside the `Assistant` modal across `kingbot-ui`, `kingbot-syn`, and `kingbot`:

1. `Sync Queue Overview` button: commands the bot to open/read the in-game Queue Overview sidebar immediately and refresh training, building, research, material production, and scout timers.
2. `Quick Server Controls` section at the bottom of the modal with:
   - `Pause / Resume Bot` toggle button.
   - `Restart Game` button with a confirmation dialog.
   - `Restart Bot` button with a confirmation dialog.
```

### MOD-04 — Inline Latest Screenshot Preview & Stream Status Indicator
- Sheet: Assistant Modal · Priority: Medium · Start: 00:57 Asia/Muscat
- Scope: The change-stream button appears muted without showing live stream availability or an inline preview of the latest captured screenshot.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 00:57 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Improve the live stream and screenshot experience inside the `Assistant` modal in `kingbot-ui`:

1. Render an inline thumbnail card showing the latest captured game screenshot with its capture timestamp and click-to-expand lightbox view.
2. Add a connection status badge next to `Open Live Stream` (`Online / Offline`) and store/bind the stream URL per slot/server independently.
```

### MOD-05 — Group Controls into 3 Logical Sections + Last 5 Commands Log
- Sheet: Assistant Modal · Priority: Medium · Start: 01:56 Asia/Muscat
- Scope: All Assistant buttons are stacked in one long list, making quick selection during gameplay harder.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 01:56 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Reorganize the `Assistant` modal in `kingbot-ui` for faster navigation and cleaner hierarchy:

1. Group controls into 3 titled sections:
   - Group 1 (`Data Sync`): Refresh All, Refresh Resources, Refresh Marches, Sync Queue Overview, Refresh Commanders, Refresh Profile & Characters.
   - Group 2 (`Monitoring & Stream`): Capture Screenshot Now (with inline thumbnail), Open Live Stream, Configure Stream URL.
   - Group 3 (`Server Controls`): Pause / Resume, Restart Game.
2. Add a compact `Recent Commands (Last 5)` strip at the bottom showing the last 5 dispatched commands, their status (`Success / Pending / Failed`), and timestamps.
```

### MOD-06 — Comprehensive Assistant Modal Overhaul (Combines MOD-01 through MOD-05)
- Sheet: Assistant Modal · Priority: Critical · Start: 02:55 Asia/Muscat
- Scope: Execute all five approved Assistant modal improvements (deduplication, live status/lock, queue sync & server controls, inline preview, and 3-group layout + last 5 commands log) in a single cohesive pass.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 02:55 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Execute a complete, cohesive overhaul of the `Assistant` modal across `kingbot-ui`, `kingbot-syn`, and `kingbot` combining MOD-01 through MOD-05:

1. Deduplication & Responsive Layout:
   - Remove all duplicate buttons (Refresh Characters, Refresh Resources, Capture Screenshot, Refresh All, Open Live Stream) so each control renders once in a mobile- and desktop-responsive layout.

2. Three Logical Groups:
   - Group 1 (`Data Sync`): Refresh All, Refresh Resources, Refresh Marches, Sync Queue Overview, Refresh Commanders, Refresh Profile & Characters.
   - Group 2 (`Monitoring & Stream`): Capture Screenshot Now + inline latest screenshot thumbnail with timestamp, Open Live Stream (with Online/Offline indicator), Configure Stream URL per slot.
   - Group 3 (`Server Controls`): Pause / Resume Bot, Restart Game, Restart Bot (with confirmation prompts).

3. Live Status & Debounce Lock:
   - On click, transition button state to `Sending...` -> `Waiting for server...` with a debounce lock preventing duplicate clicks, then show `Updated just now` + last success timestamp once `status.json` confirms execution.

4. Recent Commands Strip:
   - Display the last 5 commands at the bottom of the modal with status (`Success / Pending / Failed`) and timestamp.
```

## Mkasbi Overhaul

### EARN-01 — Fix Clipped Columns & Compact Large Numbers in Daily Gains Table
- Sheet: Mkasbi Overhaul · Priority: Critical · Start: 22:00 Asia/Muscat
- Scope: On mobile screens, the Gold column or left-side numbers get clipped due to long unformatted numbers and dense columns.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 22:00 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

In `kingbot-ui` under the `Mkasbi` (Earnings) section:

1. Make the daily gains table fully responsive on mobile viewports with zero horizontal clipping of columns or values.
2. Format large numbers compactly in tables and summary cards (e.g., `3.3M` instead of `3,300,000`, `130K` instead of `130,000`) while preserving the exact full number in a hover/tap tooltip.
3. Ensure all columns (`Day`, `Food`, `Wood`, `Stone`, `Gold`, `Gems`) remain clearly visible and aligned in RTL.
```

### EARN-02 — Add Game Resource Icons, 'All' Tab & Time-Range Pills
- Sheet: Mkasbi Overhaul · Priority: High · Start: 23:13 Asia/Muscat
- Scope: Add visual game resource icons (Food, Wood, Stone, Gold, Gems), an 'All' tab, and quick time-range pills (Today / 7 Days / 30 Days).

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 23:13 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Enhance the filter and control bar in `Mkasbi` inside `kingbot-ui`:

1. Add distinct game resource icons (Food wheat/corn, Wood logs, Stone blocks, Gold coins/ingots, Gems ruby) beside resource labels in filter pills, summary cards, and daily table headers.
2. Add an `All` tab alongside individual resource pills to render a combined/multi-resource chart view.
3. Add quick time-range selector pills (`Today`, `7 Days`, `30 Days`) that dynamically update summary cards, chart, and table.
```

### EARN-03 — Add Bar Value Labels, Trend Badges, Farming Efficiency & Net After Supply
- Sheet: Mkasbi Overhaul · Priority: High · Start: 00:27 Asia/Muscat
- Scope: Display compact totals above chart bars, day-over-day growth badges, hourly farming efficiency, and net remaining balance after supply/transport.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 00:27 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Add analytical metrics to the `Mkasbi` view across `kingbot-ui` and `kingbot-syn`:

1. Render compact value labels (e.g., `319M`, `63M`) directly above each bar in the chart for instant scanning.
2. Add day-over-day percentage change badges (e.g., `+18%` / `-12%`) on resource summary cards.
3. Add two compact metric cards/strips: `Farming Efficiency` (average gained per active runtime hour) and `Net Remaining After Supply` (net balance after deducting resources sent via supply/transport).
```

### EARN-04 — Apply Neo-Tactile Pill Buttons & Frosted Glassmorphism Cards to Mkasbi
- Sheet: Mkasbi Overhaul · Priority: High · Start: 01:41 Asia/Muscat
- Scope: Upgrade flat buttons to tactile pill controls with soft shadows and active glow, and style cards as dark frosted glass panels with a tactile progress bar.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 01:41 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Redesign the visual styling of `Mkasbi` in `kingbot-ui` using Neo-Tactile and Glassmorphism while preserving the dark theme and warm gold/emerald palette:

1. Neo-Tactile Pill Buttons:
   - Style resource filter pills (`All`, `Food`, `Wood`, `Stone`, `Gold`, `Gems`) and time-range pills (`Today`, `7 Days`, `30 Days`) as elevated pill capsules with subtle outer drop shadow and top inner highlight.
   - Give the active state a distinct pressed/elevated tactile look with a soft warm glow.
2. Glassmorphism Cards:
   - Style summary cards, chart container, and daily table card as dark frosted-glass surfaces (`backdrop-filter: blur`, subtle `1px` light border, balanced spacing).
3. Growth Badges & Tactile Progress Bar:
   - Place growth percentages (`+18%` / `-12%`) inside rounded pill badges beside values.
   - Style `Net Remaining After Supply` as a tactile progress bar/slider with smooth gradient fill.
```

### EARN-05 — Complete Mkasbi Dashboard Overhaul (Combines EARN-01 through EARN-04)
- Sheet: Mkasbi Overhaul · Priority: Critical · Start: 02:55 Asia/Muscat
- Scope: Apply all Mkasbi upgrades (Neo-Tactile & Glassmorphism, resource icons, responsive table, above-bar labels, efficiency & net supply metrics) in one unified prompt.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 02:55 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Execute a full visual and analytical overhaul of `Mkasbi` across `kingbot-ui` and `kingbot-syn` combining EARN-01 through EARN-04:

1. Neo-Tactile & Glassmorphism Styling:
   - Convert filter pills (`All`, `Food`, `Wood`, `Stone`, `Gold`, `Gems`) and time-range pills (`Today`, `7 Days`, `30 Days`) into tactile pill buttons with soft drop shadows, top inner highlight, and clear active glow.
   - Style summary cards, chart panel, and daily table as dark frosted-glass cards with subtle borders and generous spacing.

2. Resource Icons & 'All' Tab:
   - Include clear resource icons across filter pills, summary cards, and table headers, plus an `All` tab for combined chart visualization.

3. Analytics & Live KPIs:
   - Show compact values (e.g., `319M`, `63M`) above chart bars.
   - Display day-over-day `%` trend badges on resource cards, plus `Farming Efficiency (/hr)`, a tactile `Net Remaining After Supply` progress bar, and a copy/export summary button.

4. Responsive Mobile Table:
   - Use compact number formatting (`3.3M`, `2.5M`, `130K`) with full-value tooltips so all columns (`Day`, `Food`, `Wood`, `Stone`, `Gold`, `Gems`) render cleanly on mobile with zero clipping.
```

## Full App UX

### UX-01 — 2x3 Live Resource & Action Points (AP) Cards Grid
- Sheet: Full App UX · Priority: Critical · Start: 22:00 Asia/Muscat
- Scope: Display the 5 resources with daily gain delta (+12.4M today) and a dedicated Action Points (AP: 15 / 1,500) card with fill percentage.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 22:00 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Add a 2x3 live resource and Action Points (AP) card grid at the top of the main dashboard in `kingbot-ui` and `kingbot-syn`:

1. Five Resource Cards (`Food`, `Wood`, `Stone`, `Gold`, `Gems`):
   - Display current balance prominently with resource icon, daily gained delta below (e.g., `+12.4M today`), and a mini progress bar.
2. Sixth Card — Action Points (`AP`):
   - Read current and max AP from `status.json` (e.g., `15 / 1,500`) and render value, fill percentage, and progress bar.
```

### UX-02 — Live 'In The City' Queue Cards (Training, Materials & Healing)
- Sheet: Full App UX · Priority: High · Start: 22:59 Asia/Muscat
- Scope: Show active city queues in compact cards with troop type/tier (e.g., Cavalry - T4), countdown timer, and colored progress bar.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 22:59 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Build the `In The City` section in `kingbot-ui` and `kingbot` to visualize active city queues:

1. Render responsive compact cards for active queues (`Infantry`, `Cavalry`, `Archers`, `Siege` training, `Materials` production, and `Healing`) along with a `Last read` timestamp.
2. Inside each card, display queue/unit icon, unit type & tier (e.g., `Cavalry • T4`), live countdown timer, and a colored progress bar.
```

### UX-03 — Detailed 'Active Marches' Cards (Commanders, Target, Troops & Health)
- Sheet: Full App UX · Priority: High · Start: 23:58 Asia/Muscat
- Scope: Show outgoing march counter (2/5 marches out) and detailed cards per march with commander portraits, target coordinates, troop count, status, and health bar.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 23:58 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Upgrade the `Active Marches` section across `kingbot-ui`, `kingbot-syn`, and `kingbot`:

1. Show an outgoing march counter in the section header (e.g., `2/5 marches out`).
2. For each active march, render a card containing:
   - Primary and secondary commander portraits and names.
   - Target coordinates and mission type (e.g., `X:632 Y:620 [Barbarians]` or `[Rally]`).
   - Troop count, march status badge (`Going to attack`, `In rally`, `Gathering`), and troop health bar (`Health 100%`).
```

### UX-04 — Character/Account Switcher, 4 Summary KPIs & 'What the Bot Did' Cards
- Sheet: Full App UX · Priority: High · Start: 00:57 Asia/Muscat
- Scope: Add All Characters vs. single character switcher, 4 summary KPI cards (Total, Average per active day, Best day, Active days), and 'What the bot did' counters.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 00:57 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Upgrade the Gains analytics view in `kingbot-ui` and `kingbot-syn`:

1. Character/Account Switcher:
   - Provide an `All characters` button plus individual character/farm pills to inspect aggregated or per-character gains.
2. Four Summary Cards (`14 days` / `30 days`):
   - `Total`, `Average per active day`, `Best day` (with date), and `Active days`.
3. `What the bot did` Section (Last 30 days + Today):
   - Four cards tracking `Barbarians defeated`, `Gem mines gathered`, `Fort rallies started`, and `Rallies joined`.
```

### UX-05 — Fixed 5-Tab Mobile Bottom Nav Bar + Floating Assistant Trigger
- Sheet: Full App UX · Priority: Medium · Start: 01:56 Asia/Muscat
- Scope: Provide a fixed 5-tab mobile bottom navigation bar for one-handed ergonomics and a floating assistant button.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 01:56 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Improve mobile navigation ergonomics in `kingbot-ui`:

1. Fixed Bottom Navigation Bar (5 tabs):
   - `My slots`, `My gains`, `Settings`, `Scheduler`, and `Guide` with clear icons and active state styling.
2. Floating Assistant Button:
   - Fixed/floating action button opening the interactive Assistant drawer/modal for quick server commands and instant Q&A.
```

### UX-06 — Complete Live Status & Mobile App UX Overhaul (Combines UX-01 through UX-05)
- Sheet: Full App UX · Priority: Critical · Start: 02:55 Asia/Muscat
- Scope: Implement all five mobile UX and live telemetry enhancements (2x3 resource/AP grid, In The City, Active Marches, Gains switcher & bot activity, and 5-tab bottom nav + floating assistant) in one unified prompt.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 02:55 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Develop the control panel UI (`kingbot-ui`), data sync (`kingbot-syn`), and bot telemetry (`kingbot`) to deliver a comprehensive mobile-first dark-mode experience (with full Arabic RTL support alongside English) combining UX-01 through UX-05:

1. Main Dashboard & Live Telemetry:
   - 2x3 Grid: 5 resource cards (`Food`, `Wood`, `Stone`, `Gold`, `Gems`) with balance, icon, `+today` delta, and progress bar + 6th `AP` card (`current / max` and `%` full).
   - `In The City`: live queue cards for troop training (unit & tier, countdown, progress bar), materials production, and hospital healing.
   - `Active Marches`: outgoing counter (e.g., `2/5 marches out`) + per-march cards with primary/secondary commander portraits & names, coordinates & mission type, troop count, status badge, and health bar.
   - `Smart Scheduler Card`: displays current schedule status and next/current window end time with a quick edit button.

2. Gains Analytics (`14 days` / `30 days`):
   - `All characters` + individual character selector pills, resource filter pills with icons, 4 summary KPI cards (`Total`, `Average per active day`, `Best day`, `Active days`), `What the bot did` 4-card breakdown (`Barbarians defeated`, `Gem mines gathered`, `Fort rallies started`, `Rallies joined` with 30-day & Today counts), and a non-clipped mobile daily table with compact numbers (`21.4M`, `632.1K`) and resource icons in headers.

3. Navigation & Floating Assistant:
   - Fixed 5-tab bottom nav (`My slots`, `My gains`, `Settings`, `Scheduler`, `Guide`) + floating Assistant button.
```

## AI Assistant & Support

### AI-01 — AI Assistant Chat Window with Quick Question Chips
- Sheet: AI Assistant & Support · Priority: High · Start: 22:00 Asia/Muscat
- Scope: Add an AI assistant chat view with header, welcome greeting, and clickable quick-question chips (gem gathering setup, plans & pricing, account safety, capabilities).

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 22:00 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Upgrade the Assistant drawer/modal in `kingbot-ui` to include an interactive AI Assistant chat interface while preserving quick server commands:

1. Assistant Header:
   - Bot/AI badge icon, title, and subtitle summarizing supported topics (activities, panel, settings, plans).
2. Welcome Message & Quick Question Chips:
   - Display a greeting prompt and clickable quick-question chips (e.g., `How do I set up gem gathering?`, `What are the plans and pricing?`, `Is it risk free?`, `What can you help with?`) that send the query or surface an immediate structured answer.
```

### AI-02 — Chat Input Bar with Send Button & Accuracy Disclaimer
- Sheet: AI Assistant & Support · Priority: Medium · Start: 23:38 Asia/Muscat
- Scope: Add a bottom chat input bar with send button and a disclaimer note below indicating AI answers may not be 100% accurate.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 23:38 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Add the chat input bar and accuracy disclaimer to the AI Assistant in `kingbot-ui`:

1. Message Input Bar:
   - Text input (`Write your message...`) with a prominent send button and `Enter`-to-send support, rendering readable chat bubbles.
2. Disclaimer Footer:
   - Display a subtle disclaimer note at the bottom stating that generated AI information may not be 100% accurate.
```

### AI-03 — Quick Support Channel Pills (Discord / WhatsApp / Support)
- Sheet: AI Assistant & Support · Priority: High · Start: 01:16 Asia/Muscat
- Scope: Add a row of pill buttons above the chat input for direct access to Discord, WhatsApp, and Support configured via kingbot-syn.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 01:16 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Add quick-access support channel pill buttons above the message input in the Assistant view across `kingbot-ui` and `kingbot-syn`:

1. Channel Pills:
   - Render pill buttons with icons for `Discord`, `WhatsApp`, and `Support`.
2. Config-Driven Links:
   - Read channel URLs/targets from configuration in `kingbot-syn` so they can be updated centrally without code edits.
```

### AI-04 — Complete AI Assistant & Support Hub Build (Combines AI-01 through AI-03)
- Sheet: AI Assistant & Support · Priority: High · Start: 02:55 Asia/Muscat
- Scope: Build the complete AI Assistant and support channel bar (header, quick chips, support pills, input bar, and accuracy disclaimer) in one pass.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 02:55 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Build the complete AI Assistant & Support Hub in `kingbot-ui` and `kingbot-syn` (supporting RTL Arabic and LTR English cleanly) combining AI-01 through AI-03:

1. Header & Greeting + Quick Chips:
   - Include assistant header, welcome bubble, and clickable quick-question chips for common setup, safety, and plan questions.
2. Support Channel Pills + Chat Input + Disclaimer:
   - Include `Discord`, `WhatsApp`, and `Support` pill buttons wired to `kingbot-syn` config, a message input bar with send button, and a footer disclaimer noting that AI responses may not be 100% accurate.
```

## Guide & Rules

### GUIDE-01 — 'On This Page' Quick Jump Bar + 5-Step Getting Started Guide
- Sheet: Guide & Rules · Priority: High · Start: 22:00 Asia/Muscat
- Scope: Create a Guide page with an 'On This Page' collapsible jump bar and 5 numbered steps from buying/activating a slot to starting the bot (with automatic lowest graphics & muted sound).

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 22:00 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Create the `Guide` page in `kingbot-ui` (with RTL Arabic and LTR English support) starting with navigation and onboarding:

1. `On This Page` Jump Bar:
   - Collapsible section index allowing one-click smooth scroll/jump to major Guide sections (`Getting Started`, `Your Panel`, `Advanced Features`, `Smart Scheduler`, `Daily Gains`, `Event Log`, `Account & Notifications`, `Good Habits`, `Support`, `Discord`, `FAQ`).
2. `Getting Started` (5 Numbered Steps):
   - Numbered badges (1-5) explaining: purchasing/activating a slot, account preparation, signing into the game account, configuring activities & saving, and pressing `START`, plus a callout noting the bot automatically sets lowest graphics and mutes sound on launch.
```

### GUIDE-02 — Annotated Panel Diagram (1-7) & Detailed Section Walkthrough
- Sheet: Guide & Rules · Priority: High · Start: 22:12 Asia/Muscat
- Scope: Show an annotated panel mockup with numbered badges (1-7) matching detailed explanations below: Slot list, Slot header, Governor card, Preview/resources/AP, Settings & scheduler, Active marches, and Event log.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 22:12 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Add the `Your Panel` annotated walkthrough to the `Guide` page in `kingbot-ui`:

1. Annotated Mockup Card (Badges 1-7):
   - Visually mark zones 1-7: (1) Slot list with search & All/Active filter, (2) Slot header with rename pencil, status/expiry, `Get help`, `Game account`, and `START/STOP`, (3) Governor card (avatar, name, CH, VIP, alliance, power, kill points), (4) Live preview thumbnail, `Live stream`, current task, 5 resources + today delta, AP, and `Daily gains`, (5) `OPEN BOT SETTINGS` & `EDIT SCHEDULER` cards, (6) `Active marches`, and (7) `Event log`.
2. Numbered Explanations (1-7):
   - Match each badge 1-7 with clear explanations highlighting UI button names in pill badges.
```

### GUIDE-03 — Document 'In The City' Strip, Character Rotation Estimates & Freeze Days
- Sheet: Guide & Rules · Priority: Medium · Start: 22:25 Asia/Muscat
- Scope: Explain 'In The City' (read every 10 min and after character switch), 'Other Characters' estimated armies, and 'Freeze Days' (up to 7 days per 30 days, early unfreeze, and STOP vs. Freeze).

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 22:25 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Add advanced panel mechanics documentation to the `Guide` page in `kingbot-ui`:

1. `In The City` & Character Rotation Estimates:
   - Explain how the `In The City` strip shows research (including crystal research), construction, troop training, blacksmith materials, and hospital healing (read every 10 minutes and after character switches), plus how `Other Characters` shows estimated out-marching armies for non-active characters.
2. `Freeze Days` & `START / STOP`:
   - Explain pausing a slot's day countdown (up to 7 frozen days in any 30-day window; non-trial), `End the freeze now` adjusting expiry and refunding unused whole days, and how `STOP` / `START` behave.
```

### GUIDE-04 — Complete Core Guide Page Build (Combines GUIDE-01 through GUIDE-03)
- Sheet: Guide & Rules · Priority: High · Start: 22:38 Asia/Muscat
- Scope: Build the core Guide layout with 'On This Page', 5-step Getting Started, annotated 1-7 panel map, and advanced rotation/freeze sections.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 22:38 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Build the core `Guide` page in `kingbot-ui` combining GUIDE-01 through GUIDE-03 with clean dark-mode styling and RTL/LTR support:

1. `On This Page` jump menu + 5-step `Getting Started` flow + auto graphics/sound note.
2. Annotated `Your Panel` preview (1-7) with matching 1-7 guide points.
3. Explanations for `In The City` (10-min refresh), `Other Characters` estimated marches, `Freeze Days` (7/30 limit & early end), and `START / STOP`.
```

### GUIDE-05 — 'What the Status Means' Legend (7 States) & Offline/Unresponsive Alert
- Sheet: Guide & Rules · Priority: High · Start: 22:51 Asia/Muscat
- Scope: Document all 7 slot/bot statuses (Bot running, Starting..., On hold, Device not responding, No response from the game, Bot offline, Error) and a warning box to contact Support if prolonged.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 22:51 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Add the `What the Status Means` legend to the `Guide` page in `kingbot-ui`:

1. Document all 7 statuses with styled badges:
   - `Bot running`: actively executing tasks.
   - `Starting...`: launching the game (typically 1-2 min; auto-recovers if stuck past ~6 min).
   - `On hold`: temporarily paused for maintenance/check; resumes automatically.
   - `Device not responding`: temporary reachability issue; usually self-resolves within minutes.
   - `No response from the game`: game frozen; bot/system auto-restarts device (capped per day).
   - `Bot offline`: worker offline; commands queue until back online.
   - `Error`: error details shown below preview; usually self-recovers.
2. Add an amber warning callout advising users to open a Support ticket if `Device not responding` or `Bot offline` lasts more than a few minutes.
```

### GUIDE-06 — 'Signing In To The Game' Annotated Diagram (Code vs. Password)
- Sheet: Guide & Rules · Priority: Medium · Start: 23:04 Asia/Muscat
- Scope: Document signing into a Lilith/RoK account via one-time email code or password using an annotated 1-3 modal diagram.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 23:04 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Add the `Signing In To The Game` section to the `Guide` page in `kingbot-ui`:

1. Explain that the bot pauses during sign-in and resumes automatically afterward, guiding users to enable activities, press `Save`, and press `START`.
2. Include an annotated 1-3 sign-in modal diagram and steps:
   - (1) Choose `With a code` (one-time email code, no password stored) or `With password` (typed once and immediately discarded).
   - (2) Enter the game account email (and password if selected) and start sign-in.
   - (3) Enter the verification code sent to email.
```

### GUIDE-07 — Unified 'Queue Overview' Sidebar Reader Replacing Legacy Queue Checks
- Sheet: Guide & Rules · Priority: Critical · Start: 23:16 Asia/Muscat
- Scope: Use the in-game Queue Overview panel as a unified source for training, healing, building, research, alliance donations, material production, and scouts, removing redundant legacy code and showing live timers in UI.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 23:16 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Refactor `kingbot`, `kingbot-syn`, and `kingbot-ui` around a unified `queue_manager` driven by the in-game `Queue Overview` sidebar:

1. Clean Up Legacy Code:
   - Remove redundant legacy functions that manually inspect individual building/donation/material/scout/hospital screens separately when `Queue Overview` covers them, replacing them with `queue_manager`.
2. Read & Execute All Queue Sections:
   - Troop Training (`Infantry`, `Cavalry`, `Archers`, `Siege`): read timers, collect completed batches, and start new batches at configured tier.
   - Healing: read hospital status/capacity and heal when idle/configured.
   - Building & Tech Research: read active status and remaining time.
   - Alliance Donations: read remaining chances (e.g., `7/20`) and donate per settings.
   - Material Production: read available slots (e.g., `1/5`), collect finished items, and queue new materials.
   - Scout Queues: read `Scout A/B/C` status and dispatch idle scouts.
3. UI Display:
   - Render live countdown timers and per-queue toggles in `kingbot-ui`.
```

### GUIDE-08 — Verification Code Rules, Closing Sign-In Modal & Keyboard Character Warning
- Sheet: Guide & Rules · Priority: High · Start: 23:29 Asia/Muscat
- Scope: Document verification code rules (check spam, 1-min resend cooldown, always use newest code, stops after 3 wrong codes), closing modal while sign-in continues, button disappearing after governor read, and English/ASCII keyboard warning.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 23:29 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Add verification code details and keyboard character restrictions to the `Guide` page in `kingbot-ui`:

1. Verification Code & Sign-In Lifecycle:
   - Note checking spam folders, waiting 1 minute before requesting a new code, always using the newest code, and that 3 wrong codes halt sign-in.
   - Note that closing the modal does not cancel ongoing sign-in, `Game account` disappears once the governor is read, and a warning + `Sign in to your game account` appears if signed out later.
2. Keyboard Character Warning Callout:
   - Warn that some virtual/device input methods only type standard English letters, digits, and common symbols—use code sign-in if passwords contain special/non-ASCII characters.
```

### GUIDE-09 — 'Live Screen' Annotated Guide (1-3), Hourly View Quota, Idle Timeout & Session Logging
- Sheet: Guide & Rules · Priority: High · Start: 23:42 Asia/Muscat
- Scope: Document Live Screen (watch-only, save picture & fullscreen buttons, hourly quota badge green/orange/red, 5-min idle pause + 'Open again', single active tab per account, and session time/IP logging).

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 23:42 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Add the `Live Screen` section to the `Guide` page in `kingbot-ui` and `kingbot-syn`:

1. Annotated Live Screen Diagram (Badges 1-3):
   - (1) Watch-only view (taps on the stream canvas do not click in-game; use `Game account` to sign in).
   - (2) `Save picture` and `Full screen` controls.
   - (3) Hourly views-left badge (`green` = available, `orange` = last view, `red` = quota reached with minutes until next availability).
2. Stream Behavior & Security Notes:
   - Note choppy video depends on viewer internet and does not affect bot execution.
   - Explain single-session-per-account behavior (opening in another tab closes the previous one), auto-pause after ~5 minutes of no mouse movement with `Open again` button, and logging session timestamp + IP for security while keeping only the latest preview image.
```

### GUIDE-10 — 'Bot Settings' Annotated Guide (1-5), Commander Loading & Spend Warning
- Sheet: Guide & Rules · Priority: High · Start: 23:55 Asia/Muscat
- Scope: Document Bot Settings (1-5: profiles & reset, search & All/On/Changed filter, activity groups & switches, activity options/queues/commanders, Save/Discard bar), commander sync, and gem/speedup spend warning.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 23:55 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Add the `Bot Settings` section to the `Guide` page in `kingbot-ui` and `kingbot-syn`:

1. Annotated Bot Settings Diagram (Badges 1-5):
   - (1) `Profile` selector, `Save as profile`, `Manage my profiles`, and reset to default.
   - (2) Activity search box and `All / On / Changed` filters with active count (`X of Y activities on`).
   - (3) Activity groups and per-activity switches.
   - (4) Selected activity options, defaults, activity `Guide` link, per-activity reset, numbered troop queues (`Use this queue`), commander dropdowns (read from game once running, fallback `Any idle commander`, English/in-game names, `Read my alliance`), and `Copy to other characters`.
   - (5) Bottom `Save` / `Discard changes` bar and top-right `Saved` confirmation (or queued when offline).
2. Spend Warning Callout:
   - Add a warning card advising users to review options that spend gems, speedups, or items (e.g., Mysterious Merchant buys/refreshes, research speedups) before enabling.
```

### GUIDE-11 — 'Activity Groups' Overview: Gathering, Combat, City & Alliance Groups
- Sheet: Guide & Rules · Priority: Medium · Start: 00:08 Asia/Muscat
- Scope: Document Activity Groups in settings order, starting with Gathering (2), Combat (8), City (12), and Alliance (6) cards with descriptions and activity badges.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 00:08 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Add the `Activity Groups` section to the `Guide` page in `kingbot-ui`, starting with the first four groups in settings order and noting Solo vs. Leader plan availability:

1. `Gathering (2)`: `Gather Resources`, `Gather Gems`.
2. `Combat (8)`: `Chain Barbarians`, `Attack Barbarians`, `Attack Baulur`, `Attack Marauders`, `Join Rally`, `Rally Forts`, `Auto Shield`, `Fill Pass`.
3. `City (12)`: `Explore Fog`, `Investigate Mysterious Caves`, `Visit Tribal Villages`, `City Upgrade`, `Technology Research`, `Train Troops`, `Healing Troops`, `Materials Production`, `Crystal Production`, `Crystal Research`, `Collect City Resources`, `Repair City's Wall`.
4. `Alliance (6)`: `Alliance Help`, `Alliance Donation`, `Alliance Gifts`, `Territory Resource Earnings`, `Build The Alliance Flag`, `Transport Resources`.
```

### GUIDE-12 — 'Activity Groups' Remaining Groups: Rewards, Shops, Arena, Characters, Alliance & Kingdom Mgmt
- Sheet: Guide & Rules · Priority: Medium · Start: 00:21 Asia/Muscat
- Scope: Complete Activity Groups cards for Rewards (12), Shops (3), Arena (2), Characters (3), Alliance Management (4), and Kingdom Management (4).

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 00:21 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Complete the `Activity Groups` cards in the `Guide` page in `kingbot-ui` with the remaining groups:

1. `Rewards (12)`: `Chat With Hero`, `Dispatch`, `Open Mails`, `Quest Rewards`, `Event Rewards`, `Daily VIP Gifts`, `Daily Expedition Rewards`, `Lucerne Scrolls Rewards`, `Bastion Quests`, `Alliance Mobilization Quests`, `Open Free Chests At Tavern`, `Traveler's Tales`.
2. `Shops (3)`: `Mysterious Merchant's Boutique`, `VIP Shop`, `Melon Market`.
3. `Arena (2)`: `Sunset Canyon`, `Lost Canyon`.
4. `Characters (3)`: `Re-Login From Another Device`, `Switch Character`, `New Player Tutorial`.
5. `Alliance Management (4)` (Leader plan): `Resource Point`, `Daily Credit`, `Members`, `Alliance Mobilization Event`.
6. `Kingdom Management (4)` (Leader plan): `Rally Management`, `Title Management`, `City Finder`, `Scan Kingdom Data`.
```

### GUIDE-13 — 'Worth Knowing' Rules: Gem Farming 18h/Day Cap, Smart Scheduler & Conduct Score (<61)
- Sheet: Guide & Rules · Priority: High · Start: 00:33 Asia/Muscat
- Scope: Document and enforce key rules: tutorial blocking other tasks, Re-Login From Another Device default 10-min pause, Alliance Donation gold-only, Gather Gems troop range (5k-15k) & Steal gem mines & Gem-to-Gem (<75% load), smart scheduler requirement for gems (max 4h run, >=1h break, 0-15m start jitter, 18h/day UTC cap), Conduct Score <61 holding field marches while keeping city/Bastion/Mobilization tasks active, and mutual exclusion of barbarian activities.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 00:33 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Implement and document these `Worth Knowing` rules across `kingbot`, `kingbot-syn`, and `kingbot-ui`:

1. Gem Farming & Scheduler Rules:
   - Enforce smart scheduler on gem-gathering slots (max 4h per run, at least 1h rest between runs, 0-15m randomized start offset) and cap gem gathering at 18 hours per character per UTC day.
   - Support `Gem-to-Gem` (`Hold army outside city` when <75% full), optional `Steal gem mines`, and randomized troop counts within configured min/max range (default 5,000-15,000).
2. Conduct Score, Barbarian Exclusivity & Device Re-Login:
   - When Conduct Score is below 61, hold field/march/scout/transport activities (while allowing city tasks and Bastion/Mobilization quests) and resume automatically at 61+.
   - Ensure `Chain Barbarians`, `Attack Barbarians`, and `Attack Marauders` do not run concurrently (mark conflicts in UI).
   - Respect `Re-Login From Another Device` cooldown (default 10 minutes) when logging in from another device.
```

### GUIDE-14 — 'Worth Knowing' Rules: Rally Caps/Filters, Traveler's Tales, City Upgrade Bag & Baulur Timing
- Sheet: Guide & Rules · Priority: High · Start: 00:46 Asia/Muscat
- Scope: Document and implement: daily rally join cap (UTC), 'Join only the rallies of these players' list/ID filter, recalling nearest gathering march when queues are full (with 15/30/60m backoff if unused), Traveler's Tales daily equipment cap stop, City Upgrade 'Use resource items to fulfill the lack' only when covering full deficit, Bastion/Mobilization barbarian & fort rally rules (within 40 km), and Attack Baulur UTC arrival timing + 6h cooldown after defeat.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 00:46 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Implement and document these additional `Worth Knowing` rules across `kingbot`, `kingbot-syn`, and `kingbot-ui`:

1. Rallies, Gathering Recall & City Upgrade:
   - Support daily rally join cap (`UTC`), `Join only the rallies of these players` filter (alliance list or player ID), and recalling the closest gathering army when all march queues are busy (with 15m -> 30m -> 60m backoff if the freed queue isn't used).
   - Stop `Traveler's Tales` when daily equipment cap is reached until next reset.
   - In `City Upgrade`, open resource items from bag only when they cover the full missing amount for the upgrade.
2. Bastion/Mobilization & Baulur:
   - Use configured armies/commanders for barbarian quests in Bastion/Mobilization and rally nearest forts within 40 km one at a time.
   - In `Attack Baulur`, support selected Baulurs at scheduled UTC times (arriving on time, never early) and back off for 6 hours if a Baulur defeats an army.
```

### GUIDE-15 — Alliance & Kingdom Management Rules: Members, Mobilization Board, Rallies, Titles & City Finder
- Sheet: Guide & Rules · Priority: High · Start: 00:59 Asia/Muscat
- Scope: Document and implement Leader/R4/King tools: Members read & Accept/Blocked lists with role assignment (R4 cannot kick/demote another R4), Alliance Mobilization board read & R4/Leader free refresh (5-min update), Rally Management army removal & Excel export, Title Management & Excel export, City Finder + Kingdom City Ledger, and Scan Kingdom Data.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 00:59 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Implement and document Alliance & Kingdom Management features across `kingbot`, `kingbot-syn`, and `kingbot-ui` (Leader/R4/King scope):

1. Members & Mobilization Board:
   - Read members and pending applications; apply `Accept list` (accept + set rank once on join) and `Blocked list` (reject/kick; R4 cannot modify/kick another R4).
   - Read Mobilization quests, points, and holders; allow R4/Leader to refresh free quests (refreshed slot shows new quest ~5 minutes later).
2. Rallies, Titles, City Finder & Kingdom Scan:
   - `Rally Management`: monitor open alliance rallies, remove offending armies (R4/R5), and export rally/title logs to Excel.
   - `Title Management`: appoint titles on King or authorized R4 accounts; export title logs to Excel.
   - `City Finder` & `Kingdom City Ledger`: search by governor ID or name (ID searches map; name searches alliance/scan/ledger) and maintain shared map city ledger; support `Scan Kingdom Data`.
```

### GUIDE-16 — 'Settings Per Character' & Rotation Rules (General vs. Per-Character, Order & Switch Now)
- Sheet: Guide & Rules · Priority: Critical · Start: 01:12 Asia/Muscat
- Scope: Document and implement character rotation and per-character settings: random switch interval, 'Read the character list', 'General settings' vs. 'Play with its own settings' + 'Copy to other characters' + per-character turn duration, rotation ordering / 'Back to the game's order' / 'Switch characters in Star Characters', and 'Switch now' with >=10-minute minimum gap between switches.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 01:12 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Implement and document `Settings Per Character` and character rotation across `kingbot`, `kingbot-syn`, and `kingbot-ui`:

1. General vs. Per-Character Settings:
   - Add `Read the character list` and character rotation interval (random range between min and max minutes).
   - Treat base settings as `General settings` for characters without custom overrides, while allowing `Play with its own settings` per character, `Copy to other characters` per activity, and custom turn duration per character (e.g., longer for chaining barbarians, shorter for gathering).
2. Ordering, Starred Characters & Switch Now:
   - Support toggling rotation membership, reordering via arrows/position numbers, `Back to the game's order`, `Switch characters in Star Characters`, and `Switch now` with a minimum 10-minute cooldown between switches.
```

### GUIDE-17 — 'Profiles' System (Ready-Made & My Profiles up to 20) & Scheduler Profile Overrides
- Sheet: Guide & Rules · Priority: High · Start: 01:25 Asia/Muscat
- Scope: Document and implement Profiles ('Ready-made' and 'My profiles' up to 20 with rename/delete, loading without overwriting character rotation/per-character settings) and Smart Scheduler time-window profiles that revert to user settings when the window ends.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 01:25 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Implement and document the `Profiles` system across `kingbot-ui` and `kingbot-syn`:

1. Profile Management (Up to 20 Custom Profiles):
   - Organize `Profile` dropdown into `Ready-made` and `My profiles`, with `Save as profile` and `Manage my profiles` (rename/delete, max 20 user profiles).
   - Loading a profile populates slot settings without wiping character rotation or per-character overrides.
2. Scheduled Profile Overrides:
   - Allow assigning a profile to a Smart Scheduler run window so the bot uses that profile during the window and automatically restores the user's own settings when the window ends.
```

### GUIDE-18 — 'Smart Scheduler' Annotated Guide (1-4), UTC Ranges, Random Offset & Rule Validation
- Sheet: Guide & Rules · Priority: Critical · Start: 01:38 Asia/Muscat
- Scope: Build and document Smart Scheduler (1: enable toggle, 2: up to 8 UTC run ranges with current UTC clock, midnight wrap, >=30m duration, no overlap, 3: per-range profile & up to 30m random start/stop offset, 4: 'Today's plan' timeline & total hours) plus one-click presets (8/10/12/14h + 16/18h Risky badges), 'Fit to the rules', and <15m remaining skip.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 01:38 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Build and document `Smart Scheduler` across `kingbot-ui`, `kingbot-syn`, and `kingbot` combining UI and rules:

1. Annotated Scheduler Diagram & Controls (1-4):
   - (1) `Run this slot on a schedule` toggle (auto-enabled when adding a range).
   - (2) Up to 8 `Run ranges` in UTC (displaying live UTC time), supporting overnight ranges (e.g., `22:00 -> 02:00`), minimum 30-minute duration, and non-overlapping ranges.
   - (3) Optional `Profile` per range and `Random offset` up to 30 minutes shifting start/stop daily so no two days look identical.
   - (4) `Today's plan` visual timeline (`00:00` to `24:00`) and daily total run time.
2. Presets, Rule Validation & Execution Behavior:
   - Provide one-click plans (`8`, `10`, `12`, `14` hours, and `16`/`18` hour plans marked `Risky`).
   - Validate gem-gathering rules (max 4h run, >=1h break), highlight violating ranges in red, block saving invalid plans, and provide `Fit to the rules`.
   - Do not start a range with `<15` minutes remaining; honor manual `START`/`STOP` until next scheduled boundary; never start expired slots.
```

### GUIDE-19 — 'Daily Gains' & 'Event Log' Annotated Guides (Filter Tabs, Grouping & Clear Screen)
- Sheet: Guide & Rules · Priority: Medium · Start: 01:50 Asia/Muscat
- Scope: Document Daily Gains (UTC daily inflows—not subtracting spending, updated ~once/min while running, faint bar mark = no marches sent, empty = zero resource gained, 4 summary cards, 'What the bot did') and Event Log (refreshes every few seconds, keeps 7 days, 1-3 diagram: category tabs, short timestamped lines with duplicate grouping & red errors, Last 20/50/100 selector & Clear screen button without deleting logs).

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 01:50 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Add `Daily Gains` and `Event Log` walkthroughs to the `Guide` page in `kingbot-ui`:

1. `Daily Gains` Guide:
   - Clarify that totals reflect daily UTC inflows (gathering, city production, alliance territory, rewards; spending not subtracted), updated ~once per minute while active.
   - Explain the 1-4 walkthrough: period (`14`/`30 days`), resource & character filter, bar chart (faint mark = no marches sent; blank = zero gain), 4 summary cards, and `What the bot did`.
2. `Event Log` Guide (Annotated 1-3):
   - Explain live auto-refresh, 7-day retention, and points 1-3: (1) filter tabs (`All`, `Gathering`, `Barbarian/Rally`, `Rewards`, `Alliance`), (2) timestamped concise lines with duplicate grouping and red error highlights, and (3) `Last 20 / 50 / 100` selector and `Clear` button (clears view without deleting stored history).
```

### GUIDE-20 — Installable PWA App ('Use It As An App') & Device Push Notifications (5 Alert Types)
- Sheet: Guide & Rules · Priority: High · Start: 02:03 Asia/Muscat
- Scope: Support installing the panel as a PWA app (Android/Chrome/Edge Install button, iOS/iPadOS Safari Share -> Add to Home Screen, macOS File -> Add to Dock) and device push notifications ('Turn on notifications on this device', 'Send a test notification', and 5 alert toggles: Signed out of the game, Slot stuck or restarted, Period ending, Anti-cheat warning mail, Game account sign-in; changing password signs out other devices and resets notification/Telegram links).

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 02:03 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Add PWA installation support and browser/device push notifications across `kingbot-ui` and `kingbot-syn`, and document them in the `Guide` page:

1. PWA Installation (`Use It As An App`):
   - Provide PWA manifest/service worker and a panel card/instructions for installing on Android/Chrome/Edge (`Install`) and iPhone/iPad/Mac (`Add to Home Screen` / `Add to Dock`).
2. Push Notifications & Security Note:
   - Add `Turn on notifications on this device` and `Send a test notification` on `My Account`, with toggles for: `Signed out of the game`, `Slot stuck or restarted`, `Period ending`, `Anti-cheat warning mail`, and `Game account sign-in`.
   - Document that changing the panel password logs out other devices and clears notification/Telegram links so they are re-enabled intentionally.
```

### GUIDE-21 — 'Good Habits' Section: Periodic Check-Ins, Start Small, Read Before Spend & Breaks
- Sheet: Guide & Rules · Priority: Medium · Start: 02:16 Asia/Muscat
- Scope: Add 'Good Habits' to Guide: highlighted 'Look in now and then' card (latest picture, event log, notifications), plus 'Start small', 'Read before you spend', and 'Give the account a break'.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 02:16 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Add the `Good Habits` section to the `Guide` page in `kingbot-ui`:

1. Highlighted `Look in now and then` Card:
   - Emphasize checking the latest preview picture, event log, and push notifications so unexpected game screens or logouts are caught early.
2. Core Habits List:
   - `Start small` on new accounts and scale up activities gradually.
   - `Read before you spend` on options using gems, speedups, or items.
   - `Give the account a break` daily using the smart scheduler.
```

### GUIDE-22 — 'Support' Ticket System Rules: Attachments, Lifecycle, Quotas & Chat Widget Scope
- Sheet: Guide & Rules · Priority: High · Start: 02:29 Asia/Muscat
- Scope: Document Support tickets: 'New ticket' & slot 'Get help' (auto-selects Purchase/extension when expired), 'Answered' status, Discord/Telegram ticket sync, up to 3 images per message (PNG/JPEG/WebP, max 2MB each or paste), closed ticket 3-day reopen window & deleted 5 days after closing (auto-close after 30 days inactive), limits (max 3 open tickets, max 6 new tickets per 24h, max 60MB total images), and chat widget answering from Guide without account access.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 02:29 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Document and implement Support ticket workflows/rules across `kingbot-ui` and `kingbot-syn` and add the `Support` section to `Guide`:

1. Opening, Routing & Attachments:
   - Support opening tickets via `New ticket` or per-slot `Get help` (preselecting `Purchase or extension` on expired slots), showing `Answered` status, syncing with linked Discord/Telegram where configured, and allowing up to 3 images per message (`PNG`, `JPEG`, `WebP`, up to 2 MB each, or paste).
2. Ticket Lifecycle, Limits & Chat Widget:
   - Support reopening closed tickets within 3 days of reply/closure, deleting closed tickets after 5 days, auto-closing after 30 days of inactivity, and enforcing limits (up to 3 open tickets concurrently, up to 6 new tickets per 24h, up to 60 MB total image storage).
   - Clarify that the bottom-right chat assistant answers from the Guide and cannot access private account data.
```

### GUIDE-23 — 'Discord' Integration (/slots, /support, /ask, Invites, Contests, /suggest) & 'Your Review'
- Sheet: Guide & Rules · Priority: Medium · Start: 02:42 Asia/Muscat
- Scope: Document Discord linking (/link code & confirm, /unlink, DM privacy for notifications), commands (/slots, /support, /ask, /buy, /faq, /guide, /language, /help, /invite-link, /invites, /leaderboard, /suggest max 3/day), invite/contest eligibility (in server + Discord account >=30 days old), and 'Your Review' (free slot days for first review on first paid slot, public display by chosen name only—never email).

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 02:42 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Add `Discord` integration and `Your Review` sections to the `Guide` page in `kingbot-ui` and `kingbot-syn`:

1. Discord Linking, DMs & Commands:
   - Document linking via `My Account -> Discord` + `/link` confirmation (and `/unlink`), DM delivery for notifications (requiring server DMs enabled), and commands (`/slots`, `/support`, `/ask`, `/buy`, `/faq`, `/guide`, `/language`, `/help`, `/invite-link`, `/invites`, `/leaderboard`, and `/suggest` up to 3 per day).
   - Document invite/contest rules requiring invitees to remain in the server and have a Discord account at least 30 days old.
2. `Your Review`:
   - Document submitting/editing a review from `My Panel` or `My Account`, earning free slot days on the first review for a first paid slot (applied to earliest-expiring slot), and displaying approved reviews under the chosen name only (never email).
```

### GUIDE-24 — 'Questions (FAQ Accordion)' (13 Core FAQs) & 'Still Stuck? Open Support' Card
- Sheet: Guide & Rules · Priority: High · Start: 02:55 Asia/Muscat
- Scope: Add a collapsible 13-question FAQ accordion (game password, prompts/checks, unsaved/unapplied settings, Device not responding, hourly live screen limit, account warnings, playing on phone simultaneously, phone notifications, expired slot settings retention, trial auto-stop, adding another game account, pausing/freezing slot, earning days via invites) plus a 'Still stuck?' card with 'Open Support' button.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 02:55 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Add the `Questions` (13-item collapsible FAQ accordion) and `Still stuck?` support card at the bottom of the `Guide` page in `kingbot-ui`:

1. Expandable FAQ Accordion (`+` toggle):
   - Include the 13 core questions: game password policy, game prompting for input/checks, settings not changing after save, `Device not responding`, hourly live screen limit, account warnings, playing on phone at the same time, receiving phone notifications, settings after slot expiration, why a trial stops on its own, adding another game account, pausing/freezing a slot, and earning days by inviting friends.
2. `Still Stuck?` Card:
   - Render a callout card prompting users to open a ticket under Support and select the relevant slot, with an `Open Support` button.
```

## Feature Ideas

### TASK-01 — Smart Gem Farming
- Sheet: Feature Ideas · Priority: High · Start: 22:00 Asia/Muscat
- Scope: Dedicate marches to search for gem nodes during quiet hours while avoiding active combat zones.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 22:00 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Implement `Smart Gem Farming` across `kingbot`, `kingbot-syn`, and `kingbot-ui`:

1. Config (`kingbot-syn`):
   - Add `gem_farming` with `enabled`, `max_marches`, `search_radius`, `quiet_hours_only`, `avoid_combat_zones`, and `commander_preset`.
2. Bot (`kingbot`):
   - Search for level 1-2 gem nodes within radius without starving core resource marches; check nearby red attack lines/active fights before dispatching and skip risky nodes; apply jitter and log daily gems gathered in `status.json`.
3. UI (`kingbot-ui`):
   - Add `Smart Gem Farming` card with enable toggle, commander selector, quiet hours, and today's gems counter.
```

### TASK-02 — Balanced Resource Gathering
- Sheet: Feature Ideas · Priority: Medium · Start: 22:15 Asia/Muscat
- Scope: Read actual city stock and prioritize the lowest-ratio resource rather than single-resource bias.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 22:15 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Implement `Balanced Resource Gathering` across `kingbot`, `kingbot-syn`, and `kingbot-ui`:

1. Config (`kingbot-syn`):
   - Add `balanced_mode` and `target_ratios` (`food`, `wood`, `stone`, `gold`) inside gathering settings.
2. Bot (`kingbot`):
   - Read current city resource stock before dispatching a gathering march, compare against target ratios, and pick the most under-target resource while respecting commander presets.
3. UI (`kingbot-ui`):
   - Add `Balanced Mode` toggle, target ratio sliders/inputs, and current stock ratio indicators.
```

### TASK-03 — Auto-Join Rallies
- Sheet: Feature Ideas · Priority: High · Start: 22:31 Asia/Muscat
- Scope: Automatically join matching alliance rallies (barbarian forts / alliance targets) while preserving AP reserve.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 22:31 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Implement `Auto-Join Rallies` across `kingbot`, `kingbot-syn`, and `kingbot-ui`:

1. Config (`kingbot-syn`):
   - Add `auto_rally` with `enabled`, `target_types` (`forts` / `alliance`), `min_ap_reserve`, `max_march_time_minutes`, and `commander_preset`.
2. Bot (`kingbot`):
   - Monitor alliance rallies, join matching targets within max march time using configured commanders, and stop joining when AP is at or below `min_ap_reserve` without consuming AP potions.
3. UI (`kingbot-ui`):
   - Add `Auto-Join Rallies` card with enable toggle, commander preset, `min_ap_reserve`, and rallies-joined-today counter.
```

### TASK-04 — Auto-Shield
- Sheet: Feature Ideas · Priority: Critical · Start: 22:46 Asia/Muscat
- Scope: Activate peace shields automatically on scout/attack alerts or scheduled kill-event windows with urgent status alerts.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 22:46 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Implement `Auto-Shield` across `kingbot`, `kingbot-syn`, and `kingbot-ui`:

1. Config (`kingbot-syn`):
   - Add `auto_shield` with `enabled`, `trigger_on_scout`, `trigger_on_attack`, `shield_duration_hours` (`8` or `24`), and `scheduled_shield_times`.
2. Bot (`kingbot`):
   - Watch red incoming scout/attack alerts and scheduled times; halt secondary tasks immediately, open bag, apply configured shield, and emit an urgent alert in `status.json`.
3. UI (`kingbot-ui`):
   - Add `Auto-Shield` card showing current shield status, scout/attack triggers, and scheduled windows.
```

### TASK-05 — Auto-Return & Recall
- Sheet: Feature Ideas · Priority: High · Start: 23:02 Asia/Muscat
- Scope: Recall gathering marches immediately when an incoming hostile march targets a gathering node.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 23:02 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Implement `Auto-Return & Recall` across `kingbot`, `kingbot-syn`, and `kingbot-ui`:

1. Config (`kingbot-syn`):
   - Add `recall_on_threat` and `cooldown_minutes`.
2. Bot (`kingbot`):
   - Detect red enemy march lines targeting active gathering nodes, command immediate recall to city, and log the event.
3. UI (`kingbot-ui`):
   - Add `Auto-Return & Recall` toggle and avoided-attacks counter.
```

### TASK-06 — March Priority & Timeout
- Sheet: Feature Ideas · Priority: High · Start: 23:17 Asia/Muscat
- Scope: Cap concurrent marches, enforce strict search timeouts so stuck searches reset cleanly, and honor task priority order.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 23:17 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Implement `March Priority & Timeout` across `kingbot`, `kingbot-syn`, and `kingbot-ui`:

1. Config (`kingbot-syn`):
   - Add `march_control` with `max_concurrent_marches`, `search_timeout_seconds` (default `15`), and `priority_order` (e.g., `rallies`, `gathering`, `barbarians`).
2. Bot (`kingbot`):
   - Enforce a strict timeout on map searches and march list reads; on timeout, abort cleanly and return to city view without hanging or forcing a full restart, respecting `priority_order`.
3. UI (`kingbot-ui`):
   - Add concurrent march limit and priority ordering controls.
```

### TASK-07 — Task Commander Presets
- Sheet: Feature Ideas · Priority: High · Start: 23:33 Asia/Muscat
- Scope: Bind commander image picker UI to each task so primary and secondary commanders are configured per activity.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 23:33 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Implement `Task Commander Presets` across `kingbot`, `kingbot-syn`, and `kingbot-ui`:

1. Config (`kingbot-syn`):
   - Add `commander_presets` mapping tasks (`gathering_food`, `gathering_wood`, `gathering_stone`, `gathering_gold`, `barbarians`, `rallies`, `guardians`) to `primary` and `secondary` commander IDs/names.
2. UI (`kingbot-ui`):
   - Build a visual commander selector using `commanders/` images with search to assign primary/secondary commanders per task.
3. Bot (`kingbot`):
   - Read the task's preset when preparing a march and select matching primary/secondary commanders.
```

### TASK-08 — Smart Interval Scheduling
- Sheet: Feature Ideas · Priority: Critical · Start: 23:48 Asia/Muscat
- Scope: Split daily uptime into human-like work sessions and random breaks with click/timing jitter and daily hour caps.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 23:48 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Implement `Smart Interval Scheduling` across `kingbot`, `kingbot-syn`, and `kingbot-ui`:

1. Config (`kingbot-syn`):
   - Add `smart_schedule` with `enabled`, `daily_active_hours_limit` (e.g., `14`), `work_session_minutes`, `break_duration_minutes`, and `jitter_percent`.
2. Bot (`kingbot`):
   - Track daily active runtime, enter human-like rest intervals between sessions, stop for the day once `daily_active_hours_limit` is reached, and apply click coordinate jitter (+/-5px) and wait jitter.
3. UI (`kingbot-ui`):
   - Display daily active/remaining hours progress bar and current session state (`Active` / `On Break`).
```

### TASK-09 — Captcha Alert & Pause
- Sheet: Feature Ideas · Priority: Critical · Start: 00:04 Asia/Muscat
- Scope: Halt automation immediately when a verification/captcha popup appears, capture a screenshot, alert UI, and resume safely once solved.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 00:04 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Implement `Captcha Alert & Pause` across `kingbot`, `kingbot-syn`, and `kingbot-ui`:

1. Bot (`kingbot`):
   - Continuously detect verification/captcha popups, halt all automated clicks immediately, capture a clear screenshot, upload it to sync state, and set slot status to `captcha_required`.
2. UI (`kingbot-ui`):
   - Display an urgent warning modal with the captured screenshot, audio/visual alert, and a `Solved - Resume` button to safely resume execution.
```

### TASK-10 — Sunset Canyon & Guardians Hunter
- Sheet: Feature Ideas · Priority: Medium · Start: 00:19 Asia/Muscat
- Scope: Run free daily Sunset Canyon arena attempts against weaker opponents and hunt Guardians for free commander XP.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 00:19 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Implement `Sunset Canyon & Guardians Hunter` across `kingbot`, `kingbot-syn`, and `kingbot-ui`:

1. Config (`kingbot-syn`):
   - Add `events_hunter` with `sunset_canyon_enabled` (use free daily attempts against lowest-power opponent) and `guardians_enabled` (hunt guardians with designated commanders without spending AP).
2. Bot (`kingbot`):
   - Execute free Sunset Canyon battles against weakest available target and dispatch guardian-hunting march on schedule without AP potions.
3. UI (`kingbot-ui`):
   - Add toggles for Sunset Canyon and Guardians plus commander selection for Guardians.
```

### TASK-11 — Mysterious Merchant & Tavern Chests
- Sheet: Feature Ideas · Priority: Medium · Start: 00:35 Asia/Muscat
- Scope: Open free tavern chests and buy resource-only items from Mysterious Merchant while protecting gems.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 00:35 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Implement `Mysterious Merchant & Tavern Chests` across `kingbot`, `kingbot-syn`, and `kingbot-ui`:

1. Config (`kingbot-syn`):
   - Add `merchant_tavern` with `tavern_free_chests`, `merchant_buy_resources_only`, and `merchant_free_refresh`.
2. Bot (`kingbot`):
   - Open Mysterious Merchant when visible and purchase items priced in Food/Wood/Stone/Gold only (strictly blocking gem purchases), plus claim free Tavern chests.
3. UI (`kingbot-ui`):
   - Add toggles and a counter for resource items purchased today.
```

### TASK-12 — Event Milestone Claimer
- Sheet: Feature Ideas · Priority: Low · Start: 00:50 Asia/Muscat
- Scope: Periodically check the events hub and claim completed milestone rewards before events expire.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 00:50 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Implement `Event Milestone Claimer` across `kingbot`, `kingbot-syn`, and `kingbot-ui`:

1. Bot (`kingbot`):
   - Run a periodic check (e.g., every 2 hours) on the events hub to detect notification badges/claim buttons and collect completed rewards.
2. UI (`kingbot-ui`):
   - Add an enable/disable toggle for automatic event milestone claiming.
```

### TASK-13 — Auto-Build Alliance Flags/Fortress
- Sheet: Feature Ideas · Priority: Medium · Start: 01:06 Asia/Muscat
- Scope: Send a light troop march to contribute to active alliance flags or fortresses and earn alliance credits.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 01:06 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Implement `Auto-Build Alliance Flags/Fortress` across `kingbot`, `kingbot-syn`, and `kingbot-ui`:

1. Config (`kingbot-syn`):
   - Add `alliance_build` with `enabled`, `troop_count` (default `1000`), and `keep_one_march_busy`.
2. Bot (`kingbot`):
   - Check unfinished alliance flags/fortresses and dispatch a march with `troop_count` if no march from the account is already building.
3. UI (`kingbot-ui`):
   - Add `Auto-Build Alliance Structures` toggle and `troop_count` input.
```

### TASK-14 — Overflow Resource Donation
- Sheet: Feature Ideas · Priority: Low · Start: 01:21 Asia/Muscat
- Scope: Route/supply overflow resources when city storage approaches capacity (>90%) to prevent waste.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 01:21 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Implement `Overflow Resource Donation` across `kingbot`, `kingbot-syn`, and `kingbot-ui`:

1. Bot (`kingbot`):
   - When any resource exceeds ~90% of storage capacity, trigger overflow supply/routing per settings to prevent capping losses.
2. UI (`kingbot-ui`):
   - Add an overflow auto-route toggle under resource settings.
```

### TASK-15 — If-This-Then-That Rules Engine
- Sheet: Feature Ideas · Priority: High · Start: 01:37 Asia/Muscat
- Scope: Create visual automation rules linking account metrics (such as AP or hospital fill %) to task actions.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 01:37 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Implement an `If-This-Then-That Rules Engine` across `kingbot`, `kingbot-syn`, and `kingbot-ui`:

1. Config (`kingbot-syn`):
   - Add `automation_rules` array with `{ id, enabled, condition_metric, operator, threshold, action_type, target_task }` (e.g., `ap < 300 -> disable barbarians`, `hospital_fill_percent > 80 -> enable healing`).
2. Bot (`kingbot`):
   - Evaluate enabled rules each cycle, execute matching actions, and log rule triggers.
3. UI (`kingbot-ui`):
   - Provide a simple rule builder (`condition + operator + value -> action`) without manual JSON editing.
```

### TASK-16 — Performance & Yield Analytics
- Sheet: Feature Ideas · Priority: Medium · Start: 01:52 Asia/Muscat
- Scope: Daily and weekly charts tracking power growth, resources/gems gained, barbarians/rallies, and active hours.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 01:52 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Implement `Performance & Yield Analytics` across `kingbot-syn` and `kingbot-ui`:

1. Sync (`kingbot-syn`):
   - Persist daily snapshots per slot in `history/daily_stats.json` recording resources gathered, gems, barbarians, active runtime hours, and restarts.
2. UI (`kingbot-ui`):
   - Render interactive charts comparing 7-day and 30-day performance per account and slot.
```

### TASK-17 — On-Demand Live Screenshot & Action
- Sheet: Feature Ideas · Priority: High · Start: 02:08 Asia/Muscat
- Scope: On-demand screenshot capture in UI plus optional remote tap at (X, Y) coordinates with confirmation capture.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 02:08 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Implement `On-Demand Live Screenshot & Action` across `kingbot`, `kingbot-syn`, and `kingbot-ui`:

1. Control State (`kingbot-syn`):
   - Support `remote_command` actions: `capture_screen` and `tap_xy` (`x`, `y`).
2. Bot (`kingbot`):
   - Capture and upload a fresh screenshot on `capture_screen`; perform tap at `(x, y)` on `tap_xy` and upload a follow-up screenshot.
3. UI (`kingbot-ui`):
   - Add a live view card with `Capture Now` button and optional coordinate tap dispatch.
```

### TASK-18 — Smart Webhook Alerts
- Sheet: Feature Ideas · Priority: High · Start: 02:23 Asia/Muscat
- Scope: Send instant Telegram/Discord notifications only for critical events (attack, shield drop, captcha, offline, expiring).

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 02:23 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Implement `Smart Webhook Alerts` across `kingbot`, `kingbot-syn`, and `kingbot-ui`:

1. Config (`kingbot-syn`):
   - Add `alerts` toggles (`on_attack`, `on_shield_drop`, `on_captcha`, `on_server_offline`, `on_subscription_expiring`) while keeping tokens/webhooks stored securely/locally.
2. Bot (`kingbot`):
   - Dispatch immediate alert messages containing slot name, event type, and screenshot when available.
3. UI (`kingbot-ui`):
   - Add event toggles and a `Send Test Alert` button.
```

### TASK-19 — Viewport & Device Profile Randomizer
- Sheet: Feature Ideas · Priority: Medium · Start: 02:39 Asia/Muscat
- Scope: Use relative screen coordinates and vary virtual device profiles per emulator instance to avoid identical fingerprints.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 02:39 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Implement `Viewport & Device Profile Randomizer` across `kingbot` and `kingbot-syn`:

1. Bot (`kingbot`):
   - Use relative/percentage-based screen coordinates rather than hardcoded pixel coordinates where possible, and randomize virtual device profiles/identifiers per instance during provisioning.
```

### TASK-20 — Network Drop Auto-Resume
- Sheet: Feature Ideas · Priority: High · Start: 02:55 Asia/Muscat
- Scope: Detect disconnect/maintenance dialogs and use exponential backoff before retrying to prevent rapid retry loops.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 02:55 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Implement `Network Drop Auto-Resume` in `kingbot`:

1. Bot (`kingbot`):
   - Detect disconnect/reconnecting/maintenance prompts in-game, pause rapid tap retries, and apply exponential backoff (e.g., 30s -> 2m -> 5m) before retrying or restarting the game.
```

## Menu & Free Tools

### TOOLS-00 — Top Bar (Notifications Badge 9+, AR/EN Switcher) & Main Hamburger Dropdown Menu
- Sheet: Menu & Free Tools · Priority: Critical · Start: 22:00 Asia/Muscat
- Scope: Build the top header bar with notification bell + golden counter badge (e.g., 9+), language switcher (AR/EN), and hamburger menu opening a styled dropdown with Guide, Support, Referrals, My Account, collapsible Free Tools (6 tools), community links (Discord, WhatsApp, WhatsApp Group, Telegram, YouTube), and Sign out.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 22:00 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Build the top navigation bar and main dropdown menu in `kingbot-ui` and `kingbot-syn` (supporting RTL Arabic and LTR English):

1. Top Header Bar:
   - Rounded bordered hamburger menu button, language switcher (`AR / EN`) with globe icon, and notification bell with a circular golden badge (e.g., `9+`) opening notifications on click.
2. Main Dropdown Menu:
   - Render a clean dark dropdown containing in order:
     - `Guide`
     - `Support`
     - `Referrals`
     - `My Account`
     - Collapsible `Free tools` accordion expanding to: `Alliance mail generator`, `Speedup calculator`, `Equipment & crafting`, `Commander guide`, `Event calendar`, and `Crystal tech`.
     - Community links read from `kingbot-syn` config: `Discord`, `WhatsApp`, `WhatsApp Group`, `Telegram`, `YouTube`.
     - `Sign out` action at the bottom.
```

### TOOLS-01 — Unified Navigation Drawer with Free Tools & Community Links
- Sheet: Menu & Free Tools · Priority: High · Start: 22:19 Asia/Muscat
- Scope: Unify primary routes, collapsible Free Tools, community links, and Sign out in the navigation drawer.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 22:19 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Ensure the navigation drawer in `kingbot-ui` seamlessly routes to `Guide`, `Support`, `Referrals`, `My Account`, the collapsible `Free tools` section, community channels (`Discord`, `WhatsApp`, `WhatsApp Group`, `Telegram`, `YouTube`), and `Sign out` across mobile and desktop.
```

### TOOLS-02 — Alliance Mail Generator (Colors, Formatting, Templates & One-Click Copy)
- Sheet: Menu & Free Tools · Priority: High · Start: 22:39 Asia/Muscat
- Scope: Free tool for formatting Rise of Kingdoms alliance/kingdom mails with colors, bold/italic, font sizes, presets, live preview, and one-click copy.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 22:39 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Build the `Alliance mail generator` tool under `Free tools` in `kingbot-ui`:

1. Formatting & Presets:
   - Provide color swatches, bold/italic toggles, size controls, and ready-made templates (welcome mail, KvK rules, weekly events, shield reminders).
2. Live Preview & Copy:
   - Show live formatted preview with character count and a one-click copy button.
```

### TOOLS-02B — Alliance Mail Generator: Top Social Bar, 3-Tab Switcher, 8-Button Formatting Grid & Selection Editor
- Sheet: Menu & Free Tools · Priority: High · Start: 22:59 Asia/Muscat
- Scope: Upgrade Alliance Mail Generator with: top header with social icons (Discord, WhatsApp, Telegram, YouTube) + hamburger menu + breadcrumb (`Home / Rise of Kingdoms Alliance Mail Generator`) + `Free tool` pill badge; 3-tab switcher (`Mail editor`, `Templates 10`, `My templates`); 2x4 formatting grid (`Bold`, `Italic`, `Bold italic`, `Size`, `Color`, `Gradient`, `Undo`, `Clear`); and selection-based mail composer with live preview and copy.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 22:59 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Upgrade the `Alliance Mail Generator` tool under `Free tools` in `kingbot-ui` (supporting RTL Arabic and LTR English cleanly) with the exact layout and controls:

1. Header, Breadcrumb & Tool Badge:
   - Include quick social icon pills (`Discord`, `WhatsApp`, `Telegram`, `YouTube`) and the menu trigger in the header.
   - Display breadcrumb navigation (`Home / Rise of Kingdoms Alliance Mail Generator`), a `Free tool` pill badge, a prominent title, and concise instructions on styling text and copying into the game.

2. Three-Tab Switcher (`Mail editor` / `Templates 10` / `My templates`):
   - Provide a segmented 3-tab bar switching between `Mail editor`, `Templates` (with badge count, e.g., `10` ready-made templates), and `My templates` (user-saved custom templates).

3. 2x4 Formatting Toolbar Grid:
   - Render a clean 2-row x 4-column card button grid containing:
     * Row 1: `Bold` (`B`), `Italic` (`I`), `Bold italic` (`I`), `Size` (`Tt`)
     * Row 2: `Color` (palette icon), `Gradient` (gradient bar icon), `Undo` (undo arrow), `Clear` (trash icon)

4. Selection-Based Mail Composer & Live Preview/Copy:
   - Provide a rich text/markup composer allowing the user to select text or apply styles (`Bold`, `Italic`, `Bold italic`, `Size`, `Color`, `Gradient`), with `Undo` and `Clear`, a live game-styled preview, and one-click copy.
```

### TOOLS-02C — Mail Editor Box, 2,000-Char Counter (Tags Included), Draft Persistence, Save & Live Parchment Preview
- Sheet: Menu & Free Tools · Priority: High · Start: 23:18 Asia/Muscat
- Scope: Add mail input textarea with helper instruction ('Select text first, then pick a style. With nothing selected, the tags go where the cursor is.'), live character counter (`0 / 2,000` including tags), local browser draft auto-save, Preview mode toggle (desktop/mobile icons), `Save` button, `Copy code` button, parchment-style live preview card (`Your mail appears here as you type.`), and note that game font/sizes can differ slightly.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 23:18 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Build the mail editing, character counter, draft persistence, and live preview section for `Alliance Mail Generator` in `kingbot-ui` (supporting RTL Arabic and LTR English cleanly):

1. Editor Textarea, Tag Hint & 2,000-Char Counter:
   - Provide a dark mail composer textarea with guidance explaining that selecting text applies styling around the selection while placing style tags at the cursor when nothing is selected.
   - Show a live character counter (`X / 2,000`) explicitly counting markup/style tags as well, and persist drafts automatically in browser storage.

2. Preview Controls, Save & Copy Code:
   - Add `Preview` label with preview mode switcher icons (desktop/mobile view), `Save` button (saves to `My templates`), and `Copy code` button.
   - Render a warm parchment/mail-styled preview box showing formatted output live as the user types, with a note that in-game font rendering and sizes can vary slightly.
```

### TOOLS-02D — 'How To Use It' (1-3), Mail FAQ Accordion (5 Questions), Leader Plan Promo Card & 'More Free Tools'
- Sheet: Menu & Free Tools · Priority: Medium · Start: 23:38 Asia/Muscat
- Scope: Add `HOW TO USE IT` numbered cards (1: write text or start from a template; 2: select text and pick bold, italic, size, color, or gradient with live preview; 3: press `Copy code`, open Alliance Mail in-game, and paste), `QUESTIONS` accordion (colored text in RoK mail, supported styles, running out of characters quickly due to tags, who can send alliance mail, and free availability), `Leading an alliance takes time` leader-plan card with `See how it works ->` link, `More free tools` navigation list with `->` arrows, and compact footer brand tag.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 23:38 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Add the lower guidance, FAQ, leader plan promo, and `More free tools` sections to `Alliance Mail Generator` in `kingbot-ui`:

1. `How To Use It` (Steps 1-3):
   - Render 3 numbered cards: (1) write text or start from a template, (2) select text and apply bold, italic, size, color, or gradient while inspecting the preview, and (3) press `Copy code`, open Alliance Mail in-game, and paste.

2. `Questions` Accordion & Leader Plan Promo Card:
   - Add expandable `QUESTIONS` items covering: writing colored text in RoK mail, which styles work in mail, why character limits run out fast (markup tags count toward limit), who can send alliance mail, and whether the tool is free.
   - Include a highlighted leader-management card (`Leading an alliance takes time`) with a `See how it works ->` link.

3. `More Free Tools` Links & Footer Brand Tag:
   - List quick arrow links (`->`) to `Speedup calculator`, `Equipment & crafting`, `Commander guide`, `Event calendar`, and `Crystal tech`, followed by a clean footer brand caption.
```

### TOOLS-03 — Speedup Calculator (Universal, Training, Building, Research & Healing)
- Sheet: Menu & Free Tools · Priority: High · Start: 23:58 Asia/Muscat
- Scope: Free calculator summing speedup items across Universal, Training, Building, Research, and Healing into days, hours, and minutes.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 23:58 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Build the `Speedup calculator` tool under `Free tools` in `kingbot-ui`:

1. Category Inputs:
   - Support entering speedup denominations (`1m`, `5m`, `10m`, `15m`, `30m`, `60m`, `3h`, `8h`, `15h`, `24h`, `3d`, `7d`) across `Universal`, `Training`, `Building`, `Research`, and `Healing`.
2. Totals & Reset:
   - Display per-category and combined totals (`Universal + category`) formatted in days, hours, and minutes, plus a clear/reset action.
```

### TOOLS-03B — Speedup Calculator: 3-Tab Switcher (Speedups/Training/Healing), Collapsible Bag Grids & Denomination Inputs
- Sheet: Menu & Free Tools · Priority: High · Start: 00:17 Asia/Muscat
- Scope: Build Speedup Calculator with breadcrumb (`Home / Rise of Kingdoms Speedup Calculator`), `Free tool` pill badge, 3-tab switcher (`Speedups`, `Training`, `Healing`), `Speedups in your bag` card with clear-bag icon button, and collapsible (`-`/`+`) denomination input grids (`1m`, `3m`, `5m`, `10m`, `15m`, `30m`, `1h`, `3h`, `8h`, `15h`, `1d`) across `Universal`, `Training`, `Healing`, `Building`, and `Research`.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 00:17 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Build the `Speedup calculator` tool under `Free tools` in `kingbot-ui` (supporting RTL Arabic and LTR English cleanly) with the exact layout and controls:

1. Header, Breadcrumb & Mode Tabs:
   - Display breadcrumb (`Home / Rise of Kingdoms Speedup Calculator`), `Free tool` badge, title, and concise description noting values come from game data.
   - Add a 3-tab switcher (`Speedups`, `Training`, `Healing`).

2. Bag Card & Collapsible Denomination Grids:
   - Render `Speedups in your bag` with a clear-all bag button and collapsible sections (`-`/`+` toggle) for `Universal` (including `1m`, `3m`, `5m`, `10m`, `15m`, `30m`, `1h`, `3h` and higher denominations) plus `Training`, `Healing`, `Building`, and `Research` (`1m`, `5m`, `10m`, `15m`, `30m`, `1h`, `3h`, `8h`, `15h`, `1d`).
   - Provide numeric inputs inside each denomination tile with icon + duration badge.
```

### TOOLS-03C — All Speedups Total Card, Combined Totals, 'How To Use It' (1-3), Training FAQ, Promo & Site Footer
- Sheet: Menu & Free Tools · Priority: Medium · Start: 00:37 Asia/Muscat
- Scope: Add `ALL SPEEDUPS` summary card (`0.0 days` prominent display), breakdown rows for `Universal`, `Training`, `Healing`, `Building`, `Research`, plus combined rows (`Universal + Training`, `Universal + Healing`, `Universal + Building`, `Universal + Research`), browser persistence notice (`Your numbers stay in this browser.`), `HOW TO USE IT` steps (1-3), `QUESTIONS` accordion (T5 training duration, T5 troop cost, valid training speedups, where numbers come from), `Let the training run while you sleep` promo card (`See how it works ->`), `More free tools` links, and site footer (`24/7 cloud helper for Rise of Kingdoms`, social icons, `PRODUCT` and `FREE TOOLS` columns).

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 00:37 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Add the totals summary card, combined rows, `How To Use It`, `Questions`, promo card, `More free tools`, and site footer to `Speedup calculator` in `kingbot-ui`:

1. Totals Summary & Combined Breakdown Card:
   - Display `ALL SPEEDUPS` (`X.X days`), individual totals for `Universal`, `Training`, `Healing`, `Building`, and `Research`, and combined totals (`Universal + Training`, `Universal + Healing`, `Universal + Building`, `Universal + Research`), plus browser storage persistence notice.

2. `How To Use It` (Steps 1-3) & `Questions` Accordion:
   - Render numbered steps (1: enter speedup counts, 2: open `Training` or `Healing` and enter troop counts & speed bonus, 3: view time, resources, power, and speedup sufficiency).
   - Add expandable `QUESTIONS` items covering T5 training time, T5 troop cost, speedups usable for training, and data source.

3. Promo Card, `More free tools` & Footer:
   - Include a training-automation promo card (`Let the training run while you sleep` with `See how it works ->`), quick links under `More free tools` (`Alliance mail generator`, `Equipment & crafting`, `Commander guide`, `Event calendar`, `Crystal tech`), and a site footer with brand tagline, social links, and `PRODUCT` / `FREE TOOLS` columns.
```

### TOOLS-04 — Equipment Browser & Crafting Material Calculator
- Sheet: Menu & Free Tools · Priority: Medium · Start: 00:57 Asia/Muscat
- Scope: Free tool to browse equipment by troop/gathering type, slot, and rarity and calculate crafting materials, gold, and combined stats.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 00:57 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Build the `Equipment & crafting` tool under `Free tools` in `kingbot-ui`:

1. Filterable Catalog:
   - Filter gear by troop/gathering category (`Infantry`, `Cavalry`, `Archers`, `Leadership`, `Gathering`), slot, and rarity.
2. Crafting & Stat Totals:
   - Calculate total required materials (`Leather`, `Iron`, `Ebony`, `Bone`), gold, and aggregated stat bonuses for selected pieces.
```

### TOOLS-04B — Equipment & Crafting Calculator: 2-Tab Switcher (Equipment / My Crafting List), Search, Slot & Quality Pills
- Sheet: Menu & Free Tools · Priority: High · Start: 01:16 Asia/Muscat
- Scope: Build Equipment & Crafting Calculator with breadcrumb (`Home / Rise of Kingdoms Equipment & Crafting Calculator`), `Free tool` badge, 2-tab switcher (`Equipment` / `My crafting list`), `Search equipment` input, `SLOT` filter pills (`All`, `Weapons`, `Helms`, `Chest`, `Gloves`, `Legs`, `Boots`, `Accessories`), `QUALITY` filter pills (`All`, `LEGENDARY`, `EPIC`, `ELITE`, `ADVANCED`, `NORMAL`), and filtered result count (`78 pieces` example).

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 01:16 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Build the search, slot, and quality filtering controls for `Equipment & crafting calculator` under `Free tools` in `kingbot-ui` (supporting RTL Arabic and LTR English cleanly):

1. Header, Breadcrumb & Mode Tabs:
   - Display breadcrumb (`Home / Rise of Kingdoms Equipment & Crafting Calculator`), `Free tool` badge, title, and concise description noting values come from game data.
   - Add a 2-tab switcher (`Equipment` and `My crafting list`).

2. Search, SLOT & QUALITY Filter Pills:
   - Provide a `Search equipment` input box.
   - Render `SLOT` filter pills: `All`, `Weapons`, `Helms`, `Chest`, `Gloves`, `Legs`, `Boots`, `Accessories`.
   - Render `QUALITY` filter pills: `All`, `LEGENDARY`, `EPIC`, `ELITE`, `ADVANCED`, `NORMAL` with color-coded quality styling and a live count label (e.g., `78 pieces`).
```

### TOOLS-04C — Equipment Cards (Icon, Set Name & Stat Bonus), Seasonal Note & 'How To Use It' (Steps 1-2)
- Sheet: Menu & Free Tools · Priority: Medium · Start: 01:36 Asia/Muscat
- Scope: Render equipment cards showing piece icon with quality border, piece name, slot + optional set name (e.g., Hellish Wasteland Set, Eternal Empire Set, Dragon's Breath Set, Witch's Wardrobe, Garb of the Glorious Goddess, Lupine Vestments), stat bonus (e.g., Cavalry Attack +25%, Infantry Attack +25%, Archer Defense +25%, Gathering Speed +15%, Troop Attack +15%, Artifacts & Curios), seasonal client availability note, and `HOW TO USE IT` steps (1: filter by slot/quality or search; 2: open piece for stats, set bonus, crafting & refining cost).

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 01:36 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Add the equipment catalog cards, seasonal note, and `HOW TO USE IT` section to `Equipment & crafting calculator` in `kingbot-ui`:

1. Equipment Catalog Cards & Dataset Structure:
   - Display each item card with an icon frame matching its quality border, piece name, slot and optional set name (e.g., `Weapons`, `Helms`, `Chest`, `Gloves`, `Legs`, `Boots`, `Accessories`, sets, artifacts, and curios), and primary stat bonus (e.g., attack/defense/health/gathering speed percentages).
   - Include a note stating that newest season pieces appear once their names reach the game client.

2. `HOW TO USE IT` Steps:
   - Render numbered guide cards explaining: (1) filtering by slot and quality or searching by name, and (2) opening a piece to inspect stats, set bonus, crafting cost, and refining/special talent cost.
```

### TOOLS-05 — Commander Guide & Pairings Browser (Using Commander Assets)
- Sheet: Menu & Free Tools · Priority: High · Start: 01:56 Asia/Muscat
- Scope: Free commander reference using existing commander images to browse commanders, recommended pairings, skill priorities, and roles.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 01:56 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Build the `Commander guide` tool under `Free tools` in `kingbot-ui` using the existing commander image assets:

1. Search & Filters:
   - Search by commander name and filter by specialty (`Infantry`, `Cavalry`, `Archers`, `Leadership`, `Rally`, `Garrison`, `Gathering`) and rarity.
2. Commander Details:
   - Display recommended primary/secondary pairings, skill upgrade priority (e.g., `5-5-1-1`), and role notes.
```

### TOOLS-06 — Recurring Event Calendar (UTC Schedule & Resource Tips)
- Sheet: Menu & Free Tools · Priority: Medium · Start: 02:15 Asia/Muscat
- Scope: Free UTC event schedule showing recurring events (MGE, Wheel of Fortune, More Than Gems, etc.) with tips for optimizing gems and speedups.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 02:15 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Build the `Event calendar` tool under `Free tools` in `kingbot-ui`:

1. UTC Schedule & Categories:
   - Display current and upcoming recurring events in UTC with category tags and resource optimization tips (e.g., saving gems for `More Than Gems` or timing speedups with event milestones).
```

### TOOLS-07 — Seasonal Crystal Tech Cost & Time Calculator
- Sheet: Menu & Free Tools · Priority: High · Start: 02:35 Asia/Muscat
- Scope: Free calculator estimating crystal cost, research time, and season points for crystal tech upgrades with Crystal Research Center discount support.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 02:35 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Build the `Crystal tech` calculator under `Free tools` in `kingbot-ui`:

1. Inputs & Discounts:
   - Configure current and target levels for crystal technologies along with Crystal Research Center / alliance discount percentages.
2. Summary Outputs:
   - Calculate discounted crystal required, total research duration, and season points gained.
```

### TOOLS-08 — Complete Header, Main Menu & 6 Free Tools Build (Combines TOOLS-00 through TOOLS-07)
- Sheet: Menu & Free Tools · Priority: High · Start: 02:55 Asia/Muscat
- Scope: Build the top bar, main dropdown menu, and all 6 free tools in one comprehensive prompt.

```text
[NIGHTLY AUTO-RUN POLICY — ASIA/MUSCAT (+04) | WINDOW: 22:00 - 03:00]
- Trigger / Start Time (Asia/Muscat): 02:55 Asia/Muscat
- Execution Rules: Take all the time needed to complete thoroughly. Do NOT enforce an end-time cutoff and do NOT stop early if not finished by 03:00.
- Permissions Upon Start: Full access granted across all repositories (`kingbot`, `kingbot-syn`, `kingbot-ui`), files, configs, UI components, and automation logic.
--------------------------------------------------------------------------------

Build the top header bar, main dropdown menu, and all 6 free tools in `kingbot-ui` (wired to `kingbot-syn` config where applicable) combining TOOLS-00 through TOOLS-07:

1. Top Header & Main Dropdown Menu:
   - Include notification bell with badge (`9+`), `AR/EN` toggle, and menu drawer with `Guide`, `Support`, `Referrals`, `My Account`, collapsible `Free tools`, community links (`Discord`, `WhatsApp`, `WhatsApp Group`, `Telegram`, `YouTube`), and `Sign out`.
2. Six Free Tools:
   - `Alliance mail generator`, `Speedup calculator`, `Equipment & crafting`, `Commander guide`, `Event calendar`, and `Crystal tech` with responsive dark/gold styling.
```

# Pause/Resume Feature

## Overview

AgenticTown now supports **pausing and resuming** the automatic cycle scheduler to conserve resources when the simulation is not actively being monitored.

## How It Works

### UI Control
- **Pause Button (⏸ Pause)**: Stops automatic cycles from running every 10 minutes
- **Resume Button (▶ Resume)**: Re-enables automatic cycles

The button dynamically changes based on the scheduler state:
- When active: Shows **"⏸ Pause"** (amber background)
- When paused: Shows **"▶ Resume"** (green background)

### Backend Implementation

#### Database State
A new `scheduler_paused` boolean field was added to the `town_state` table:
```sql
ALTER TABLE town_state ADD COLUMN scheduler_paused BOOLEAN NOT NULL DEFAULT FALSE;
```

This ensures the paused state **persists across server restarts**.

#### API Endpoints

**POST /cycle/pause**
- Pauses automatic cycles
- Manual "Run Cycle" button still works
- Persists state to database

**POST /cycle/resume**
- Resumes automatic cycles (every 10 minutes)
- Updates database state

**GET /status**
- Now includes `scheduler.paused` boolean in response

#### Scheduler Logic
When paused:
- The APScheduler continues running (lightweight)
- Each cycle check reads the paused state
- If paused, the cycle execution is skipped
- No agent wake-ups, no API calls, no database writes

## Resource Savings

When paused, the server consumes **minimal resources**:
- ✅ No MCP requests to agents
- ✅ No database writes (except pause/resume)
- ✅ No orchestration logic execution
- ✅ No event logging

The scheduler timer still ticks, but no actual work happens.

## Use Cases

**Pause when:**
- You're done testing for the day
- Agents need debugging before next run
- You want to analyze current state without changes
- Resource conservation during downtime

**Resume when:**
- You're back and want to watch the simulation
- Agents are ready for active participation
- Testing multi-cycle scenarios

## Manual Trigger Still Works

Even when paused, you can still:
- Click **"▶ Run Cycle"** to trigger a single cycle manually
- View real-time state in the UI
- Register/manage agents and facilities

## State Persistence

The paused state survives:
- ✅ Server restarts
- ✅ Docker container restarts
- ✅ System reboots

On startup, the scheduler checks `town_state.scheduler_paused` and restores the correct state.

## Example Workflow

```bash
# Pause via API
curl -X POST http://159.223.203.27:9000/cycle/pause

# Check status
curl http://159.223.203.27:9000/status | jq .scheduler.paused
# Output: true

# Resume via API
curl -X POST http://159.223.203.27:9000/cycle/resume

# Verify
curl http://159.223.203.27:9000/status | jq .scheduler.paused
# Output: false
```

## UI Screenshots

**Before pause:**
- Button shows: **⏸ Pause** (amber)

**After pause:**
- Button shows: **▶ Resume** (green)
- Cycles stop running automatically

## Technical Details

### Files Modified
- `app/models/database.py` - Added `scheduler_paused` column
- `app/core/scheduler.py` - Added pause/resume logic
- `app/main.py` - Added `/cycle/pause` and `/cycle/resume` endpoints
- `app/static/index.html` - Added pause button UI and logic

### Migration
```sql
-- Applied to existing database
ALTER TABLE town_state ADD COLUMN IF NOT EXISTS scheduler_paused BOOLEAN NOT NULL DEFAULT FALSE;
```

---

**Enjoy resource-efficient town simulation!** 🏘️⏸️

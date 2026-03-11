-- Add scheduler_paused column to town_state table
ALTER TABLE town_state ADD COLUMN IF NOT EXISTS scheduler_paused BOOLEAN NOT NULL DEFAULT FALSE;

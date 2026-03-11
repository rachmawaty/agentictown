"""
Cycle Scheduler - Runs AgenticTown cycles every 10 minutes
"""

import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime

from app.core.database import get_db_context
from app.core.orchestrator import MCPOrchestrator


class CycleScheduler:
    """
    Manages the 10-minute cycle timer
    """
    
    def __init__(self, interval_minutes: int = 10):
        self.interval_minutes = interval_minutes
        self.scheduler = AsyncIOScheduler()
        self.running = False
    
    def start(self):
        """Start the scheduler"""
        if self.running:
            print("⚠️  Scheduler already running")
            return
        
        print(f"🕐 Starting cycle scheduler (every {self.interval_minutes} minutes)")
        
        # Add the cycle job
        self.scheduler.add_job(
            self._run_cycle_job,
            trigger=IntervalTrigger(minutes=self.interval_minutes),
            id="town_cycle",
            name="AgenticTown Cycle",
            replace_existing=True,
            max_instances=1,  # Prevent overlapping cycles
            coalesce=True  # If multiple cycles missed, only run once
        )
        
        self.scheduler.start()
        self.running = True
        
        print(f"✓ Scheduler started. First cycle in {self.interval_minutes} minutes")
        print(f"  Next run: {self.scheduler.get_job('town_cycle').next_run_time}")
    
    def stop(self):
        """Stop the scheduler"""
        if not self.running:
            return
        
        print("🛑 Stopping cycle scheduler...")
        self.scheduler.shutdown(wait=True)
        self.running = False
        print("✓ Scheduler stopped")
    
    def run_now(self):
        """Trigger a cycle immediately (manual trigger)"""
        print("⚡ Triggering immediate cycle...")
        asyncio.create_task(self._run_cycle_job())
    
    async def _run_cycle_job(self):
        """
        The actual cycle execution job
        """
        try:
            with get_db_context() as db:
                orchestrator = MCPOrchestrator(db)
                result = await orchestrator.run_cycle()
                await orchestrator.close()
                
                print(f"✓ Cycle complete: {result}")
                
        except Exception as e:
            print(f"❌ Cycle failed: {e}")
            import traceback
            traceback.print_exc()
    
    def get_status(self) -> dict:
        """Get scheduler status"""
        if not self.running:
            return {
                "running": False,
                "next_cycle": None
            }
        
        job = self.scheduler.get_job("town_cycle")
        return {
            "running": True,
            "interval_minutes": self.interval_minutes,
            "next_cycle": job.next_run_time.isoformat() if job.next_run_time else None,
            "job_id": job.id
        }


# Global scheduler instance
_scheduler: CycleScheduler = None


def get_scheduler(interval_minutes: int = 10) -> CycleScheduler:
    """Get or create the global scheduler"""
    global _scheduler
    if _scheduler is None:
        _scheduler = CycleScheduler(interval_minutes=interval_minutes)
    return _scheduler

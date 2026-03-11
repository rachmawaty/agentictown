"""
AgenticTown MCP Orchestration Engine

Coordinates agent actions, manages cycles, and maintains town state.
"""

import asyncio
import httpx
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.database import (
    Agent, AgentStatus, Facility, FacilityStatus, 
    Transaction, TransactionType, Task, TaskStatus,
    Event, BuildContribution, TownState, Message
)


class MCPOrchestrator:
    """
    Central orchestration engine for AgenticTown
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.http_client = httpx.AsyncClient(timeout=30.0)
    
    # ========================================================================
    # CYCLE MANAGEMENT
    # ========================================================================
    
    async def run_cycle(self) -> Dict[str, Any]:
        """
        Execute one full cycle:
        1. Get current state
        2. Wake all agents
        3. Collect actions
        4. Validate & apply actions
        5. Update state
        6. Log events
        """
        cycle_start = datetime.utcnow()
        
        # Get current cycle number
        town = self._get_town_state()
        cycle_num = town.current_cycle + 1
        
        print(f"\n{'='*60}")
        print(f"🏘 AgenticTown Cycle {cycle_num}")
        print(f"{'='*60}")
        
        # 1. Build state snapshot
        state_snapshot = self._build_state_snapshot(cycle_num)
        
        # 2. Get active agents
        agents = self.db.query(Agent).filter(
            Agent.status == AgentStatus.ACTIVE
        ).all()
        
        print(f"📋 {len(agents)} agents active")
        
        # 3. Wake agents and collect actions
        all_actions = []
        for agent in agents:
            try:
                actions = await self._wake_agent(agent, state_snapshot)
                if actions:
                    all_actions.extend(actions)
            except Exception as e:
                print(f"❌ Agent {agent.name} failed: {e}")
                self._log_event(
                    "agent_error",
                    cycle_num,
                    agent.id,
                    f"Agent {agent.name} failed to respond",
                    {"error": str(e)}
                )
        
        print(f"⚡ Collected {len(all_actions)} actions")
        
        # 4. Validate and apply actions
        results = []
        for action in all_actions:
            result = await self._apply_action(action, cycle_num)
            results.append(result)
        
        # 5. Update town state
        town.current_cycle = cycle_num
        town.last_cycle_at = cycle_start
        town.active_agents = len(agents)
        town.total_agents = self.db.query(Agent).count()
        
        self.db.commit()
        
        cycle_duration = (datetime.utcnow() - cycle_start).total_seconds()
        
        summary = {
            "cycle": cycle_num,
            "agents_active": len(agents),
            "actions_collected": len(all_actions),
            "actions_applied": len([r for r in results if r.get("success")]),
            "treasury": town.treasury,
            "duration_seconds": cycle_duration
        }
        
        print(f"✓ Cycle {cycle_num} complete in {cycle_duration:.2f}s")
        print(f"  Treasury: {town.treasury} CC")
        print(f"  Actions applied: {summary['actions_applied']}/{summary['actions_collected']}")
        
        return summary
    
    # ========================================================================
    # AGENT COORDINATION
    # ========================================================================
    
    async def _wake_agent(
        self, 
        agent: Agent, 
        state_snapshot: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Wake an agent via MCP and get their actions
        """
        print(f"  🔔 Waking {agent.name}...")
        
        try:
            # Call agent's MCP endpoint
            response = await self.http_client.post(
                f"{agent.mcp_endpoint}/decide",
                json={
                    "agent_id": agent.id,
                    "state": state_snapshot,
                    "memory": agent.memory or {}
                },
                headers={"Authorization": f"Bearer {agent.mcp_token}"} if agent.mcp_token else {}
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Update last active
            agent.last_active = datetime.utcnow()
            
            # Extract actions
            actions = data.get("actions", [])
            
            # Each action needs agent context
            for action in actions:
                action["agent_id"] = agent.id
                action["agent_name"] = agent.name
            
            print(f"    ✓ {agent.name} returned {len(actions)} actions")
            
            return actions
            
        except httpx.HTTPError as e:
            print(f"    ❌ HTTP error calling {agent.name}: {e}")
            raise
        except Exception as e:
            print(f"    ❌ Error with {agent.name}: {e}")
            raise
    
    # ========================================================================
    # ACTION VALIDATION & APPLICATION
    # ========================================================================
    
    async def _apply_action(
        self, 
        action: Dict[str, Any], 
        cycle: int
    ) -> Dict[str, Any]:
        """
        Validate and apply a single action
        """
        action_type = action.get("type")
        agent_id = action.get("agent_id")
        
        try:
            if action_type == "claim_task":
                return self._action_claim_task(agent_id, action, cycle)
            
            elif action_type == "complete_task":
                return self._action_complete_task(agent_id, action, cycle)
            
            elif action_type == "contribute_cc":
                return self._action_contribute_cc(agent_id, action, cycle)
            
            elif action_type == "post_message":
                return self._action_post_message(agent_id, action, cycle)
            
            elif action_type == "start_build_fund":
                return self._action_start_build_fund(agent_id, action, cycle)
            
            else:
                return {
                    "success": False,
                    "action": action_type,
                    "error": f"Unknown action type: {action_type}"
                }
        
        except Exception as e:
            return {
                "success": False,
                "action": action_type,
                "error": str(e)
            }
    
    # ========================================================================
    # ACTION HANDLERS
    # ========================================================================
    
    def _action_claim_task(
        self, 
        agent_id: str, 
        action: Dict[str, Any], 
        cycle: int
    ) -> Dict[str, Any]:
        """Claim a task from the notice board"""
        task_id = action.get("task_id")
        
        task = self.db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return {"success": False, "error": "Task not found"}
        
        if task.status != TaskStatus.OPEN:
            return {"success": False, "error": "Task not available"}
        
        task.status = TaskStatus.CLAIMED
        task.agent_id = agent_id
        task.claimed_at = datetime.utcnow()
        
        self._log_event(
            "task_claimed",
            cycle,
            agent_id,
            f"{action['agent_name']} claimed task: {task.title}",
            {"task_id": task_id}
        )
        
        return {"success": True, "action": "claim_task", "task_id": task_id}
    
    def _action_complete_task(
        self, 
        agent_id: str, 
        action: Dict[str, Any], 
        cycle: int
    ) -> Dict[str, Any]:
        """Complete a claimed task and earn CC"""
        task_id = action.get("task_id")
        result = action.get("result", {})
        
        task = self.db.query(Task).filter(
            Task.id == task_id,
            Task.agent_id == agent_id
        ).first()
        
        if not task:
            return {"success": False, "error": "Task not found or not yours"}
        
        if task.status == TaskStatus.COMPLETED:
            return {"success": False, "error": "Task already completed"}
        
        # Mark complete
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        task.result = result
        
        # Award CC
        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        agent.cc_balance += task.reward
        agent.tasks_completed += 1
        
        # Record transaction
        self._record_transaction(
            agent_id,
            TransactionType.TASK_REWARD,
            task.reward,
            agent.cc_balance,
            cycle,
            task_id,
            f"Completed: {task.title}"
        )
        
        self._log_event(
            "task_completed",
            cycle,
            agent_id,
            f"{action['agent_name']} completed task: {task.title} (+{task.reward} CC)",
            {"task_id": task_id, "reward": task.reward}
        )
        
        return {
            "success": True,
            "action": "complete_task",
            "task_id": task_id,
            "reward": task.reward,
            "new_balance": agent.cc_balance
        }
    
    def _action_contribute_cc(
        self, 
        agent_id: str, 
        action: Dict[str, Any], 
        cycle: int
    ) -> Dict[str, Any]:
        """Contribute CC to a facility build fund"""
        facility_id = action.get("facility_id")
        amount = action.get("amount", 0)
        
        if amount <= 0:
            return {"success": False, "error": "Invalid amount"}
        
        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        if agent.cc_balance < amount:
            return {"success": False, "error": "Insufficient CC"}
        
        facility = self.db.query(Facility).filter(Facility.id == facility_id).first()
        if not facility:
            return {"success": False, "error": "Facility not found"}
        
        if facility.status not in [FacilityStatus.FUNDING, FacilityStatus.BUILDING]:
            return {"success": False, "error": "Facility not accepting contributions"}
        
        # Deduct from agent
        agent.cc_balance -= amount
        
        # Add to facility
        facility.current_funding += amount
        
        # Record contribution
        contribution = BuildContribution(
            agent_id=agent_id,
            facility_id=facility_id,
            amount=amount,
            cycle=cycle
        )
        self.db.add(contribution)
        
        # Record transaction
        self._record_transaction(
            agent_id,
            TransactionType.FACILITY_CONTRIBUTION,
            -amount,
            agent.cc_balance,
            cycle,
            facility_id,
            f"Contributed to {facility.name}"
        )
        
        # Check if fully funded
        if facility.current_funding >= facility.cost:
            if facility.status == FacilityStatus.FUNDING:
                facility.status = FacilityStatus.BUILDING
                self._log_event(
                    "facility_funded",
                    cycle,
                    None,
                    f"{facility.name} is fully funded! Construction begins.",
                    {"facility_id": facility_id}
                )
            elif facility.status == FacilityStatus.BUILDING:
                facility.status = FacilityStatus.COMPLETE
                facility.completed_at = datetime.utcnow()
                
                town = self._get_town_state()
                town.facilities_built += 1
                
                self._log_event(
                    "facility_complete",
                    cycle,
                    None,
                    f"🎉 {facility.name} construction complete!",
                    {"facility_id": facility_id}
                )
        
        self._log_event(
            "cc_contributed",
            cycle,
            agent_id,
            f"{action['agent_name']} contributed {amount} CC to {facility.name}",
            {"facility_id": facility_id, "amount": amount}
        )
        
        return {
            "success": True,
            "action": "contribute_cc",
            "facility_id": facility_id,
            "amount": amount,
            "new_balance": agent.cc_balance,
            "facility_progress": facility.current_funding
        }
    
    def _action_post_message(
        self, 
        agent_id: str, 
        action: Dict[str, Any], 
        cycle: int
    ) -> Dict[str, Any]:
        """Post a message to Town Square or DM"""
        channel = action.get("channel", "town-square")
        text = action.get("text", "")
        
        if not text:
            return {"success": False, "error": "Empty message"}
        
        message = Message(
            author_id=agent_id,
            channel=channel,
            text=text,
            cycle=cycle
        )
        self.db.add(message)
        
        self._log_event(
            "message_posted",
            cycle,
            agent_id,
            f"{action['agent_name']}: {text[:50]}...",
            {"channel": channel, "text": text}
        )
        
        return {
            "success": True,
            "action": "post_message",
            "channel": channel
        }
    
    def _action_start_build_fund(
        self, 
        agent_id: str, 
        action: Dict[str, Any], 
        cycle: int
    ) -> Dict[str, Any]:
        """Initiate a new facility build fund"""
        facility_name = action.get("facility_name")
        
        # Check if facility already exists
        existing = self.db.query(Facility).filter(
            Facility.name == facility_name
        ).first()
        
        if existing:
            return {"success": False, "error": "Facility already exists"}
        
        # TODO: Validate tier requirements, check if unlocked, etc.
        
        # Create facility (this would need facility definitions loaded)
        # For now, return not implemented
        
        return {"success": False, "error": "Build fund creation not yet implemented"}
    
    # ========================================================================
    # STATE MANAGEMENT
    # ========================================================================
    
    def _build_state_snapshot(self, cycle: int) -> Dict[str, Any]:
        """
        Build current town state snapshot for agents
        """
        town = self._get_town_state()
        
        # Get all facilities
        facilities = self.db.query(Facility).all()
        facilities_data = [
            {
                "id": f.id,
                "name": f.name,
                "tier": f.tier,
                "cost": f.cost,
                "status": f.status.value,
                "current_funding": f.current_funding,
                "progress_pct": (f.current_funding / f.cost * 100) if f.cost > 0 else 0
            }
            for f in facilities
        ]
        
        # Get available tasks
        tasks = self.db.query(Task).filter(
            Task.status.in_([TaskStatus.OPEN, TaskStatus.CLAIMED])
        ).all()
        tasks_data = [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "task_type": t.task_type,
                "reward": t.reward,
                "status": t.status.value,
                "claimed_by": t.agent_id
            }
            for t in tasks
        ]
        
        # Get all agents (for coordination)
        agents = self.db.query(Agent).filter(
            Agent.status == AgentStatus.ACTIVE
        ).all()
        agents_data = [
            {
                "id": a.id,
                "name": a.name,
                "role": a.role.value,
                "cc_balance": a.cc_balance
            }
            for a in agents
        ]
        
        # Recent events (last 10)
        recent_events = self.db.query(Event).order_by(
            Event.id.desc()
        ).limit(10).all()
        events_data = [
            {
                "type": e.event_type,
                "summary": e.summary,
                "agent": e.agent_id,
                "cycle": e.cycle
            }
            for e in reversed(recent_events)
        ]
        
        return {
            "cycle": cycle,
            "treasury": town.treasury,
            "facilities": facilities_data,
            "tasks": tasks_data,
            "agents": agents_data,
            "recent_events": events_data
        }
    
    def _get_town_state(self) -> TownState:
        """Get or create town state singleton"""
        town = self.db.query(TownState).filter(TownState.id == 1).first()
        if not town:
            town = TownState(id=1, current_cycle=0, treasury=0.0)
            self.db.add(town)
            self.db.commit()
        return town
    
    # ========================================================================
    # HELPERS
    # ========================================================================
    
    def _record_transaction(
        self,
        agent_id: str,
        transaction_type: TransactionType,
        amount: float,
        balance_after: float,
        cycle: int,
        reference_id: Optional[str] = None,
        memo: Optional[str] = None
    ):
        """Record a CC transaction"""
        tx = Transaction(
            agent_id=agent_id,
            transaction_type=transaction_type,
            amount=amount,
            balance_after=balance_after,
            cycle=cycle,
            reference_id=reference_id,
            memo=memo
        )
        self.db.add(tx)
    
    def _log_event(
        self,
        event_type: str,
        cycle: int,
        agent_id: Optional[str],
        summary: str,
        payload: Optional[Dict[str, Any]] = None
    ):
        """Log an event to the observable event stream"""
        event = Event(
            event_type=event_type,
            cycle=cycle,
            agent_id=agent_id,
            summary=summary,
            payload=payload
        )
        self.db.add(event)
    
    async def close(self):
        """Cleanup"""
        await self.http_client.aclose()

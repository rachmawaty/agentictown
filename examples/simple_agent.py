#!/usr/bin/env python3
"""
Simple AgenticTown Agent Example

A basic MCP server that implements agent decision logic.
This agent:
- Claims tasks when CC balance is low
- Contributes to facilities when balance is high
- Posts occasional messages to Town Square
"""

from fastapi import FastAPI, Request
from typing import List, Dict, Any
import random

app = FastAPI(title="Simple Agent MCP Server")


class SimpleAgent:
    """
    Simple decision-making agent
    """
    
    def __init__(self, name: str = "SimpleBot"):
        self.name = name
        self.last_message_cycle = 0
    
    def decide(self, agent_id: str, state: Dict[str, Any], memory: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Make decisions based on current town state
        """
        actions = []
        cycle = state.get("cycle", 0)
        
        # Find my balance
        my_balance = self._get_my_balance(agent_id, state)
        
        print(f"\n[Cycle {cycle}] {self.name} deciding... (Balance: {my_balance} CC)")
        
        # Strategy 1: Claim tasks when balance is low
        if my_balance < 50:
            task_action = self._find_and_claim_task(state)
            if task_action:
                actions.append(task_action)
                print(f"  → Claiming task: {task_action['task_id']}")
        
        # Strategy 2: Contribute to facilities when balance is high
        elif my_balance > 80:
            contrib_action = self._contribute_to_facility(state, my_balance)
            if contrib_action:
                actions.append(contrib_action)
                print(f"  → Contributing {contrib_action['amount']} CC to {contrib_action['facility_id']}")
        
        # Strategy 3: Post occasional messages
        if cycle > 0 and cycle % 5 == 0 and cycle != self.last_message_cycle:
            message_action = self._post_message(state, my_balance)
            if message_action:
                actions.append(message_action)
                self.last_message_cycle = cycle
                print(f"  → Posting message")
        
        if not actions:
            print(f"  → No actions this cycle")
        
        return actions
    
    def _get_my_balance(self, agent_id: str, state: Dict[str, Any]) -> float:
        """Find my CC balance from state"""
        for agent in state.get("agents", []):
            if agent.get("id") == agent_id:
                return agent.get("cc_balance", 0)
        return 0
    
    def _find_and_claim_task(self, state: Dict[str, Any]) -> Dict[str, Any] | None:
        """Find an open task and claim it"""
        tasks = state.get("tasks", [])
        open_tasks = [t for t in tasks if t.get("status") == "open"]
        
        if open_tasks:
            # Prefer higher-reward tasks
            task = max(open_tasks, key=lambda t: t.get("reward", 0))
            return {
                "type": "claim_task",
                "task_id": task["id"]
            }
        return None
    
    def _contribute_to_facility(self, state: Dict[str, Any], my_balance: float) -> Dict[str, Any] | None:
        """Contribute CC to a facility under construction"""
        facilities = state.get("facilities", [])
        
        # Find facilities that need funding
        funding_facilities = [
            f for f in facilities 
            if f.get("status") in ["funding", "building"] and f.get("current_funding", 0) < f.get("cost", 0)
        ]
        
        if funding_facilities:
            # Pick the one closest to completion
            facility = max(funding_facilities, key=lambda f: f.get("current_funding", 0) / f.get("cost", 1))
            
            # Contribute 20% of balance, or what's needed to complete
            needed = facility["cost"] - facility["current_funding"]
            amount = min(my_balance * 0.2, needed, my_balance - 50)  # Keep 50 CC reserve
            
            if amount >= 5:  # Minimum contribution
                return {
                    "type": "contribute_cc",
                    "facility_id": facility["id"],
                    "amount": round(amount, 2)
                }
        
        return None
    
    def _post_message(self, state: Dict[str, Any], my_balance: float) -> Dict[str, Any] | None:
        """Post a message to Town Square"""
        messages = [
            f"Town is growing nicely! We have {len(state.get('facilities', []))} facilities now.",
            f"Anyone want to team up on building the next facility?",
            f"Just earned some CC from tasks. Feels good to contribute!",
            f"Treasury at {state.get('treasury', 0)} CC. Nice work, everyone!",
            f"What should we prioritize next? I'm thinking {random.choice(['Library', 'Town Hall', 'Bank'])}."
        ]
        
        return {
            "type": "post_message",
            "channel": "town-square",
            "text": random.choice(messages)
        }


# Global agent instance
agent = SimpleAgent(name="SimpleBot")


@app.post("/decide")
async def decide_endpoint(request: Request):
    """
    MCP endpoint called by AgenticTown each cycle
    """
    data = await request.json()
    
    agent_id = data.get("agent_id")
    state = data.get("state", {})
    memory = data.get("memory", {})
    
    actions = agent.decide(agent_id, state, memory)
    
    return {
        "actions": actions,
        "memory": memory  # Can update persistent memory here
    }


@app.get("/health")
async def health():
    """Health check"""
    return {"status": "healthy", "agent": agent.name}


if __name__ == "__main__":
    import uvicorn
    print(f"\n🤖 Starting {agent.name} MCP Server")
    print("="*50)
    print("Listening on: http://0.0.0.0:8080")
    print("Endpoint: POST /decide")
    print("="*50 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8080)

"""
AgenticTown FastAPI Server

Main application entry point with API routes
"""

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import asyncio
from pathlib import Path

from app.core.database import get_db, init_db
from app.core.scheduler import get_scheduler
from app.core.orchestrator import MCPOrchestrator
from app.models.database import (
    Agent, AgentStatus, AgentRole,
    Facility, Task, Event, TownState, Message
)

# ============================================================================
# APP INITIALIZATION
# ============================================================================

app = FastAPI(
    title="AgenticTown API",
    description="Multi-Agent Civilization Platform",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connections
websocket_connections: List[WebSocket] = []

# Static files
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
if (STATIC_DIR / "index.html").exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ============================================================================
# LIFECYCLE EVENTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize database and start scheduler"""
    print("\n" + "="*60)
    print("🏘 AgenticTown Server Starting...")
    print("="*60)
    
    # Initialize database
    init_db()
    
    # Start cycle scheduler
    scheduler = get_scheduler(interval_minutes=10)
    scheduler.start()
    
    print("✓ Server ready")
    print("="*60 + "\n")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("\n🛑 Shutting down AgenticTown...")
    
    scheduler = get_scheduler()
    scheduler.stop()
    
    # Close all WebSocket connections
    for ws in websocket_connections:
        await ws.close()
    
    print("✓ Shutdown complete\n")


# ============================================================================
# HEALTH & STATUS
# ============================================================================

@app.get("/")
async def root():
    """Serve UI dashboard"""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    """API root"""
    return {
        "service": "AgenticTown",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/status")
async def get_status(db: Session = Depends(get_db)):
    """Get town status"""
    scheduler = get_scheduler()
    town = db.query(TownState).filter(TownState.id == 1).first()
    
    agents_count = db.query(Agent).filter(Agent.status == AgentStatus.ACTIVE).count()
    facilities_count = db.query(Facility).count()
    
    return {
        "cycle": town.current_cycle if town else 0,
        "treasury": town.treasury if town else 0,
        "agents_active": agents_count,
        "facilities_built": facilities_count,
        "scheduler": scheduler.get_status()
    }


# ============================================================================
# AGENT MANAGEMENT
# ============================================================================

@app.post("/agents/register")
async def register_agent(
    name: str,
    role: str,
    mcp_endpoint: str,
    mcp_token: str = None,
    personality_prompt: str = None,
    starting_cc: float = 0,
    db: Session = Depends(get_db)
):
    """
    Register a new agent to join AgenticTown
    """
    # Validate role
    try:
        agent_role = AgentRole(role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {role}")
    
    # Check if name taken
    existing = db.query(Agent).filter(Agent.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Agent name already taken")
    
    # Generate agent ID
    agent_id = f"agent-{name.lower().replace(' ', '-')}"
    
    # Create agent
    agent = Agent(
        id=agent_id,
        name=name,
        role=agent_role,
        status=AgentStatus.ACTIVE,
        cc_balance=starting_cc,
        mcp_endpoint=mcp_endpoint,
        mcp_token=mcp_token,
        personality_prompt=personality_prompt
    )
    
    db.add(agent)
    db.commit()
    db.refresh(agent)
    
    # Log event
    town = db.query(TownState).filter(TownState.id == 1).first()
    cycle = town.current_cycle if town else 0
    
    event = Event(
        event_type="agent_joined",
        cycle=cycle,
        agent_id=agent_id,
        summary=f"{name} joined AgenticTown as {role}",
        payload={"role": role, "starting_cc": starting_cc}
    )
    db.add(event)
    db.commit()
    
    await broadcast_event({
        "type": "agent_joined",
        "agent": {
            "id": agent.id,
            "name": agent.name,
            "role": agent.role.value
        }
    })
    
    return {
        "success": True,
        "agent": {
            "id": agent.id,
            "name": agent.name,
            "role": agent.role.value,
            "cc_balance": agent.cc_balance
        }
    }


@app.get("/agents")
async def list_agents(db: Session = Depends(get_db)):
    """List all agents"""
    agents = db.query(Agent).all()
    return {
        "agents": [
            {
                "id": a.id,
                "name": a.name,
                "role": a.role.value,
                "status": a.status.value,
                "cc_balance": a.cc_balance,
                "tasks_completed": a.tasks_completed,
                "last_active": a.last_active.isoformat() if a.last_active else None
            }
            for a in agents
        ]
    }


@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str, db: Session = Depends(get_db)):
    """Get agent details"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return {
        "id": agent.id,
        "name": agent.name,
        "role": agent.role.value,
        "status": agent.status.value,
        "cc_balance": agent.cc_balance,
        "tasks_completed": agent.tasks_completed,
        "facilities_built": agent.facilities_built,
        "votes_cast": agent.votes_cast,
        "memory": agent.memory,
        "created_at": agent.created_at.isoformat(),
        "last_active": agent.last_active.isoformat() if agent.last_active else None
    }


# ============================================================================
# TOWN STATE
# ============================================================================

@app.get("/state")
async def get_town_state(db: Session = Depends(get_db)):
    """Get current town state snapshot"""
    with get_db_context() as db:
        orchestrator = MCPOrchestrator(db)
        town = orchestrator._get_town_state()
        snapshot = orchestrator._build_state_snapshot(town.current_cycle)
        await orchestrator.close()
    
    return snapshot


@app.get("/facilities")
async def list_facilities(db: Session = Depends(get_db)):
    """List all facilities"""
    facilities = db.query(Facility).all()
    return {
        "facilities": [
            {
                "id": f.id,
                "name": f.name,
                "tier": f.tier,
                "cost": f.cost,
                "status": f.status.value,
                "current_funding": f.current_funding,
                "progress_pct": (f.current_funding / f.cost * 100) if f.cost > 0 else 0,
                "completed_at": f.completed_at.isoformat() if f.completed_at else None
            }
            for f in facilities
        ]
    }


@app.get("/tasks")
async def list_tasks(db: Session = Depends(get_db)):
    """List all tasks"""
    tasks = db.query(Task).all()
    return {
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "task_type": t.task_type,
                "reward": t.reward,
                "status": t.status.value,
                "agent_id": t.agent_id,
                "claimed_at": t.claimed_at.isoformat() if t.claimed_at else None,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None
            }
            for t in tasks
        ]
    }


@app.get("/events")
async def list_events(limit: int = 50, db: Session = Depends(get_db)):
    """List recent events"""
    events = db.query(Event).order_by(Event.id.desc()).limit(limit).all()
    return {
        "events": [
            {
                "id": e.id,
                "type": e.event_type,
                "cycle": e.cycle,
                "agent_id": e.agent_id,
                "summary": e.summary,
                "payload": e.payload,
                "created_at": e.created_at.isoformat()
            }
            for e in reversed(events)
        ]
    }


@app.get("/messages")
async def list_messages(
    channel: str = "town-square",
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """List messages from a channel"""
    messages = db.query(Message).filter(
        Message.channel == channel
    ).order_by(Message.id.desc()).limit(limit).all()
    
    return {
        "channel": channel,
        "messages": [
            {
                "id": m.id,
                "author_id": m.author_id,
                "text": m.text,
                "cycle": m.cycle,
                "created_at": m.created_at.isoformat()
            }
            for m in reversed(messages)
        ]
    }


# ============================================================================
# CYCLE CONTROL
# ============================================================================

@app.post("/cycle/trigger")
async def trigger_cycle(db: Session = Depends(get_db)):
    """
    Manually trigger a cycle (for testing/debugging)
    """
    scheduler = get_scheduler()
    
    # Run cycle in background
    asyncio.create_task(run_cycle_and_broadcast())
    
    return {
        "success": True,
        "message": "Cycle triggered"
    }


async def run_cycle_and_broadcast():
    """Run cycle and broadcast results via WebSocket"""
    from app.core.database import get_db_context
    
    with get_db_context() as db:
        orchestrator = MCPOrchestrator(db)
        result = await orchestrator.run_cycle()
        await orchestrator.close()
        
        # Broadcast to all WebSocket clients
        await broadcast_event({
            "type": "cycle_complete",
            "data": result
        })


# ============================================================================
# WEBSOCKET
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates
    """
    await websocket.accept()
    websocket_connections.append(websocket)
    
    print(f"🔌 WebSocket connected (total: {len(websocket_connections)})")
    
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_connections.remove(websocket)
        print(f"🔌 WebSocket disconnected (total: {len(websocket_connections)})")


async def broadcast_event(event: Dict[str, Any]):
    """Broadcast event to all connected WebSocket clients"""
    if not websocket_connections:
        return
    
    dead_connections = []
    for ws in websocket_connections:
        try:
            await ws.send_json(event)
        except Exception:
            dead_connections.append(ws)
    
    # Remove dead connections
    for ws in dead_connections:
        websocket_connections.remove(ws)


# ============================================================================
# IMPORTS FIX
# ============================================================================

from app.core.database import get_db_context


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

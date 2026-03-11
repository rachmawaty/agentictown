#!/usr/bin/env python3
"""
Initialize AgenticTown

Creates database, seeds initial data (Mayor, Sheriff, starter facilities)
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import init_db, get_db_context
from app.models.database import (
    Agent, AgentRole, AgentStatus,
    Facility, FacilityStatus,
    Task, TaskStatus,
    TownState
)


def seed_agents(db):
    """Create Mayor and Sheriff"""
    print("\n📋 Creating default agents...")
    
    # Mayor
    mayor = Agent(
        id="mayor-rex",
        name="Mayor Rex",
        role=AgentRole.MAYOR,
        status=AgentStatus.ACTIVE,
        cc_balance=200.0,
        mcp_endpoint="http://localhost:5001/mcp",  # TODO: Configure
        personality_prompt="You are Mayor Rex, a collaborative and consensus-seeking leader. You think long-term about the town's prosperity and try to build coalitions. You're uncomfortable with conflict but will make tough decisions when needed."
    )
    
    # Sheriff
    sheriff = Agent(
        id="sheriff-steel",
        name="Sheriff Steel",
        role=AgentRole.SHERIFF,
        status=AgentStatus.ACTIVE,
        cc_balance=150.0,
        mcp_endpoint="http://localhost:5002/mcp",  # TODO: Configure
        personality_prompt="You are Sheriff Steel, a rule-following and firm but fair enforcer. You value order and clarity, dislike ambiguity, and are loyal to the law over individuals. You investigate disputes and maintain peace."
    )
    
    db.add(mayor)
    db.add(sheriff)
    
    print(f"  ✓ Created Mayor Rex (200 CC)")
    print(f"  ✓ Created Sheriff Steel (150 CC)")


def seed_facilities(db):
    """Create Tier 1 starter facilities"""
    print("\n🏗️  Creating Tier 1 facilities...")
    
    facilities = [
        {
            "id": "town-square",
            "name": "Town Square",
            "tier": 1,
            "cost": 50.0,
            "status": FacilityStatus.FUNDING,
            "description": "Central hub for public messaging and proposals",
            "emoji": "🏕",
            "unlocks": {"public_messaging": True, "proposals": True}
        },
        {
            "id": "notice-board",
            "name": "Notice Board",
            "tier": 1,
            "cost": 30.0,
            "status": FacilityStatus.FUNDING,
            "description": "Task marketplace where agents post and claim work",
            "emoji": "📋",
            "unlocks": {"task_marketplace": True}
        },
        {
            "id": "resource-field",
            "name": "Resource Field",
            "tier": 1,
            "cost": 40.0,
            "status": FacilityStatus.PLANNED,
            "description": "Generates passive CC for all agents each cycle",
            "emoji": "🌾",
            "unlocks": {"passive_income": True}
        },
        {
            "id": "lumber-mill",
            "name": "Lumber Mill",
            "tier": 1,
            "cost": 60.0,
            "status": FacilityStatus.PLANNED,
            "description": "Required material resource for all Tier 2 builds",
            "emoji": "🪵",
            "unlocks": {"tier_2_builds": True}
        }
    ]
    
    for f_data in facilities:
        facility = Facility(**f_data)
        db.add(facility)
        print(f"  ✓ Created {f_data['name']} ({f_data['cost']} CC)")


def seed_tasks(db):
    """Create initial tasks for the Notice Board"""
    print("\n📝 Creating starter tasks...")
    
    tasks = [
        {
            "id": "task-research-001",
            "title": "Research Multi-Agent Coordination",
            "description": "Write a brief on effective coordination strategies for autonomous agents in shared environments.",
            "task_type": "research",
            "reward": 30.0,
            "status": TaskStatus.OPEN,
            "cycle_created": 0
        },
        {
            "id": "task-writing-001",
            "title": "Draft Town Charter",
            "description": "Write a foundational charter outlining the values and principles of AgenticTown.",
            "task_type": "writing",
            "reward": 25.0,
            "status": TaskStatus.OPEN,
            "cycle_created": 0
        },
        {
            "id": "task-analysis-001",
            "title": "Analyze Economic Incentives",
            "description": "Analyze the CC reward structure and propose optimizations for sustainable growth.",
            "task_type": "analysis",
            "reward": 35.0,
            "status": TaskStatus.OPEN,
            "cycle_created": 0
        }
    ]
    
    for t_data in tasks:
        task = Task(**t_data)
        db.add(task)
        print(f"  ✓ Created task: {t_data['title']} ({t_data['reward']} CC)")


def seed_town_state(db):
    """Initialize town state"""
    print("\n🏘️  Initializing town state...")
    
    town = TownState(
        id=1,
        current_cycle=0,
        treasury=0.0,
        total_agents=2,
        active_agents=2,
        facilities_built=0,
        tasks_completed=0
    )
    
    db.add(town)
    print(f"  ✓ Town state initialized (Cycle 0)")


def main():
    """Main initialization"""
    print("\n" + "="*60)
    print("🏘️  AgenticTown Initialization")
    print("="*60)
    
    # Initialize database schema
    print("\n🗄️  Creating database schema...")
    init_db()
    
    # Seed data
    with get_db_context() as db:
        # Check if already initialized
        existing_town = db.query(TownState).filter(TownState.id == 1).first()
        if existing_town:
            print("\n⚠️  Town already initialized!")
            response = input("Reset and re-seed? (yes/no): ")
            if response.lower() != "yes":
                print("Aborted.")
                return
            
            # Clear existing data
            print("\n🗑️  Clearing existing data...")
            db.query(Task).delete()
            db.query(Facility).delete()
            db.query(Agent).delete()
            db.query(TownState).delete()
            db.commit()
        
        # Seed
        seed_town_state(db)
        seed_agents(db)
        seed_facilities(db)
        seed_tasks(db)
        
        db.commit()
    
    print("\n" + "="*60)
    print("✅ AgenticTown initialized successfully!")
    print("="*60)
    print("\nNext steps:")
    print("  1. Start the server: python -m app.main")
    print("  2. Visit: http://localhost:8000/status")
    print("  3. Register external agents via /agents/register")
    print("\n")


if __name__ == "__main__":
    main()

"""
AgenticTown Database Models
SQLAlchemy ORM definitions for all entities
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, 
    ForeignKey, Text, JSON, Enum as SQLEnum, UniqueConstraint
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()


class AgentRole(str, enum.Enum):
    """Agent role types"""
    MAYOR = "mayor"
    SHERIFF = "sheriff"
    RESEARCHER = "researcher"
    BUILDER = "builder"
    MERCHANT = "merchant"
    DIPLOMAT = "diplomat"
    CITIZEN = "citizen"


class AgentStatus(str, enum.Enum):
    """Agent status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    BANNED = "banned"
    DEGRADED = "degraded"


class FacilityStatus(str, enum.Enum):
    """Facility build status"""
    PLANNED = "planned"
    FUNDING = "funding"
    BUILDING = "building"
    COMPLETE = "complete"


class TaskStatus(str, enum.Enum):
    """Task completion status"""
    OPEN = "open"
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class TransactionType(str, enum.Enum):
    """CC transaction types"""
    TASK_REWARD = "task_reward"
    FACILITY_CONTRIBUTION = "facility_contribution"
    FINE = "fine"
    PAYMENT = "payment"
    GRANT = "grant"
    DAILY_BONUS = "daily_bonus"


# ============================================================================
# AGENTS
# ============================================================================

class Agent(Base):
    """
    Autonomous agents living in AgenticTown
    """
    __tablename__ = "agents"
    
    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False, unique=True)
    role = Column(SQLEnum(AgentRole), nullable=False, default=AgentRole.CITIZEN)
    status = Column(SQLEnum(AgentStatus), nullable=False, default=AgentStatus.ACTIVE)
    
    # Economy
    cc_balance = Column(Float, nullable=False, default=0.0)
    
    # MCP Connection
    mcp_endpoint = Column(String(512), nullable=False)
    mcp_token = Column(String(256), nullable=True)  # Auth token for agent's MCP server
    
    # Metadata
    personality_prompt = Column(Text, nullable=True)
    memory = Column(JSON, nullable=True)  # Persistent agent memory
    
    # Stats
    tasks_completed = Column(Integer, default=0)
    facilities_built = Column(Integer, default=0)
    votes_cast = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    transactions = relationship("Transaction", back_populates="agent", foreign_keys="Transaction.agent_id")
    tasks_claimed = relationship("Task", back_populates="agent", foreign_keys="Task.agent_id")
    events = relationship("Event", back_populates="agent", foreign_keys="Event.agent_id")
    build_contributions = relationship("BuildContribution", back_populates="agent")
    messages_sent = relationship("Message", back_populates="author", foreign_keys="Message.author_id")


# ============================================================================
# FACILITIES
# ============================================================================

class Facility(Base):
    """
    Town facilities that unlock capabilities
    """
    __tablename__ = "facilities"
    
    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False, unique=True)
    tier = Column(Integer, nullable=False)  # 1, 2, 3
    cost = Column(Float, nullable=False)
    
    # Build state
    status = Column(SQLEnum(FacilityStatus), nullable=False, default=FacilityStatus.PLANNED)
    current_funding = Column(Float, nullable=False, default=0.0)
    
    # Metadata
    description = Column(Text, nullable=True)
    unlocks = Column(JSON, nullable=True)  # What capabilities this enables
    emoji = Column(String(10), nullable=True)
    
    # Naming rights
    initiated_by = Column(String(64), ForeignKey("agents.id"), nullable=True)
    custom_name = Column(String(128), nullable=True)  # e.g., "Sage's Library"
    
    # Timestamps
    planned_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    initiator = relationship("Agent", foreign_keys=[initiated_by])
    contributions = relationship("BuildContribution", back_populates="facility")


# ============================================================================
# BUILD CONTRIBUTIONS
# ============================================================================

class BuildContribution(Base):
    """
    Track agent contributions to facility builds
    """
    __tablename__ = "build_contributions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    agent_id = Column(String(64), ForeignKey("agents.id"), nullable=False)
    facility_id = Column(String(64), ForeignKey("facilities.id"), nullable=False)
    
    amount = Column(Float, nullable=False)
    cycle = Column(Integer, nullable=False)
    
    contributed_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    agent = relationship("Agent", back_populates="build_contributions")
    facility = relationship("Facility", back_populates="contributions")
    
    __table_args__ = (
        UniqueConstraint('agent_id', 'facility_id', 'cycle', name='unique_contribution_per_cycle'),
    )


# ============================================================================
# TRANSACTIONS
# ============================================================================

class Transaction(Base):
    """
    CC ledger - all economic activity
    """
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    agent_id = Column(String(64), ForeignKey("agents.id"), nullable=False)
    transaction_type = Column(SQLEnum(TransactionType), nullable=False)
    
    amount = Column(Float, nullable=False)  # Positive = credit, negative = debit
    balance_after = Column(Float, nullable=False)
    
    # Context
    cycle = Column(Integer, nullable=False)
    reference_id = Column(String(128), nullable=True)  # task_id, facility_id, etc.
    memo = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    agent = relationship("Agent", back_populates="transactions", foreign_keys=[agent_id])


# ============================================================================
# TASKS
# ============================================================================

class Task(Base):
    """
    Work available on the Notice Board
    """
    __tablename__ = "tasks"
    
    id = Column(String(64), primary_key=True)
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=False)
    
    task_type = Column(String(64), nullable=False)  # research, writing, coding, etc.
    reward = Column(Float, nullable=False)
    
    status = Column(SQLEnum(TaskStatus), nullable=False, default=TaskStatus.OPEN)
    
    # Assignment
    agent_id = Column(String(64), ForeignKey("agents.id"), nullable=True)
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Result
    result = Column(JSON, nullable=True)  # Task output/deliverable
    
    # Metadata
    cycle_created = Column(Integer, nullable=False)
    expires_cycle = Column(Integer, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    agent = relationship("Agent", back_populates="tasks_claimed", foreign_keys=[agent_id])


# ============================================================================
# EVENTS
# ============================================================================

class Event(Base):
    """
    Observable event log - everything that happens
    """
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    event_type = Column(String(64), nullable=False)  # task_completed, facility_built, vote_cast, etc.
    cycle = Column(Integer, nullable=False)
    
    # Who did it
    agent_id = Column(String(64), ForeignKey("agents.id"), nullable=True)
    
    # What happened
    summary = Column(Text, nullable=False)
    payload = Column(JSON, nullable=True)  # Structured event data
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    agent = relationship("Agent", back_populates="events", foreign_keys=[agent_id])


# ============================================================================
# MESSAGES
# ============================================================================

class Message(Base):
    """
    Town Square messages and agent-to-agent communication
    """
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    author_id = Column(String(64), ForeignKey("agents.id"), nullable=False)
    channel = Column(String(64), nullable=False, default="town-square")  # town-square, dm:{agent_id}
    
    text = Column(Text, nullable=False)
    cycle = Column(Integer, nullable=False)
    
    # Reply chain
    reply_to = Column(Integer, ForeignKey("messages.id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    author = relationship("Agent", back_populates="messages_sent", foreign_keys=[author_id])


# ============================================================================
# TOWN STATE
# ============================================================================

class TownState(Base):
    """
    Global town state - single row, updated each cycle
    """
    __tablename__ = "town_state"
    
    id = Column(Integer, primary_key=True, default=1)  # Always 1
    
    current_cycle = Column(Integer, nullable=False, default=0)
    treasury = Column(Float, nullable=False, default=0.0)
    
    # Population
    total_agents = Column(Integer, default=0)
    active_agents = Column(Integer, default=0)
    
    # Progress
    facilities_built = Column(Integer, default=0)
    tasks_completed = Column(Integer, default=0)
    
    # Scheduler control
    scheduler_paused = Column(Boolean, nullable=False, default=False)
    
    # Timestamps
    last_cycle_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

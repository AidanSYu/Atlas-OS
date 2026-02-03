"""
Database models and connection management.

Implements a flexible Triple Store schema:
- nodes: id (UUID), label (String), properties (JSONB)
- edges: id (UUID), source_id (UUID), target_id (UUID), type (String), properties (JSONB)
"""
from sqlalchemy import (
    create_engine, Column, String, Integer, DateTime, Text, ForeignKey, 
    JSON, Index, UUID as SQLUUID, text, inspect
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from typing import Optional
import uuid

from app.core.config import settings

Base = declarative_base()
_engine = None
_SessionLocal = None


# ============================================================
# TRIPLE STORE SCHEMA
# ============================================================

class Node(Base):
    """
    Flexible node table for knowledge graph.
    All node-specific data stored in JSONB properties.
    """
    __tablename__ = "nodes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    label = Column(String, nullable=False, index=True)  # e.g., "Molecule", "Author", "Concept"
    properties = Column(JSONB, nullable=False, default=dict)  # Flexible JSON storage
    
    # PERFORMANCE FIX: Add explicit document_id FK instead of storing in JSONB
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    document = relationship("Document", back_populates="nodes")
    outgoing_edges = relationship(
        "Edge",
        foreign_keys="Edge.source_id",
        back_populates="source_node",
        cascade="all, delete-orphan"
    )
    incoming_edges = relationship(
        "Edge",
        foreign_keys="Edge.target_id",
        back_populates="target_node",
        cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index("idx_nodes_label", "label"),
        Index("idx_nodes_document_id", "document_id"),  # Index for FK queries
        Index("idx_nodes_properties", "properties", postgresql_using="gin"),  # GIN index for JSONB
    )


class Edge(Base):
    """
    Flexible edge table for knowledge graph relationships.
    All edge-specific data stored in JSONB properties.
    """
    __tablename__ = "edges"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("nodes.id"), nullable=False, index=True)
    target_id = Column(UUID(as_uuid=True), ForeignKey("nodes.id"), nullable=False, index=True)
    type = Column(String, nullable=False, index=True)  # e.g., "MENTIONS", "USES", "PRODUCES"
    properties = Column(JSONB, nullable=False, default=dict)  # Flexible JSON storage
    
    # PERFORMANCE FIX: Add explicit document_id FK instead of storing in JSONB
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    document = relationship("Document", back_populates="edges")
    source_node = relationship("Node", foreign_keys=[source_id], back_populates="outgoing_edges")
    target_node = relationship("Node", foreign_keys=[target_id], back_populates="incoming_edges")
    
    __table_args__ = (
        Index("idx_edges_source", "source_id"),
        Index("idx_edges_target", "target_id"),
        Index("idx_edges_type", "type"),
        Index("idx_edges_document_id", "document_id"),  # Index for FK queries
        Index("idx_edges_properties", "properties", postgresql_using="gin"),  # GIN index for JSONB
        Index("idx_edges_source_target", "source_id", "target_id"),
    )


# ============================================================
# DOCUMENT STORE (for file management)
# ============================================================

class Document(Base):
    """Original documents with metadata."""
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String, nullable=False, unique=True)
    file_hash = Column(String, nullable=False, index=True)  # SHA256 for deduplication
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String, nullable=True)
    
    # Timestamps
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    
    # Status
    status = Column(String, default="pending")  # pending, processing, completed, failed
    
    # Progress tracking
    total_chunks = Column(Integer, default=0, nullable=False)
    processed_chunks = Column(Integer, default=0, nullable=False)
    
    # Additional metadata (avoid reserved name 'metadata')
    doc_metadata = Column(JSONB, default=dict)
    
    # PERFORMANCE FIX: Add back_populates relationships for efficient querying
    nodes = relationship("Node", back_populates="document", cascade="all, delete-orphan")
    edges = relationship("Edge", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """Chunked document text for retrieval."""
    __tablename__ = "document_chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    
    # Content
    text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=True)
    
    # Source location
    page_number = Column(Integer, nullable=True)
    start_char = Column(Integer, nullable=True)
    end_char = Column(Integer, nullable=True)
    
    # Metadata
    chunk_metadata = Column(JSONB, default=dict)
    
    __table_args__ = (
        Index("idx_chunk_document", "document_id", "chunk_index"),
    )


# ============================================================
# DATABASE SETUP
# ============================================================

def get_engine():
    """Create or reuse a singleton SQLAlchemy engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,  # Verify connections before using
            echo=False
        )
    return _engine


def get_session():
    """Get a new database session."""
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(bind=engine)
    return _SessionLocal()


def init_db():
    """Initialize database and create all tables.
    
    FATAL: Raises RuntimeError if PostgreSQL connection fails.
    No silent failures allowed in production.
    """
    try:
        engine = get_engine()
        # Test connection before proceeding
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        Base.metadata.create_all(engine)
        _ensure_schema(engine)
        return engine
    except Exception as e:
        raise RuntimeError(f"FATAL: PostgreSQL connection failed: {e}") from e


def reset_db():
    """Drop all tables and recreate (USE WITH CAUTION)."""
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def _ensure_schema(engine) -> None:
    """Ensure new columns/indexes exist for live databases (lightweight migration)."""
    inspector = inspect(engine)
    with engine.begin() as conn:
        # Ensure nodes.document_id exists
        if "nodes" in inspector.get_table_names():
            node_columns = {col["name"] for col in inspector.get_columns("nodes")}
            if "document_id" not in node_columns:
                conn.execute(text("ALTER TABLE nodes ADD COLUMN document_id UUID"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_nodes_document_id ON nodes (document_id)"))
            # Add FK constraint if missing (nullable, safe for existing data)
            node_fks = {fk.get("name") for fk in inspector.get_foreign_keys("nodes")}
            if "fk_nodes_document_id" not in node_fks:
                conn.execute(text(
                    "ALTER TABLE nodes ADD CONSTRAINT fk_nodes_document_id "
                    "FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE"
                ))

        # Ensure edges.document_id exists
        if "edges" in inspector.get_table_names():
            edge_columns = {col["name"] for col in inspector.get_columns("edges")}
            if "document_id" not in edge_columns:
                conn.execute(text("ALTER TABLE edges ADD COLUMN document_id UUID"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_edges_document_id ON edges (document_id)"))
            # Add FK constraint if missing (nullable, safe for existing data)
            edge_fks = {fk.get("name") for fk in inspector.get_foreign_keys("edges")}
            if "fk_edges_document_id" not in edge_fks:
                conn.execute(text(
                    "ALTER TABLE edges ADD CONSTRAINT fk_edges_document_id "
                    "FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE"
                ))

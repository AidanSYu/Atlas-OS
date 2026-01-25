"""
Database models and connection management.

Implements a flexible Triple Store schema:
- nodes: id (UUID), label (String), properties (JSONB)
- edges: id (UUID), source_id (UUID), target_id (UUID), type (String), properties (JSONB)
"""
from sqlalchemy import (
    create_engine, Column, String, Integer, DateTime, Text, ForeignKey, 
    JSON, Index, UUID as SQLUUID
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
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
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
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    source_node = relationship("Node", foreign_keys=[source_id], back_populates="outgoing_edges")
    target_node = relationship("Node", foreign_keys=[target_id], back_populates="incoming_edges")
    
    __table_args__ = (
        Index("idx_edges_source", "source_id"),
        Index("idx_edges_target", "target_id"),
        Index("idx_edges_type", "type"),
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
    """Initialize database and create all tables."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    return engine


def reset_db():
    """Drop all tables and recreate (USE WITH CAUTION)."""
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

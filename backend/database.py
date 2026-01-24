"""
Database initialization and schema for PostgreSQL-backed knowledge layer.

This module creates:
1. Document store tables
2. Knowledge graph tables (entities and relationships)
3. Indexes for efficient queries
"""

from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, ForeignKey, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
from config import settings

Base = declarative_base()
_engine = None

# ============================================================
# DOCUMENT STORE
# ============================================================

class Document(Base):
    """Original documents with metadata."""
    __tablename__ = "documents"
    
    id = Column(String, primary_key=True)  # UUID
    filename = Column(String, nullable=False, unique=True)
    file_hash = Column(String, nullable=False, index=True)  # SHA256 for deduplication
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String)
    
    # Timestamps
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    
    # Status
    status = Column(String, default="pending")  # pending, processing, completed, failed
    
    # Metadata
    doc_metadata = Column(JSON)  # Additional document-specific metadata
    
    # Relationships
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    entities = relationship("Entity", back_populates="document")

class DocumentChunk(Base):
    """Chunked document text for retrieval."""
    __tablename__ = "document_chunks"
    
    id = Column(String, primary_key=True)  # chunk_id
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    
    # Content
    text = Column(Text, nullable=False)
    chunk_index = Column(Integer)
    
    # Source location
    page_number = Column(Integer)
    start_char = Column(Integer)
    end_char = Column(Integer)
    
    # Metadata
    chunk_metadata = Column(JSON)
    
    # Relationships
    document = relationship("Document", back_populates="chunks")
    
    __table_args__ = (
        Index("idx_chunk_document", "document_id", "chunk_index"),
    )

# ============================================================
# KNOWLEDGE GRAPH
# ============================================================

class Entity(Base):
    """Entities extracted from documents (nodes in the knowledge graph)."""
    __tablename__ = "entities"
    
    id = Column(String, primary_key=True)  # UUID
    
    # Entity information
    name = Column(String, nullable=False, index=True)
    entity_type = Column(String, nullable=False, index=True)  # person, org, concept, chemical, etc.
    description = Column(Text)
    
    # Source
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    chunk_id = Column(String, ForeignKey("document_chunks.id"), index=True)
    page_number = Column(Integer)
    
    # Metadata
    entity_properties = Column(JSON)  # Additional entity-specific properties
    confidence = Column(Float)  # Extraction confidence score
    
    # Timestamps
    extracted_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    document = relationship("Document", back_populates="entities")
    outgoing_relationships = relationship("Relationship", 
                                         foreign_keys="Relationship.source_id",
                                         back_populates="source")
    incoming_relationships = relationship("Relationship", 
                                         foreign_keys="Relationship.target_id",
                                         back_populates="target")
    
    __table_args__ = (
        Index("idx_entity_name_type", "name", "entity_type"),
        Index("idx_entity_document", "document_id", "entity_type"),
    )

class Relationship(Base):
    """Relationships between entities (edges in the knowledge graph)."""
    __tablename__ = "relationships"
    
    id = Column(String, primary_key=True)  # UUID
    
    # Relationship structure
    source_id = Column(String, ForeignKey("entities.id"), nullable=False, index=True)
    target_id = Column(String, ForeignKey("entities.id"), nullable=False, index=True)
    relationship_type = Column(String, nullable=False, index=True)  # mentions, uses, produces, etc.
    
    # Context
    context = Column(Text)  # Text snippet where relationship was found
    document_id = Column(String, ForeignKey("documents.id"), index=True)
    
    # Metadata
    rel_properties = Column(JSON)  # Additional relationship properties
    confidence = Column(Float)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    source = relationship("Entity", foreign_keys=[source_id], back_populates="outgoing_relationships")
    target = relationship("Entity", foreign_keys=[target_id], back_populates="incoming_relationships")
    
    __table_args__ = (
        Index("idx_rel_source_type", "source_id", "relationship_type"),
        Index("idx_rel_target_type", "target_id", "relationship_type"),
        Index("idx_rel_document", "document_id"),
    )

# ============================================================
# DATABASE SETUP
# ============================================================

def _get_engine():
    """Create or reuse a singleton SQLAlchemy engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(settings.database_url)
    return _engine

def init_db():
    """Initialize database and create all tables."""
    engine = _get_engine()
    Base.metadata.create_all(engine)
    return engine

def get_session():
    """Get a new database session."""
    engine = _get_engine()
    Session = sessionmaker(bind=engine)
    return Session()

def reset_db():
    """Drop all tables and recreate (USE WITH CAUTION)."""
    engine = _get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

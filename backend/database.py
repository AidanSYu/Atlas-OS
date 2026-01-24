"""Database models and connection management."""
from sqlalchemy import create_engine, Column, String, DateTime, Integer, Text, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from config import settings

# Database setup
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Models
class Document(Base):
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String, nullable=False)
    file_hash = Column(String, unique=True, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    
    # Relationships
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    page_number = Column(Integer)
    start_char = Column(Integer)
    end_char = Column(Integer)
    chunk_metadata = Column(JSON)
    
    # Relationships
    document = relationship("Document", back_populates="chunks")

class Node(Base):
    __tablename__ = "nodes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    label = Column(String, nullable=False)  # entity type
    properties = Column(JSON, nullable=False)  # name, description, etc.
    created_at = Column(DateTime, default=datetime.utcnow)

class Edge(Base):
    __tablename__ = "edges"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("nodes.id"), nullable=False)
    target_id = Column(UUID(as_uuid=True), ForeignKey("nodes.id"), nullable=False)
    type = Column(String, nullable=False)  # relationship type
    properties = Column(JSON)  # context, confidence, etc.
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)

def get_session() -> Session:
    """Get database session."""
    return SessionLocal()
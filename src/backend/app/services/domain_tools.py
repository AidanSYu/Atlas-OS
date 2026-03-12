"""
Domain-agnostic tool services for the Discovery OS Golden Path.

Provides:
- Molecular / entity rendering (RDKit where available, SVG fallback otherwise)
- Capability gap storage and resolution
"""
import uuid
import logging
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, Literal

from app.core.database import get_session, get_engine, Base
from sqlalchemy import Column, String, Integer, JSON, DateTime, Text
from datetime import datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database model for capability gaps (lightweight, self-contained table)
# ---------------------------------------------------------------------------

class CapabilityGapRecord(Base):
    __tablename__ = "capability_gaps"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, nullable=False)
    stage = Column(Integer, nullable=False)
    required_function = Column(Text, nullable=False)
    input_schema = Column(JSON, nullable=False, default=dict)
    output_schema = Column(JSON, nullable=False, default=dict)
    standard_reference = Column(Text, nullable=True)
    resolution_method = Column(String, nullable=True)
    resolution_config = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


def ensure_capability_gap_table():
    """Create the capability_gaps table if it doesn't exist yet."""
    engine = get_engine()
    CapabilityGapRecord.__table__.create(bind=engine, checkfirst=True)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_molecule_2d_svg(smiles: str, width: int = 300, height: int = 200) -> str:
    """Render a SMILES string to an SVG via RDKit. Falls back to a labelled
    placeholder SVG when RDKit is unavailable."""
    try:
        from rdkit import Chem
        from rdkit.Chem.Draw import rdMolDraw2D

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return _placeholder_svg(f"Invalid SMILES: {smiles[:60]}", width, height)

        drawer = rdMolDraw2D.MolDraw2DSVG(width, height)
        drawer.DrawMolecule(mol)
        drawer.FinishDrawing()
        return drawer.GetDrawingText()
    except ImportError:
        logger.debug("RDKit not installed — returning placeholder SVG")
        return _placeholder_svg(smiles, width, height)
    except Exception as exc:
        logger.warning(f"RDKit render failed for '{smiles[:40]}': {exc}")
        return _placeholder_svg(f"Render error: {smiles[:60]}", width, height)


def render_placeholder_svg(
    data_preview: str,
    render_type: str,
    width: int = 300,
    height: int = 200,
) -> str:
    """Generic placeholder SVG for render types not yet implemented."""
    label = f"[{render_type}]  {data_preview[:80]}"
    return _placeholder_svg(label, width, height)


def _placeholder_svg(label: str, w: int, h: int) -> str:
    from xml.sax.saxutils import escape
    safe = escape(label)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">'
        f'<rect width="{w}" height="{h}" rx="8" fill="#1a1a2e" stroke="#30305a" stroke-width="1.5"/>'
        f'<text x="{w // 2}" y="{h // 2}" text-anchor="middle" dominant-baseline="central" '
        f'fill="#a0a0c0" font-family="monospace" font-size="11">{safe}</text>'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# Capability gap CRUD
# ---------------------------------------------------------------------------

def create_capability_gap(
    run_id: str,
    stage: int,
    required_function: str,
    input_schema: dict,
    output_schema: dict,
    standard_reference: Optional[str] = None,
) -> str:
    """Persist a new capability gap record. Returns the gap_id."""
    ensure_capability_gap_table()
    gap_id = str(uuid.uuid4())
    session = get_session()
    try:
        record = CapabilityGapRecord(
            id=gap_id,
            run_id=run_id,
            stage=stage,
            required_function=required_function,
            input_schema=input_schema,
            output_schema=output_schema,
            standard_reference=standard_reference,
        )
        session.add(record)
        session.commit()
        return gap_id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def resolve_capability_gap(
    gap_id: str,
    method: Literal["local_script", "api_endpoint", "plugin", "skip"],
    config: dict,
) -> None:
    """Validate and store the resolution for a capability gap."""
    if method == "local_script":
        path = config.get("path", "")
        if not path or not Path(path).exists():
            raise ValueError(f"Local script path does not exist: {path}")

    if method == "api_endpoint":
        url = config.get("url", "")
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL: {url}")

    ensure_capability_gap_table()
    session = get_session()
    try:
        record = session.query(CapabilityGapRecord).filter_by(id=gap_id).first()
        if record is None:
            raise ValueError(f"Capability gap not found: {gap_id}")

        record.resolution_method = method
        record.resolution_config = config
        record.resolved_at = datetime.utcnow()
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

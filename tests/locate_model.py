
import logging
import inspect
from pathlib import Path
from sentence_transformers import SentenceTransformer

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def locate_model_code():
    # Use relative path from this script
    model_path = Path(__file__).resolve().parent.parent / "models" / "nomic-embed-text-v1.5"
    
    logger.info(f"Loading model from {model_path}")
    try:
        model = SentenceTransformer(str(model_path), trust_remote_code=True)
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        return

    # Get the underlying transformer model (first module usually)
    transformer = model[0].auto_model
    logger.info(f"Transformer type: {type(transformer)}")
    
    # Get the file defining the class
    source_file = inspect.getfile(transformer.__class__)
    logger.info(f"Source file for model class: {source_file}")

if __name__ == "__main__":
    locate_model_code()

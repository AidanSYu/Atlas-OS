
import logging
from pathlib import Path
from sentence_transformers import SentenceTransformer
import torch

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_embedding():
    # Path from logs
    model_path = Path("C:/Users/aidan/OneDrive - Duke University/Code/ContAInnum_Atlas2.0_backup_20260124_181415/models/nomic-embed-text-v1.5")
    
    if not model_path.exists():
        logger.error(f"Model path does not exist: {model_path}")
        return

    logger.info(f"Loading model from {model_path}")
    try:
        model = SentenceTransformer(str(model_path), trust_remote_code=True)
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        return

    logger.info("Model loaded. Testing embeddings...")
    
    # Test cases with varying lengths to trigger the shape mismatch
    # 160 and 175 were mentioned in the error.
    # We will try lengths ensuring token count is around that.
    # ~4 chars per token. 160 tokens ~ 640 chars.
    
    test_texts = [
        "Short text.",
        "A" * 100,
        "A" * 500,  # ~125 tokens
        "A" * 640,  # ~160 tokens
        "A" * 700,  # ~175 tokens
        "A" * 1000, # ~250 tokens
        "search_document: " + "A" * 640,
    ]

    for i, text in enumerate(test_texts):
        try:
            logger.info(f"Embedding text {i} length {len(text)}...")
            emb = model.encode(text)
            logger.info(f"Success. Shape: {emb.shape}")
        except Exception as e:
            logger.error(f"Failed to embed text {i}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_embedding()

"""
Download required models for offline bundling.

This script downloads all AI models needed for the Atlas desktop application:
1. Llama 3 8B (GGUF format, quantized) - for text generation
2. nomic-embed-text-v1.5 - for text embeddings
3. GLiNER small - for named entity recognition

Run this script before building the desktop app to ensure all models are bundled.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from huggingface_hub import hf_hub_download, snapshot_download


def get_models_dir() -> Path:
    """Get the models directory path."""
    # Try to use settings, fall back to default
    try:
        from app.core.config import settings
        models_dir = Path(settings.MODELS_DIR)
    except Exception:
        models_dir = Path(__file__).parent.parent / "models"
    
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir


def download_llama_model(models_dir: Path) -> None:
    """Download Llama 3 8B GGUF model."""
    print("Downloading Llama 3 8B Instruct (Q4_K_M quantization)...")
    print("This is approximately 4.7GB and may take a while.")
    
    try:
        hf_hub_download(
            repo_id="bartowski/Meta-Llama-3-8B-Instruct-GGUF",
            filename="Meta-Llama-3-8B-Instruct-Q4_K_M.gguf",
            local_dir=models_dir,
            local_dir_use_symlinks=False
        )
        print("Llama 3 8B model downloaded successfully!")
    except Exception as e:
        print(f"Error downloading Llama model: {e}")
        print("You may need to accept the license at https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct")
        raise


def download_embedding_model(models_dir: Path) -> None:
    """Download nomic-embed-text embedding model."""
    print("Downloading nomic-embed-text-v1.5...")
    print("This is approximately 275MB.")
    
    embed_dir = models_dir / "nomic-embed-text-v1.5"
    
    try:
        snapshot_download(
            repo_id="nomic-ai/nomic-embed-text-v1.5",
            local_dir=embed_dir,
            local_dir_use_symlinks=False
        )
        print("Embedding model downloaded successfully!")
    except Exception as e:
        print(f"Error downloading embedding model: {e}")
        raise


def download_gliner_model(models_dir: Path) -> None:
    """Download GLiNER model for entity extraction."""
    print("Downloading GLiNER small model...")
    print("This is approximately 50MB.")
    
    gliner_dir = models_dir / "gliner_small-v2.1"
    
    try:
        snapshot_download(
            repo_id="urchade/gliner_small-v2.1",
            local_dir=gliner_dir,
            local_dir_use_symlinks=False
        )
        print("GLiNER model downloaded successfully!")
    except Exception as e:
        print(f"Error downloading GLiNER model: {e}")
        raise


def main():
    """Download all required models."""
    print("=" * 60)
    print("Atlas 2.0 Model Download Script")
    print("=" * 60)
    print()
    
    models_dir = get_models_dir()
    print(f"Models will be downloaded to: {models_dir}")
    print()
    
    # Check existing models
    llama_exists = any(models_dir.glob("*.gguf"))
    embed_exists = (models_dir / "nomic-embed-text-v1.5").exists()
    gliner_exists = (models_dir / "gliner_small-v2.1").exists()
    
    if llama_exists and embed_exists and gliner_exists:
        print("All models already downloaded!")
        print()
        print("To re-download, delete the models directory and run again.")
        return
    
    # Download missing models
    if not llama_exists:
        print("-" * 60)
        download_llama_model(models_dir)
        print()
    else:
        print("Llama model already exists, skipping...")
    
    if not embed_exists:
        print("-" * 60)
        download_embedding_model(models_dir)
        print()
    else:
        print("Embedding model already exists, skipping...")
    
    if not gliner_exists:
        print("-" * 60)
        download_gliner_model(models_dir)
        print()
    else:
        print("GLiNER model already exists, skipping...")
    
    print("=" * 60)
    print("All models downloaded successfully!")
    print()
    print(f"Models location: {models_dir}")
    print()
    print("Total estimated size: ~5GB")
    print("=" * 60)


if __name__ == "__main__":
    main()

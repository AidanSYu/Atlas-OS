import os
import sys
from huggingface_hub import hf_hub_download
from pathlib import Path

def download_model():
    # Define paths
    # Fix: Correctly navigate from this script location (scripts/setup) to the models dir
    # Actually, simpler to just use the environment variable or a known relative path from the project root.
    # The user's metadata shows the files are in `.../scripts/setup/fix_gpu.ps1`
    # Let's assume this script is run from the project root or src/backend.
    
    # We will output to the standard dev models directory for now: src/backend/models
    # But wait, run_server.py says:
    # Dev: Path(__file__).resolve().parent.parent.parent / "models" -> which is project_root/models
    
    # Let's try to find the project root
    current_dir = Path(os.getcwd())
    if "src" in str(current_dir):
        # We are likely in src/backend or similar
        project_root = current_dir
        while project_root.name != "ContAInnum_Atlas2.0_backup_20260124_181415" and project_root.parent != project_root:
            project_root = project_root.parent
    else:
        # Fallback
        project_root = Path(r"C:\Users\aidan\OneDrive - Duke University\Code\ContAInnum_Atlas2.0_backup_20260124_181415")
        
    models_dir = project_root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Target models directory: {models_dir}")
    
    repo_id = "bartowski/Phi-3.5-mini-instruct-GGUF"
    filename = "Phi-3.5-mini-instruct-Q5_K_M.gguf"
    
    print(f"Downloading {filename} from {repo_id}...")
    try:
        model_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=str(models_dir),
            local_dir_use_symlinks=False
        )
        print(f"Successfully downloaded to: {model_path}")
    except Exception as e:
        print(f"Error downloading model: {e}")
        sys.exit(1)

if __name__ == "__main__":
    download_model()

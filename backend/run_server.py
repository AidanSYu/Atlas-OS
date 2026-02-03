"""
Atlas Backend Server Entry Point

This is the main entry point for the PyInstaller-bundled backend.
It starts the FastAPI server with uvicorn.
"""
import os
import sys
import logging
from pathlib import Path

# Configure logging before any imports
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent
    
    return base_path / relative_path


def setup_environment():
    """Set up environment variables for bundled app."""
    # Set MODELS_DIR to bundled models location
    if hasattr(sys, '_MEIPASS'):
        models_dir = get_resource_path('models')
        os.environ.setdefault('MODELS_DIR', str(models_dir))
        logger.info(f"Using bundled models from: {models_dir}")
        
        # Set upload directory to user's app data
        if sys.platform == 'win32':
            app_data = Path(os.environ.get('LOCALAPPDATA', '')) / 'Atlas'
        elif sys.platform == 'darwin':
            app_data = Path.home() / 'Library' / 'Application Support' / 'Atlas'
        else:
            app_data = Path.home() / '.atlas'
        
        app_data.mkdir(parents=True, exist_ok=True)
        upload_dir = app_data / 'uploads'
        upload_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault('UPLOAD_DIR', str(upload_dir))
        logger.info(f"Using upload directory: {upload_dir}")


def main():
    """Start the Atlas backend server."""
    import uvicorn
    
    logger.info("Starting Atlas Backend Server...")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    
    # Set up environment for bundled app
    setup_environment()
    
    # Import the app after environment setup
    from app.main import app
    
    # Run the server
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info",
        access_log=True
    )


if __name__ == "__main__":
    main()

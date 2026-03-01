"""
ML Model Loader Utilities
Handles loading and initialization of ML models
"""

import logging
from pathlib import Path
from typing import Optional
import os

logger = logging.getLogger(__name__)


class ModelLoader:
    """Utility class for loading ML models"""
    
    @staticmethod
    def get_model_path(model_name: str) -> Optional[Path]:
        """
        Get path to model file
        
        Args:
            model_name: Name of the model
            
        Returns:
            Path to model file if it exists, None otherwise
        """
        logger.info(f"Searching for model: {model_name}")
        logger.info(f"Current working directory: {Path.cwd()}")
        
        # Check in multiple locations (prefer .keras over .h5)
        possible_paths = [
            Path("models") / f"{model_name}.keras",
            Path("app/ml/models") / f"{model_name}.keras",
            Path("ml/models") / f"{model_name}.keras",
            Path("models") / f"{model_name}.h5",
            Path("models") / f"{model_name}.keras",
            Path("app/ml/models") / f"{model_name}.h5",
            Path("ml/models") / f"{model_name}.h5",
        ]
        
        for path in possible_paths:
            absolute_path = path.resolve()
            logger.debug(f"  Checking: {path} (absolute: {absolute_path})")
            if path.exists():
                logger.info(f">>> FOUND MODEL at {path.resolve()} <<<")
                return path
        
        logger.error(f"XXX Model {model_name} not found in any location XXX")
        logger.error(f"Searched paths: {[str(p) for p in possible_paths]}")
        return None
    
    @staticmethod
    def load_lstm_predictor():
        """
        Load LSTM predictor model
        
        Returns:
            LSTMPredictor instance
        """
        from app.ml.lstm_predictor import LSTMPredictor
        
        # Try both possible model names
        model_path = (ModelLoader.get_model_path("lstm_network_predictor") or 
                     ModelLoader.get_model_path("lstm_signal_predictor"))
        
        if model_path:
            predictor = LSTMPredictor(model_path=str(model_path))
        else:
            logger.warning("LSTM model not found. Using heuristic fallback.")
            predictor = LSTMPredictor()  # Will use heuristic
        
        return predictor

"""
LSTM Time-Series Predictor for Network Signal Drop Prediction
Implements the predictive monitoring component
"""

import numpy as np
from typing import List, Optional, Tuple
import logging
from datetime import datetime

from app.models.telemetry import NetworkTelemetry, SignalDropPrediction
from app.core.config import settings

logger = logging.getLogger(__name__)


class LSTMPredictor:
    """
    LSTM-based time-series predictor for network signal drops
    
    Features used:
    - Signal strength
    - Latency (ms)
    - Packet loss (%)
    - Bandwidth (Kbps)
    - GPS velocity (km/h)
    - Time-of-day
    - Location hash (encoded)
    """
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize LSTM predictor
        
        Args:
            model_path: Path to saved model file (.h5 or .keras)
        """
        self.model = None
        self.model_version = "lstm_v1"
        self.sequence_length = 10  # Number of historical points needed
        self.prediction_horizon = 5  # Seconds ahead to predict
        
        # Feature normalization parameters (learned during training)
        self.feature_means = np.array([0.7, 200.0, 5.0, 2000.0, 30.0])
        self.feature_stds = np.array([0.2, 150.0, 8.0, 1500.0, 40.0])
        
        if model_path:
            self.load_model(model_path)
        else:
            logger.warning("LSTM model not loaded. Using heuristic fallback.")
    
    def load_model(self, model_path: str) -> bool:
        """
        Load trained LSTM model
        
        Args:
            model_path: Path to model file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Attempting to load LSTM model from: {model_path}")
            # Lazy import TensorFlow only when needed
            import tensorflow as tf
            
            self.model = tf.keras.models.load_model(model_path)
            logger.info(f"✓✓✓ LSTM model loaded successfully from {model_path} ✓✓✓")
            logger.info(f"Model summary: {self.model.summary()}")
            return True
        except Exception as e:
            logger.error(f"Failed to load LSTM model: {e}", exc_info=True)
            self.model = None
            return False
    
    def prepare_features(self, telemetry_points: List[NetworkTelemetry]) -> np.ndarray:
        """
        Extract and normalize features from telemetry points
        
        Args:
            telemetry_points: List of telemetry data points (time-ordered)
            
        Returns:
            Normalized feature array of shape (sequence_length, num_features)
        """
        features = []
        
        for point in telemetry_points:
            feature_vector = [
                point.signal_strength,
                point.latency_ms,
                point.packet_loss_percent,
                point.bandwidth_kbps,
                point.gps_velocity_kmh
            ]
            features.append(feature_vector)
        
        features_array = np.array(features)
        
        # Normalize features
        normalized = (features_array - self.feature_means) / self.feature_stds
        
        return normalized
    
    def predict_signal_drop(
        self, 
        telemetry_history: List[NetworkTelemetry],
        device_id: str,
        session_id: str
    ) -> Optional[SignalDropPrediction]:
        """
        Predict if signal drop will occur within prediction horizon
        
        Args:
            telemetry_history: Recent telemetry points (at least 10 points)
            device_id: Device identifier
            session_id: Session identifier
            
        Returns:
            SignalDropPrediction if drop is predicted, None otherwise
        """
        if len(telemetry_history) < self.sequence_length:
            logger.warning(f"Insufficient telemetry history: {len(telemetry_history)} < {self.sequence_length}")
            return None
        
        # Use most recent points
        recent_points = telemetry_history[-self.sequence_length:]
        
        # Prepare features
        features = self.prepare_features(recent_points)
        
        # Use ML model if available, otherwise use heuristic
        if self.model is not None:
            return self._predict_with_model(features, device_id, session_id)
        else:
            return self._predict_with_heuristic(recent_points, device_id, session_id)
    
    def _predict_with_model(
        self, 
        features: np.ndarray,
        device_id: str,
        session_id: str
    ) -> Optional[SignalDropPrediction]:
        """
        Predict using trained LSTM model
        
        Args:
            features: Normalized feature array
            device_id: Device identifier
            session_id: Session identifier
            
        Returns:
            SignalDropPrediction if drop is predicted, None otherwise
        """
        try:
            # Reshape for LSTM: (batch_size, sequence_length, num_features)
            input_data = features.reshape(1, *features.shape)
            
            # Get prediction
            # Model outputs: probability_of_drop (sigmoid output for binary classification)
            prediction = self.model.predict(input_data, verbose=0)
            
            drop_probability = float(prediction[0][0])
            
            # Estimate current bandwidth from last telemetry point (use as predicted bandwidth)
            # Since we moved to binary classification, we don't predict bandwidth anymore
            predicted_bandwidth = float(features[-1][3] * self.feature_stds[3] + self.feature_means[3])
            
            # Check if prediction exceeds threshold
            if drop_probability >= settings.PREDICTION_THRESHOLD:
                # Estimate time to signal drop based on current trend
                time_to_drop = self._estimate_time_to_drop(features)
                
                return SignalDropPrediction(
                    device_id=device_id,
                    session_id=session_id,
                    timestamp=datetime.now().timestamp(),
                    confidence=drop_probability,
                    predicted_time_seconds=time_to_drop,
                    predicted_bandwidth_kbps=max(0, predicted_bandwidth),
                    prediction_horizon_seconds=self.prediction_horizon,
                    model_version=self.model_version,
                    features_used=["signal_strength", "latency_ms", "packet_loss_percent", 
                                   "bandwidth_kbps", "gps_velocity_kmh"],
                    predictor_type="lstm"
                )
            
            return None
            
        except Exception as e:
            logger.error(f"LSTM prediction failed: {e}")
            return None
    
    def _predict_with_heuristic(
        self,
        telemetry_points: List[NetworkTelemetry],
        device_id: str,
        session_id: str
    ) -> Optional[SignalDropPrediction]:
        """
        Fallback heuristic-based prediction when ML model unavailable
        
        Args:
            telemetry_points: Recent telemetry points
            device_id: Device identifier
            session_id: Session identifier
            
        Returns:
            SignalDropPrediction if drop is predicted, None otherwise
        """
        # Calculate trends
        signal_strengths = [p.signal_strength for p in telemetry_points]
        bandwidths = [p.bandwidth_kbps for p in telemetry_points]
        latencies = [p.latency_ms for p in telemetry_points]
        
        # Check for declining trends
        signal_trend = np.polyfit(range(len(signal_strengths)), signal_strengths, 1)[0]
        bandwidth_trend = np.polyfit(range(len(bandwidths)), bandwidths, 1)[0]
        latency_trend = np.polyfit(range(len(latencies)), latencies, 1)[0]
        
        # Current values
        current_signal = signal_strengths[-1]
        current_bandwidth = bandwidths[-1]
        current_latency = latencies[-1]
        
        # Heuristic rules
        signal_declining = signal_trend < -0.05  # Declining more than 5% per sample
        bandwidth_declining = bandwidth_trend < -100  # Declining more than 100 Kbps per sample
        latency_increasing = latency_trend > 50  # Increasing more than 50ms per sample
        
        # Calculate confidence based on multiple indicators
        indicators_triggered = sum([signal_declining, bandwidth_declining, latency_increasing])
        base_confidence = 0.6 if indicators_triggered >= 2 else 0.0
        
        # Adjust confidence based on severity
        if current_signal < 0.3:
            base_confidence += 0.2
        if current_bandwidth < 500:
            base_confidence += 0.15
        if current_latency > 500:
            base_confidence += 0.15
        
        confidence = min(1.0, base_confidence)
        
        if confidence >= settings.PREDICTION_THRESHOLD:
            # Estimate time to critical drop
            if signal_declining and signal_trend != 0:
                time_to_drop = max(0.5, min(5.0, abs((0.2 - current_signal) / signal_trend)))
            else:
                time_to_drop = 3.0  # Default estimate
            
            # Predict minimum bandwidth
            predicted_bandwidth = max(0, current_bandwidth + (bandwidth_trend * 3))
            
            return SignalDropPrediction(
                device_id=device_id,
                session_id=session_id,
                timestamp=datetime.now().timestamp(),
                confidence=confidence,
                predicted_time_seconds=time_to_drop,
                predicted_bandwidth_kbps=predicted_bandwidth,
                prediction_horizon_seconds=self.prediction_horizon,
                model_version="heuristic_fallback",
                predictor_type="heuristic",
                features_used=["signal_strength_trend", "bandwidth_trend", "latency_trend"]
            )
        
        return None
    
    def _estimate_time_to_drop(self, features: np.ndarray) -> float:
        """
        Estimate time until signal drop based on trends
        
        Args:
            features: Normalized feature array
            
        Returns:
            Estimated time to signal drop in seconds
        """
        # Calculate rate of change for signal strength
        signal_strengths = features[:, 0]  # First feature is signal strength
        
        if len(signal_strengths) >= 2:
            # Fit linear trend
            trend = np.polyfit(range(len(signal_strengths)), signal_strengths, 1)[0]
            
            if trend < 0:  # Declining signal
                # Denormalize current signal
                current_signal = signal_strengths[-1] * self.feature_stds[0] + self.feature_means[0]
                
                # Estimate time to reach critical threshold (0.2)
                if current_signal > 0.2:
                    # Convert trend from normalized to actual
                    actual_trend = trend * self.feature_stds[0]
                    time_to_drop = (0.2 - current_signal) / actual_trend
                    
                    # Clamp to reasonable range
                    return max(0.5, min(self.prediction_horizon, abs(time_to_drop)))
        
        # Default estimate
        return 3.0

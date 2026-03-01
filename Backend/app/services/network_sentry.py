"""
Network Sentry Agent Service
Implements predictive network monitoring and signal drop detection
"""

import logging
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from collections import defaultdict

from app.models.telemetry import (
    NetworkTelemetry, 
    SignalDropPrediction, 
    PredictionRequest,
    PredictionResponse
)
from app.ml.lstm_predictor import LSTMPredictor
from app.core.config import settings

logger = logging.getLogger(__name__)


class NetworkSentryAgent:
    """
    Network Sentry Agent - Predictive Monitoring Component
    
    Responsibilities:
    - Collect and store network telemetry
    - Run time-series prediction models
    - Detect signal drop events
    - Maintain location-based historical patterns
    """
    
    def __init__(self, predictor: Optional[LSTMPredictor] = None):
        """
        Initialize Network Sentry Agent
        
        Args:
            predictor: LSTM predictor instance (optional)
        """
        self.predictor = predictor or LSTMPredictor()
        
        # In-memory storage for recent telemetry (for demo)
        # In production, this would be stored in Timestream
        self.telemetry_buffer: Dict[str, List[NetworkTelemetry]] = defaultdict(list)
        self.max_buffer_size = 100
        
        # Prediction cache to avoid redundant predictions
        self.prediction_cache: Dict[str, SignalDropPrediction] = {}
        self.cache_ttl_seconds = 2  # Cache predictions for 2 seconds
        
        logger.info("Network Sentry Agent initialized")
    
    def ingest_telemetry(self, telemetry: NetworkTelemetry) -> bool:
        """
        Ingest a single telemetry data point
        
        Args:
            telemetry: Network telemetry data point
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Store in buffer
            key = f"{telemetry.device_id}:{telemetry.session_id}"
            self.telemetry_buffer[key].append(telemetry)
            
            # Maintain buffer size
            if len(self.telemetry_buffer[key]) > self.max_buffer_size:
                self.telemetry_buffer[key] = self.telemetry_buffer[key][-self.max_buffer_size:]
            
            logger.debug(f"Telemetry ingested for {key}: signal={telemetry.signal_strength:.2f}, "
                        f"bandwidth={telemetry.bandwidth_kbps:.0f} Kbps")
            
            # In production: Store in AWS Timestream
            # await self.timestream_client.write_telemetry(telemetry)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to ingest telemetry: {e}")
            return False
    
    def ingest_telemetry_batch(self, batch: List[NetworkTelemetry]) -> int:
        """
        Ingest a batch of telemetry data points
        
        Args:
            batch: List of telemetry data points
            
        Returns:
            Number of successfully ingested points
        """
        success_count = 0
        
        for telemetry in batch:
            if self.ingest_telemetry(telemetry):
                success_count += 1
        
        logger.info(f"Batch ingestion complete: {success_count}/{len(batch)} successful")
        return success_count
    
    def get_recent_telemetry(
        self, 
        device_id: str, 
        session_id: str, 
        count: int = 30
    ) -> List[NetworkTelemetry]:
        """
        Get recent telemetry points for a device/session
        
        Args:
            device_id: Device identifier
            session_id: Session identifier
            count: Number of recent points to retrieve
            
        Returns:
            List of telemetry points (time-ordered)
        """
        key = f"{device_id}:{session_id}"
        telemetry_list = self.telemetry_buffer.get(key, [])
        
        # Return most recent points
        return telemetry_list[-count:]
    
    def predict_signal_drop(
        self, 
        device_id: str,
        session_id: str,
        recent_telemetry: Optional[List[NetworkTelemetry]] = None
    ) -> PredictionResponse:
        """
        Predict if signal drop will occur
        
        Args:
            device_id: Device identifier
            session_id: Session identifier
            recent_telemetry: Optional recent telemetry (if not provided, uses buffer)
            
        Returns:
            PredictionResponse with prediction and recommended action
        """
        try:
            # Check cache first
            cache_key = f"{device_id}:{session_id}"
            cached_prediction = self._get_cached_prediction(cache_key)
            
            if cached_prediction:
                return PredictionResponse(
                    prediction=cached_prediction,
                    should_prepare_transition=True,
                    recommended_action="PREPARE_FALLBACK"
                )
            
            # Get telemetry history
            if recent_telemetry is None:
                recent_telemetry = self.get_recent_telemetry(device_id, session_id, count=30)
            
            if len(recent_telemetry) < 5:
                return PredictionResponse(
                    prediction=None,
                    should_prepare_transition=False,
                    recommended_action="COLLECT_MORE_DATA"
                )
            
            # Run prediction
            prediction = self.predictor.predict_signal_drop(
                telemetry_history=recent_telemetry,
                device_id=device_id,
                session_id=session_id
            )
            
            if prediction:
                # Cache the prediction
                self._cache_prediction(cache_key, prediction)
                
                # Determine recommended action based on prediction
                recommended_action = self._determine_recommended_action(prediction, recent_telemetry[-1])
                
                logger.info(f"Signal drop predicted for {cache_key}: "
                           f"confidence={prediction.confidence:.2f}, "
                           f"time={prediction.predicted_time_seconds:.1f}s, "
                           f"action={recommended_action}")
                
                return PredictionResponse(
                    prediction=prediction,
                    should_prepare_transition=True,
                    recommended_action=recommended_action
                )
            else:
                return PredictionResponse(
                    prediction=None,
                    should_prepare_transition=False,
                    recommended_action="CONTINUE_MONITORING"
                )
                
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return PredictionResponse(
                prediction=None,
                should_prepare_transition=False,
                recommended_action="ERROR"
            )
    
    def _get_cached_prediction(self, cache_key: str) -> Optional[SignalDropPrediction]:
        """Get cached prediction if still valid"""
        if cache_key in self.prediction_cache:
            prediction = self.prediction_cache[cache_key]
            age = datetime.now().timestamp() - prediction.timestamp
            
            if age < self.cache_ttl_seconds:
                logger.debug(f"Using cached prediction for {cache_key}")
                return prediction
            else:
                # Expired, remove from cache
                del self.prediction_cache[cache_key]
        
        return None
    
    def _cache_prediction(self, cache_key: str, prediction: SignalDropPrediction):
        """Cache a prediction"""
        self.prediction_cache[cache_key] = prediction
    
    def _determine_recommended_action(
        self, 
        prediction: SignalDropPrediction,
        current_telemetry: NetworkTelemetry
    ) -> str:
        """
        Determine recommended action based on prediction and current state
        
        Args:
            prediction: Signal drop prediction
            current_telemetry: Current telemetry data
            
        Returns:
            Recommended action string
        """
        current_bandwidth = current_telemetry.bandwidth_kbps
        predicted_bandwidth = prediction.predicted_bandwidth_kbps
        time_to_drop = prediction.predicted_time_seconds
        confidence = prediction.confidence
        
        # High confidence, immediate danger
        if confidence > 0.9 and time_to_drop < 2.0:
            if predicted_bandwidth < settings.AUDIO_MIN_BANDWIDTH:
                return "IMMEDIATE_TEXT_FALLBACK"
            else:
                return "IMMEDIATE_AUDIO_FALLBACK"
        
        # Moderate confidence, prepare fallback
        if confidence > 0.75 and time_to_drop < 5.0:
            if predicted_bandwidth < settings.AUDIO_MIN_BANDWIDTH:
                return "PREPARE_TEXT_FALLBACK"
            else:
                return "PREPARE_AUDIO_FALLBACK"
        
        # Lower confidence or more time, just prepare
        return "PREPARE_FALLBACK"
    
    def should_increase_monitoring_frequency(
        self, 
        device_id: str,
        session_id: str
    ) -> bool:
        """
        Determine if monitoring frequency should be increased
        
        Based on GPS velocity and network instability
        
        Args:
            device_id: Device identifier
            session_id: Session identifier
            
        Returns:
            True if frequency should be increased, False otherwise
        """
        recent_telemetry = self.get_recent_telemetry(device_id, session_id, count=5)
        
        if not recent_telemetry:
            return False
        
        # Check for high-speed movement
        latest = recent_telemetry[-1]
        if latest.gps_velocity_kmh >= settings.HIGH_SPEED_THRESHOLD_KMH:
            logger.info(f"High-speed movement detected: {latest.gps_velocity_kmh:.1f} km/h")
            return True
        
        # Check for network instability (high variance)
        if len(recent_telemetry) >= 5:
            signal_strengths = [t.signal_strength for t in recent_telemetry]
            variance = sum((x - sum(signal_strengths)/len(signal_strengths))**2 
                          for x in signal_strengths) / len(signal_strengths)
            
            if variance > 0.1:  # High variance
                logger.info(f"Network instability detected: variance={variance:.3f}")
                return True
        
        return False
    
    def get_monitoring_frequency(
        self,
        device_id: str,
        session_id: str
    ) -> int:
        """
        Get recommended monitoring frequency in Hz
        
        Args:
            device_id: Device identifier
            session_id: Session identifier
            
        Returns:
            Monitoring frequency in Hz
        """
        if self.should_increase_monitoring_frequency(device_id, session_id):
            return settings.HIGH_SPEED_MONITORING_FREQUENCY_HZ
        else:
            return settings.MONITORING_FREQUENCY_HZ
    
    def clear_session_data(self, device_id: str, session_id: str):
        """
        Clear telemetry data for a session
        
        Args:
            device_id: Device identifier
            session_id: Session identifier
        """
        key = f"{device_id}:{session_id}"
        if key in self.telemetry_buffer:
            del self.telemetry_buffer[key]
            logger.info(f"Cleared telemetry buffer for {key}")
        
        if key in self.prediction_cache:
            del self.prediction_cache[key]
            logger.info(f"Cleared prediction cache for {key}")

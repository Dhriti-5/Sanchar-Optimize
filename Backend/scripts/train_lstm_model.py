# Training script for LSTM signal drop predictor

"""
Train LSTM model for network signal drop prediction

Usage:
    python scripts/train_lstm_model.py --data ./data/telemetry.csv --output ./models/lstm_signal_predictor.h5
"""

import argparse
import logging
import numpy as np
import pandas as pd
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_telemetry_data(data_path: str) -> pd.DataFrame:
    """Load telemetry data from CSV"""
    logger.info(f"Loading data from {data_path}")
    df = pd.read_csv(data_path)
    logger.info(f"Loaded {len(df)} records")
    return df


def prepare_features(df: pd.DataFrame, sequence_length: int = 10):
    """Prepare features and labels for LSTM training"""
    logger.info("Preparing features...")
    
    # Feature columns
    feature_cols = [
        'signal_strength',
        'latency_ms',
        'packet_loss_percent',
        'bandwidth_kbps',
        'gps_velocity_kmh'
    ]
    
    # Create sequences
    sequences = []
    labels = []
    
    # Group by session
    for session_id, group in df.groupby('session_id'):
        group = group.sort_values('timestamp')
        values = group[feature_cols].values
        
        # Check if signal dropped (bandwidth < 500 Kbps)
        signal_dropped = (group['bandwidth_kbps'] < 500).astype(int).values
        
        for i in range(len(group) - sequence_length):
            sequences.append(values[i:i+sequence_length])
            # Label is 1 if signal drops within next 5 records
            future_drops = signal_dropped[i+1:i+6]
            labels.append(1 if any(future_drops) else 0)
    
    X = np.array(sequences)
    y = np.array(labels)
    
    logger.info(f"Prepared {len(X)} sequences")
    logger.info(f"Positive samples: {y.sum()} ({y.mean()*100:.1f}%)")
    
    return X, y


def build_lstm_model(input_shape, num_features):
    """Build LSTM model architecture"""
    try:
        import tensorflow as tf
        from tensorflow.keras import layers, models
    except ImportError:
        logger.error("TensorFlow not installed. Please install: pip install tensorflow")
        return None
    
    logger.info("Building LSTM model...")
    
    model = models.Sequential([
        # Use LSTM with input_shape directly to avoid batch_shape compatibility issues
        layers.LSTM(64, return_sequences=True, input_shape=input_shape),
        layers.Dropout(0.2),
        layers.LSTM(32),
        layers.Dropout(0.2),
        layers.Dense(16, activation='relu'),
        layers.Dense(1, activation='sigmoid')  # Binary classification: will_drop
    ])
    
    model.compile(
        optimizer='adam',
        loss='binary_crossentropy',
        metrics=['accuracy', 'AUC']
    )
    
    logger.info(f"Model built with {model.count_params()} parameters")
    return model


def train_model(model, X_train, y_train, X_val, y_val, epochs=50):
    """Train the LSTM model"""
    logger.info("Training model...")
    
    import tensorflow as tf
    
    # Callbacks
    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor='val_loss',
            patience=10,
            restore_best_weights=True
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor='val_loss',
            factor=0.5,
            patience=5
        )
    ]
    
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=32,
        callbacks=callbacks,
        verbose=1
    )
    
    logger.info("Training complete")
    return history


def main():
    parser = argparse.ArgumentParser(description='Train LSTM signal drop predictor')
    parser.add_argument('--data', type=str, required=True, help='Path to telemetry CSV')
    parser.add_argument('--output', type=str, default='app/ml/models/lstm_network_predictor.keras', 
                       help='Output model path (use .keras for best compatibility)')
    parser.add_argument('--epochs', type=int, default=50, help='Number of training epochs')
    parser.add_argument('--sequence-length', type=int, default=10, 
                       help='Sequence length for LSTM')
    
    args = parser.parse_args()
    
    # Load data
    df = load_telemetry_data(args.data)
    
    # Prepare features
    X, y = prepare_features(df, sequence_length=args.sequence_length)
    
    # Split train/val
    split_idx = int(len(X) * 0.8)
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]
    
    logger.info(f"Train: {len(X_train)}, Val: {len(X_val)}")
    
    # Build model
    model = build_lstm_model(
        input_shape=(args.sequence_length, X.shape[2]),
        num_features=X.shape[2]
    )
    
    if model is None:
        return
    
    # Train
    history = train_model(model, X_train, y_train, X_val, y_val, epochs=args.epochs)
    
    # Save model
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Use native Keras format (.keras) for best compatibility
    if output_path.suffix == '.h5':
        # Convert to .keras format
        keras_path = output_path.with_suffix('.keras')
        model.save(str(keras_path))
        logger.info(f"Model saved to {keras_path} (native Keras format)")
        logger.info(f"Note: .keras format recommended over .h5 for compatibility")
    else:
        model.save(str(output_path))
        logger.info(f"Model saved to {output_path}")
    
    # Print final metrics
    final_loss = history.history['val_loss'][-1]
    final_acc = history.history['val_accuracy'][-1]
    logger.info(f"Final validation loss: {final_loss:.4f}")
    logger.info(f"Final validation accuracy: {final_acc:.4f}")
    logger.info(f"✓ Model trained successfully and saved to {output_path}")


if __name__ == '__main__':
    main()

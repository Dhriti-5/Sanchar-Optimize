"""
Generate synthetic telemetry data for LSTM training

This creates realistic network telemetry patterns including:
- Normal conditions
- Gradual signal degradation
- Sudden drops
- Recovery patterns
"""

import numpy as np
import pandas as pd
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_session_data(session_id, num_samples=100, drop_probability=0.3):
    """Generate telemetry data for one session"""
    
    timestamps = []
    signal_strengths = []
    latencies = []
    packet_losses = []
    bandwidths = []
    velocities = []
    
    # Starting conditions
    current_time = 1709251200.0  # March 1, 2024
    signal = -65  # Good signal (dBm)
    latency = 30
    packet_loss = 0.5
    bandwidth = 5000  # 5 Mbps
    velocity = np.random.uniform(0, 80)  # 0-80 km/h
    
    # Decide if this session will have a drop
    will_drop = np.random.random() < drop_probability
    drop_point = np.random.randint(30, 70) if will_drop else None
    
    for i in range(num_samples):
        # Time progression (1 second intervals)
        current_time += 1.0
        timestamps.append(current_time)
        
        # Simulate signal drop scenario
        if will_drop and i >= drop_point - 10 and i < drop_point + 5:
            # Gradual degradation before drop
            if i < drop_point:
                degradation = (drop_point - i) / 10
                signal += np.random.normal(-2 * degradation, 1)
                latency += np.random.normal(10 * degradation, 5)
                packet_loss += np.random.normal(1 * degradation, 0.5)
                bandwidth *= (1 - 0.1 * degradation)
            # During drop
            elif i == drop_point:
                signal = -95
                latency = 200
                packet_loss = 15
                bandwidth = 200
            # Recovery
            else:
                recovery = (i - drop_point) / 5
                signal += np.random.normal(5 * recovery, 2)
                latency -= np.random.normal(20 * recovery, 10)
                packet_loss -= np.random.normal(2 * recovery, 1)
                bandwidth *= (1 + 0.2 * recovery)
        else:
            # Normal fluctuations
            signal += np.random.normal(0, 2)
            latency += np.random.normal(0, 5)
            packet_loss += np.random.normal(0, 0.2)
            bandwidth *= np.random.uniform(0.95, 1.05)
            velocity += np.random.normal(0, 5)
        
        # Clamp values to realistic ranges
        signal = np.clip(signal, -100, -50)
        latency = np.clip(latency, 10, 500)
        packet_loss = np.clip(packet_loss, 0, 20)
        bandwidth = np.clip(bandwidth, 100, 10000)
        velocity = np.clip(velocity, 0, 120)
        
        signal_strengths.append(signal)
        latencies.append(latency)
        packet_losses.append(packet_loss)
        bandwidths.append(bandwidth)
        velocities.append(velocity)
    
    return pd.DataFrame({
        'session_id': [session_id] * num_samples,
        'timestamp': timestamps,
        'signal_strength': signal_strengths,
        'latency_ms': latencies,
        'packet_loss_percent': packet_losses,
        'bandwidth_kbps': bandwidths,
        'gps_velocity_kmh': velocities
    })


def generate_training_data(num_sessions=100, output_path='data/telemetry_training.csv'):
    """Generate complete training dataset"""
    
    logger.info(f"Generating {num_sessions} sessions...")
    
    all_sessions = []
    for i in range(num_sessions):
        # Vary session lengths
        num_samples = np.random.randint(50, 150)
        session_data = generate_session_data(f"session_{i}", num_samples)
        all_sessions.append(session_data)
        
        if (i + 1) % 20 == 0:
            logger.info(f"Generated {i + 1}/{num_sessions} sessions")
    
    # Combine all sessions
    df = pd.concat(all_sessions, ignore_index=True)
    
    # Save to CSV
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    
    logger.info(f"✓ Saved {len(df)} records to {output_path}")
    
    # Print statistics
    drops = (df['bandwidth_kbps'] < 500).sum()
    logger.info(f"  Total records: {len(df)}")
    logger.info(f"  Signal drops: {drops} ({drops/len(df)*100:.1f}%)")
    logger.info(f"  Sessions: {num_sessions}")
    logger.info(f"  Avg records/session: {len(df)/num_sessions:.1f}")
    
    return df


if __name__ == '__main__':
    logger.info("Generating synthetic telemetry data for LSTM training...")
    generate_training_data(num_sessions=100, output_path='data/telemetry_training.csv')
    logger.info("Done! Now run: python scripts/train_lstm_model.py --data data/telemetry_training.csv")

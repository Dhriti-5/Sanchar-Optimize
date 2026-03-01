"""
Test script to verify LSTM model integration with backend API
"""
import requests
import time
import json

# Generate sample telemetry data (10 data points simulating SEVERE degradation)
base_time = time.time()
telemetry_points = []

for i in range(10):
    telemetry_points.append({
        "device_id": "test_device_001",
        "session_id": "test_session_001",
        "timestamp": base_time + i,
        "signal_strength": max(0.1, 0.9 - (i * 0.09)),  # Severe degradation: 0.9 -> 0.1
        "latency_ms": int(50 + (i * 50)),  # Severe increase: 50ms -> 500ms
        "packet_loss_percent": min(15.0, i * 1.5),  # High packet loss
        "bandwidth_kbps": max(200, 3000 - (i * 280)),  # Severe decrease
        "gps_velocity_kmh": 45.0,
        "location_hash": "h3_test",
        "content_id": "test_video_123",
        "content_position": float(i * 10)
    })

# Create prediction request
prediction_request = {
    "device_id": "test_device_001",
    "session_id": "test_session_001",
    "recent_telemetry": telemetry_points
}

print("=" * 60)
print("Testing LSTM Prediction API")
print("=" * 60)

# Test health endpoint
print("\n1. Testing health endpoint...")
try:
    response = requests.get("http://localhost:8000/api/v1/health")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
except Exception as e:
    print(f"   Error: {e}")

# Test prediction endpoint
print("\n2. Testing prediction endpoint with 10 telemetry points...")
print(f"   Signal strength trend: {telemetry_points[0]['signal_strength']:.2f} -> {telemetry_points[-1]['signal_strength']:.2f}")
print(f"   Latency trend: {telemetry_points[0]['latency_ms']}ms -> {telemetry_points[-1]['latency_ms']}ms")

try:
    response = requests.post(
        "http://localhost:8000/api/v1/telemetry/predict",
        json=prediction_request,
        timeout=10
    )
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n   ✓ Prediction successful!")
        print(f"   Full response: {json.dumps(result, indent=2)}")
        
        if result.get('prediction'):
            predictor_type = result['prediction'].get('predictor_type', result['prediction'].get('model_used', 'unknown'))
            print(f"\n   Predictor type: {predictor_type}")
            print(f"   Model version: {result['prediction']['model_version']}")
            print(f"   Confidence: {result['prediction']['confidence']:.4f}")
            print(f"   Time to drop: {result['prediction']['predicted_time_seconds']:.1f}s")
            print(f"   Recommended action: {result['recommended_action']}")
            print(f"   Should prepare transition: {result['should_prepare_transition']}")
            
            if predictor_type == 'lstm':
                print("\n   ✓✓✓ LSTM MODEL IS LOADED AND WORKING! ✓✓✓")
            else:
                print(f"\n   ⚠ Using fallback: {predictor_type}")
        else:
            print(f"\n   ⚠ Warning: prediction field is None")
    else:
        print(f"   Error: {response.text}")
        
except Exception as e:
    print(f"   Error: {e}")

print("\n" + "=" * 60)
print("Test complete")
print("=" * 60)

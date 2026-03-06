/* Extension Reload Test - Run in extension console */

// Test 1: Check if BackendAPI is imported
console.log('🧪 Test 1: BackendAPI import');
console.log('   BackendAPI available:', typeof BackendAPI !== 'undefined');
console.log('   backendAPI instance:', typeof backendAPI !== 'undefined');

// Test 2: Check API_CONFIG
console.log('\n🧪 Test 2: API Configuration');
console.log('   BASE_URL:', API_CONFIG?.BASE_URL);
console.log('   Endpoints count:', Object.keys(API_CONFIG?.ENDPOINTS || {}).length);

// Test 3: Test health check
console.log('\n🧪 Test 3: Backend Health Check');
backendAPI.checkHealth()
  .then(isHealthy => {
    console.log('   Backend status:', isHealthy ? '✅ HEALTHY' : '❌ UNAVAILABLE');
  })
  .catch(err => {
    console.log('   Backend error:', err.message);
  });

// Test 4: System state
console.log('\n🧪 Test 4: System State');
console.log('   Current state:', currentState);
console.log('   Backend available:', isBackendAvailable);
console.log('   Monitoring active:', monitoringInterval !== null);

console.log('\n✅ Extension tests complete! Check results above.');

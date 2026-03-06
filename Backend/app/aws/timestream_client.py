"""
Time-Series Telemetry Client (DynamoDB Implementation)
Handles storage and retrieval of historical network telemetry data

This replaces Amazon Timestream with DynamoDB for time-series data storage.
Design:
- Partition Key: location_hour (e.g., "28.6_77.2_2026-03-02-14")
- Sort Key: timestamp (ISO format)
- TTL: 30 days automatic deletion
- GSI: user_id-timestamp-index for user history queries
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import boto3
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


class TimestreamClient:
    """Client for time-series telemetry operations using DynamoDB"""
    
    def __init__(self):
        """Initialize DynamoDB client for telemetry storage"""
        self.dynamodb = None
        self.table_name = f"{settings.DYNAMODB_TABLE_PREFIX}_telemetry"
        self.available = False
        
        try:
            # Initialize DynamoDB client
            # In Lambda, use IAM role credentials automatically
            import os
            is_lambda = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None
            
            client_kwargs = {'region_name': settings.AWS_REGION}
            
            # Only use explicit credentials if not in Lambda and they are set
            if not is_lambda and settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
                client_kwargs['aws_access_key_id'] = settings.AWS_ACCESS_KEY_ID
                client_kwargs['aws_secret_access_key'] = settings.AWS_SECRET_ACCESS_KEY
            
            self.dynamodb = boto3.resource('dynamodb', **client_kwargs)
            
            # Test connection
            self.table = self.dynamodb.Table(self.table_name)
            self.table.load()
            
            self.available = True
            logger.info(f"Telemetry DynamoDB client initialized: {self.table_name}")
        except ClientError as e:
            if e.response['Error']['Code'] in ['ResourceNotFoundException', 'AccessDeniedException']:
                logger.debug(f"Telemetry table not available: {self.table_name}. Telemetry features disabled.")
            else:
                logger.warning(f"Could not initialize telemetry client: {e}")
            self.available = False
        except Exception as e:
            logger.debug(f"Telemetry client not available: {e}")
            self.available = False
    
    def _anonymize_location(self, latitude: float, longitude: float) -> tuple:
        """Anonymize GPS coordinates to 0.1 degree grid (~11km)"""
        return round(latitude, 1), round(longitude, 1)
    
    def _get_location_hour_key(self, latitude: float, longitude: float, timestamp: datetime) -> str:
        """Generate partition key: location_hour"""
        anon_lat, anon_lon = self._anonymize_location(latitude, longitude)
        hour_str = timestamp.strftime('%Y-%m-%d-%H')
        return f"{anon_lat}_{anon_lon}_{hour_str}"
    
    async def write_telemetry(
        self,
        session_id: str,
        signal_strength: float,
        latency: float,
        packet_loss: float,
        bandwidth_mbps: float,
        velocity_kmh: float,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        network_type: str = "4g"
    ) -> bool:
        """
        Write network telemetry data to DynamoDB
        
        Args:
            session_id: User session identifier
            signal_strength: Signal strength (0-100)
            latency: Network latency in milliseconds
            packet_loss: Packet loss percentage (0-100)
            bandwidth_mbps: Available bandwidth in Mbps
            velocity_kmh: GPS velocity in km/h
            latitude: GPS latitude (anonymized)
            longitude: GPS longitude (anonymized)
            network_type: Network type (2g, 3g, 4g, 5g)
            
        Returns:
            True if successful
        """
        if not self.available:
            logger.warning("Telemetry storage not available, skipping write")
            return False
        
        try:
            current_time = datetime.now()
            timestamp_iso = current_time.isoformat()
            
            # Calculate TTL (30 days from now)
            ttl = int((current_time + timedelta(days=30)).timestamp())
            
            # Prepare item
            item = {
                'timestamp': timestamp_iso,
                'session_id': session_id,
                'signal_strength': Decimal(str(signal_strength)),
                'latency': Decimal(str(latency)),
                'packet_loss': Decimal(str(packet_loss)),
                'bandwidth_mbps': Decimal(str(bandwidth_mbps)),
                'velocity_kmh': Decimal(str(velocity_kmh)),
                'network_type': network_type,
                'ttl': ttl
            }
            
            # Add location-based partition key if coordinates provided
            if latitude is not None and longitude is not None:
                location_hour = self._get_location_hour_key(latitude, longitude, current_time)
                anon_lat, anon_lon = self._anonymize_location(latitude, longitude)
                
                item['location_hour'] = location_hour
                item['latitude'] = Decimal(str(anon_lat))
                item['longitude'] = Decimal(str(anon_lon))
            else:
                # Use session-based partition key if no location
                location_hour = f"session_{session_id}_{current_time.strftime('%Y-%m-%d-%H')}"
                item['location_hour'] = location_hour
            
            # Write to DynamoDB
            self.table.put_item(Item=item)
            
            logger.debug(f"Wrote telemetry record to DynamoDB: {location_hour}")
            return True
            
        except ClientError as e:
            logger.error(f"DynamoDB write error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error writing telemetry: {e}")
            return False
    
    async def query_historical_patterns(
        self,
        latitude: float,
        longitude: float,
        time_range_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Query historical network patterns for a geographic location
        
        Args:
            latitude: GPS latitude
            longitude: GPS longitude
            time_range_hours: Time range to query (default 24 hours)
            
        Returns:
            List of historical telemetry records
        """
        if not self.available:
            logger.warning("Telemetry storage not available, returning empty results")
            return []
        
        try:
            anon_lat, anon_lon = self._anonymize_location(latitude, longitude)
            
            # Calculate time range
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=time_range_hours)
            
            # Query each hour partition in range
            results = []
            current_hour = start_time
            
            while current_hour <= end_time:
                location_hour = self._get_location_hour_key(anon_lat, anon_lon, current_hour)
                
                try:
                    response = self.table.query(
                        KeyConditionExpression='location_hour = :loc_hour AND #ts >= :start_ts',
                        ExpressionAttributeNames={'#ts': 'timestamp'},
                        ExpressionAttributeValues={
                            ':loc_hour': location_hour,
                            ':start_ts': start_time.isoformat()
                        },
                        Limit=100  # Limit per hour to avoid excessive reads
                    )
                    
                    for item in response.get('Items', []):
                        # Convert Decimal to float for JSON serialization
                        record = {
                            'time': item['timestamp'],
                            'signal_strength': float(item.get('signal_strength', 0)),
                            'latency': float(item.get('latency', 0)),
                            'packet_loss': float(item.get('packet_loss', 0)),
                            'bandwidth_mbps': float(item.get('bandwidth_mbps', 0)),
                            'velocity_kmh': float(item.get('velocity_kmh', 0)),
                            'network_type': item.get('network_type', 'unknown')
                        }
                        results.append(record)
                        
                except ClientError as e:
                    if e.response['Error']['Code'] != 'ResourceNotFoundException':
                        logger.warning(f"Error querying partition {location_hour}: {e}")
                
                # Move to next hour
                current_hour += timedelta(hours=1)
            
            # Sort by time descending
            results.sort(key=lambda x: x['time'], reverse=True)
            
            # Limit total results
            results = results[:1000]
            
            logger.info(f"Retrieved {len(results)} historical records for location ({anon_lat}, {anon_lon})")
            return results
            
        except Exception as e:
            logger.error(f"Error querying historical patterns: {e}")
            return []
    
    async def get_location_statistics(
        self,
        latitude: float,
        longitude: float,
        time_range_hours: int = 168  # 7 days
    ) -> Dict[str, Any]:
        """
        Get statistical summary of network conditions for a location
        
        Args:
            latitude: GPS latitude
            longitude: GPS longitude
            time_range_hours: Time range to analyze (default 7 days)
            
        Returns:
            Dictionary with statistical metrics
        """
        if not self.available:
            return {}
        
        try:
            # Get historical data
            records = await self.query_historical_patterns(latitude, longitude, time_range_hours)
            
            if not records:
                return {}
            
            # Calculate statistics
            metrics = ['signal_strength', 'latency', 'packet_loss', 'bandwidth_mbps', 'velocity_kmh']
            statistics = {}
            
            for metric in metrics:
                values = [r[metric] for r in records if metric in r and r[metric] is not None]
                
                if values:
                    statistics[metric] = {
                        'avg': sum(values) / len(values),
                        'min': min(values),
                        'max': max(values),
                        'count': len(values)
                    }
                    
                    # Calculate standard deviation
                    if len(values) > 1:
                        mean = statistics[metric]['avg']
                        variance = sum((x - mean) ** 2 for x in values) / len(values)
                        statistics[metric]['stddev'] = variance ** 0.5
                    else:
                        statistics[metric]['stddev'] = 0.0
            
            anon_lat, anon_lon = self._anonymize_location(latitude, longitude)
            logger.info(f"Calculated statistics for location ({anon_lat}, {anon_lon}): {len(records)} samples")
            return statistics
            
        except Exception as e:
            logger.error(f"Error calculating location statistics: {e}")
            return {}
    
    async def identify_shadow_zones(
        self,
        min_samples: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Identify geographic "shadow zones" with consistently poor network
        
        Args:
            min_samples: Minimum number of samples required for a zone
            
        Returns:
            List of shadow zones with their characteristics
        """
        if not self.available:
            return []
        
        try:
            # Scan approach: This is expensive for large datasets
            # In production, consider using DynamoDB Streams + Lambda for aggregation
            # or pre-computing summaries periodically
            
            # For now, we'll use a simplified approach with a scan
            # Limited to recent data (last 7 days worth of partitions)
            logger.warning("Shadow zone identification uses table scan - expensive operation")
            
            end_time = datetime.now()
            start_time = end_time - timedelta(days=7)
            
            # Aggregate by location grid
            location_aggregates = {}
            
            # Scan with filter (limit to avoid excessive reads)
            response = self.table.scan(
                FilterExpression='#ts > :start_time',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={':start_time': start_time.isoformat()},
                Limit=10000  # Limit scan to control costs
            )
            
            for item in response.get('Items', []):
                if 'latitude' not in item or 'longitude' not in item:
                    continue
                
                lat = float(item['latitude'])
                lon = float(item['longitude'])
                location_key = f"{lat},{lon}"
                
                if location_key not in location_aggregates:
                    location_aggregates[location_key] = {
                        'signal_strengths': [],
                        'count': 0
                    }
                
                signal_strength = float(item.get('signal_strength', 0))
                location_aggregates[location_key]['signal_strengths'].append(signal_strength)
                location_aggregates[location_key]['count'] += 1
            
            # Identify shadow zones (low avg signal, enough samples)
            shadow_zones = []
            for location_key, data in location_aggregates.items():
                if data['count'] >= min_samples:
                    avg_signal = sum(data['signal_strengths']) / len(data['signal_strengths'])
                    if avg_signal < 50:  # Poor signal threshold
                        shadow_zones.append({
                            'location_grid': location_key,
                            'avg_signal_strength': avg_signal,
                            'sample_count': data['count']
                        })
            
            # Sort by worst signal first
            shadow_zones.sort(key=lambda x: x['avg_signal_strength'])
            shadow_zones = shadow_zones[:100]  # Top 100 worst zones
            
            logger.info(f"Identified {len(shadow_zones)} shadow zones from {len(location_aggregates)} locations")
            return shadow_zones
            
        except Exception as e:
            logger.error(f"Error identifying shadow zones: {e}")
            return []


# Global instance
timestream_client = TimestreamClient()

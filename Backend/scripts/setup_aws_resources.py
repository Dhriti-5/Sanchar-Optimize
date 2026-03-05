"""
AWS Resource Setup Script
Creates Timestream database/table and DynamoDB tables for Phase 3
"""

import boto3
from botocore.exceptions import ClientError
import sys

from app.core.config import settings


def setup_timestream():
    """Create Timestream database and table"""
    print("\n🕐 Setting up Amazon Timestream...")
    
    try:
        write_client = boto3.client(
            'timestream-write',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID if settings.AWS_ACCESS_KEY_ID else None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY if settings.AWS_SECRET_ACCESS_KEY else None
        )
        
        # Create database
        try:
            write_client.create_database(
                DatabaseName=settings.TIMESTREAM_DATABASE
            )
            print(f"✅ Created Timestream database: {settings.TIMESTREAM_DATABASE}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConflictException':
                print(f"ℹ️  Timestream database already exists: {settings.TIMESTREAM_DATABASE}")
            else:
                raise
        
        # Create table with retention policies
        try:
            write_client.create_table(
                DatabaseName=settings.TIMESTREAM_DATABASE,
                TableName=settings.TIMESTREAM_TABLE,
                RetentionProperties={
                    'MemoryStoreRetentionPeriodInHours': 24,  # 1 day in memory
                    'MagneticStoreRetentionPeriodInDays': 30  # 30 days in magnetic store
                }
            )
            print(f"✅ Created Timestream table: {settings.TIMESTREAM_TABLE}")
            print("   - Memory retention: 24 hours")
            print("   - Magnetic retention: 30 days")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConflictException':
                print(f"ℹ️  Timestream table already exists: {settings.TIMESTREAM_TABLE}")
            else:
                raise
        
        return True
        
    except ClientError as e:
        if 'AccessDeniedException' in str(e) and 'LiveAnalytics' in str(e):
            print(f"⚠️  Timestream not enabled for this account")
            print("\n   📋 To enable Timestream:")
            print("   1. Go to AWS Console: https://console.aws.amazon.com/timestream")
            print("   2. Click 'Get started' or 'Enable Timestream'")
            print("   3. Or contact AWS Support to enable Timestream for LiveAnalytics")
            print("\n   ℹ️  System will work without Timestream (graceful degradation)")
            return False
        else:
            print(f"❌ Timestream setup failed: {e}")
            return False
    except Exception as e:
        print(f"❌ Timestream setup failed: {e}")
        return False


def setup_dynamodb():
    """Create DynamoDB tables"""
    print("\n📊 Setting up Amazon DynamoDB...")
    
    try:
        dynamodb = boto3.client(
            'dynamodb',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID if settings.AWS_ACCESS_KEY_ID else None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY if settings.AWS_SECRET_ACCESS_KEY else None
        )
        
        # Create sessions table
        sessions_table = f"{settings.DYNAMODB_TABLE_PREFIX}_sessions"
        try:
            dynamodb.create_table(
                TableName=sessions_table,
                KeySchema=[
                    {'AttributeName': 'session_id', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'session_id', 'AttributeType': 'S'}
                ],
                BillingMode='PAY_PER_REQUEST'  # On-demand pricing for scalability
            )
            print(f"✅ Created DynamoDB table: {sessions_table}")
            print("   - Billing: PAY_PER_REQUEST (auto-scaling)")
            
            # Wait for table to be active
            waiter = dynamodb.get_waiter('table_exists')
            waiter.wait(TableName=sessions_table)
            
            # Enable TTL (must be done after table creation)
            try:
                dynamodb.update_time_to_live(
                    TableName=sessions_table,
                    TimeToLiveSpecification={
                        'Enabled': True,
                        'AttributeName': 'ttl'
                    }
                )
                print("   - TTL: Enabled (7-day retention)")
            except Exception as ttl_error:
                print(f"   ⚠️  TTL configuration warning: {ttl_error}")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceInUseException':
                print(f"ℹ️  DynamoDB table already exists: {sessions_table}")
            else:
                raise
        
        # Create transitions table
        transitions_table = f"{settings.DYNAMODB_TABLE_PREFIX}_transitions"
        try:
            dynamodb.create_table(
                TableName=transitions_table,
                KeySchema=[
                    {'AttributeName': 'transition_id', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'transition_id', 'AttributeType': 'S'},
                    {'AttributeName': 'session_id', 'AttributeType': 'S'},
                    {'AttributeName': 'transition_time', 'AttributeType': 'S'}
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'session_id-transition_time-index',
                        'KeySchema': [
                            {'AttributeName': 'session_id', 'KeyType': 'HASH'},
                            {'AttributeName': 'transition_time', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'}
                    }
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            print(f"✅ Created DynamoDB table: {transitions_table}")
            print("   - Billing: PAY_PER_REQUEST (auto-scaling)")
            print("   - GSI: session_id-transition_time-index")
            
            # Wait for table to be active
            waiter = dynamodb.get_waiter('table_exists')
            waiter.wait(TableName=transitions_table)
            
            # Enable TTL (must be done after table creation)
            try:
                dynamodb.update_time_to_live(
                    TableName=transitions_table,
                    TimeToLiveSpecification={
                        'Enabled': True,
                        'AttributeName': 'ttl'
                    }
                )
                print("   - TTL: Enabled (30-day retention)")
            except Exception as ttl_error:
                print(f"   ⚠️  TTL configuration warning: {ttl_error}")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceInUseException':
                print(f"ℹ️  DynamoDB table already exists: {transitions_table}")
            else:
                raise
        
        # Create telemetry table (replaces Timestream)
        telemetry_table = f"{settings.DYNAMODB_TABLE_PREFIX}_telemetry"
        try:
            dynamodb.create_table(
                TableName=telemetry_table,
                KeySchema=[
                    {'AttributeName': 'location_hour', 'KeyType': 'HASH'},
                    {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'location_hour', 'AttributeType': 'S'},
                    {'AttributeName': 'timestamp', 'AttributeType': 'S'},
                    {'AttributeName': 'session_id', 'AttributeType': 'S'}
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'session_id-timestamp-index',
                        'KeySchema': [
                            {'AttributeName': 'session_id', 'KeyType': 'HASH'},
                            {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'}
                    }
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            print(f"✅ Created DynamoDB table: {telemetry_table}")
            print("   - Billing: PAY_PER_REQUEST (auto-scaling)")
            print("   - Purpose: Time-series telemetry storage (replaces Timestream)")
            print("   - GSI: session_id-timestamp-index")
            
            # Wait for table to be active
            waiter = dynamodb.get_waiter('table_exists')
            waiter.wait(TableName=telemetry_table)
            
            # Enable TTL (must be done after table creation)
            try:
                dynamodb.update_time_to_live(
                    TableName=telemetry_table,
                    TimeToLiveSpecification={
                        'Enabled': True,
                        'AttributeName': 'ttl'
                    }
                )
                print("   - TTL: Enabled (30-day retention)")
            except Exception as ttl_error:
                print(f"   ⚠️  TTL configuration warning: {ttl_error}")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceInUseException':
                print(f"ℹ️  DynamoDB table already exists: {telemetry_table}")
            else:
                raise
        
        return True
        
    except Exception as e:
        print(f"❌ DynamoDB setup failed: {e}")
        return False


def verify_setup():
    """Verify that all resources are accessible"""
    print("\n🔍 Verifying setup...")
    
    try:
        # Check Timestream
        write_client = boto3.client(
            'timestream-write',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID if settings.AWS_ACCESS_KEY_ID else None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY if settings.AWS_SECRET_ACCESS_KEY else None
        )
        
        response = write_client.describe_table(
            DatabaseName=settings.TIMESTREAM_DATABASE,
            TableName=settings.TIMESTREAM_TABLE
        )
        print(f"✅ Timestream table verified: {response['Table']['TableStatus']}")
        
        # Check DynamoDB
        dynamodb = boto3.client(
            'dynamodb',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID if settings.AWS_ACCESS_KEY_ID else None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY if settings.AWS_SECRET_ACCESS_KEY else None
        )
        
        sessions_table = f"{settings.DYNAMODB_TABLE_PREFIX}_sessions"
        response = dynamodb.describe_table(TableName=sessions_table)
        print(f"✅ DynamoDB sessions table verified: {response['Table']['TableStatus']}")
        
        transitions_table = f"{settings.DYNAMODB_TABLE_PREFIX}_transitions"
        response = dynamodb.describe_table(TableName=transitions_table)
        print(f"✅ DynamoDB transitions table verified: {response['Table']['TableStatus']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False


def main():
    """Main setup function"""
    print("=" * 60)
    print("SANCHAR-OPTIMIZE PHASE 3 AWS SETUP")
    print("=" * 60)
    
    print(f"\nRegion: {settings.AWS_REGION}")
    print(f"DynamoDB Table Prefix: {settings.DYNAMODB_TABLE_PREFIX}")
    print(f"\nℹ️  Using DynamoDB for time-series telemetry storage")
    print("   (Timestream not available for new accounts since June 2025)")
    
    # Check credentials
    if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
        print("\n⚠️  Warning: AWS credentials not found in environment")
        print("Using default credential chain (IAM role, profile, etc.)")
    
    # Run setup - Skip Timestream, use DynamoDB only
    timestream_ok = False  # Timestream disabled
    dynamodb_ok = setup_dynamodb()
    
    if dynamodb_ok:
        print("\n" + "=" * 60)
        print("✅ SETUP COMPLETE - DynamoDB (All Features)")
        print("=" * 60)
        print("\nYour Sanchar-Optimize Phase 3 infrastructure is ready!")
        print("\n📊 Created Tables:")
        print(f"   • {settings.DYNAMODB_TABLE_PREFIX}_sessions (Session management)")
        print(f"   • {settings.DYNAMODB_TABLE_PREFIX}_transitions (Modality transitions)")
        print(f"   • {settings.DYNAMODB_TABLE_PREFIX}_telemetry (Time-series data)")
        print("\nNext steps:")
        print("1. Start the backend: cd Backend && python main.py")
        print("2. Load the extension in Chrome")
        print("3. Test with: python Backend/test_phase3_integration.py")
        print("\n✨ All Phase 3 features are fully functional with DynamoDB!")
        
        return 0
    else:
        print("\n❌ Setup failed")
        print("\nTroubleshooting:")
        print("- Check AWS credentials are configured")
        print("- Verify IAM permissions for DynamoDB")
        print("- Check AWS region is correct")
        return 1


if __name__ == "__main__":
    sys.exit(main())

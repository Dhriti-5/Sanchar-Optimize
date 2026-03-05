"""Check DynamoDB tables and connectivity"""
import os

import boto3
from botocore.exceptions import ClientError

print("=" * 60)
print("DYNAMODB TABLES CHECK")
print("=" * 60)

try:
    dynamodb = boto3.client('dynamodb', region_name='ap-south-1')
    response = dynamodb.list_tables()
    
    print("\nExisting DynamoDB Tables:")
    if response['TableNames']:
        for table in response['TableNames']:
            print(f"  ✓ {table}")
    else:
        print("  ❌ No tables found!")
    
    print("\n\nExpected Tables:")
    expected = [
        'sanchar_optimize_sessions',
        'sanchar_optimize_transitions',
        'sanchar_optimize_telemetry'
    ]
    
    existing_tables = set(response['TableNames'])
    for table in expected:
        status = "✓" if table in existing_tables else "✗"
        print(f"  {status} {table}")
    
except ClientError as e:
    error_code = e.response['Error']['Code']
    error_message = e.response['Error']['Message']
    print(f"\n❌ AWS Error: {error_code}")
    print(f"   Message: {error_message}")
    
    if error_code == 'UnrecognizedClientException':
        print("\n   → AWS credentials are invalid or incorrect")
    elif error_code == 'AccessDeniedException':
        print("\n   → AWS credentials don't have DynamoDB permissions")
    elif error_code == 'InvalidSignatureException':
        print("\n   → AWS signature is invalid (check credentials)")
        
except Exception as e:
    print(f"\n❌ Error: {e}")

print("\n" + "=" * 60)

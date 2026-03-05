"""Check session data in DynamoDB"""
import os

import boto3
from botocore.exceptions import ClientError

# The session ID from your error message
session_id = 'session_1772505099350_v8zingfgg'

print("=" * 60)
print(f"CHECKING SESSION IN DYNAMODB")
print("=" * 60)
print(f"\nLooking for session: {session_id}\n")

try:
    dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
    table = dynamodb.Table('sanchar_optimize_sessions')
    
    response = table.get_item(Key={'session_id': session_id})
    
    if 'Item' in response:
        print("✓ Session FOUND in DynamoDB!")
        print("\nSession Data:")
        for key, value in response['Item'].items():
            print(f"  {key}: {value}")
    else:
        print("✗ Session NOT found in DynamoDB")
        
        # Try to list all sessions
        print("\n\nAll sessions in table:")
        scan_response = table.scan()
        if scan_response['Items']:
            for item in scan_response['Items']:
                print(f"  - {item['session_id']}")
        else:
            print("  (Table is empty)")
            
except ClientError as e:
    print(f"❌ Error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 60)

#!/usr/bin/env python3
"""
Test each job API individually to see which ones work
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from app.services.integrations.remoteok import RemoteOKIntegration
from app.services.integrations.remotive import RemotiveIntegration
from app.services.integrations.arbeitnow import ArbeitnowIntegration
from app.services.integrations.aiesec import AIESECIntegration
from app.services.integrations.base import SearchParams

async def test_api(api_class):
    print(f"\n{'='*60}")
    print(f"Testing {api_class.__name__}")
    print(f"{'='*60}")
    
    try:
        api = api_class()
        params = SearchParams(query="developer", max_results=10)
        result = await api.search(params)
        
        print(f"✓ Success! Found {len(result.jobs)} jobs")
        if result.jobs:
            print(f"\nSample jobs:")
            for i, job in enumerate(result.jobs[:3]):
                print(f"  {i+1}. {job.get('title')} at {job.get('company')}")
        return True
    except Exception as e:
        print(f"✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    print("Testing job APIs...")
    
    apis = [
        RemoteOKIntegration,
        RemotiveIntegration,
        ArbeitnowIntegration,
        AIESECIntegration,
    ]
    
    results = {}
    for api_cls in apis:
        results[api_cls.__name__] = await test_api(api_cls)
    
    print(f"\n{'='*60}")
    print("Summary:")
    for name, success in results.items():
        status = "✓ WORKING" if success else "✗ FAILED"
        print(f"  {name}: {status}")
    print(f"{'='*60}")

if __name__ == "__main__":
    asyncio.run(main())

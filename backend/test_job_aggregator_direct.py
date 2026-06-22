#!/usr/bin/env python3
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from app.services.job_aggregator import JobSearchAgent
from app.schemas.job import SearchFilters


async def main():
    print("=== Testing Job Search Agent Directly ===")
    agent = JobSearchAgent()
    filters = SearchFilters(
        location="",
        contract_type="",
        max_results=10
    )
    
    # Test searching for "software developer"
    print("\n--- Searching for 'software developer' ---")
    try:
        jobs = await agent.run("software developer", {}, filters)
        print(f"SUCCESS: Found {len(jobs)} jobs!")
        for j in jobs[:3]:
            print(f"  - {j.title} @ {j.company} ({j.location})")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

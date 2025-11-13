"""Integration test for cloud-agent API and task execution."""

import os
import time

import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
TIMEOUT = 300  # 5 minutes max wait for task completion


def main():
    """Run integration test."""
    print("=== Cloud Agent Integration Test ===\n")

    # Check if API is running
    print(f"1. Checking API health at {API_BASE_URL}...")
    try:
        response = httpx.get(f"{API_BASE_URL}/health")
        response.raise_for_status()
        print(f"   ✓ API is healthy: {response.json()}\n")
    except Exception as e:
        print(f"   ✗ API health check failed: {e}")
        print("   Make sure the API is running: uv run uvicorn app.main:app --reload")
        return 1

    # Create a test task
    print("2. Creating a test task...")
    task_data = {
        "prompt": "Create a file called hello.txt with the content 'Hello from Cloud Agent!'",
        "repository_url": "https://github.com/anthropics/anthropic-sdk-python.git",
    }

    try:
        response = httpx.post(f"{API_BASE_URL}/v1/tasks", json=task_data, timeout=30.0)
        response.raise_for_status()
        task = response.json()
        task_id = task["id"]
        print(f"   ✓ Task created with ID: {task_id}")
        print(f"   Status: {task['status']}\n")
    except Exception as e:
        print(f"   ✗ Task creation failed: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"   Response: {e.response.text}")
        return 1

    # Poll task status
    print("3. Waiting for task to complete...")
    start_time = time.time()
    last_status = None

    while time.time() - start_time < TIMEOUT:
        try:
            response = httpx.get(f"{API_BASE_URL}/v1/tasks/{task_id}", timeout=10.0)
            response.raise_for_status()
            task = response.json()
            status = task["status"]

            if status != last_status:
                elapsed = int(time.time() - start_time)
                print(f"   [{elapsed}s] Status: {status}")
                if task.get("sandbox_id"):
                    print(f"   Sandbox ID: {task['sandbox_id']}")
                last_status = status

            if status in ["completed", "failed"]:
                break

            time.sleep(5)  # Poll every 5 seconds

        except Exception as e:
            print(f"   ✗ Error polling task: {e}")
            return 1

    # Check final result
    print("\n4. Final result:")
    print(f"   Status: {task['status']}")

    if task.get("result"):
        print("   Result preview (first 500 chars):")
        print(f"   {task['result'][:500]}")

    if task["status"] == "completed":
        print("\n✓ Integration test PASSED!")
        return 0
    else:
        print(f"\n✗ Integration test FAILED - task status: {task['status']}")
        if task.get("result"):
            print(f"\nFull result:\n{task['result']}")
        return 1


if __name__ == "__main__":
    exit(main())

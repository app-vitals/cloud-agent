"""API client service for interacting with Cloud Agent API."""

import os
import time
from typing import Any

import httpx


class ApiClientService:
    """Service for Cloud Agent API client operations."""

    @staticmethod
    def get_client(
        base_url: str | None = None, api_key: str | None = None
    ) -> httpx.Client:
        """Get configured HTTP client.

        Args:
            base_url: API base URL (defaults to CLOUD_AGENT_URL env var or http://localhost:8000)
            api_key: API key for authentication (defaults to API_SECRET_KEY env var)

        Returns:
            Configured httpx.Client with base_url, headers, and timeout
        """
        if base_url is None:
            base_url = os.getenv("CLOUD_AGENT_URL", "http://localhost:8000")
        if api_key is None:
            api_key = os.getenv("API_SECRET_KEY", "")

        return httpx.Client(
            base_url=base_url,
            headers={"X-API-Key": api_key},
            timeout=30.0,
        )

    @staticmethod
    def create_task(
        prompt: str,
        repository_url: str,
        parent_task_id: str | None = None,
        client: httpx.Client | None = None,
    ) -> dict[str, Any]:
        """Create a new task.

        Args:
            prompt: Natural language prompt for the task
            repository_url: Repository URL to clone
            parent_task_id: Optional parent task ID to resume from
            client: Optional httpx.Client to use (if None, creates new client)

        Returns:
            Task data as dict with id, status, prompt, repository_url, etc.

        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        should_close = client is None
        if client is None:
            client = ApiClientService.get_client()

        try:
            payload: dict[str, Any] = {
                "prompt": prompt,
                "repository_url": repository_url,
            }
            if parent_task_id is not None:
                payload["parent_task_id"] = parent_task_id

            response = client.post("/v1/tasks", json=payload)
            response.raise_for_status()
            return response.json()
        finally:
            if should_close:
                client.close()

    @staticmethod
    def get_task(task_id: str, client: httpx.Client | None = None) -> dict[str, Any]:
        """Get task by ID.

        Args:
            task_id: Task ID to retrieve
            client: Optional httpx.Client to use (if None, creates new client)

        Returns:
            Task data as dict with id, status, prompt, repository_url, etc.

        Raises:
            httpx.HTTPStatusError: If API request fails (e.g., 404 for not found)
        """
        should_close = client is None
        if client is None:
            client = ApiClientService.get_client()

        try:
            response = client.get(f"/v1/tasks/{task_id}")
            response.raise_for_status()
            return response.json()
        finally:
            if should_close:
                client.close()

    @staticmethod
    def wait_for_task(
        task_id: str,
        timeout: int = 600,
        poll_interval: int = 5,
    ) -> dict[str, Any]:
        """Wait for task to complete with polling.

        Args:
            task_id: Task ID to wait for
            timeout: Maximum time to wait in seconds (default: 600)
            poll_interval: Time between status checks in seconds (default: 5)

        Returns:
            Final task data when completed or failed

        Raises:
            TimeoutError: If task doesn't complete within timeout period
            httpx.HTTPStatusError: If the API returns an error
        """
        start_time = time.time()

        while True:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Task {task_id} did not complete within {timeout}s")

            task = ApiClientService.get_task(task_id)
            status = task["status"]

            if status in ["completed", "failed", "cancelled"]:
                return task

            time.sleep(poll_interval)

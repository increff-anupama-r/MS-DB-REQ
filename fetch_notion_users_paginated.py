#!/usr/bin/env python3
"""
Notion Users Extraction with Pagination Support

This module provides functions to extract users from Notion workspace
with proper pagination handling and data validation.
"""

import os
import json
import requests
import logging
from typing import List, Dict, Optional
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def fetch_users_in_batches() -> List[Dict]:
    """
    Fetch all users from Notion workspace using pagination.

    Returns:
        List of user dictionaries
    """
    notion_token = os.environ.get("NOTION_INTEGRATION_TOKEN2")
    if not notion_token:
        raise ValueError("NOTION_INTEGRATION_TOKEN2 environment variable is required")

    headers = {
        "Authorization": f"Bearer {notion_token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    all_users = []
    has_more = True
    next_cursor = None

    logger.info("Starting user extraction from Notion workspace...")

    while has_more:
        try:
            params = {"page_size": 100}
            if next_cursor:
                params["start_cursor"] = next_cursor

            response = requests.get(
                "https://api.notion.com/v1/users", headers=headers, params=params
            )

            if response.status_code != 200:
                logger.error(
                    f"Failed to fetch users: {response.status_code} - {response.text}"
                )
                raise Exception(f"API request failed: {response.text}")

            data = response.json()
            users = data.get("results", [])

            # Filter for person users only
            person_users = []
            for user in users:
                if user.get("object") == "user" and user.get("type") == "person":
                    person_users.append(
                        {
                            "id": user["id"],
                            "name": user.get("name", ""),
                            "email": user.get("person", {}).get("email", ""),
                            "type": user.get("type"),
                            "avatar_url": user.get("avatar_url"),
                        }
                    )

            all_users.extend(person_users)
            logger.info(
                f"Fetched batch of {len(person_users)} users (total: {len(all_users)})"
            )

            has_more = data.get("has_more", False)
            next_cursor = data.get("next_cursor")

        except Exception as e:
            logger.error(f"Error during batch fetch: {e}")
            raise

    logger.info(f"Successfully extracted {len(all_users)} users from Notion workspace")
    return all_users


def save_users_to_json(users: List[Dict], filename: str = "notion_users.json") -> str:
    """
    Save users to JSON file.

    Args:
        users: List of user dictionaries
        filename: Output filename

    Returns:
        Path to saved file
    """
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2, ensure_ascii=False)

        logger.info(f"Users saved to {filename}")
        return filename
    except Exception as e:
        logger.error(f"Error saving users to file: {e}")
        raise


def verify_extraction(users: List[Dict]) -> bool:
    """
    Verify the extracted user data.

    Args:
        users: List of user dictionaries

    Returns:
        True if verification passes
    """
    if not users:
        logger.warning("No users found in extraction")
        return False

    # Check for required fields
    required_fields = ["id", "name", "type"]
    for i, user in enumerate(users):
        for field in required_fields:
            if field not in user:
                logger.error(f"User {i} missing required field: {field}")
                return False

    # Check for duplicate IDs
    user_ids = [user["id"] for user in users]
    if len(user_ids) != len(set(user_ids)):
        logger.error("Duplicate user IDs found")
        return False

    logger.info("User data verification passed")
    return True


def show_sample_users(users: List[Dict], count: int = 5) -> None:
    """
    Display sample users for verification.

    Args:
        users: List of user dictionaries
        count: Number of sample users to show
    """
    if not users:
        print("No users to display")
        return

    print(f"\nSample Users (showing {min(count, len(users))} of {len(users)}):")
    print("=" * 60)

    for i, user in enumerate(users[:count]):
        print(f"{i+1}. ID: {user['id']}")
        print(f"   Name: {user['name']}")
        print(f"   Email: {user.get('email', 'N/A')}")
        print(f"   Type: {user['type']}")
        print("-" * 40)

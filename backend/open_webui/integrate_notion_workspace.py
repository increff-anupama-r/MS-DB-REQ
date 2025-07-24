#!/usr/bin/env python3
"""
Integration Script for Notion Workspace Functionality

This script shows how to integrate the new Notion workspace functionality
into the existing Open WebUI FastAPI application without modifying existing code.

Usage:
    1. Set environment variables: NOTION_INTEGRATION_TOKEN2, NOTION_DB_ID2
    2. Import and include the router in your main FastAPI app
    3. The new endpoints will be available at /notion-workspace/*
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from notion_workspace_api import router as notion_workspace_router


def integrate_with_fastapi_app(app):
    """
    Integrate the Notion workspace functionality with an existing FastAPI app.

    Args:
        app: FastAPI application instance
    """
    # Include the router
    app.include_router(notion_workspace_router)


def check_environment():
    """Check if required environment variables are set."""
    required_vars = ["NOTION_INTEGRATION_TOKEN2", "NOTION_DB_ID2"]
    missing_vars = []

    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)

    if missing_vars:
        print("Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        return False
    return True


def example_integration():
    """
    Example of how to integrate with the existing Open WebUI FastAPI app.

    This function shows the pattern for integration without modifying existing code.
    """
    try:
        if not check_environment():
            return False

        """
        # Example integration code (add this to your main FastAPI app):
        
        from fastapi import FastAPI
        from integrate_notion_workspace import integrate_with_fastapi_app
        
        app = FastAPI()
        
        # Add your existing routes here...
        
        # Integrate the new Notion workspace functionality
        integrate_with_fastapi_app(app)
        
        # Continue with your existing app setup...
        """
        return True

    except Exception as e:
        print(f"Error during integration: {e}")
        return False


def test_functionality():
    """Test the Notion workspace functionality."""
    try:
        from notion_workspace_manager import NotionWorkspaceManager

        # Initialize manager
        manager = NotionWorkspaceManager()

        # Test getting users
        users = manager.get_workspace_users()
        print(f"Found {len(users)} users in workspace")

        # Test name matching
        if users:
            test_name = users[0]["name"].split()[0]  # Use first name of first user
            user = manager.find_user_by_name(test_name)
            if user:
                print(f"Name matching works: '{test_name}' -> '{user['name']}'")
            else:
                print(f"Name matching failed for '{test_name}'")

        # Test database schema
        schema = manager.get_database_schema()
        print(f"Database schema retrieved successfully")
        return True

    except Exception as e:
        print(f"Test failed: {e}")
        return False


def main():
    """Main function to run the integration setup."""
    print("=" * 50)

    # Check environment
    if not check_environment():
        return 1

    # Test functionality
    if not test_functionality():
        return 1

    # Show integration example
    if not example_integration():
        return 1

    return 0


if __name__ == "__main__":
    exit(main())

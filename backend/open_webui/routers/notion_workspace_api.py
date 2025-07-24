import os
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
from difflib import SequenceMatcher
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
import requests

from notion_workspace_manager import NotionWorkspaceManager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/notion-workspace", tags=["notion-workspace"])


class WorkspaceUserResponse(BaseModel):
    id: str
    name: str
    email: str
    avatar_url: Optional[str] = None
    type: str


class NameMatchRequest(BaseModel):
    name: str


class NameMatchResponse(BaseModel):
    found: bool
    user: Optional[WorkspaceUserResponse] = None
    confidence_score: Optional[float] = None
    original_search: str


class FormDataRequest(BaseModel):
    title: str
    type: str
    description: str
    module: str
    owner: str
    priority: str
    due_date: str
    client: str
    reference_link: Optional[str] = None
    attachments: Optional[List[Dict[str, str]]] = []


class DatabaseEntryResponse(BaseModel):
    success: bool
    page_id: Optional[str] = None
    error: Optional[str] = None


# Global workspace manager instance
workspace_manager = None


def get_workspace_manager() -> NotionWorkspaceManager:
    """Get or create the workspace manager instance."""
    global workspace_manager
    if workspace_manager is None:
        try:
            workspace_manager = NotionWorkspaceManager()
        except Exception as e:
            logger.error(f"Failed to initialize workspace manager: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize Notion workspace manager: {str(e)}",
            )
    return workspace_manager


@router.get("/users", response_model=List[WorkspaceUserResponse])
async def get_workspace_users():
    """
    Get all users from the Notion workspace.

    Returns:
        List of all users in the workspace
    """
    try:
        manager = get_workspace_manager()
        users = manager.get_workspace_users()

        return [
            WorkspaceUserResponse(
                id=user["id"],
                name=user["name"],
                email=user["email"],
                avatar_url=user.get("avatar_url"),
                type=user["type"],
            )
            for user in users
        ]
    except Exception as e:
        logger.error(f"Error getting workspace users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get workspace users: {str(e)}",
        )


@router.post("/match-name", response_model=NameMatchResponse)
async def match_user_name(request: NameMatchRequest):
    """
    Find a user by name with smart matching for mispronounced or partial names.

    Args:
        request: Contains the name to search for

    Returns:
        Match result with user information and confidence score
    """
    try:
        manager = get_workspace_manager()
        user = manager.find_user_by_name(request.name)

        if user:
            search_lower = request.name.lower()
            user_name_lower = user["name"].lower()
            confidence_score = SequenceMatcher(
                None, search_lower, user_name_lower
            ).ratio()

            return NameMatchResponse(
                found=True,
                user=WorkspaceUserResponse(
                    id=user["id"],
                    name=user["name"],
                    email=user["email"],
                    avatar_url=user.get("avatar_url"),
                    type=user["type"],
                ),
                confidence_score=confidence_score,
                original_search=request.name,
            )
        else:
            return NameMatchResponse(
                found=False,
                user=None,
                confidence_score=None,
                original_search=request.name,
            )
    except Exception as e:
        logger.error(f"Error matching user name: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to match user name: {str(e)}",
        )


@router.post("/create-entry", response_model=DatabaseEntryResponse)
async def create_database_entry(request: FormDataRequest):
    """
    Create a new entry in the Notion database with smart user matching.

    Args:
        request: Form data containing all the information

    Returns:
        Success status and page ID if created successfully
    """
    try:
        manager = get_workspace_manager()
        form_data = request.model_dump()
        result = manager.create_database_entry(form_data)

        return DatabaseEntryResponse(success=True, page_id=result.get("id"), error=None)
    except Exception as e:
        logger.error(f"Error creating database entry: {e}")
        return DatabaseEntryResponse(success=False, page_id=None, error=str(e))


@router.get("/database-schema")
async def get_database_schema():
    """
    Get the database schema to understand available properties and options.

    Returns:
        Database schema information
    """
    try:
        manager = get_workspace_manager()
        schema = manager.get_database_schema()
        return schema
    except Exception as e:
        logger.error(f"Error getting database schema: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get database schema: {str(e)}",
        )


# Test endpoint removed for production security


@router.get("/health")
async def health_check():
    """
    Health check endpoint to verify the workspace manager is working.

    Returns:
        Health status
    """
    try:
        manager = get_workspace_manager()

        # Test basic functionality
        users = manager.get_workspace_users()

        return {
            "status": "healthy",
            "workspace_users_count": len(users),
            "database_id": manager.database_id,
            "token_configured": bool(manager.notion_token),
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "workspace_users_count": 0,
            "database_id": None,
            "token_configured": False,
        }


# Example usage function
def example_usage():
    """Example of how to use the workspace manager programmatically."""
    try:
        manager = NotionWorkspaceManager()
        users = manager.get_workspace_users()
        print(f"Found {len(users)} users in workspace")
        test_name = "Dinesh"
        user = manager.find_user_by_name(test_name)
        if user:
            print(f"Found user '{user['name']}' for search '{test_name}'")
        else:
            print(f"No user found for '{test_name}'")
        # Create a database entry
        form_data = {
            "title": "API Test Request",
            "type": "feature",
            "description": "Testing the API integration",
            "module": "API",
            "owner": "Dinesh",
            "priority": "High",
            "due_date": "2024-12-31",
            "client": "Internal",
            "reference_link": "https://example.com",
        }

        result = manager.create_database_entry(form_data)

    except Exception as e:
        print(f"Error in example usage: {e}")


if __name__ == "__main__":
    example_usage()

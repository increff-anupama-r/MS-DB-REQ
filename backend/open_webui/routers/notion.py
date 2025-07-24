import json
import logging
import requests
import os
import shutil
from typing import Optional, List
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
    UploadFile,
    File,
    Form,
)
from pydantic import BaseModel
from open_webui.utils.auth import get_verified_user
from open_webui.env import (
    NOTION_INTEGRATION_TOKEN,
    NOTION_DB_ID,
    OPENAI_API_KEY,
    STATIC_DIR,
)
from open_webui.constants import ERROR_MESSAGES
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

router = APIRouter()

UPLOADS_DIR = STATIC_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

from open_webui.notion_workspace_manager import NotionWorkspaceManager

_workspace_manager = None


def get_workspace_manager():
    """Get or create the workspace manager instance"""
    global _workspace_manager
    if _workspace_manager is None:
        import os

        os.environ["NOTION_INTEGRATION_TOKEN2"] = NOTION_INTEGRATION_TOKEN
        os.environ["NOTION_DB_ID2"] = NOTION_DB_ID
        _workspace_manager = NotionWorkspaceManager()
    return _workspace_manager


def get_notion_user_id(name):
    """Get Notion user ID by name using fuzzy matching"""
    try:
        manager = get_workspace_manager()
        user_id = manager.get_user_id_by_name(name)
        if user_id:
            return user_id
        else:
            raise Exception(f"Could not find Notion user id for {name}")
    except Exception as e:
        log.error(f"Error finding user '{name}': {e}")
        raise Exception(f"Could not find Notion user id for {name}")


class FeatureRequestForm(BaseModel):
    title: str
    type: str
    client: str
    module: str
    description: str
    owner: str
    priority: str
    due_date: str
    reference_link: Optional[str] = None
    attachments: Optional[List[str]] = []
    attachment_urls: Optional[List[str]] = []


class NameSuggestionRequest(BaseModel):
    partial_name: str
    limit: Optional[int] = 5


class NameSuggestionResponse(BaseModel):
    suggestions: List[dict]
    total_found: int


class UserMatchRequest(BaseModel):
    name: str


class UserMatchResponse(BaseModel):
    found: bool
    user: Optional[dict] = None
    confidence_score: Optional[float] = None
    suggestions: Optional[List[dict]] = None


@router.get("/users/all")
async def get_all_notion_users(request: Request, user=Depends(get_verified_user)):
    """
    Get all users from Notion workspace for dropdown/autocomplete
    """
    try:
        manager = get_workspace_manager()
        users = manager.get_all_users_for_dropdown()
        return {"users": users, "total": len(users)}
    except Exception as e:
        log.error(f"Error getting all users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get users: {str(e)}",
        )


# Test endpoints removed for production security


@router.post("/users/suggestions")
async def get_name_suggestions(
    request: NameSuggestionRequest, user=Depends(get_verified_user)
):
    """
    Get AI-powered name suggestions for partial input
    """
    try:
        manager = get_workspace_manager()
        suggestions = manager.get_name_suggestions(request.partial_name, request.limit)

        # Format suggestions for frontend
        formatted_suggestions = []
        for suggestion in suggestions:
            formatted_suggestions.append(
                {
                    "id": suggestion["user"]["id"],
                    "name": suggestion["name"],
                    "email": suggestion["user"].get("email", ""),
                    "score": suggestion["score"],
                    "display": f"{suggestion['name']} ({suggestion['user'].get('email', '')})",
                }
            )

        return NameSuggestionResponse(
            suggestions=formatted_suggestions, total_found=len(formatted_suggestions)
        )
    except Exception as e:
        log.error(f"Error getting name suggestions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get name suggestions: {str(e)}",
        )


@router.post("/users/match")
async def match_user_name(request: UserMatchRequest, user=Depends(get_verified_user)):
    """
    Find exact user match and provide suggestions if not found
    """
    try:
        manager = get_workspace_manager()
        matched_user = manager.find_user_by_name(request.name)

        if matched_user:
            from difflib import SequenceMatcher

            search_lower = request.name.lower()
            user_name_lower = matched_user["name"].lower()
            confidence_score = SequenceMatcher(
                None, search_lower, user_name_lower
            ).ratio()

            return UserMatchResponse(
                found=True,
                user={
                    "id": matched_user["id"],
                    "name": matched_user["name"],
                    "email": matched_user.get("email", ""),
                    "display": f"{matched_user['name']} ({matched_user.get('email', '')})",
                },
                confidence_score=confidence_score,
                suggestions=None,
            )
        else:
            suggestions = manager.get_name_suggestions(request.name, 3)
            formatted_suggestions = []
            for suggestion in suggestions:
                formatted_suggestions.append(
                    {
                        "id": suggestion["user"]["id"],
                        "name": suggestion["name"],
                        "email": suggestion["user"].get("email", ""),
                        "score": suggestion["score"],
                        "display": f"{suggestion['name']} ({suggestion['user'].get('email', '')})",
                    }
                )

            return UserMatchResponse(
                found=False,
                user=None,
                confidence_score=None,
                suggestions=formatted_suggestions,
            )
    except Exception as e:
        log.error(f"Error matching user name: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to match user name: {str(e)}",
        )


@router.post("/feature-request")
async def create_feature_request(
    request: Request,
    form_data: str = Form(...),
    files: Optional[List[UploadFile]] = File(None),
    user=Depends(get_verified_user),
):
    """
    Create a new feature request entry in Notion database with enhanced people property support
    """
    if not NOTION_INTEGRATION_TOKEN or not NOTION_DB_ID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Notion integration not configured",
        )

    try:
        form_data_dict = json.loads(form_data)
        uploaded_files = []
        if files:
            for file in files:
                if file.filename:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_filename = f"{timestamp}_{file.filename.replace(' ', '_')}"
                    file_path = UPLOADS_DIR / safe_filename
                    with open(file_path, "wb") as buffer:
                        shutil.copyfileobj(file.file, buffer)
                    base_url = str(request.base_url).rstrip("/")
                    file_url = f"{base_url}/static/uploads/{safe_filename}"

                    uploaded_files.append({"name": file.filename, "url": file_url})

        all_files = uploaded_files + [
            {"name": name, "url": url}
            for name, url in zip(
                form_data_dict.get("attachments", []),
                form_data_dict.get("attachment_urls", []),
            )
        ]

        now_iso = datetime.now(timezone.utc).isoformat()
        # Reference Link: handle empty string/list/null
        ref_link = form_data_dict["reference_link"]
        if isinstance(ref_link, list):
            ref_link_val = ref_link[0] if ref_link and ref_link[0].strip() else None
        elif isinstance(ref_link, str):
            ref_link_val = ref_link.strip() if ref_link.strip() else None
        else:
            ref_link_val = None

        # Priority mapping for Notion format
        priority_value = form_data_dict["priority"]
        try:
            headers = {
                "Authorization": f"Bearer {NOTION_INTEGRATION_TOKEN}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28",
            }

            db_response = requests.get(
                f"https://api.notion.com/v1/databases/{NOTION_DB_ID}", headers=headers
            )

            if db_response.status_code == 200:
                database_info = db_response.json()
                actual_priority_options = []

                if (
                    "properties" in database_info
                    and "Priority" in database_info["properties"]
                ):
                    priority_prop = database_info["properties"]["Priority"]
                    if (
                        "select" in priority_prop
                        and "options" in priority_prop["select"]
                    ):
                        actual_priority_options = [
                            option["name"]
                            for option in priority_prop["select"]["options"]
                        ]
                        log.info(
                            f"Actual Notion priority options: {actual_priority_options}"
                        )
                if actual_priority_options:
                    priority_map = {}
                    if "Critical" in actual_priority_options:
                        priority_map.update(
                            {
                                "0 - Critical": "Critical",
                                "0": "Critical",
                                "critical": "Critical",
                                "Critical": "Critical",
                            }
                        )
                    if "High" in actual_priority_options:
                        priority_map.update(
                            {
                                "1 - High": "High",
                                "1": "High",
                                "high": "High",
                                "High": "High",
                            }
                        )
                    if "Medium" in actual_priority_options:
                        priority_map.update(
                            {
                                "2 - Medium": "Medium",
                                "2": "Medium",
                                "medium": "Medium",
                                "Medium": "Medium",
                            }
                        )
                    if "Low" in actual_priority_options:
                        priority_map.update(
                            {"3 - Low": "Low", "3": "Low", "low": "Low", "Low": "Low"}
                        )
                else:
                    # Fallback to default mapping
                    priority_map = {
                        "0 - Critical": "Critical",
                        "1 - High": "High",
                        "2 - Medium": "Medium",
                        "3 - Low": "Low",
                        "0": "Critical",
                        "1": "High",
                        "2": "Medium",
                        "3": "Low",
                        "critical": "Critical",
                        "high": "High",
                        "medium": "Medium",
                        "low": "Low",
                        "Critical": "Critical",
                        "High": "High",
                        "Medium": "Medium",
                        "Low": "Low",
                    }
            else:
                # Fallback to default mapping if can't fetch database schema
                priority_map = {
                    "0 - Critical": "Critical",
                    "1 - High": "High",
                    "2 - Medium": "Medium",
                    "3 - Low": "Low",
                    "0": "Critical",
                    "1": "High",
                    "2": "Medium",
                    "3": "Low",
                    "critical": "Critical",
                    "high": "High",
                    "medium": "Medium",
                    "low": "Low",
                    "Critical": "Critical",
                    "High": "High",
                    "Medium": "Medium",
                    "Low": "Low",
                }
        except Exception as e:
            log.error(f"Error fetching database schema: {e}")
            priority_map = {
                "0 - Critical": "Critical",
                "1 - High": "High",
                "2 - Medium": "Medium",
                "3 - Low": "Low",
                "0": "Critical",
                "1": "High",
                "2": "Medium",
                "3": "Low",
                "critical": "Critical",
                "high": "High",
                "medium": "Medium",
                "low": "Low",
                "Critical": "Critical",
                "High": "High",
                "Medium": "Medium",
                "Low": "Low",
            }

        mapped_priority = priority_map.get(priority_value, "Medium")
        log.info(f"Mapped priority '{priority_value}' to '{mapped_priority}'")
        enhanced_form_data = {
            "title": form_data_dict["title"],
            "type": form_data_dict["type"],
            "description": form_data_dict["description"],
            "module": form_data_dict["module"],
            "owner": form_data_dict["owner"],
            "created_by": form_data_dict.get("created_by", ""),
            "priority": mapped_priority,
            "due_date": form_data_dict["due_date"],
            "client": form_data_dict["client"],
            "reference_link": ref_link_val,
            "attachments": all_files,
        }

        manager = get_workspace_manager()
        result = manager.create_database_entry(enhanced_form_data)

        return {
            "success": True,
            "page_id": result.get("id"),
            "message": "Feature request created successfully",
            "priority_mapped": mapped_priority,
        }

    except Exception as e:
        log.error(f"Error creating feature request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create feature request: {str(e)}",
        )


@router.get("/config")
async def get_notion_config(request: Request, user=Depends(get_verified_user)):
    """
    Get Notion configuration status
    """
    return {
        "notion_configured": bool(NOTION_INTEGRATION_TOKEN and NOTION_DB_ID),
        "has_token": bool(NOTION_INTEGRATION_TOKEN),
        "has_database_id": bool(NOTION_DB_ID),
    }


@router.get("/database-schema")
async def get_notion_database_schema(request: Request, user=Depends(get_verified_user)):
    """
    Get Notion database schema for form validation
    """
    if not NOTION_INTEGRATION_TOKEN or not NOTION_DB_ID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Notion integration not configured",
        )

    try:
        headers = {
            "Authorization": f"Bearer {NOTION_INTEGRATION_TOKEN}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

        response = requests.get(
            f"https://api.notion.com/v1/databases/{NOTION_DB_ID}", headers=headers
        )

        if response.status_code == 200:
            database_info = response.json()
            properties = {}
            if "properties" in database_info:
                for prop_name, prop_info in database_info["properties"].items():
                    prop_type = list(prop_info.keys())[0] if prop_info else "unknown"
                    properties[prop_name] = {
                        "type": prop_type,
                        "options": (
                            prop_info.get(prop_type, {}).get("options", [])
                            if prop_type == "select"
                            else []
                        ),
                    }

            return {
                "database_id": NOTION_DB_ID,
                "properties": properties,
                "title": database_info.get("title", []),
                "description": database_info.get("description", ""),
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch database schema: {response.text}",
            )
    except Exception as e:
        log.error(f"Error fetching database schema: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch database schema: {str(e)}",
        )


# Test endpoint removed for production security

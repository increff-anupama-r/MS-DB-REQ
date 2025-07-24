import json
import os
from pathlib import Path
from typing import List, Optional
from uuid import uuid4
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request, status
import logging

from open_webui.models.artifacts import (
    Artifacts,
    ArtifactForm,
    ArtifactResponse,
)
from open_webui.constants import ERROR_MESSAGES
from open_webui.utils.auth import get_verified_user
from open_webui.utils.access_control import has_permission
from open_webui.config import CACHE_DIR

from open_webui.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

router = APIRouter()


class ArtifactsConfigResponse(BaseModel):
    fields: List[dict]


############################
# Get Artifacts Config
############################


@router.get("/config", response_model=ArtifactsConfigResponse)
async def get_artifacts_config(request: Request, user=Depends(get_verified_user)):
    """Get artifacts configuration from artifacts.json file"""
    try:
        # Try to load from workspace-specific artifacts.json
        workspace_id = request.query_params.get("workspace_id")
        if workspace_id:
            artifacts_path = (
                Path.home()
                / ".local"
                / "share"
                / "open-webui"
                / "data"
                / "workspace"
                / workspace_id
                / "artifacts.json"
            )
            if artifacts_path.exists():
                with open(artifacts_path, "r") as f:
                    config = json.load(f)
                    return ArtifactsConfigResponse(**config)

        # Fallback to default artifacts.json in project root
        default_path = Path("artifacts.json")
        if default_path.exists():
            with open(default_path, "r") as f:
                config = json.load(f)
                return ArtifactsConfigResponse(**config)

        # Return empty config if no file found
        return ArtifactsConfigResponse(fields=[])

    except Exception as e:
        log.exception(f"Failed to load artifacts config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.DEFAULT("Failed to load artifacts configuration"),
        )


############################
# Get Artifacts
############################


@router.get("/", response_model=List[ArtifactResponse])
async def get_artifacts(workspace_id: str, user=Depends(get_verified_user)):
    """Get all artifacts for a workspace"""
    try:
        artifacts = Artifacts.get_artifacts_by_workspace_id(workspace_id)
        return [
            ArtifactResponse(
                id=getattr(artifact, "id"),
                workspace_id=getattr(artifact, "workspace_id"),
                title=getattr(artifact, "title"),
                type=getattr(artifact, "type"),
                client=getattr(artifact, "client"),
                module=getattr(artifact, "module"),
                description=getattr(artifact, "description"),
                owner=getattr(artifact, "owner"),
                priority=getattr(artifact, "priority"),
                due_date=getattr(artifact, "due_date").isoformat(),
                data=getattr(artifact, "data"),
                created_at=getattr(artifact, "created_at").isoformat(),
                updated_at=getattr(artifact, "updated_at").isoformat(),
            )
            for artifact in artifacts
        ]
    except Exception as e:
        log.exception(f"Failed to get artifacts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.DEFAULT("Failed to get artifacts"),
        )


############################
# Get Artifact by ID
############################


@router.get("/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact_by_id(artifact_id: str, user=Depends(get_verified_user)):
    """Get a specific artifact by ID"""
    try:
        artifact = Artifacts.get_artifact_by_id(artifact_id)
        if not artifact:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Artifact not found",
            )

        return ArtifactResponse(
            id=getattr(artifact, "id"),
            workspace_id=getattr(artifact, "workspace_id"),
            title=getattr(artifact, "title"),
            type=getattr(artifact, "type"),
            client=getattr(artifact, "client"),
            module=getattr(artifact, "module"),
            description=getattr(artifact, "description"),
            owner=getattr(artifact, "owner"),
            priority=getattr(artifact, "priority"),
            due_date=getattr(artifact, "due_date").isoformat(),
            data=getattr(artifact, "data"),
            created_at=getattr(artifact, "created_at").isoformat(),
            updated_at=getattr(artifact, "updated_at").isoformat(),
        )
    except HTTPException:
        raise
    except Exception as e:
        log.exception(f"Failed to get artifact: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.DEFAULT("Failed to get artifact"),
        )


############################
# Create New Artifact
############################


@router.post("/create", response_model=Optional[ArtifactResponse])
async def create_new_artifact(
    request: Request,
    form_data: ArtifactForm,
    workspace_id: str,
    user=Depends(get_verified_user),
):
    """Create a new artifact"""
    try:
        artifact_id = str(uuid4())
        artifact = Artifacts.insert_new_artifact(workspace_id, form_data, artifact_id)

        if artifact:
            return ArtifactResponse(
                id=getattr(artifact, "id"),
                workspace_id=getattr(artifact, "workspace_id"),
                title=getattr(artifact, "title"),
                type=getattr(artifact, "type"),
                client=getattr(artifact, "client"),
                module=getattr(artifact, "module"),
                description=getattr(artifact, "description"),
                owner=getattr(artifact, "owner"),
                priority=getattr(artifact, "priority"),
                due_date=getattr(artifact, "due_date").isoformat(),
                data=getattr(artifact, "data"),
                created_at=getattr(artifact, "created_at").isoformat(),
                updated_at=getattr(artifact, "updated_at").isoformat(),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Error creating artifact"),
            )
    except HTTPException:
        raise
    except Exception as e:
        log.exception(f"Failed to create artifact: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.DEFAULT("Failed to create artifact"),
        )


############################
# Update Artifact
############################


@router.put("/{artifact_id}", response_model=Optional[ArtifactResponse])
async def update_artifact(
    artifact_id: str,
    form_data: ArtifactForm,
    user=Depends(get_verified_user),
):
    """Update an existing artifact"""
    try:
        artifact = Artifacts.update_artifact(artifact_id, form_data)

        if artifact:
            return ArtifactResponse(
                id=getattr(artifact, "id"),
                workspace_id=getattr(artifact, "workspace_id"),
                title=getattr(artifact, "title"),
                type=getattr(artifact, "type"),
                client=getattr(artifact, "client"),
                module=getattr(artifact, "module"),
                description=getattr(artifact, "description"),
                owner=getattr(artifact, "owner"),
                priority=getattr(artifact, "priority"),
                due_date=getattr(artifact, "due_date").isoformat(),
                data=getattr(artifact, "data"),
                created_at=getattr(artifact, "created_at").isoformat(),
                updated_at=getattr(artifact, "updated_at").isoformat(),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Artifact not found",
            )
    except HTTPException:
        raise
    except Exception as e:
        log.exception(f"Failed to update artifact: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.DEFAULT("Failed to update artifact"),
        )


############################
# Delete Artifact
############################


@router.delete("/{artifact_id}")
async def delete_artifact(
    artifact_id: str,
    user=Depends(get_verified_user),
):
    """Delete an artifact"""
    try:
        success = Artifacts.delete_artifact(artifact_id)

        if success:
            return {"message": "Artifact deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Artifact not found",
            )
    except HTTPException:
        raise
    except Exception as e:
        log.exception(f"Failed to delete artifact: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.DEFAULT("Failed to delete artifact"),
        )

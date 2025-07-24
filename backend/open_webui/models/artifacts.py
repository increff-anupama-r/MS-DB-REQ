from typing import Optional, List
from pydantic import BaseModel
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON
from sqlalchemy.sql import func
from open_webui.internal.db import Base


class ArtifactModel(Base):
    __tablename__ = "artifacts"
    
    id = Column(String, primary_key=True)
    workspace_id = Column(String, nullable=False)
    title = Column(String, nullable=False)
    type = Column(String, nullable=False)
    client = Column(String, nullable=False)
    module = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    owner = Column(String, nullable=False)
    priority = Column(String, nullable=False)
    due_date = Column(DateTime, nullable=False)
    reference_link = Column(String, nullable=True)
    data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class ArtifactForm(BaseModel):
    title: str
    type: str
    client: str
    module: str
    description: str
    owner: str
    priority: str
    due_date: str
    reference_link: Optional[str] = None
    data: Optional[dict] = None


class ArtifactResponse(BaseModel):
    id: str
    workspace_id: str
    title: str
    type: str
    client: str
    module: str
    description: str
    owner: str
    priority: str
    due_date: str
    reference_link: Optional[str] = None
    data: Optional[dict] = None
    created_at: str
    updated_at: str


class Artifacts:
    @staticmethod
    def get_artifacts_by_workspace_id(workspace_id: str) -> List[ArtifactModel]:
        from open_webui.internal.db import Session
        with Session() as session:
            return session.query(ArtifactModel).filter(
                ArtifactModel.workspace_id == workspace_id
            ).all()
    
    @staticmethod
    def get_artifact_by_id(artifact_id: str) -> Optional[ArtifactModel]:
        from open_webui.internal.db import Session
        with Session() as session:
            return session.query(ArtifactModel).filter(
                ArtifactModel.id == artifact_id
            ).first()
    
    @staticmethod
    def insert_new_artifact(workspace_id: str, form_data: ArtifactForm, artifact_id: str) -> Optional[ArtifactModel]:
        from open_webui.internal.db import Session
        from datetime import datetime
        with Session() as session:
            artifact = ArtifactModel(
                id=artifact_id,
                workspace_id=workspace_id,
                title=form_data.title,
                type=form_data.type,
                client=form_data.client,
                module=form_data.module,
                description=form_data.description,
                owner=form_data.owner,
                priority=form_data.priority,
                due_date=datetime.fromisoformat(form_data.due_date),
                reference_link=form_data.reference_link,
                data=form_data.data
            )

            session.add(artifact)
            session.commit()
            session.refresh(artifact)
            return artifact
    
    @staticmethod 
    def update_artifact(artifact_id: str, form_data: ArtifactForm) -> Optional[ArtifactModel]:
        from open_webui.internal.db import Session
        from datetime import datetime
        with Session() as session:
            artifact = session.query(ArtifactModel).filter(
                ArtifactModel.id == artifact_id
            ).first()
            if artifact:
                setattr(artifact, 'title', form_data.title)
                setattr(artifact, 'type', form_data.type)
                setattr(artifact, 'client', form_data.client)
                setattr(artifact, 'module', form_data.module)
                setattr(artifact, 'description', form_data.description)
                setattr(artifact, 'owner', form_data.owner)
                setattr(artifact, 'priority', form_data.priority)
                setattr(artifact, 'due_date', datetime.fromisoformat(form_data.due_date))
                setattr(artifact, 'reference_link', form_data.reference_link)
                setattr(artifact, 'data', form_data.data)
                session.commit()
                session.refresh(artifact)
                return artifact
            return None
    
    @staticmethod
    def delete_artifact(artifact_id: str) -> bool:
        from open_webui.internal.db import Session
        with Session() as session:
            artifact = session.query(ArtifactModel).filter(
                ArtifactModel.id == artifact_id
            ).first()
            if artifact:
                session.delete(artifact)
                session.commit()
                return True
            return False 
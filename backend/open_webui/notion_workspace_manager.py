import os
import json
import logging
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from difflib import SequenceMatcher
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class NotionWorkspaceManager:
    def __init__(self):
        self.notion_token = os.environ.get("NOTION_INTEGRATION_TOKEN2")
        self.database_id = os.environ.get("NOTION_DB_ID2")
        self.use_api = bool(self.notion_token and self.database_id)

        if self.use_api:
            self.headers = {
                "Authorization": f"Bearer {self.notion_token}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28",
            }
        else:
            self.headers = None

        self.workspace_users = None
        self.user_name_mapping = {}
        self.get_workspace_users()

    def get_workspace_users(self) -> List[Dict]:
        if self.workspace_users is not None:
            return self.workspace_users
        possible_paths = [
            "notion_users.json",
            "../notion_users.json",
            "../../notion_users.json",
            "/Users/anupamar/Documents/open-webui-f/notion_users.json",
        ]

        for file_path in possible_paths:
            try:
                with open(file_path, "r") as f:
                    self.workspace_users = json.load(f)
                    self._build_name_mapping()
                    logger.info(
                        f"Loaded {len(self.workspace_users)} users from local JSON file: {file_path}"
                    )
                    return self.workspace_users
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.debug(f"Could not load local users file from {file_path}: {e}")
                continue

        logger.warning(
            f"Could not load local users file from any of the tried paths: {possible_paths}"
        )

        # Fallback to API if local file not found
        if self.use_api:
            try:
                response = requests.get(
                    "https://api.notion.com/v1/users", headers=self.headers
                )
                if response.status_code != 200:
                    logger.error(
                        f"Failed to fetch users: {response.status_code} - {response.text}"
                    )
                    raise Exception(f"Failed to fetch users: {response.text}")

                users = response.json().get("results", [])
                person_users = []

                for user in users:
                    if user.get("object") == "user" and user.get("type") == "person":
                        person_users.append(
                            {
                                "id": user["id"],
                                "name": user.get("name", ""),
                                "email": user.get("person", {}).get("email", ""),
                                "type": user.get("type"),
                            }
                        )

                self.workspace_users = person_users
                self._build_name_mapping()
                return person_users
            except Exception as e:
                logger.error(f"Failed to fetch users from API: {e}")

        self.workspace_users = []
        return []

    def _build_name_mapping(self):
        """Build comprehensive name mapping for fuzzy matching"""
        if not self.workspace_users:
            return

        for user in self.workspace_users:
            name = user.get("name", "").strip()
            if name:
                self.user_name_mapping[name.lower()] = user["id"]

                # Store individual parts
                parts = name.split()
                if parts:
                    self.user_name_mapping[parts[0].lower()] = user["id"]
                    if len(parts) > 1:
                        self.user_name_mapping[parts[-1].lower()] = user["id"]
                    for part in parts[1:-1]:
                        if part:
                            self.user_name_mapping[part.lower()] = user["id"]

                    if len(parts) >= 2:
                        self.user_name_mapping[
                            f"{parts[0].lower()} {parts[-1].lower()}"
                        ] = user["id"]
                        initials = "".join([p[0].lower() for p in parts if p])
                        self.user_name_mapping[initials] = user["id"]

        logger.info(
            f"Built comprehensive name mapping with {len(self.user_name_mapping)} entries"
        )

    def find_user_by_name(self, search_name: str) -> Optional[Dict]:
        """Enhanced AI-powered name matching"""
        if not search_name or not self.workspace_users:
            logger.warning(
                f"Invalid search: search_name='{search_name}', workspace_users={bool(self.workspace_users)}"
            )
            return None

        search_lower = search_name.strip().lower()
        logger.info(
            f"Searching for user with name: '{search_name}' (lowercase: '{search_lower}')"
        )

        # 1. Exact match in mapping
        if search_lower in self.user_name_mapping:
            user_id = self.user_name_mapping[search_lower]
            user = next((u for u in self.workspace_users if u["id"] == user_id), None)
            logger.info(f"Found exact match in mapping: {user}")
            return user

        # 2. AI-powered fuzzy matching
        best_match = None
        best_score = 0.0
        matches = []

        for user in self.workspace_users:
            user_name = user.get("name", "").strip()
            if not user_name:
                continue

            # Calculate multiple similarity scores
            scores = []
            full_score = SequenceMatcher(None, search_lower, user_name.lower()).ratio()
            scores.append(full_score)
            if search_lower in user_name.lower() or user_name.lower() in search_lower:
                scores.append(0.8)

            # First name exact match
            parts = user_name.split()
            if parts and search_lower == parts[0].lower():
                scores.append(0.95)

            # Last name exact match
            if len(parts) > 1 and search_lower == parts[-1].lower():
                scores.append(0.9)

            # Middle name match
            for part in parts[1:-1]:
                if search_lower == part.lower():
                    scores.append(0.85)

            # Initials match
            initials = "".join([p[0].lower() for p in parts if p])
            if search_lower == initials:
                scores.append(0.9)

            # Take the best score
            score = max(scores) if scores else 0.0

            if score >= 0.5:  # Lower threshold for more matches
                matches.append((user, score))
                if score > best_score:
                    best_score = score
                    best_match = user

        logger.info(f"Found {len(matches)} potential matches, best score: {best_score}")
        if best_match and best_score >= 0.6:
            return best_match

        return None

    def get_name_suggestions(self, partial_name: str, limit: int = 5) -> List[Dict]:
        """Get AI-powered name suggestions for partial input"""
        if not partial_name or not self.workspace_users:
            return []

        partial_lower = partial_name.strip().lower()
        suggestions = []

        for user in self.workspace_users:
            user_name = user.get("name", "").strip()
            if not user_name:
                continue

            # Calculate relevance score
            score = 0.0

            # Starts with partial
            if user_name.lower().startswith(partial_lower):
                score += 0.8

            # Contains partial
            if partial_lower in user_name.lower():
                score += 0.6

            # First name starts with
            parts = user_name.split()
            if parts and parts[0].lower().startswith(partial_lower):
                score += 0.9

            # Last name starts with
            if len(parts) > 1 and parts[-1].lower().startswith(partial_lower):
                score += 0.7

            # Fuzzy similarity
            similarity = SequenceMatcher(None, partial_lower, user_name.lower()).ratio()
            score += similarity * 0.5

            if score > 0.3:  # Only include relevant suggestions
                suggestions.append({"user": user, "score": score, "name": user_name})

        # Sort by score and return top matches
        suggestions.sort(key=lambda x: x["score"], reverse=True)
        return suggestions[:limit]

    def get_user_id_by_name(self, name: str) -> Optional[str]:
        """Get user ID by name with enhanced matching"""
        user = self.find_user_by_name(name)
        if user and "id" in user:
            logger.info(f"Found user ID {user['id']} for name '{name}'")
            return user["id"]
        logger.warning(f"Could not find user ID for name '{name}'")
        return None

    def create_database_entry(self, form_data: Dict) -> Dict:
        """Create database entry with people property support"""
        if not self.workspace_users:
            self.get_workspace_users()

        now_iso = datetime.now(timezone.utc).isoformat()
        owner_name = form_data.get("owner", "")
        created_by_name = form_data.get("created_by", "")

        # Get user IDs for people properties
        owner_user_id = self.get_user_id_by_name(owner_name) if owner_name else None
        created_by_user_id = (
            self.get_user_id_by_name(created_by_name) if created_by_name else None
        )

        properties = {
            "Request Title": {
                "title": [{"text": {"content": form_data.get("title", "")}}]
            },
            "Request Type": {
                "select": {"name": form_data.get("type", "").capitalize()}
            },
            "Request Description": {
                "rich_text": [{"text": {"content": form_data.get("description", "")}}]
            },
            "Module": {
                "rich_text": [{"text": {"content": form_data.get("module", "")}}]
            },
            "Due Date": {"date": {"start": form_data.get("due_date", "")}},
            "Priority": {"select": {"name": form_data.get("priority", "Medium")}},
            "Requesting Client": {
                "rich_text": [{"text": {"content": form_data.get("client", "")}}]
            },
            "Created Date": {"date": {"start": now_iso}},
        }

        # Use people properties for owner and created_by if user IDs found
        if owner_user_id:
            properties["Request Owner"] = {"people": [{"id": owner_user_id}]}
        else:
            properties["Request Owner"] = {
                "rich_text": [{"text": {"content": owner_name}}]
            }

        if created_by_user_id:
            properties["Created By"] = {"people": [{"id": created_by_user_id}]}
        elif created_by_name:
            properties["Created By"] = {
                "rich_text": [{"text": {"content": created_by_name}}]
            }

        ref_link = form_data.get("reference_link")
        if ref_link:
            properties["Reference Link"] = {"url": ref_link.strip()}

        attachments = form_data.get("attachments", [])
        if attachments:
            properties["Attachments"] = {
                "files": [
                    {
                        "name": att.get("name", ""),
                        "external": {"url": att.get("url", "")},
                    }
                    for att in attachments
                ]
            }

        page_data = {
            "parent": {"database_id": self.database_id},
            "properties": properties,
        }

        if not self.use_api:
            logger.warning("Notion API not configured, returning mock response")
            return {"id": "mock-page-id", "properties": properties}

        response = requests.post(
            "https://api.notion.com/v1/pages", headers=self.headers, json=page_data
        )
        if response.status_code != 200:
            logger.error(
                f"Failed to create database entry: {response.status_code} - {response.text}"
            )
            raise Exception(f"Failed to create database entry: {response.text}")

        return response.json()

    def save_users_to_json(self, filename="notion_users.json"):
        """Save current users to JSON file"""
        users = self.get_workspace_users()
        with open(filename, "w") as f:
            json.dump(users, f, indent=2)
        return filename

    def get_all_users_for_dropdown(self) -> List[Dict]:
        """Get all users formatted for dropdown/autocomplete"""
        users = self.get_workspace_users()
        return [
            {
                "id": user["id"],
                "name": user["name"],
                "email": user.get("email", ""),
                "display": f"{user['name']} ({user.get('email', '')})",
            }
            for user in users
        ]

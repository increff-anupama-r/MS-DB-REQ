import os
import sys
from dotenv import load_dotenv
from fetch_notion_users_paginated import (
    fetch_users_in_batches,
    save_users_to_json,
    verify_extraction,
    show_sample_users,
)

# Load environment variables from .env file
load_dotenv()


def check_environment():
    notion_token = os.environ.get("NOTION_INTEGRATION_TOKEN2")
    if not notion_token:
        print("NOTION_INTEGRATION_TOKEN2 not found in environment variables")
        return False
    return True


def main():
    """Main extraction function."""
    print(" Notion User Extraction Tool")
    print("=" * 40)
    if not check_environment():
        sys.exit(1)

    try:
        users = fetch_users_in_batches()

        if not users:
            print("No users were extracted!")
            sys.exit(1)

        show_sample_users(users, count=10)
        output_file = "notion_users.json"
        save_users_to_json(users, output_file)
        print(f"Total users: {len(users)}")

    except Exception as e:
        print(f"Error during extraction: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

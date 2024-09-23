import argparse
import datetime
import time
import textwrap
from plexapi import CONFIG
from plexapi.myplex import MyPlexAccount
from plexapi.utils import getMyPlexAccount
from plexapi.exceptions import BadRequest

COMMUNITY_API_URL = "https://community.plex.tv/api"

GET_WATCH_HISTORY_QUERY = """\
query GetWatchHistoryHub(
  $uuid: ID = ""
  $first: PaginationInt!
  $after: String
) {
  user(id: $uuid) {
    watchHistory(first: $first, after: $after) {
      nodes {
        metadataItem {
          id
          title
          type
          year
          parent {
            title
            index
          }
          grandparent {
            title
          }
        }
        date
        id
      }
      pageInfo {
        hasNextPage
        endCursor
      }
    }
  }
}
"""

REMOVE_WATCH_HISTORY_QUERY = """\
mutation removeActivity($input: RemoveActivityInput!) {
  removeActivity(input: $input)
}
"""

# ---------------------------------------------
# Helper functions for interacting with Plex API
# ---------------------------------------------

def query_plex_api(account, query, variables, retries=3, delay=5):
    """Helper to interact with Plex community API with retries."""
    params = {
        "query": query,
        "variables": variables
    }
    for attempt in range(retries):
        try:
            response = account.query(
                COMMUNITY_API_URL,
                json=params,
                method=account._session.post,
                headers={"Content-Type": "application/json"}
            )
            if response:
                return response
        except Exception as e:
            print(f"Error querying API (Attempt {attempt+1}/{retries}): {e}")
            time.sleep(delay)
    return None

# ---------------------------------------------
# Core functions for Plex watch history management
# ---------------------------------------------

def get_watch_history(account, first=100, after=None):
    """Generator to fetch watch history from Plex API."""
    variables = {
        "uuid": account.uuid,
        "first": first,
        "after": after
    }

    while True:
        response = query_plex_api(account, GET_WATCH_HISTORY_QUERY, variables)
        if not response:
            print("Failed to retrieve watch history.")
            return

        watch_history = response["data"]["user"]["watchHistory"]
        for node in watch_history["nodes"]:
            yield node

        if not watch_history["pageInfo"]["hasNextPage"]:
            break

        variables["after"] = watch_history["pageInfo"]["endCursor"]
        time.sleep(2)  # Avoid API rate limiting

def remove_watch_history(account, entry_id):
    """Remove a single watch history entry."""
    variables = {
        "input": {
            "id": entry_id,
            "type": "WATCH_HISTORY"
        }
    }
    response = query_plex_api(account, REMOVE_WATCH_HISTORY_QUERY, variables)
    if response and "data" in response and response["data"]["removeActivity"]:
        return True
    return False

def delete_all_watch_history(account):
    """Delete all Plex watch history in batches."""
    for entry in get_watch_history(account):
        formatted_entry = format_watch_history_entry(entry)
        print(f"Deleting: {formatted_entry}")
        
        success = remove_watch_history(account, entry["id"])
        if success:
            print(f"Successfully deleted: {formatted_entry}")
        else:
            print(f"Failed to delete: {formatted_entry}")

        time.sleep(1)  # Rate limit to avoid overwhelming API

# ---------------------------------------------
# Formatting utilities
# ---------------------------------------------

def format_watch_history_entry(entry):
    """Format a watch history entry for display."""
    date_str = datetime.datetime.fromisoformat(entry["date"]).strftime("%Y-%m-%d %H:%M:%S")
    title = entry["metadataItem"]["title"]
    entry_type = entry["metadataItem"]["type"]
    year = entry["metadataItem"].get("year", "Unknown Year")

    parent_title = entry["metadataItem"].get("parent", {}).get("title")
    grandparent_title = entry["metadataItem"].get("grandparent", {}).get("title")

    if entry_type == "episode":
        return f"{date_str} - {grandparent_title}: {parent_title} - {title} ({year})"
    elif entry_type == "movie":
        return f"{date_str} - {title} ({year})"
    else:
        return f"{date_str} - {title} ({entry_type})"

# ---------------------------------------------
# CLI and entry point
# ---------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=textwrap.dedent("""
            Manage your Plex watch history.
            
            This script allows you to list or delete your Plex watch history entries.
        """),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(required=True)

    # List command
    parser_list = subparsers.add_parser(
        "list", 
        help="List your Plex watch history."
    )
    parser_list.set_defaults(func=list_watch_history)

    # Delete command
    parser_delete = subparsers.add_parser(
        "delete",
        help="Delete all your Plex watch history."
    )
    parser_delete.set_defaults(func=delete_all_watch_history)

    for subparser in [parser_list, parser_delete]:
        subparser.add_argument(
            "--token",
            help="Your Plex token",
            default=CONFIG.get("auth.server_token")
        )
        subparser.add_argument(
            "--username",
            help="Your Plex username",
            default=CONFIG.get("auth.myplex_username")
        )
        subparser.add_argument(
            "--password",
            help="Your Plex password",
            default=CONFIG.get("auth.myplex_password")
        )

    args = parser.parse_args()

    # Authentication
    if bool(args.username) != bool(args.password):
        parser.error("You must provide both username and password, or neither.")
    
    account = MyPlexAccount(token=args.token) if args.token else getMyPlexAccount(args)
    args.func(account)

def list_watch_history(account):
    """List Plex watch history in a readable format."""
    for entry in get_watch_history(account):
        print(format_watch_history_entry(entry))

if __name__ == "__main__":
    main()

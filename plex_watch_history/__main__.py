import time
import datetime
from plexapi.exceptions import BadRequest

COMMUNITY_API_URL = "https://community.plex.tv/api"

REMOVE_WATCH_HISTORY_QUERY = """\
mutation removeActivity($input: RemoveActivityInput!) {
  removeActivity(input: $input)
}
"""

# Helper function to format watch history entry for output
def format_watch_history_entry(entry):
    """Format watch history entry with date and title."""
    date = datetime.datetime.fromisoformat(entry["date"]).strftime("%c")
    title = entry["metadataItem"]["title"]
    return f"{date}: {title}"

# Query Plex API with retry mechanism
def query_plex_api(account, query, variables, retries=10, delay=5):
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

# Function to remove a single watch history entry with retries
def remove_watch_history(account, entry_id, retries=10, delay=5):
    """Remove a single watch history entry with retries if it fails."""
    variables = {
        "input": {
            "id": entry_id,
            "type": "WATCH_HISTORY"
        }
    }

    for attempt in range(retries):
        print(f"Attempt {attempt+1}/{retries} to delete entry ID {entry_id}...")
        response = query_plex_api(account, REMOVE_WATCH_HISTORY_QUERY, variables)
        
        # Error handling for NoneType and unexpected responses
        if response is None:
            print(f"API returned None for entry ID {entry_id}. Retrying...")
        elif "data" in response and "removeActivity" in response["data"]:
            if response["data"]["removeActivity"]:
                print(f"Successfully deleted entry ID {entry_id}")
                return True
            else:
                print(f"API responded but deletion failed for entry ID {entry_id}. Retrying...")
        else:
            print(f"Unexpected API response format for entry ID {entry_id}: {response}. Retrying...")
        
        time.sleep(delay)  # Delay before the next attempt
    
    print(f"Failed to delete entry ID {entry_id} after {retries} attempts. Skipping.")
    return False

# Function to delete all watch history with retry mechanism for failures
def delete_all_watch_history(account, retries=10, delay=5):
    """Delete all Plex watch history with retry mechanism for failures."""
    watch_history = get_watch_history(account)  # Assuming this is a generator or iterable
    for entry in watch_history:
        formatted_entry = format_watch_history_entry(entry)
        print(f"Attempting to delete: {formatted_entry}")
        
        success = remove_watch_history(account, entry["id"], retries=retries, delay=delay)
        if not success:
            print(f"Skipping failed entry: {formatted_entry}")

        time.sleep(1)  # Rate limit to avoid overwhelming API

# Assuming get_watch_history function is defined elsewhere
def get_watch_history(account, first=100, after=None):
    """
    Example function to get watch history from Plex account.
    Replace this function with the actual logic to fetch watch history.
    """
    # Example watch history, replace this with the actual API call.
    return [
        {"id": "1", "date": "2023-09-01T12:34:56", "metadataItem": {"title": "Movie A"}},
        {"id": "2", "date": "2023-09-02T13:45:12", "metadataItem": {"title": "Movie B"}},
        # More entries...
    ]

def main():
    """Main function to run the script."""
    # Assuming you handle arguments like token, username, password in actual implementation
    account = None  # Get the Plex account object (MyPlexAccount)
    
    # Example: Deleting all watch history
    delete_all_watch_history(account, retries=10, delay=5)

if __name__ == "__main__":
    main()

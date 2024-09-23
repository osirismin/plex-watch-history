import argparse
import datetime
import os
import textwrap
import time
import logging

from plexapi import CONFIG
from plexapi.exceptions import BadRequest, Unauthorized
from plexapi.myplex import MyPlexAccount
from plexapi.utils import getMyPlexAccount

COMMUNITY = "https://community.plex.tv/api"

GET_WATCH_HISTORY_QUERY = """\
# (省略了之前的查询部分...)
"""

REMOVE_WATCH_HISTORY_QUERY = """\
# (省略了之前的查询部分...)
"""

# 设置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def plex_format(item):
    item_type = item["type"].lower()
    parent = item["parent"]
    grandparent = item["grandparent"]

    if item_type == "season":
        return f"{parent['title']}: Season {item['index']}"
    if item_type == "episode":
        return (
            f"{grandparent['title']}: Season {parent['index']}: "
            f"Episode {item['index']:2d} - {item['title']}"
        )
    return f"{item['title']} ({item['year']})"

def community_query(account, params):
    try:
        response = account.query(
            COMMUNITY,
            json=params,
            method=account._session.post,
            headers={"Content-Type": "application/json"},
        )
        return response
    except BadRequest as e:
        logging.error(f"BadRequest error: {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise

def exponential_backoff(retries, max_wait=60):
    """指数退避策略"""
    wait_time = min(2 ** retries, max_wait)
    logging.info(f"Retrying in {wait_time} seconds...")
    time.sleep(wait_time)

def get_watch_history(account, first=100, after=None, user_state=False, all_=True):
    params = {
        "query": GET_WATCH_HISTORY_QUERY,
        "operationName": "GetWatchHistoryHub",
        "variables": {
            "uuid": account.uuid,
            "first": first,
            "after": after,
            "skipUserState": not user_state,
        },
    }
    retries = 0
    while True:
        try:
            response = community_query(account, params)
            watch_history = response["data"]["user"]["watchHistory"]
            page_info = watch_history["pageInfo"]
            yield from watch_history["nodes"]

            if not all_ or not page_info["hasNextPage"]:
                return
            params["variables"]["after"] = page_info["endCursor"]
            time.sleep(2)  # 正常情况的等待时间，避免速率限制
        except BadRequest:
            if retries < 5:
                retries += 1
                exponential_backoff(retries)
            else:
                logging.error("Max retries reached, aborting.")
                break

def remove_watch_history(account, item):
    params = {
        "query": REMOVE_WATCH_HISTORY_QUERY,
        "operationName": "removeActivity",
        "variables": {
            "input": {
                "id": item["id"],
                "type": "WATCH_HISTORY",
            },
        },
    }
    retries = 0
    while retries < 5:
        try:
            response = community_query(account, params)
            return response["data"]["removeActivity"]
        except BadRequest:
            retries += 1
            exponential_backoff(retries)

def plex_format_entry(entry):
    date = datetime.datetime.fromisoformat(entry["date"]).strftime("%c")
    entry = plex_format(entry["metadataItem"])
    return f"{date}: {entry}"

def list_watch_history(account):
    try:
        for entry in get_watch_history(account):
            print(plex_format_entry(entry))
    except Exception as e:
        logging.error(f"Error listing watch history: {e}")

def delete_watch_history(account):
    while True:
        try:
            history = list(get_watch_history(account))
            if not history:
                break
            print(f"Deleting {len(history)} watch history entries\n")
            for entry in history:
                print(plex_format_entry(entry))
                remove_watch_history(account, entry)
                time.sleep(1)  # 避免速率限制
        except Exception as e:
            logging.error(f"Error deleting watch history: {e}")
            break

def main():
    parser = argparse.ArgumentParser(
        description=textwrap.dedent("""
            Manage your Plex watch history.

            Note: This works with the watch history that is synced to your Plex account."""),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(required=True)

    parser_list = subparsers.add_parser(
        "list",
        help="Display all your watched movies and shows, along with the date you watched them.",
    )
    parser_list.set_defaults(func=list_watch_history)

    parser_delete = subparsers.add_parser(
        "delete",
        help="Permanently delete your entire watch history.",
    )
    parser_delete.set_defaults(func=delete_watch_history)

    for subparser in (parser_list, parser_delete):
        subparser.add_argument("--token", help="Your Plex token", default=CONFIG.get("auth.server_token"))
        subparser.add_argument("--username", help="Your Plex username", default=CONFIG.get("auth.myplex_username"))
        subparser.add_argument("--password", help="Your Plex password", default=CONFIG.get("auth.myplex_password"))

    args = parser.parse_args()

    if bool(args.username) != bool(args.password):
        parser.error("both username and password must be given together")

    try:
        account = MyPlexAccount(token=args.token) if args.token else getMyPlexAccount(args)
        args.func(account)
    except Unauthorized:
        logging.error("Authentication failed, please check your credentials.")
    except Exception as e:
        logging.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()

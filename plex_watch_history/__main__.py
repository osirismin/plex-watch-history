import argparse
import datetime
import os
import textwrap
import time

from plexapi import CONFIG
from plexapi.exceptions import BadRequest
from plexapi.myplex import MyPlexAccount
from plexapi.utils import getMyPlexAccount


COMMUNITY = "https://community.plex.tv/api"

GET_WATCH_HISTORY_QUERY = """\
query GetWatchHistoryHub(
  $uuid: ID = ""
  $first: PaginationInt!
  $after: String
  $skipUserState: Boolean = false
) {
  user(id: $uuid) {
    watchHistory(first: $first, after: $after) {
      nodes {
        metadataItem {
          ...itemFields
        }
        date
        id
      }
      pageInfo {
        hasNextPage
        hasPreviousPage
        endCursor
      }
    }
  }
}

fragment itemFields on MetadataItem {
  id
  images {
    coverArt
    coverPoster
    thumbnail
    art
  }
  userState @skip(if: $skipUserState) {
    viewCount
    viewedLeafCount
    watchlistedAt
  }
  title
  key
  type
  index
  publicPagesURL
  parent {
    ...parentFields
  }
  grandparent {
    ...parentFields
  }
  publishedAt
  leafCount
  year
  originallyAvailableAt
  childCount
}

fragment parentFields on MetadataItem {
  index
  title
  publishedAt
  key
  type
  images {
    coverArt
    coverPoster
    thumbnail
    art
  }
  userState @skip(if: $skipUserState) {
    viewCount
    viewedLeafCount
    watchlistedAt
  }
}
"""

REMOVE_WATCH_HISTORY_QUERY = """\
mutation removeActivity($input: RemoveActivityInput!) {
  removeActivity(input: $input)
}
"""


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
    response = account.query(
        COMMUNITY,
        json=params,
        method=account._session.post,
        headers={"Content-Type": "application/json"},
    )

    if False:
        import json

        print(json.dumps(response, indent=4))

    return response


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

    while True:
        try:
            response = community_query(account, params)
            watch_history = response["data"]["user"]["watchHistory"]
            page_info = watch_history["pageInfo"]

            yield from watch_history["nodes"]

            if not all_ or not page_info["hasNextPage"]:
                return

            params["variables"]["after"] = page_info["endCursor"]

            # Try to avoid API rate limiting
            time.sleep(2)

        except BadRequest:
            time.sleep(30)


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

    response = community_query(account, params)
    return response["data"]["removeActivity"]


def plex_format_entry(entry):
    date = datetime.datetime.fromisoformat(entry["date"]).strftime("%c")
    entry = plex_format(entry["metadataItem"])

    return f"{date}: {entry}"


def list_watch_history(account):
    for entry in get_watch_history(account):
        print(plex_format_entry(entry))


def delete_watch_history(account):
    while True:
        history = list(get_watch_history(account))
        if len(history) == 0:
            break

        print(f"Deleting {len(history)} watch history entries\n")

        for entry in history:
            print(plex_format_entry(entry))

            while True:
                try:
                    remove_watch_history(account, entry)

                    # Try to avoid API rate limiting
                    time.sleep(1)
                    break

                except BadRequest:
                    time.sleep(30)


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
        description="Display all your watched movies and shows, along with the date you watched them.",
    )
    parser_list.set_defaults(func=list_watch_history)

    parser_delete = subparsers.add_parser(
        "delete",
        help="Permanently delete your entire watch history.",
        description="Permanently delete your entire watch history.",
    )
    parser_delete.set_defaults(func=delete_watch_history)

    for subparser in (parser_list, parser_delete):
        subparser.add_argument(
            "--token",
            help="Your Plex token",
            default=CONFIG.get("auth.server_token"),
        )

        subparser.add_argument(
            "--username",
            help="Your Plex username",
            default=CONFIG.get("auth.myplex_username"),
        )
        subparser.add_argument(
            "--password",
            help="Your Plex password",
            default=CONFIG.get("auth.myplex_password"),
        )

    args = parser.parse_args()

    if bool(args.username) != bool(args.password):
        parser.error("both username and password must be given together")

    if args.token:
        account = MyPlexAccount(token=args.token)

    else:
        account = getMyPlexAccount(args)

    args.func(account)

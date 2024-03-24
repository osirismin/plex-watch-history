# plex-watch-history: Manage Your Plex Watch History with Ease

* **List:** Get a complete overview of your watch history, including titles and watched dates.
* **Delete:** Permanently delete your entire watch history if you want a fresh start.

**Note:** This works with the watch history that is synced to your Plex account.

# Installation

plex-watch-history requires Python 3.8 or later. It's recommended to install it in an isolated environment using `pipx`.

1. Install pipx:

    If `pipx` is not already installed, you can follow any of the options in the
    [official pipx installation instructions](https://pipx.pypa.io/stable/installation/).

2. Install plex-watch-history:

   ```bash
   pipx install git+https://github.com/gregier/plex-watch-history.git
   ```

# Usage

### View Your Watch History:

This will display all your watched movies and shows, along with the date you watched them.

```bash
> plex-watch-history list
Mon Jan 01 16:23:42 2024: The Martian (2015)
Mon Jan 01 04:08:15 2024: For All Mankind: Season 1: Episode  1: Red Moon
```

### Delete Your Watch History:

**Important!** This will permanently delete your entire watch history.

```bash
> plex-watch-history delete
Deleting 2 watch history entries

Mon Jan 01 16:23:42 2024: The Martian (2015)
Mon Jan 01 04:08:15 2024: For All Mankind: Season 1: Episode  1: Red Moon
```

### Authentication:

Login using your username and password.
```bash
> plex-watch-history list --username USERNAME --password PASSWORD

> plex-watch-history list
What is your plex.tv username:
What is your plex.tv password:
```

With a Plex authentication token.
```bash
> plex-watch-history list --token b28bada3dc5d2506f
```

You can also use a [configuration file](https://python-plexapi.readthedocs.io/en/latest/configuration.html).


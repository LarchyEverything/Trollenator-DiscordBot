I'm the slop master and here is Trollenator. A bot I vibe coded with Claude.

# Features
Trollenator is a bot meant for trolling! Or just sending embeds I guess. It is a bot you can "talk through" meaning you can make it basically say anything. The bot responds with a private message which is the editor. You can further customize or you can just send, this roundabout way of sending messages actually hides who sent it which can enhance the trolling ability. However you can see who used the bot opening the context menu and looking at "interaction info". 
## Slash Commands
* /permcheck
A private command to see what the bot can or can't do in a given situation. Best to run first.
* /say
A simple "say" command. Just plain text, you can add images, emotes, everything you'd expcect.
* /voice
You upload an audio file, and it'll be converted into a "voice recording".
* /embed
A full on embed builder, allows you to upload images, embed them, add text outside embeds, everything you'd need.
* /poll
Lets you make polls through the bot.
## Control Bot
The control bot is basically where all the dev commands will be. Below is what it does:
* /ban | banedit | bans | baninfo | unban
All commands for banning people from the bot and managing that.
* devpanel
Sends a private message showing debug info, and allows you to add new bot tokens on the fly and switch to them. I added this because Discord terminated my account and bot because someone said something mean on my bot. Fuck you too buddy.
## Misc
* Logging
The bot logs everything done with the bot, so if anyone does break ToS, you can see and ban them.
* ToS Warnings
Due to Discord banning my account, I added ToS warnings. Of course you can ignore them if you don't care but they're there at least.
# Setup
I am lazy and I have some dumb friends so I tortured Claude and forced it to write it for me.
# Trollenator: Setup Guide (from a brand-new computer)

This guide assumes you have never set up a program like this before. Follow the steps in order. Windows, Mac and Linux are covered.

Setup takes about 30 minutes. You need:

- A computer connected to the internet
- A Discord account
- A private Discord server of your own (you can create one in Discord with the **+** button in the server list). This is where you control the bot.

> **Important:** Trollenator only works while it is running. If you close its window, shut down, or the computer goes to sleep, the bot goes offline. For 24/7 use you need a computer or server that stays on.

---

## Step 1: Install the programs you need

### 1a. Python (required)

Python is the language Trollenator is written in. You need version **3.10 or newer**.

- **Windows / Mac:** Go to https://www.python.org/downloads/ and download the latest version.
  - **Windows:** run the installer and **tick the box "Add python.exe to PATH"** at the bottom of the first screen before clicking Install. This is the most common thing people miss.
  - **Mac:** open the downloaded file and click through the installer.
- **Linux (Debian/Ubuntu/Raspberry Pi OS):** open a terminal and run:
  ```
  sudo apt update
  sudo apt install python3 python3-pip python3-venv
  ```

### 1b. ffmpeg (optional)

Only the `/voice` command needs this, and everything else works without it.

- **Windows:** open PowerShell and run `winget install ffmpeg`, then close and reopen PowerShell.
- **Mac:** install Homebrew from https://brew.sh, then run `brew install ffmpeg`.
- **Linux:** `sudo apt install ffmpeg`

### 1c. Get the Trollenator files

Easiest way, with no extra programs: on the GitHub page click the green **Code** button, then **Download ZIP**. Unzip it somewhere easy to find, such as your Documents folder.

(If you know Git, `git clone` works too.)

---

## Step 2: Open a terminal in the Trollenator folder

A terminal is a window where you type commands.

- **Windows:** open the unzipped folder in File Explorer, click the address bar at the top, type `powershell` and press Enter.
- **Mac:** open the **Terminal** app (press Cmd+Space, type "Terminal"). Type `cd ` (with a space), drag the Trollenator folder into the window, and press Enter.
- **Linux:** open a terminal and `cd` into the folder.

Check Python works:

- Windows: `python --version`
- Mac/Linux: `python3 --version`

It should print 3.10 or higher. (Below, Windows users type `python` where Mac/Linux users type `python3`.)

---

## Step 3: Install Trollenator's requirements

Create a private "virtual environment" so the install stays tidy:

**Windows**
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**Mac / Linux**
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

You will see `(venv)` at the start of the line when it's active. Every time you open a new terminal to run the bot, you must activate it again (the `activate` / `source` line).

---

## Step 4: Turn on Discord Developer Mode

You need to copy ID numbers from Discord.

Discord → **User Settings** (gear icon) → **Advanced** → turn on **Developer Mode**.

Now you can right-click any user or server and choose **Copy User ID** / **Copy Server ID**.

- Copy **your own user ID** (right-click your name) and keep it somewhere.
- Copy **your private server's ID** (right-click the server icon) and keep it somewhere.

---

## Step 5: Create the two Discord apps

Trollenator uses **two** Discord applications. Go to https://discord.com/developers/applications and log in.

### App 1: the user app (the one people use)

1. Click **New Application**, give it a name (the first 6 letters become the command prefix, e.g. "Trollenator" gives `/trolle-say`), and create it.
2. Left menu → **Installation**:
   - Turn **User Install ON**
   - Turn **Guild Install OFF**
3. Left menu → **Bot** → click **Reset Token** → **copy the token**. Keep it somewhere safe for now.
4. Left menu → **Installation** → copy the **Install Link**. This is what people open to add the app to their account.

### App 2: the control bot (your private admin bot)

1. Click **New Application** again and name it something like "Trollenator Control".
2. Left menu → **Installation**:
   - Turn **Guild Install ON**
   - Turn **User Install OFF**
   - Under Guild Install, make sure the scopes include `applications.commands` and `bot`.
3. Left menu → **Bot** → **Reset Token** → **copy this second token**.
4. Open this app's **Install Link** in your browser and add it to **your private server only**.

> **Never share your tokens**, post them online, or upload them to GitHub. Anyone with a token controls that bot. 

---

## Step 6: Fill in the config file

1. Open the `Configs` folder.
2. Make a copy of `trollenator_config.example.json` and rename the copy to **`trollenator_config.json`**.
3. Open it in a plain text editor (Notepad on Windows, TextEdit on Mac in plain-text mode, or any code editor).
4. Replace the placeholder values. The file looks like this:

```json
{
  "enabled": true,
  "token": "PASTE-USER-APP-TOKEN-HERE",
  "tokens": [],
  "control_token": "PASTE-CONTROL-BOT-TOKEN-HERE",
  "control_guild_id": 123456789012345678,
  "admins": [
    "123456789012345678"
  ],
  "mods": [],
  "cooldown_seconds": 3,
  "tos_warnings": true,
  "tos_terms": [],
  "tos_terms_file": "",
  "log_webhook_url": ""
}
```

**Required settings**

| Setting | What to put |
|---|---|
| `token` | The token from **App 1** (user app), inside the quotes |
| `control_token` | The token from **App 2** (control bot), inside the quotes. It must be a different app from `token`. |
| `control_guild_id` | Your private server's ID (the number from Step 4) |
| `admins` | Your user ID. Add more IDs separated by commas, e.g. `["111...", "222..."]`. Admins can do everything, including the dev panel. |

**Optional settings** (leave them as they are if you're unsure)

| Setting | What it does |
|---|---|
| `enabled` | `false` turns the user app off. The control bot keeps running. |
| `tokens` | Extra user-app tokens (up to 25 bots total). Only one runs at a time, and admins switch between them in `/devpannel`. Usually left empty. |
| `mods` | User IDs that may ban, unban and look at bans, but can't use the dev panel. Empty `[]` is fine. |
| `cooldown_seconds` | Seconds a person must wait between posts. `0` turns it off. |
| `tos_warnings` | `true` shows a warning before a risky-looking post is sent. It never blocks anyone. |
| `tos_terms` / `tos_terms_file` | Your own list of words to flag (nothing is built in). `tos_terms_file` is a text file with one word per line. |
| `log_webhook_url` | A Discord webhook URL that receives an activity log. Leave it as `""` for no log. |

**Rules that trip up beginners**

- Tokens and the webhook URL go **inside quotes**. The server ID is a plain number with **no quotes**. User IDs in `admins` and `mods` can go either way.
- Every item in a list is followed by a comma **except the last one**, and the file must not contain `//` comments.
- Don't leave placeholders like `REPLACE-ME` or `SERVER-ID` in the file. If the config is not valid JSON, the program stops at start-up and tells you which file is wrong.

Keep the quotes, commas and brackets exactly as in the example file. A missing comma will stop the bot from starting, and the error message in the terminal will tell you which file is wrong.

---

## Step 7: Start it

In the terminal (with `(venv)` showing):

- Windows: `python main.py`
- Mac/Linux: `python3 main.py`

You should see messages ending in **"Trollenator is running."** Both bots should appear online. Leave this window open.

To stop it, click the terminal and press **Ctrl+C**.

---

## Step 8: Install the user app on your account

Open the user app's **Install Link** (from Step 5, App 1) in your browser and choose **Add to my apps** (user install). Then go into any server or DM, type `/` and the commands appear with your prefix, e.g. `/trolle-say`, `/trolle-embed`, `/trolle-voice`, `/trolle-poll`, `/trolle-permcheck`.

In your private server, the control bot gives admins and mods `/ban`, `/unban`, `/bans`, `/baninfo`, `/banedit`, and admins also get `/devpannel` (diagnostics, switch bots, add tokens). Run `/devpannel` and press **Self-test** to check that everything works.

The very first start can take a moment while the commands register with Discord.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `python` is not recognised (Windows) | Reinstall Python and tick **Add python.exe to PATH**, or try `py main.py` |
| "Trollenator needs Python 3.10 or newer" | Install a newer Python (Step 1a) |
| "trollenator_config.json not found" | You haven't copied/renamed the example file (Step 6) |
| "control_token is not set — the control bot is OFF" | Fill in `control_token` and `control_guild_id` |
| Control bot is online but has no commands | Add it to your private server using its Install Link (Step 5, App 2) |
| Login failed / token rejected | You pasted the wrong token, or reset it since. Reset and copy again |
| Slash commands don't appear | Restart Discord (Ctrl+R) and wait a minute; check you installed the user app on your account |
| `/trolle-voice` fails | ffmpeg isn't installed (Step 1b) |
| "Another Trollenator is already running" | Close the other terminal window running it |

More detail on errors is in `Data/trollenator.log`.

---

## For people publishing a fork on GitHub

Never commit your real config or database. Add a `.gitignore` containing:

```
Configs/trollenator_config.json
Data/
venv/
__pycache__/
```
# Reporting and whatever
This is a slop bot, so feel free to report issues but you'd probably be better at fixing it than me. I'll use my slop skills if I feel like it but the current build I have shared is basically complete so don't expect more.

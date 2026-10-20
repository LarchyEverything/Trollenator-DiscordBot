# Trollenator (standalone)

One program, two Discord applications:

| | **User app** (`trollenator.py`) | **Control bot** (`control.py`) |
|---|---|---|
| Install type | **User install** (on people's accounts) | **Server install**, ONE private server of yours |
| Does | `/say /embed /voice /poll /permcheck` (prefixed, e.g. `/trolle-say`) | `/ban /unban /bans /baninfo /banedit` and `/devpannel` (diagnostics, switch bot, add token) |
| Who can use it | everyone who isn't banned | only the IDs in `admins` / `mods`, only in `control_guild_id` |

Nothing else was changed in the user app. bot-Bot is no longer involved.

## Setup
1. `pip install -r requirements.txt` (Python 3.10+) and `sudo apt install ffmpeg` (only `/voice` needs it).
2. **User app**: Developer Portal → New Application → Installation: *User Install* ON, *Guild Install* OFF → Bot → Reset Token.
3. **Control bot**: a *different* application → Installation: *Guild Install* ON (scope `bot` + `applications.commands`), *User Install* OFF → Bot → Reset Token. No privileged intents. Add it to your private server with its Install Link.
4. `cp Configs/trollenator_config.example.json Configs/trollenator_config.json` and fill it in (`chmod 600` it).
5. `python3 main.py`

## Config (new keys)
| key | meaning |
|---|---|
| `control_token` | the control bot's token. Not set → control bot off (a warning is logged; existing bans still apply). |
| `control_guild_id` | the private server. **Required** with `control_token` — the bot refuses to run without it, answers nobody elsewhere, and leaves any other server it is added to. |
| `admins` | user IDs: everything — bans (incl. of mods), `/devpannel`, switching bots, adding tokens. |
| `mods` | user IDs: `/ban /unban /bans /baninfo /banedit`; can't touch other staff, can't use `/devpannel`. |

All other keys are as before (`token`, `tokens`, `cooldown_seconds`, `tos_*`, `log_webhook_url`, `enabled`). `enabled:false` now stops only the user app; the control bot keeps running.

## Moving over from bot-Bot
* Remove `Plugins/trollenator.py` from bot-Bot (and `Configs/trollenator_config.json` there, after copying it here).
* Existing user bans: stop Trollenator, then `python3 tools/import_bot_bans.py <bot's .db file>` (read-only on bot's DB; safe to run twice).
* Promoted bot mods are not copied — put their IDs under `mods`.
* `Data/trollenator_state.json` can be copied over so commands aren't re-synced.

## Run as a service (systemd)
```
[Unit]
Description=Trollenator
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=/home/pi/Trollenator
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=5
User=pi

[Install]
WantedBy=multi-user.target
```
There is no hot-reload any more (that was bot's `dev reload`): update the files, then `sudo systemctl restart trollenator`. The control bot is down for those few seconds too.

## Tests
`pip install -r requirements-dev.txt && python3 -m pytest tests` — offline; they drive the real command code with fake interactions. They do not talk to Discord.

# AI Info Radar launchd deployment

This runbook deploys the CLI as scheduled commands on a Mac mini. It is not a
long-running web service. launchd runs polling every 10 minutes and the morning
digest once each day.

## Runtime layout

Use repo files for code and templates only. Keep runtime data, config, logs,
reports, and secrets outside git.

Recommended local paths:

- Repo: `/Users/abi/Documents/project/personal/ai-info-radar`
- Runtime config: `/Users/abi/.config/ai-info-radar`
- Local manifest: `/Users/abi/.config/ai-info-radar/sources.local.json`
- Local rules: `/Users/abi/.config/ai-info-radar/rules.local.json`
- Secret env file: `/Users/abi/.config/ai-info-radar/ai-info-radar.env`
- SQLite DB: `/Users/abi/Library/Application Support/ai-info-radar/radar.sqlite`
- Logs: `/Users/abi/Library/Logs/ai-info-radar`
- Reports: `/Users/abi/Documents/ai-info-radar-reports`

Create the directories:

```sh
mkdir -p "$HOME/.config/ai-info-radar"
mkdir -p "$HOME/Library/Application Support/ai-info-radar"
mkdir -p "$HOME/Library/Logs/ai-info-radar"
mkdir -p "$HOME/Documents/ai-info-radar-reports"
mkdir -p "$HOME/Library/LaunchAgents"
```

## Install the CLI environment

Use Python 3.11 or newer. On this Mac, Homebrew Python is usually under
`/opt/homebrew/bin/python3`.

```sh
cd /Users/abi/Documents/project/personal/ai-info-radar
/opt/homebrew/bin/python3 --version
PYTHONPATH=src /opt/homebrew/bin/python3 -m ai_info_radar --help
```

There are no required third-party packages in the current slice. If later
dependencies are added, install them into a local virtual environment and point
`AI_INFO_RADAR_PYTHON` at that interpreter.

## Local config and secrets

Copy tracked defaults into local files before editing:

```sh
cp configs/sources.official.json "$HOME/.config/ai-info-radar/sources.local.json"
cp configs/rules.default.json "$HOME/.config/ai-info-radar/rules.local.json"
```

Edit `sources.local.json` to enable only sources that are ready to run on the
Mac mini. Keep broad placeholder sources disabled until their parser is
implemented and smoke-tested.

Create `/Users/abi/.config/ai-info-radar/ai-info-radar.env`:

```sh
AI_INFO_RADAR_ROOT=/Users/abi/Documents/project/personal/ai-info-radar
AI_INFO_RADAR_PYTHON=/opt/homebrew/bin/python3
AI_INFO_RADAR_MANIFEST=/Users/abi/.config/ai-info-radar/sources.local.json
AI_INFO_RADAR_RULES=/Users/abi/.config/ai-info-radar/rules.local.json
AI_INFO_RADAR_DB=/Users/abi/Library/Application Support/ai-info-radar/radar.sqlite
AI_INFO_RADAR_LOG_DIR=/Users/abi/Library/Logs/ai-info-radar
AI_INFO_RADAR_REPORT_DIR=/Users/abi/Documents/ai-info-radar-reports
AI_INFO_RADAR_TIMEOUT=20
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/replace-me
```

Lock down the env file:

```sh
chmod 600 "$HOME/.config/ai-info-radar/ai-info-radar.env"
```

Do not commit the env file, local manifest, local rules, SQLite DB, logs, or
reports. The repository `.gitignore` covers the normal local runtime paths and
secret-like file names.

## launchd setup

Copy the templates:

```sh
cp docs/launchd/com.abi.ai-info-radar.poll.plist.example \
  "$HOME/Library/LaunchAgents/com.abi.ai-info-radar.poll.plist"
cp docs/launchd/com.abi.ai-info-radar.digest.plist.example \
  "$HOME/Library/LaunchAgents/com.abi.ai-info-radar.digest.plist"
```

Review both copied plist files and replace paths if the Mac mini repo path or
user home differs.

The poll plist uses `StartInterval` set to `600`, which means launchd attempts
to run the poll command every 10 minutes. The digest plist uses
`StartCalendarInterval` with `Hour=8` and `Minute=0`, which means one morning
digest run each day at 08:00 local time.

Validate the plists:

```sh
plutil -lint "$HOME/Library/LaunchAgents/com.abi.ai-info-radar.poll.plist"
plutil -lint "$HOME/Library/LaunchAgents/com.abi.ai-info-radar.digest.plist"
```

Load the jobs:

```sh
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.abi.ai-info-radar.poll.plist"
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.abi.ai-info-radar.digest.plist"
```

Kickstart them manually:

```sh
launchctl kickstart -k "gui/$(id -u)/com.abi.ai-info-radar.poll"
launchctl kickstart -k "gui/$(id -u)/com.abi.ai-info-radar.digest"
```

Inspect status:

```sh
launchctl print "gui/$(id -u)/com.abi.ai-info-radar.poll"
launchctl print "gui/$(id -u)/com.abi.ai-info-radar.digest"
tail -n 100 "$HOME/Library/Logs/ai-info-radar/poll.out.log"
tail -n 100 "$HOME/Library/Logs/ai-info-radar/digest.out.log"
```

Unload when needed:

```sh
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.abi.ai-info-radar.poll.plist"
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.abi.ai-info-radar.digest.plist"
```

## Manual smoke test

Run this from the repo before loading launchd jobs. It uses fixture manifests,
so it does not need network access or a Feishu webhook.

```sh
mkdir -p var/smoke logs/smoke reports/smoke
PYTHONPATH=src python3 -m ai_info_radar poll \
  --manifest configs/sources.claude-code.fixture.json \
  --db var/smoke/radar.sqlite \
  --repo-root .
PYTHONPATH=src python3 -m ai_info_radar poll \
  --manifest configs/sources.claude-code.fixture.json \
  --db var/smoke/radar.sqlite \
  --repo-root .
PYTHONPATH=src python3 -m ai_info_radar rule-test \
  --db var/smoke/radar.sqlite \
  --limit 5
PYTHONPATH=src python3 -m ai_info_radar daily \
  --db var/smoke/radar.sqlite \
  --reports-dir reports/smoke
```

Expected result:

- First poll reports inserted items.
- Second poll reports existing items and does not duplicate them.
- `rule-test` reports would-alert or would-digest outcomes.
- `daily` writes a Markdown report and says the Feishu webhook is not configured
  when `FEISHU_WEBHOOK_URL` is absent.

To smoke-test source failure visibility, run a temporary manifest with a missing
fixture path and then run the daily command. The poll output should include
`failures=1`, and the generated digest should list the source failure.

After launchd is loaded, kickstart the poll job and confirm that
`poll.out.log` receives output. Then kickstart the digest job and confirm that a
report appears in `AI_INFO_RADAR_REPORT_DIR`.

## Operations notes

- Keep `sources.local.json` conservative. Enable a source only after one manual
  poll succeeds and parser output looks reasonable.
- Use `rule-test --rules "$AI_INFO_RADAR_RULES"` before changing alert rules on
  a live DB.
- Use `reclassify --rules "$AI_INFO_RADAR_RULES"` after changing rules. It does
  not resend previous alerts by default.
- Rotate or delete old logs and reports manually if disk usage grows.
- For Feishu webhook changes, edit only the env file and reload or kickstart
  the launchd jobs. Do not store webhook URLs in git.

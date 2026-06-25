# Windows Maintenance Tool

A small, dark-themed desktop app that bundles common Windows maintenance tasks
behind one tidy interface. Pick the tasks you want with checkboxes and run them
in one go, or fire any single task on its own. Built with Python and
[CustomTkinter](https://github.com/TomSchimansky/CustomTkinter).

> ⚠️ **This tool deletes files and changes system state.** Read what each task
> does before running it. Some tasks require administrator privileges.

## Features

| Task | What it does | Admin |
|------|--------------|:-----:|
| **Network Reset** | Flushes the DNS cache (`ipconfig /flushdns`) | |
| **Release and Renew IP** | Releases and renews the DHCP lease, shows the new IP | |
| **Clean Temp Folders** | Clears `%TEMP%` (and `C:\Windows\Temp` when admin) | partial |
| **Empty Recycle Bin** | Empties the Recycle Bin for all drives | |
| **DISM + SFC** | Component cleanup, restore health, and system file check | ✓ |
| **Optimize All Drives** | Defrags HDDs / TRIMs SSDs; pick which drives when you have several | ✓ |
| **Create Restore Point** | Creates a system restore point as a safety net | ✓ |
| **Clean Windows Update Cache** | Stops update services, clears the download cache, restarts them | ✓ |

Plus:

- **Run Selected** — run any combination of the checked tasks in sequence, with
  a progress bar and a summary report (including disk space freed).
- **Startup Manager** — view and enable/disable programs that run at startup.
  Changes are **reversible** (entries are moved aside, never deleted).
- **Live log** — colour-coded, written to `logs/vedlikehold_logg.txt`, with
  view/export buttons.
- **Light / dark theme** and your task selection are remembered between sessions
  (`settings.json`).
- **Pending-reboot detection** — warns before DISM/SFC if Windows has a repair
  pending that would make them fail.

## Running from source

Requires Python 3.8+ on Windows.

```sh
pip install customtkinter
python vedlikehold.py
```

For admin-only tasks, run the script (or the built executable) as administrator.
The app can also relaunch itself elevated when you trigger one of those tasks.

## Building an executable

The project is built with [PyInstaller](https://pyinstaller.org/). The
**onedir** build is recommended — it avoids the antivirus/extraction issues that
single-file builds can hit:

```sh
pip install pyinstaller
pyinstaller --onedir --windowed --name "VedlikeholdWInf" --collect-all customtkinter vedlikehold.py
```

The result is a folder under `dist/` containing `VedlikeholdWInf.exe` and its
dependencies. Zip that folder to distribute it.

> **Note on antivirus:** unsigned PyInstaller executables are sometimes flagged
> by Windows Defender or SmartScreen. This is expected for unsigned binaries —
> building from source yourself avoids it entirely.

## The "Unknown publisher" warning

When you run the downloaded `.exe`, Windows may show **"Windows protected your
PC"** (SmartScreen) or a **"Unknown publisher"** prompt. This is **expected and
not a sign that anything is wrong** — it appears for every program that isn't
signed with a paid code-signing certificate, which this free tool is not.

To run it: click **More info → Run anyway**.

If you'd rather not trust the prebuilt binary at all, you can
[run it from source](#running-from-source) or
[build it yourself](#building-an-executable) — the result is identical and shows
no warning when you build it on your own machine.

### Verifying the download

Each release ships with a `.sha256` checksum file. To confirm your download
wasn't tampered with, compare the hash in PowerShell:

```powershell
Get-FileHash .\VedlikeholdWInf-v0.9.11-win64.zip -Algorithm SHA256
```

The output should match the value in `VedlikeholdWInf-v0.9.11-win64.zip.sha256`
(and the checksum listed on the release page).

## Notes & limitations

- **Restore points** require System Protection to be enabled on the system
  drive, and Windows normally creates at most one restore point per 24 hours.
- **Drive optimization** uses `defrag /O`, which automatically does the right
  thing per drive type (TRIM for SSDs, defrag for HDDs).
- Logs contain machine-specific details (timestamps, IP addresses) and are
  git-ignored by default.

## License

[MIT](LICENSE)

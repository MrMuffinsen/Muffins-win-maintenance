import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
import subprocess
import ctypes
import os
import sys
import shutil
import string
import datetime
import json
import re
import threading
import winreg

VERSJON = "0.9.14"

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
SETTINGS_FIL = os.path.join(BASE_DIR, "settings.json")

# Fulle stier til systemkommandoer — hindrer binary planting via PATH
SYSTEM32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")
POWERSHELL = os.path.join(SYSTEM32, "WindowsPowerShell", "v1.0", "powershell.exe")

def sys_cmd(exe, *args):
    return [os.path.join(SYSTEM32, exe), *args]

# Startup-plasseringer (label, hive, path, krever_admin)
STARTUP_RUN_KEYS = [
    ("Registry: Current User", winreg.HKEY_CURRENT_USER,
     r"Software\Microsoft\Windows\CurrentVersion\Run", False),
    ("Registry: All Users", winreg.HKEY_LOCAL_MACHINE,
     r"Software\Microsoft\Windows\CurrentVersion\Run", True),
    ("Registry: All Users (32-bit)", winreg.HKEY_LOCAL_MACHINE,
     r"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Run", True),
]
STARTUP_FOLDERS = [
    ("Startup folder: Current User",
     os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup"), False),
    ("Startup folder: All Users",
     os.path.join(os.environ.get("ProgramData", ""), r"Microsoft\Windows\Start Menu\Programs\Startup"), True),
]
DISABLED_SUFFIX = "-MaintenanceDisabled"   # registernøkkel for deaktiverte oppføringer
DISABLED_FOLDER = "Disabled (Maintenance Tool)"

# ----------------------------
# Disk-hjelpere (brukes både i GUI-bygging og oppgaver)
# ----------------------------
def get_local_drives():
    DRIVE_FIXED = 3
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    drives  = []
    for letter in string.ascii_uppercase:
        if bitmask & 1:
            path = f"{letter}:\\"
            if ctypes.windll.kernel32.GetDriveTypeW(path) == DRIVE_FIXED:
                drives.append(f"{letter}:")
        bitmask >>= 1
    return drives

def get_disk_free():
    """Returnerer {stasjon: ledig_bytes} for alle lokale faste disker."""
    result = {}
    for drive in get_local_drives():
        try:
            result[drive] = shutil.disk_usage(f"{drive}\\").free
        except OSError:
            pass
    return result

def format_bytes(b):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(b) < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"

t = {
    "flush_dns":        "Network Reset",
    "release_renew":    "Release and Renew IP",
    "dism_sfc":         "DISM + SFC  (Admin)",
    "tøm_papirkurv":    "Empty Recycle Bin",
    "vis_logg":         "View Log",
    "eksporter_logg":   "Export Log",
    "ferdig":           "Done",
    "klar":             "Ready.",
    "feil":             "Error",
    "admin_advarsel":   "This task requires administrator privileges.",
    "papirkurv_tømt":   "Recycle Bin emptied.",
    "dns_flushed":      "DNS cache flushed.",
    "renewing_ip":      "Renewing IP...",
    "ip_popup":         "New IP address: {}",
    "log_missing":      "No log file found.",
    "tt_flush":         "Flush DNS cache",
    "tt_release_renew": "Release current IP and request new from DHCP",
    "tt_dism_sfc":      "Creates a restore point, then cleans components, restores system health, and verifies files",
    "tt_bin":           "Empty recycle bin",
    "tt_all":           "Run only the checked tasks",
    "tt_logg":          "View a log of all actions",
    "tt_export":        "Save the log file to a chosen location",
    "optimize_drive":   "Optimize All Drives  (Admin)",
    "tt_optimize":      "Defragment HDDs / TRIM SSDs on your local drives",
    "optimize_done":    "All drives optimized.",
    "tøm_temp":         "Clean Temp Folders",
    "tt_temp":          "Delete temporary files from %TEMP% (and C:\\Windows\\Temp when admin)",
    "tt_velg_disker":   "Choose which drives to optimize",
    "velg_disker":      "Select Drives to Optimize",
    "restore_point":    "Create Restore Point  (Admin)",
    "tt_restore":       "Create a system restore point you can roll back to",
    "restore_start":    "Creating system restore point...",
    "wu_cache":         "Clean Windows Update Cache  (Admin)",
    "tt_wu_cache":      "Stop update services, clear the download cache, then restart them",
    "startup_mgr":      "Startup Apps",
    "tt_startup":       "View and enable/disable programs that run at startup",
    "startup_title":    "Startup Manager",
    "kjør_valgte":      "▶   Run Selected",
}

logg_lock = threading.Lock()

# ----------------------------
# GUI
# ----------------------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

root = ctk.CTk()
root.title("Windows Maintenance Tool")
root.geometry("640x800")
root.resizable(False, False)

ramme = ctk.CTkFrame(root, fg_color="transparent")
ramme.pack(fill=tk.BOTH, expand=True, padx=20, pady=(12, 15))

# Tittelrad med tema-toggle
title_row = ctk.CTkFrame(ramme, fg_color="transparent")
title_row.pack(fill=tk.X, pady=(0, 2))

ctk.CTkLabel(
    title_row, text="Windows Maintenance Tool",
    font=ctk.CTkFont("Segoe UI", 15, weight="bold")
).pack(side=tk.LEFT)

theme_btn = ctk.CTkButton(
    title_row, text="☀  Light", width=90, height=26,
    corner_radius=8,
    fg_color=("#d6d6d6", "#2b2b2b"), hover_color=("#c4c4c4", "#3a3a3a"),
    text_color=("gray20", "gray90"),
    font=ctk.CTkFont("Segoe UI", 10)
)
theme_btn.pack(side=tk.RIGHT)

ctk.CTkLabel(
    ramme,
    text=f"v{VERSJON}  —  Some tasks require administrator privileges.",
    font=ctk.CTkFont("Segoe UI", 10), text_color="gray60"
).pack(anchor="w", pady=(0, 10))

# Progress
progress = ctk.CTkProgressBar(ramme, height=14, corner_radius=7)
progress.pack(fill=tk.X, pady=(0, 6))
progress.set(0)

status_var = tk.StringVar(value=t['klar'])
ctk.CTkLabel(
    ramme, textvariable=status_var,
    font=ctk.CTkFont("Segoe UI", 11), text_color=("gray25", "gray80")
).pack(pady=(0, 10))

# Oppgaverader
var_flush    = tk.BooleanVar(value=True)
var_renew    = tk.BooleanVar(value=True)
var_dism     = tk.BooleanVar(value=True)
var_optimize = tk.BooleanVar(value=True)
var_temp     = tk.BooleanVar(value=True)
var_bin      = tk.BooleanVar(value=True)
var_restore  = tk.BooleanVar(value=True)
var_wu       = tk.BooleanVar(value=True)

# Hvilke disker som skal optimaliseres. None = alle oppdagede disker.
valgte_disker = None

# Tooltip-klassen må ligge her så _task_row kan bruke den
class Tooltip:
    def __init__(self, widget, text):
        self.widget    = widget
        self.text      = text
        self.tipwindow = None
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tipwindow or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self.text, justify="left",
                 background="#2a2a2a", foreground="white",
                 relief="solid", borderwidth=1,
                 font=("Segoe UI", 9)).pack(ipadx=6, ipady=3)

    def hide_tip(self, event=None):
        if self.tipwindow:
            self.tipwindow.destroy()
        self.tipwindow = None

def _task_row(var, label_text, tooltip_text=""):
    f = ctk.CTkFrame(ramme, fg_color=("#e8e8e8", "#202020"), corner_radius=8)
    f.pack(fill=tk.X, pady=2)
    cb = ctk.CTkCheckBox(f, text="", variable=var,
                         checkbox_width=20, checkbox_height=20, width=28)
    cb.pack(side=tk.LEFT, padx=(8, 4), pady=6)
    lbl = ctk.CTkLabel(f, text=label_text, anchor="w",
                       font=ctk.CTkFont("Segoe UI", 11))
    lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
    if tooltip_text:
        Tooltip(lbl, tooltip_text)
    run_btn = ctk.CTkButton(f, text="▶", width=42, height=28, corner_radius=6,
                            font=ctk.CTkFont("Segoe UI", 11))
    run_btn.pack(side=tk.RIGHT, padx=(4, 8), pady=5)
    return f, cb, run_btn

row_f, cb_flush,    knapp_flush         = _task_row(var_flush,    t['flush_dns'],     t['tt_flush'])
row_r, cb_renew,    knapp_release_renew = _task_row(var_renew,    t['release_renew'], t['tt_release_renew'])
row_d, cb_dism,     knapp_dism          = _task_row(var_dism,     t['dism_sfc'],      t['tt_dism_sfc'])
row_o, cb_optimize, knapp_optimize      = _task_row(var_optimize, t['optimize_drive'], t['tt_optimize'])
row_rp, cb_restore, knapp_restore       = _task_row(var_restore,  t['restore_point'], t['tt_restore'])
row_wu, cb_wu,      knapp_wu            = _task_row(var_wu,       t['wu_cache'],      t['tt_wu_cache'])
row_t, cb_temp,     knapp_temp          = _task_row(var_temp,     t['tøm_temp'],      t['tt_temp'])
row_b, cb_bin,      knapp_bin           = _task_row(var_bin,      t['tøm_papirkurv'], t['tt_bin'])

# Tannhjul-knapp på optimize-raden — kun når det finnes flere disker å velge mellom
knapp_velg_disker = None
if len(get_local_drives()) > 1:
    knapp_velg_disker = ctk.CTkButton(
        row_o, text="⚙", width=34, height=28, corner_radius=6,
        fg_color=("#d0d0d0", "#333333"), hover_color=("#c0c0c0", "#404040"),
        text_color=("gray20", "gray85"), font=ctk.CTkFont("Segoe UI", 12)
    )
    # Pakkes side=RIGHT slik at den havner til venstre for ▶-knappen
    knapp_velg_disker.pack(side=tk.RIGHT, padx=(0, 2), pady=5)
    Tooltip(knapp_velg_disker, t['tt_velg_disker'])

knapp_kjør_valgte = ctk.CTkButton(
    ramme, text=t['kjør_valgte'], height=40, corner_radius=10,
    font=ctk.CTkFont("Segoe UI", 12, weight="bold")
)
knapp_kjør_valgte.pack(fill=tk.X, pady=(10, 4))

# Logg-knappar side om side
log_btn_row = ctk.CTkFrame(ramme, fg_color="transparent")
log_btn_row.pack(fill=tk.X, pady=(0, 8))

SMALL_BTN = dict(
    height=28, corner_radius=8,
    fg_color=("#e0e0e0", "#222222"), hover_color=("#d0d0d0", "#2e2e2e"),
    text_color=("gray30", "gray70"), font=ctk.CTkFont("Segoe UI", 10)
)
knapp_logg    = ctk.CTkButton(log_btn_row, text=t['vis_logg'],       **SMALL_BTN)
knapp_export  = ctk.CTkButton(log_btn_row, text=t['eksporter_logg'], **SMALL_BTN)
knapp_startup = ctk.CTkButton(log_btn_row, text=t['startup_mgr'],    **SMALL_BTN)
knapp_logg.pack(   side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
knapp_export.pack( side=tk.LEFT, fill=tk.X, expand=True, padx=3)
knapp_startup.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(3, 0))

# Live log
log_frame = ctk.CTkFrame(ramme, corner_radius=8, fg_color=("#f0f0f0", "#181818"))
log_frame.pack(fill=tk.BOTH, expand=True)

log_text = ctk.CTkTextbox(
    log_frame, wrap="word",
    font=ctk.CTkFont("Segoe UI", 9),
    fg_color=("#f0f0f0", "#181818"), text_color=("#333333", "#cccccc"),
    state="disabled"
)
log_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

# Fargetagger for loggen (på underliggende tk.Text)
_lt = getattr(log_text, "_textbox", log_text)
_lt.tag_config("ok",   foreground="#4caf50")
_lt.tag_config("warn", foreground="#f59e0b")
_lt.tag_config("err",  foreground="#ef4444")

clear_log_btn = ctk.CTkButton(
    ramme, text="Clear Log", height=26, corner_radius=8,
    fg_color=("#e8e8e8", "#1e1e1e"), hover_color=("#dadada", "#2a2a2a"),
    text_color=("gray45", "gray50"), font=ctk.CTkFont("Segoe UI", 9)
)
clear_log_btn.pack(fill=tk.X, pady=(4, 0))

alle_knapper = [
    knapp_flush, knapp_release_renew, knapp_dism, knapp_optimize,
    knapp_restore, knapp_wu, knapp_temp, knapp_bin,
    knapp_kjør_valgte, knapp_logg, knapp_export, knapp_startup, clear_log_btn,
    cb_flush, cb_renew, cb_dism, cb_optimize, cb_restore, cb_wu, cb_temp, cb_bin,
]
if knapp_velg_disker is not None:
    alle_knapper.append(knapp_velg_disker)

# ----------------------------
# Tooltips (resterende knapper)
# ----------------------------
Tooltip(knapp_kjør_valgte, t['tt_all'])
Tooltip(knapp_logg,        t['tt_logg'])
Tooltip(knapp_export,      t['tt_export'])

# ----------------------------
# GUI-hjelpere
# ----------------------------
def safe_after(delay, func, *args):
    """root.after som ikke krasjer hvis vinduet er lukket mens en jobb kjører."""
    try:
        root.after(delay, func, *args)
    except (RuntimeError, tk.TclError):
        pass

def _setup_dialog(dlg):
    """Felles oppsett for CTkToplevel-dialoger: modal, fremst, og mørk tittellinje.

    CTkToplevel setter tittellinjefargen for tidlig (før vinduet er mappet), så
    den fester seg ikke. Vi setter den på nytt etter en kort forsinkelse når
    vinduet faktisk er tegnet."""
    def _try(func, *args):
        """Ignorer TclError hvis dialogen lukkes før en forsinket callback fyrer."""
        try:
            func(*args)
        except tk.TclError:
            pass

    dlg.transient(root)
    dlg.lift()
    dlg.attributes("-topmost", True)
    if sys.platform.startswith("win"):
        def fiks_tittellinje():
            try:
                dlg._windows_set_titlebar_color(dlg._get_appearance_mode())
            except Exception:
                pass
        dlg.after(200, fiks_tittellinje)
    # grab settes etter at tittellinje-fiksens skjul/vis er ferdig, så den ikke mistes
    dlg.after(320, lambda: _try(dlg.grab_set))
    dlg.after(350, lambda: _try(dlg.attributes, "-topmost", False))
    dlg.focus_force()

def update_progress(value):
    progress.set(value / 100)

def _logg_farge(tekst):
    lav = tekst.lower()
    if any(o in lav for o in ("error", "failed", "could not", "exited with code")):
        return "err"
    if any(o in lav for o in ("warning", "skipped", "pending reboot", "cancelled", "already empty")):
        return "warn"
    if any(o in lav for o in ("completed", "emptied", "flushed", "optimized", "cleaned", "freed", "new ip address")):
        return "ok"
    return None

def append_gui_log(tekst):
    log_text.configure(state="normal")
    log_text.insert(tk.END, tekst + "\n", _logg_farge(tekst))
    log_text.configure(state="disabled")
    log_text.see(tk.END)

def clear_gui_log():
    log_text.configure(state="normal")
    log_text.delete("1.0", tk.END)
    log_text.configure(state="disabled")
    append_gui_log("--- Log cleared ---")

def set_buttons_state(state):
    for btn in alle_knapper:
        btn.configure(state=state)

def restore_buttons_state():
    set_buttons_state(tk.NORMAL)
    if not er_admin():
        for knapp in (knapp_dism, knapp_optimize, knapp_restore, knapp_wu,
                      cb_dism, cb_optimize, cb_restore, cb_wu):
            knapp.configure(state=tk.DISABLED)

def toggle_theme():
    new_mode = "light" if ctk.get_appearance_mode() == "Dark" else "dark"
    ctk.set_appearance_mode(new_mode)
    theme_btn.configure(text="🌙  Dark" if new_mode == "light" else "☀  Light")

def last_innstillinger():
    try:
        with open(SETTINGS_FIL, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}

def lagre_innstillinger():
    data = {
        "theme": ctk.get_appearance_mode().lower(),
        "tasks": {
            "flush":    var_flush.get(),
            "renew":    var_renew.get(),
            "dism":     var_dism.get(),
            "optimize": var_optimize.get(),
            "temp":     var_temp.get(),
            "bin":      var_bin.get(),
            "restore":  var_restore.get(),
            "wu":       var_wu.get(),
        },
        # None = alle disker; ellers liste over valgte stasjonsbokstaver
        "optimize_drives": None if valgte_disker is None else sorted(valgte_disker),
    }
    try:
        with open(SETTINGS_FIL, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass

def on_close():
    lagre_innstillinger()
    root.destroy()

def eksporter_logg():
    loggfil = os.path.join(LOG_DIR, "vedlikehold_logg.txt")
    if not os.path.exists(loggfil):
        messagebox.showinfo("Export Log", t['log_missing'])
        return
    dest = filedialog.asksaveasfilename(
        defaultextension=".txt",
        filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        initialfile=f"vedlikehold_{datetime.date.today()}.txt",
        title="Export Log"
    )
    if dest:
        try:
            shutil.copy2(loggfil, dest)
            messagebox.showinfo("Export Log", f"Log saved to:\n{dest}")
        except OSError as e:
            messagebox.showerror(t['feil'], f"Could not save log:\n{e}")

# ----------------------------
# Verktøy
# ----------------------------
def er_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except OSError:
        return False

def ventende_omstart():
    """True hvis Windows har en ventende omstart som blokkerer DISM/SFC."""
    nokler = (
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\PackagesPending",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired",
    )
    for nokkel in nokler:
        try:
            winreg.CloseKey(winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, nokkel))
            return True
        except OSError:
            continue
    return False

def advar_ventende_omstart():
    """Viser advarsel hvis omstart venter. Returnerer True hvis brukeren vil fortsette likevel."""
    if not ventende_omstart():
        return True
    logg("Warning: Windows has a pending reboot. DISM/SFC will likely fail.")
    return messagebox.askyesno(
        "Pending Reboot Detected",
        "Windows has a pending system repair or update that requires a restart.\n\n"
        "DISM and SFC will most likely fail until you reboot.\n\n"
        "Restart your PC first, then run these tasks again.\n\n"
        "Run anyway?",
        icon="warning"
    )

def hent_ip(text):
    match = re.search(r"IPv4[^\d]+([\d.]+)", text, re.IGNORECASE)
    return match.group(1) if match else "Unknown"

def logg(tekst):
    tidspunkt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs(LOG_DIR, exist_ok=True)
    with logg_lock:
        with open(os.path.join(LOG_DIR, "vedlikehold_logg.txt"), "a", encoding="utf-8") as f:
            f.write(f"{tidspunkt}: {tekst}\n")
    safe_after(0, append_gui_log, f"[{tidspunkt}] {tekst}")

def kjør_kommando(cmd, base_progress, step_size):
    """cmd er en liste (program + argumenter) — kjøres uten shell."""
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,   # ingen kommando skal kunne vente på input
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    for line in iter(process.stdout.readline, ''):
        # SFC skriver UTF-16LE når output pipes; fjern null-bytes så regex treffer
        line = line.replace('\x00', '').strip()
        if line:
            logg(line)
        match_dism   = re.search(r'(\d{1,3}\.\d+)%', line)
        match_sfc    = re.search(r'Verification\s+(\d+)%', line)
        match_defrag = re.search(r'^\s*(\d+)\s*%', line)
        if match_dism:
            prosent = float(match_dism.group(1))
            safe_after(0, update_progress, base_progress + (prosent / 100) * step_size)
        elif match_sfc:
            prosent = int(match_sfc.group(1))
            safe_after(0, update_progress, base_progress + (prosent / 100) * step_size)
        elif match_defrag:
            prosent = int(match_defrag.group(1))
            safe_after(0, update_progress, base_progress + (prosent / 100) * step_size)
    process.wait()
    if process.returncode != 0:
        logg(f"Command exited with code {process.returncode}: {' '.join(cmd)}")

# ----------------------------
# Relaunch helper
# ----------------------------
def relaunch_as_admin():
    if getattr(sys, 'frozen', False):
        params = None
    else:
        params = f'"{os.path.abspath(__file__)}"'
    ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
    if ret > 32:
        root.destroy()
    else:
        logg("Relaunch as admin was cancelled or failed.")

# ----------------------------
# Oppgaver
# ----------------------------
def flush_dns(silent=False):
    logg(f"--- {t['flush_dns']} ---")
    kjør_kommando(sys_cmd("ipconfig.exe", "/flushdns"), 0, 0)
    if not silent:
        safe_after(0, messagebox.showinfo, t['ferdig'], t['dns_flushed'])

def release_renew(silent=False):
    logg(f"--- {t['release_renew']} ---")
    try:
        kjør_kommando(sys_cmd("ipconfig.exe", "/release"), 0, 0)
        logg(t['renewing_ip'])
        output_renew = subprocess.check_output(
            sys_cmd("ipconfig.exe", "/renew"), text=True, errors="replace",
            timeout=60, stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        ip = hent_ip(output_renew)
        logg(f"New IP address: {ip}")
        if not silent:
            safe_after(0, messagebox.showinfo, "IP Address", t['ip_popup'].format(ip))
    except subprocess.TimeoutExpired:
        logg("Error: ipconfig /renew timed out after 60 seconds.")
    except subprocess.CalledProcessError as e:
        logg(f"Error during IP renew: {e}")

def tøm_papirkurv():
    logg(f"--- {t['tøm_papirkurv']} ---")
    res = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x00000001)
    if res == 0:
        logg(t['papirkurv_tømt'])
    elif res in (-2147418113, 0x8000FFFF):  # E_UNEXPECTED: allerede tom
        logg("Recycle Bin was already empty.")
    else:
        logg(f"Error emptying Recycle Bin (HRESULT {res & 0xFFFFFFFF:#010x})")

def _mappe_størrelse(sti):
    total = 0
    for dirpath, _, filenames in os.walk(sti, onerror=lambda e: None):
        for f in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
    return total

def _trygg_temp_mappe(sti):
    """Avviser diskrøtter og stier som ikke ser ut som temp-mapper —
    beskytter mot manipulert/feilkonfigurert %TEMP%."""
    if not sti:
        return False
    sti = os.path.abspath(sti)
    _, rest = os.path.splitdrive(sti)
    if rest.strip("\\/") == "":   # diskrot, f.eks. C:\
        return False
    return "temp" in os.path.basename(sti).lower()

def tøm_temp():
    logg(f"--- {t['tøm_temp']} ---")
    mapper = [os.environ.get("TEMP")]
    if er_admin():
        mapper.append(os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Temp"))
    frigjort = 0
    hoppet_over = 0
    for mappe in mapper:
        if not _trygg_temp_mappe(mappe):
            logg(f"Warning: refusing to clean suspicious temp path: {mappe!r}")
            continue
        if not os.path.isdir(mappe):
            continue
        logg(f"Cleaning {mappe} ...")
        for navn in os.listdir(mappe):
            sti = os.path.join(mappe, navn)
            try:
                if os.path.isfile(sti) or os.path.islink(sti):
                    størrelse = os.path.getsize(sti)
                    os.remove(sti)
                    frigjort += størrelse
                elif os.path.isdir(sti):
                    størrelse = _mappe_størrelse(sti)
                    shutil.rmtree(sti)
                    frigjort += størrelse
            except OSError:
                hoppet_over += 1  # fil i bruk eller låst — normalt for temp
    logg(f"Temp folders cleaned. Freed {format_bytes(frigjort)} ({hoppet_over} items in use, skipped).")

def lag_gjenopprettingspunkt():
    logg(f"--- {t['restore_point']} ---")
    safe_after(0, status_var.set, t['restore_start'])
    # Checkpoint-Computer krever at System Protection er på for systemstasjonen.
    # Windows begrenser normalt til ett punkt per 24 timer.
    kjør_kommando([
        POWERSHELL, "-NoProfile", "-NonInteractive", "-Command",
        "Checkpoint-Computer -Description 'Windows Maintenance Tool' "
        "-RestorePointType 'MODIFY_SETTINGS'"
    ], 0, 0)
    logg("Restore point requested (see lines above for any warnings).")

def tøm_wu_cache():
    logg(f"--- {t['wu_cache']} ---")
    download = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                            "SoftwareDistribution", "Download")
    for svc in ("wuauserv", "bits"):
        logg(f"Stopping {svc} ...")
        # /y svarer automatisk ja hvis avhengige tjenester også må stoppes
        kjør_kommando(sys_cmd("net.exe", "stop", svc, "/y"), 0, 0)

    frigjort = 0
    hoppet_over = 0
    if os.path.isdir(download):
        logg(f"Cleaning {download} ...")
        for navn in os.listdir(download):
            sti = os.path.join(download, navn)
            try:
                if os.path.isfile(sti) or os.path.islink(sti):
                    størrelse = os.path.getsize(sti)
                    os.remove(sti)
                    frigjort += størrelse
                elif os.path.isdir(sti):
                    størrelse = _mappe_størrelse(sti)
                    shutil.rmtree(sti)
                    frigjort += størrelse
            except OSError:
                hoppet_over += 1

    for svc in ("wuauserv", "bits"):
        logg(f"Starting {svc} ...")
        kjør_kommando(sys_cmd("net.exe", "start", svc), 0, 0)

    logg(f"Windows Update cache cleaned. Freed {format_bytes(frigjort)} "
         f"({hoppet_over} items in use, skipped).")

def _animate_status(label, stop_event):
    n = 0
    while not stop_event.wait(0.6):
        dots = '.' * (n % 4)
        safe_after(0, status_var.set, f"{label}{dots}")
        n += 1

def dism_startcomponentcleanup(base, step):
    logg("--- DISM StartComponentCleanup ---")
    kjør_kommando(sys_cmd("Dism.exe", "/online", "/cleanup-image", "/startcomponentcleanup"), base, step)

def dism_restorehealth(base, step):
    logg("--- DISM RestoreHealth ---")
    stop = threading.Event()
    threading.Thread(target=_animate_status, args=("DISM RestoreHealth", stop), daemon=True).start()
    kjør_kommando(sys_cmd("Dism.exe", "/online", "/cleanup-image", "/restorehealth"), base, step)
    stop.set()

def sfc_kjør(base, step):
    logg("--- SFC ---")
    stop = threading.Event()
    threading.Thread(target=_animate_status, args=("Running SFC", stop), daemon=True).start()
    kjør_kommando(sys_cmd("sfc.exe", "/scannow"), base, step)
    stop.set()

def optimize_alle_disker(base, step):
    drives = get_local_drives()
    if not drives:
        logg("No local fixed drives found.")
        return
    # Filtrer på brukerens valg (None = alle disker)
    if valgte_disker is not None:
        drives = [d for d in drives if d in valgte_disker]
    if not drives:
        logg("No drives selected for optimization.")
        return
    drive_step = step / len(drives)
    for i, drive in enumerate(drives):
        safe_after(0, status_var.set, f"Optimizing {drive}...")
        logg(f"--- Optimize Drive ({drive}) ---")
        kjør_kommando(sys_cmd("defrag.exe", drive, "/O", "/U", "/V"), base + i * drive_step, drive_step)
    logg(t['optimize_done'])

# ----------------------------
# Startup manager
# ----------------------------
def _reg_les_alle(hive, path):
    out = []
    try:
        key = winreg.OpenKey(hive, path, 0, winreg.KEY_READ)
    except OSError:
        return out
    try:
        i = 0
        while True:
            try:
                navn, data, _typ = winreg.EnumValue(key, i)
                out.append((navn, data))
                i += 1
            except OSError:
                break
    finally:
        winreg.CloseKey(key)
    return out

def _reg_flytt_verdi(hive, fra_path, til_path, navn):
    """Flytter en navngitt verdi mellom to registernøkler, bevarer datatype."""
    key = winreg.OpenKey(hive, fra_path, 0, winreg.KEY_READ)
    try:
        data, typ = winreg.QueryValueEx(key, navn)
    finally:
        winreg.CloseKey(key)
    dkey = winreg.CreateKey(hive, til_path)
    try:
        winreg.SetValueEx(dkey, navn, 0, typ, data)
    finally:
        winreg.CloseKey(dkey)
    key = winreg.OpenKey(hive, fra_path, 0, winreg.KEY_SET_VALUE)
    try:
        winreg.DeleteValue(key, navn)
    finally:
        winreg.CloseKey(key)

def hent_startup_entries():
    entries = []
    for label, hive, path, krever_admin in STARTUP_RUN_KEYS:
        for navn, data in _reg_les_alle(hive, path):
            entries.append({"navn": navn, "kommando": str(data), "kilde": label,
                            "type": "reg", "hive": hive, "path": path,
                            "krever_admin": krever_admin, "aktiv": True})
        for navn, data in _reg_les_alle(hive, path + DISABLED_SUFFIX):
            entries.append({"navn": navn, "kommando": str(data), "kilde": label,
                            "type": "reg", "hive": hive, "path": path,
                            "krever_admin": krever_admin, "aktiv": False})
    for label, folder, krever_admin in STARTUP_FOLDERS:
        if not folder:
            continue
        if os.path.isdir(folder):
            for navn in os.listdir(folder):
                full = os.path.join(folder, navn)
                if os.path.isfile(full) and navn.lower() != "desktop.ini":
                    entries.append({"navn": navn, "kommando": full, "kilde": label,
                                    "type": "folder", "folder": folder,
                                    "krever_admin": krever_admin, "aktiv": True})
        dis = os.path.join(folder, DISABLED_FOLDER)
        if os.path.isdir(dis):
            for navn in os.listdir(dis):
                full = os.path.join(dis, navn)
                if os.path.isfile(full) and navn.lower() != "desktop.ini":
                    entries.append({"navn": navn, "kommando": full, "kilde": label,
                                    "type": "folder", "folder": folder,
                                    "krever_admin": krever_admin, "aktiv": False})
    return entries

def toggle_startup(entry):
    """Slår en oppføring av (flytt til disabled) eller på (flytt tilbake)."""
    if entry["type"] == "reg":
        path = entry["path"]
        dis  = path + DISABLED_SUFFIX
        if entry["aktiv"]:
            _reg_flytt_verdi(entry["hive"], path, dis, entry["navn"])
        else:
            _reg_flytt_verdi(entry["hive"], dis, path, entry["navn"])
    else:
        folder = entry["folder"]
        dis    = os.path.join(folder, DISABLED_FOLDER)
        if entry["aktiv"]:
            os.makedirs(dis, exist_ok=True)
            shutil.move(os.path.join(folder, entry["navn"]), os.path.join(dis, entry["navn"]))
        else:
            shutil.move(os.path.join(dis, entry["navn"]), os.path.join(folder, entry["navn"]))

def startup_manager_dialog():
    dlg = ctk.CTkToplevel(root)
    dlg.title(t['startup_title'])
    # Sentrer over hovedvinduet, som de andre dialogene
    x = root.winfo_x() + (root.winfo_width()  - 580) // 2
    y = root.winfo_y() + (root.winfo_height() - 540) // 2
    dlg.geometry(f"580x540+{x}+{y}")
    _setup_dialog(dlg)

    ctk.CTkLabel(dlg, text="Programs that run at startup",
                 font=ctk.CTkFont("Segoe UI", 13, weight="bold")).pack(pady=(16, 2))
    if not er_admin():
        ctk.CTkLabel(dlg, text="Run as administrator to manage all-users entries.",
                     font=ctk.CTkFont("Segoe UI", 9), text_color="gray60").pack(pady=(0, 4))

    liste = ctk.CTkScrollableFrame(dlg, fg_color="transparent", label_fg_color="transparent")
    liste.pack(fill=tk.BOTH, expand=True, padx=16, pady=(6, 8))

    def refresh():
        for w in liste.winfo_children():
            w.destroy()
        entries = hent_startup_entries()
        if not entries:
            ctk.CTkLabel(liste, text="No startup entries found.",
                         text_color="gray60").pack(pady=20)
            return
        for entry in entries:
            rad = ctk.CTkFrame(liste, fg_color=("#e8e8e8", "#202020"), corner_radius=8)
            rad.pack(fill=tk.X, pady=3)

            tekst = ctk.CTkFrame(rad, fg_color="transparent")
            tekst.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=6)
            navn_farge = ("gray20", "white") if entry["aktiv"] else ("gray55", "gray55")
            ctk.CTkLabel(tekst, text=entry["navn"], anchor="w",
                         font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
                         text_color=navn_farge).pack(fill=tk.X)
            status = "Enabled" if entry["aktiv"] else "Disabled"
            ctk.CTkLabel(tekst, text=f"{entry['kilde']}  ·  {status}", anchor="w",
                         font=ctk.CTkFont("Segoe UI", 9), text_color="gray60").pack(fill=tk.X)
            kmd = entry["kommando"]
            if len(kmd) > 72:
                kmd = kmd[:69] + "..."
            ctk.CTkLabel(tekst, text=kmd, anchor="w",
                         font=ctk.CTkFont("Segoe UI", 9), text_color="gray50").pack(fill=tk.X)

            kan = er_admin() or not entry["krever_admin"]

            def lag_cmd(e=entry):
                def gjør():
                    try:
                        var_aktiv = e["aktiv"]
                        toggle_startup(e)
                        logg(f"Startup: {'disabled' if var_aktiv else 'enabled'} '{e['navn']}'")
                    except OSError as ex:
                        logg(f"Startup: could not change '{e['navn']}': {ex}")
                        messagebox.showerror(t['feil'], f"Could not change entry:\n{ex}")
                    refresh()
                return gjør

            b = ctk.CTkButton(rad, text=("Disable" if entry["aktiv"] else "Enable"),
                              width=80, height=28, corner_radius=6, command=lag_cmd())
            if entry["aktiv"]:
                b.configure(fg_color=("#d9a441", "#8a6d3b"), hover_color=("#cf9a35", "#9c7c43"))
            if not kan:
                b.configure(state=tk.DISABLED)
                Tooltip(b, "Requires administrator")
            b.pack(side=tk.RIGHT, padx=10, pady=8)

    refresh()

    ctk.CTkButton(dlg, text="Close", width=120, height=32, corner_radius=8,
                  command=dlg.destroy).pack(pady=(0, 16))
    dlg.bind("<Escape>", lambda e: dlg.destroy())

def velg_disker_dialog():
    drives = get_local_drives()
    if not drives:
        messagebox.showinfo(t['velg_disker'], "No local fixed drives found.")
        return

    valgt_naa = set(drives) if valgte_disker is None else set(valgte_disker)
    free = get_disk_free()

    dlg = ctk.CTkToplevel(root)
    dlg.title(t['velg_disker'])
    dlg.resizable(False, False)
    _setup_dialog(dlg)

    pad = dict(padx=20)
    ctk.CTkLabel(
        dlg, text="Select drives to optimize",
        font=ctk.CTkFont("Segoe UI", 13, weight="bold")
    ).pack(pady=(20, 10), **pad)

    vars_per_drive = {}
    for drive in drives:
        v = tk.BooleanVar(value=(drive in valgt_naa))
        vars_per_drive[drive] = v
        fri = f"  ({format_bytes(free[drive])} free)" if drive in free else ""
        ctk.CTkCheckBox(
            dlg, text=f"{drive}{fri}", variable=v,
            font=ctk.CTkFont("Segoe UI", 11)
        ).pack(anchor="w", pady=3, **pad)

    def lagre_valg():
        valgt = {d for d, v in vars_per_drive.items() if v.get()}
        if not valgt:
            messagebox.showinfo(t['velg_disker'], "Select at least one drive.")
            return
        global valgte_disker
        # Alle valgt => None (følg automatisk med nye disker som kobles til)
        valgte_disker = None if valgt == set(drives) else valgt
        dlg.destroy()

    knapp_rad = ctk.CTkFrame(dlg, fg_color="transparent")
    knapp_rad.pack(pady=(14, 20), **pad)
    ctk.CTkButton(knapp_rad, text="OK", width=90, height=32, corner_radius=8,
                  command=lagre_valg).pack(side=tk.LEFT, padx=4)
    ctk.CTkButton(knapp_rad, text="Cancel", width=90, height=32, corner_radius=8,
                  fg_color=("#d0d0d0", "#333333"), hover_color=("#c0c0c0", "#404040"),
                  text_color=("gray20", "gray85"),
                  command=dlg.destroy).pack(side=tk.LEFT, padx=4)
    dlg.bind("<Escape>", lambda e: dlg.destroy())

    dlg.update_idletasks()
    w = max(dlg.winfo_reqwidth(), 300)
    h = dlg.winfo_reqheight()
    x = root.winfo_x() + (root.winfo_width()  - w) // 2
    y = root.winfo_y() + (root.winfo_height() - h) // 2
    dlg.geometry(f"{w}x{h}+{x}+{y}")

def optimize_drive():
    if not er_admin():
        if messagebox.askyesno(
            "Administrator Required",
            "Drive optimization requires administrator privileges.\nRelaunch as administrator?"
        ):
            relaunch_as_admin()
        return
    set_buttons_state(tk.DISABLED)
    update_progress(0)
    def job():
        try:
            optimize_alle_disker(0, 100)
        finally:
            safe_after(0, update_progress, 100)
            safe_after(0, status_var.set, t['klar'])
            safe_after(0, restore_buttons_state)
    threading.Thread(target=job, daemon=True).start()

def vis_logg():
    loggfil = os.path.join(LOG_DIR, "vedlikehold_logg.txt")
    if os.path.exists(loggfil):
        try:
            os.startfile(loggfil)
        except Exception as e:
            messagebox.showerror(t['feil'], f"Could not open log file:\n{e}")
    else:
        messagebox.showinfo("Log", t['log_missing'])

# ----------------------------
# Sammendragsrapport
# ----------------------------
def vis_sammendrag(completed, disk_before, disk_after):
    ok_count  = sum(1 for _, ok in completed if ok)
    err_count = len(completed) - ok_count

    dlg = ctk.CTkToplevel(root)
    dlg.title("Run Summary")
    dlg.resizable(False, False)
    _setup_dialog(dlg)

    pad = dict(padx=20)

    # Fast topp
    ctk.CTkLabel(
        dlg, text="Run Complete",
        font=ctk.CTkFont("Segoe UI", 14, weight="bold")
    ).pack(pady=(20, 4), **pad)

    summary_color = "#4caf50" if err_count == 0 else "#f59e0b"
    summary_text  = f"{ok_count} of {len(completed)} tasks completed successfully"
    ctk.CTkLabel(
        dlg, text=summary_text,
        font=ctk.CTkFont("Segoe UI", 10), text_color=summary_color
    ).pack(pady=(0, 10), **pad)

    # Fast bunnknapp — pakkes FØR midtdelen slik at pack gir den plass-prioritet
    ctk.CTkButton(
        dlg, text="OK", width=120, height=32, corner_radius=8,
        command=dlg.destroy
    ).pack(side=tk.BOTTOM, pady=(12, 20))
    dlg.bind("<Return>", lambda e: dlg.destroy())
    dlg.bind("<Escape>", lambda e: dlg.destroy())

    # Scrollbar midtdel: oppgaveliste + diskendringer
    innhold = ctk.CTkScrollableFrame(dlg, width=320, height=260, fg_color="transparent")
    innhold.pack(fill=tk.BOTH, expand=True, **pad)

    for name, ok in completed:
        row = ctk.CTkFrame(innhold, fg_color="transparent")
        row.pack(fill=tk.X, pady=1)
        ctk.CTkLabel(
            row, text="✓" if ok else "✗",
            text_color="#4caf50" if ok else "#ef4444",
            font=ctk.CTkFont("Segoe UI", 12), width=22
        ).pack(side=tk.LEFT)
        ctk.CTkLabel(
            row, text=name, anchor="w",
            font=ctk.CTkFont("Segoe UI", 11)
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

    disk_changes = [
        (drive, disk_after.get(drive, before) - before)
        for drive, before in disk_before.items()
        if abs(disk_after.get(drive, before) - before) > 512 * 1024  # > 512 KB
    ]
    if disk_changes:
        ctk.CTkFrame(innhold, height=1, fg_color="gray30").pack(fill=tk.X, pady=(10, 0))
        ctk.CTkLabel(
            innhold, text="Disk space freed:",
            font=ctk.CTkFont("Segoe UI", 11, weight="bold"), anchor="w"
        ).pack(fill=tk.X, pady=(8, 2))
        for drive, delta in disk_changes:
            sign  = "+" if delta >= 0 else ""
            color = "#4caf50" if delta >= 0 else "#f59e0b"
            ctk.CTkLabel(
                innhold,
                text=f"  {drive}    {sign}{format_bytes(delta)}",
                anchor="w", font=ctk.CTkFont("Segoe UI", 11),
                text_color=color
            ).pack(fill=tk.X)

    dlg.update_idletasks()
    w = max(dlg.winfo_reqwidth(), 380)
    h = dlg.winfo_reqheight()
    x = root.winfo_x() + (root.winfo_width()  - w) // 2
    y = root.winfo_y() + (root.winfo_height() - h) // 2
    dlg.geometry(f"{w}x{h}+{x}+{y}")

# ----------------------------
# Task runners
# ----------------------------
def run_standalone(func, label, **kwargs):
    set_buttons_state(tk.DISABLED)
    status_var.set(f"{label}...")
    update_progress(0)
    def job():
        try:
            func(**kwargs)
        finally:
            safe_after(0, update_progress, 100)
            safe_after(0, status_var.set, t['klar'])
            safe_after(0, restore_buttons_state)
    threading.Thread(target=job, daemon=True).start()

def run_selected():
    # (navn, funksjon, has_progress, kwargs)
    tasks = []
    if var_flush.get():
        tasks.append(("Network Reset",    flush_dns,    False, {"silent": True}))
    if var_renew.get():
        tasks.append(("Release & Renew",  release_renew, False, {"silent": True}))
    if var_temp.get():
        tasks.append(("Clean Temp Folders", tøm_temp, False, {}))
    if var_bin.get():
        tasks.append(("Empty Recycle Bin", tøm_papirkurv, False, {}))
    if var_wu.get() and er_admin():
        tasks.append(("Clean Windows Update Cache", tøm_wu_cache, False, {}))
    if var_dism.get() and er_admin():
        if advar_ventende_omstart():
            tasks += [
                ("DISM Cleanup",      dism_startcomponentcleanup, True, {}),
                ("DISM RestoreHealth", dism_restorehealth,         True, {}),
                ("SFC Scan",           sfc_kjør,                   True, {}),
            ]
        else:
            logg("DISM + SFC skipped due to pending reboot.")
    if var_optimize.get() and er_admin():
        tasks.append(("Optimize Drives", optimize_alle_disker, True, {}))

    # Gjenopprettingspunkt skal alltid kjøres FØRST — som sikkerhetsnett
    if var_restore.get() and er_admin():
        tasks.insert(0, ("Create Restore Point", lag_gjenopprettingspunkt, False, {}))

    if not tasks:
        messagebox.showinfo("No tasks", "Select at least one task.")
        return

    disk_before = get_disk_free()
    set_buttons_state(tk.DISABLED)
    status_var.set("Running selected tasks...")
    update_progress(0)

    def job():
        completed = []
        try:
            step_size = 100 / len(tasks)
            for i, (name, func, has_progress, kwargs) in enumerate(tasks):
                base = i * step_size
                try:
                    if has_progress:
                        func(base, step_size)
                    else:
                        safe_after(0, update_progress, base)
                        func(**kwargs)
                        safe_after(0, update_progress, base + step_size)
                    completed.append((name, True))
                except Exception as e:
                    logg(f"Error in {name}: {e}")
                    completed.append((name, False))
        finally:
            disk_after = get_disk_free()
            safe_after(0, update_progress, 100)
            safe_after(0, status_var.set, t['klar'])
            safe_after(0, restore_buttons_state)
            safe_after(200, vis_sammendrag, completed, disk_before, disk_after)

    threading.Thread(target=job, daemon=True).start()

def kjør_dism_sfc():
    if not er_admin():
        if messagebox.askyesno(
            "Administrator Required",
            "DISM + SFC requires administrator privileges.\nRelaunch as administrator?"
        ):
            relaunch_as_admin()
        return
    if not advar_ventende_omstart():
        return
    set_buttons_state(tk.DISABLED)
    status_var.set("Running DISM + SFC...")
    update_progress(0)
    def job():
        try:
            # Sikkerhetsnett før systemfiler røres. Windows begrenser uansett
            # til ett punkt per 24t, så et ferskt punkt gir bare en logglinje.
            lag_gjenopprettingspunkt()
            safe_after(0, update_progress, 10)
            safe_after(0, status_var.set, "Running DISM + SFC...")
            dism_startcomponentcleanup(10, 30)
            dism_restorehealth(40, 30)
            sfc_kjør(70, 30)
        finally:
            safe_after(0, update_progress, 100)
            safe_after(0, status_var.set, t['klar'])
            safe_after(0, restore_buttons_state)
    threading.Thread(target=job, daemon=True).start()

# ----------------------------
# Knappekoblinger
# ----------------------------
knapp_flush.configure(        command=lambda: run_standalone(flush_dns,     t['flush_dns']))
knapp_release_renew.configure(command=lambda: run_standalone(release_renew, t['release_renew']))
knapp_bin.configure(          command=lambda: run_standalone(tøm_papirkurv, t['tøm_papirkurv']))
knapp_temp.configure(         command=lambda: run_standalone(tøm_temp,      t['tøm_temp']))
knapp_restore.configure(      command=lambda: run_standalone(lag_gjenopprettingspunkt, t['restore_point']))
knapp_wu.configure(           command=lambda: run_standalone(tøm_wu_cache, t['wu_cache']))
if knapp_velg_disker is not None:
    knapp_velg_disker.configure(command=velg_disker_dialog)
knapp_kjør_valgte.configure(  command=run_selected)
knapp_logg.configure(         command=vis_logg)
knapp_export.configure(       command=eksporter_logg)
knapp_startup.configure(      command=startup_manager_dialog)
Tooltip(knapp_startup, t['tt_startup'])
knapp_dism.configure(         command=kjør_dism_sfc)
knapp_optimize.configure(     command=optimize_drive)
clear_log_btn.configure(      command=clear_gui_log)
theme_btn.configure(          command=toggle_theme)

# Last lagrede innstillinger (tema + checkbox-valg)
_s = last_innstillinger()
if _s.get("theme") == "light":
    ctk.set_appearance_mode("light")
    theme_btn.configure(text="🌙  Dark")
_tasks = _s.get("tasks", {})
var_flush.set(   _tasks.get("flush",    True))
var_renew.set(   _tasks.get("renew",    True))
var_dism.set(    _tasks.get("dism",     True))
var_optimize.set(_tasks.get("optimize", True))
var_temp.set(    _tasks.get("temp",     True))
var_bin.set(     _tasks.get("bin",      True))
var_restore.set( _tasks.get("restore",  True))
var_wu.set(      _tasks.get("wu",       True))

# Lagret diskvalg for optimize (kun disker som fortsatt finnes)
_lagret_disker = _s.get("optimize_drives")
if isinstance(_lagret_disker, list):
    _gyldige = {d for d in _lagret_disker if d in get_local_drives()}
    valgte_disker = _gyldige or None

# Admin-begrensninger overstyrer lagrede valg
if not er_admin():
    for knapp in (knapp_dism, knapp_optimize, knapp_restore, knapp_wu,
                  cb_dism, cb_optimize, cb_restore, cb_wu):
        knapp.configure(state=tk.DISABLED)
    var_dism.set(False)
    var_optimize.set(False)
    var_restore.set(False)
    var_wu.set(False)

root.protocol("WM_DELETE_WINDOW", on_close)
root.mainloop()

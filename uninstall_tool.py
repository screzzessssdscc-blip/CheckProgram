import os, sys, subprocess, ctypes, threading, time, tempfile, json, re
import urllib.request
import tkinter as tk
from tkinter import messagebox

try:
    import customtkinter as ctk
    CTK = True
except ImportError:
    CTK = False

try:
    import winreg
except ImportError:
    sys.exit(1)

VERSION = "1.0.5"
GITHUB_REPO = "screzzessssdscc-blip/CheckProgram"


def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except: return False


def parse_version(v):
    v = v.lstrip("vV").strip()
    parts = re.split(r'[^0-9]', v)
    nums = [int(p) for p in parts if p.isdigit()]
    while len(nums) < 3: nums.append(0)
    return tuple(nums[:3])


def format_size(kb):
    if kb <= 0: return ""
    if kb < 1024: return f"{int(kb)} КБ"
    mb = kb / 1024
    if mb < 1024: return f"{mb:.1f} МБ"
    return f"{mb/1024:.1f} ГБ"


def check_update():
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(url, headers={"User-Agent": f"UninstallTool/{VERSION}"})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode("utf-8"))
        tag = data.get("tag_name", "")
        if not tag: return None
        if parse_version(tag) <= parse_version(VERSION): return None
        exe_url = None
        for a in data.get("assets", []):
            if a.get("name", "").endswith(".exe"):
                exe_url = a.get("browser_download_url")
                break
        return {"version": tag, "url": exe_url, "changelog": data.get("body", "")}
    except:
        return None


def do_download(url, progress_fn=None):
    tmp = os.path.join(tempfile.gettempdir(), "UninstallTool_new.exe")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": f"UninstallTool/{VERSION}"})
        resp = urllib.request.urlopen(req, timeout=300)
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        with open(tmp, "wb") as f:
            while True:
                chunk = resp.read(256 * 1024)
                if not chunk: break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_fn and total:
                    progress_fn(int(downloaded * 100 / total))
        return tmp
    except:
        return None


def create_update_bat(new_path):
    cur = os.path.abspath(sys.executable)
    d = os.path.dirname(cur)
    n = os.path.basename(cur)
    old = n.replace(".exe", "_old.exe")
    bp = os.path.join(tempfile.gettempdir(), "upd.bat")
    bat = f"""@echo off
powershell -NoProfile -Command "Start-Sleep -Seconds 5"
taskkill /F /IM "{n}" >nul 2>&1
powershell -NoProfile -Command "Start-Sleep -Seconds 2"
if exist "{os.path.join(d, old)}" del /f /q "{os.path.join(d, old)}" >nul 2>&1
if exist "{cur}" ren "{cur}" "{old}" >nul 2>&1
powershell -NoProfile -Command "Start-Sleep -Seconds 1"
copy /Y "{new_path}" "{cur}" >nul 2>&1
start "" "{cur}"
if exist "{os.path.join(d, old)}" del /f /q "{os.path.join(d, old)}" >nul 2>&1
del /f /q "{new_path}" >nul 2>&1
del /f /q "%~f0" >nul 2>&1
"""
    with open(bp, "w", encoding="ascii") as f:
        f.write(bat)
    return bp


def get_programs():
    progs, seen = [], set()
    paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, p in paths:
        try: root = winreg.OpenKey(hive, p, 0, winreg.KEY_READ)
        except: continue
        i = 0
        while True:
            try: sk = winreg.EnumKey(root, i)
            except OSError: break
            i += 1
            try: sub = winreg.OpenKey(root, sk, 0, winreg.KEY_READ)
            except: continue
            dn = us = sz = None
            try: dn, _ = winreg.QueryValueEx(sub, "DisplayName")
            except: pass
            try: us, _ = winreg.QueryValueEx(sub, "UninstallString")
            except: pass
            try: sz, _ = winreg.QueryValueEx(sub, "EstimatedSize")
            except: pass
            winreg.CloseKey(sub)
            if dn and us and dn not in seen:
                seen.add(dn)
                progs.append({"name": dn, "cmd": us, "size": sz or 0})
        winreg.CloseKey(root)
    progs.sort(key=lambda x: x["name"].lower())
    return progs


def kill_by_name(name):
    kws = ["360", "zhuang", "uninst", "helper", "safe", "guard", "shield", "tray", "protect", "av", "total", "security"]
    nps = name.lower().split()
    try:
        r = subprocess.run("tasklist /FO CSV /NH", shell=True, capture_output=True, text=True, timeout=10)
        for line in r.stdout.splitlines():
            parts = line.strip().strip('"').split('","')
            if len(parts) >= 2:
                pn, pid = parts[0].lower(), parts[1]
                if any(k in pn for k in kws) or any(np in pn for np in nps if len(np) > 3):
                    try: subprocess.run(f"taskkill /F /PID {pid} /T", shell=True, capture_output=True, timeout=10)
                    except: pass
    except: pass


def send_enter():
    try:
        ctypes.windll.user32.keybd_event(0x0D, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0x0D, 0, 2, 0)
    except: pass


def try_uninstall(cmd_str, prog_name):
    exe = cmd_str.strip()
    if not exe: return False
    kill_by_name(prog_name)
    time.sleep(1)
    low = exe.lower()
    is_msi = "msiexec" in low or ".msi" in low
    attempts = [exe]
    if is_msi:
        if "/qn" not in low:
            attempts += [exe + " /qn /norestart", exe + " /passive /norestart"]
    else:
        if not any(s in low for s in ["/s", "/silent", "/quiet", "/passive", "/q"]):
            attempts += [exe + " /S", exe + " /silent /quiet", exe + " /verysilent /supressmsgboxes /norestart"]
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0
    for a in attempts:
        try:
            r = subprocess.run(a, shell=True, capture_output=True, timeout=120, startupinfo=si)
            if r.returncode == 0: return True
        except subprocess.TimeoutExpired: return True
        except: pass
    for a in attempts[:2]:
        try:
            proc = subprocess.Popen(a, shell=True, startupinfo=si)
            time.sleep(3)
            if proc.poll() is None:
                send_enter(); time.sleep(3)
                send_enter(); time.sleep(3)
            if proc.poll() is None:
                proc.terminate()
                try: proc.wait(timeout=10)
                except: proc.kill()
            if proc.returncode == 0: return True
        except: pass
    return False


def bg_uninstall(cmd, name, cb):
    cb(try_uninstall(cmd, name))


class Spinner:
    def __init__(self, label):
        self.lbl = label
        self.on = False
        self._id = None
        self._fi = 0
        self._frames = ["\u2502", "\u2570\u256f", "\u2500", "\u256e\u2569"]
        self.base = ""

    def start(self, text=""):
        self.base = text; self.on = True; self._fi = 0; self._tick()

    def stop(self):
        self.on = False
        if self._id:
            try: self.lbl.configure(text="")
            except: pass
        self._id = None

    def _tick(self):
        if not self.on: return
        sp = self._frames[self._fi % 4]; self._fi += 1
        dots = "." * (self._fi % 4)
        try: self.lbl.configure(text=f"{sp} {self.base}{dots}")
        except: return
        self._id = self.lbl.after(300, self._tick)


class App:
    def __init__(self):
        self.all = []
        self.filt = []
        self.search_id = None
        self.busy = False
        self.update_info = None

        if CTK:
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("dark-blue")
            self.r = ctk.CTk()
        else:
            self.r = tk.Tk()
        self.u = CTK

        self.r.title("UninstallTool")
        self.r.geometry("960x720")
        self.r.minsize(680, 500)
        self.r.configure(bg="#000000")

        ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trash_can.ico")
        if os.path.exists(ico):
            try: self.r.iconbitmap(default=ico)
            except: pass

        self._ui()
        self._load()
        self.r.after(2000, self._auto_check)

    def _ui(self):
        self.r.grid_columnconfigure(0, weight=1)
        self.r.grid_rowconfigure(2, weight=1)
        self._search()
        self._update_bar()
        self._list()
        self._bar()

    def _search(self):
        bg = "#000000"
        w = ctk.CTkFrame(self.r, fg_color=bg) if self.u else tk.Frame(self.r, bg=bg)
        w.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 2))
        if self.u:
            self.search_e = ctk.CTkEntry(w, placeholder_text="\u041f\u043e\u0438\u0441\u043a...", width=350, font=ctk.CTkFont(size=14), corner_radius=8, height=36, border_width=1, border_color="#333333", fg_color="#111111")
            self.search_e.pack(side="left", padx=5, pady=5)
            self.cnt_lbl = ctk.CTkLabel(w, text="", font=ctk.CTkFont(size=11), text_color="#555555")
        else:
            self.search_e = tk.Entry(w, font=("Segoe UI", 13), width=35, bg="#111111", fg="#ffffff", insertbackground="white", highlightthickness=1, highlightcolor="#333333", relief="flat")
            self.search_e.pack(side="left", padx=5, pady=5)
            self.cnt_lbl = tk.Label(w, text="", font=("Segoe UI", 10), bg=bg, fg="#555555")
        self.cnt_lbl.pack(side="right", padx=10, pady=5)
        self.search_e.bind("<KeyRelease>", self._on_type)

    def _update_bar(self):
        self.upd_frame = ctk.CTkFrame(self.r, fg_color="#0d1a0d", corner_radius=0, height=0) if self.u else tk.Frame(self.r, bg="#0d1a0d", height=0)
        self.upd_frame.grid(row=1, column=0, sticky="ew")
        self.upd_frame.grid_remove()
        self.upd_visible = False
        self.upd_progress_var = None

    def _show_update_banner(self, info):
        ver = info["version"]
        if self.u:
            self.upd_frame.configure(height=50)
            self.upd_frame.grid()
            self.upd_visible = True
            for w in self.upd_frame.winfo_children(): w.destroy()
            f = ctk.CTkFrame(self.upd_frame, fg_color="transparent")
            f.pack(fill="both", expand=True, padx=12, pady=5)
            ctk.CTkLabel(f, text=f"\u0414\u043e\u0441\u0442\u0443\u043f\u043d\u043e \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435 \u2014 {ver}", font=ctk.CTkFont(size=12, weight="bold"), text_color="#4caf50").pack(side="left", padx=8)
            ctk.CTkButton(f, text="\u0423\u0441\u0442\u0430\u043d\u043e\u0432\u0438\u0442\u044c", command=lambda: self._start_download(info), fg_color="#4caf50", hover_color="#388e3c", text_color="#ffffff", width=120, height=28, corner_radius=5, font=ctk.CTkFont(size=11, weight="bold")).pack(side="right", padx=4)
            ctk.CTkButton(f, text="\u041f\u043e\u0437\u0436\u0435", command=self._hide_update_banner, fg_color="#333333", hover_color="#444444", width=80, height=28, corner_radius=5, font=ctk.CTkFont(size=11)).pack(side="right", padx=4)
        else:
            self.upd_frame.configure(height=40)
            self.upd_frame.grid()
            self.upd_visible = True
            for w in self.upd_frame.winfo_children(): w.destroy()
            f = tk.Frame(self.upd_frame, bg="#0d1a0d")
            f.pack(fill="both", expand=True, padx=12, pady=4)
            tk.Label(f, text=f"\u0414\u043e\u0441\u0442\u0443\u043f\u043d\u043e \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435 \u2014 {ver}", font=("Segoe UI", 11, "bold"), bg="#0d1a0d", fg="#4caf50").pack(side="left", padx=8)
            tk.Button(f, text="\u0423\u0441\u0442\u0430\u043d\u043e\u0432\u0438\u0442\u044c", command=lambda: self._start_download(info), bg="#4caf50", fg="white", font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2", width=14).pack(side="right", padx=4)
            tk.Button(f, text="\u041f\u043e\u0437\u0436\u0435", command=self._hide_update_banner, bg="#333333", fg="white", font=("Segoe UI", 10), relief="flat", cursor="hand2", width=8).pack(side="right", padx=4)

    def _show_download_progress(self, info):
        if self.u:
            self.upd_frame.configure(height=70)
            for w in self.upd_frame.winfo_children(): w.destroy()
            f = ctk.CTkFrame(self.upd_frame, fg_color="transparent")
            f.pack(fill="both", expand=True, padx=12, pady=5)
            ctk.CTkLabel(f, text=f"\u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430 {info['version']}...", font=ctk.CTkFont(size=12), text_color="#aaaaaa").pack(anchor="w", padx=4)
            self.upd_progress_var = ctk.DoubleVar(value=0)
            bar = ctk.CTkProgressBar(f, variable=self.upd_progress_var, maximum=100, height=10, fg_color="#222222", progress_color="#4caf50", corner_radius=3)
            bar.pack(fill="x", padx=4, pady=(4, 0))
            self.upd_pct_lbl = ctk.CTkLabel(f, text="0%", font=ctk.CTkFont(size=10), text_color="#666666")
            self.upd_pct_lbl.pack(anchor="e", padx=4)
        else:
            self.upd_frame.configure(height=60)
            for w in self.upd_frame.winfo_children(): w.destroy()
            f = tk.Frame(self.upd_frame, bg="#0d1a0d")
            f.pack(fill="both", expand=True, padx=12, pady=4)
            tk.Label(f, text=f"\u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430 {info['version']}...", font=("Segoe UI", 11), bg="#0d1a0d", fg="#aaaaaa").pack(anchor="w", padx=4)
            canvas = tk.Canvas(f, bg="#222222", height=10, highlightthickness=0)
            canvas.pack(fill="x", padx=4, pady=(4, 0))
            self.upd_canvas = canvas
            self.upd_pct_lbl = tk.Label(f, text="0%", font=("Segoe UI", 9), bg="#0d1a0d", fg="#666666")
            self.upd_pct_lbl.pack(anchor="e", padx=4)
            self.upd_progress_var = None

    def _update_progress(self, pct):
        try:
            if self.upd_progress_var is not None:
                self.upd_progress_var.set(pct)
                self.upd_pct_lbl.configure(text=f"{pct}%")
            elif hasattr(self, "upd_canvas"):
                w = self.upd_canvas.winfo_width()
                self.upd_canvas.delete("all")
                self.upd_canvas.create_rectangle(0, 0, int(w * pct / 100), 10, fill="#4caf50", outline="")
                self.upd_pct_lbl.configure(text=f"{pct}%")
        except: pass

    def _hide_update_banner(self):
        if self.upd_visible:
            self.upd_frame.grid_remove()
            self.upd_visible = False

    def _list(self):
        if self.u:
            c = ctk.CTkFrame(self.r, corner_radius=8, fg_color="#0a0a0a", border_width=1, border_color="#222222")
            c.grid(row=2, column=0, sticky="nsew", padx=15, pady=5)
            c.grid_columnconfigure(0, weight=1)
            c.grid_rowconfigure(0, weight=1)
            self.lb = tk.Listbox(c, font=("Segoe UI", 12), selectmode="extended", bg="#0a0a0a", fg="#dddddd", selectbackground="#ffffff", selectforeground="#000000", activestyle="none", borderwidth=0, highlightthickness=0)
            self.lb.grid(row=0, column=0, sticky="nsew", padx=(3,0), pady=3)
            self.lb.bind("<<ListboxSelect>>", self._on_select)
            sb_frame = tk.Frame(c, bg="#0a0a0a", width=14)
            sb_frame.grid(row=0, column=1, sticky="ns")
            sb_frame.grid_propagate(False)
            self._sb_canvas = tk.Canvas(sb_frame, bg="#0a0a0a", highlightthickness=0, width=14)
            self._sb_canvas.pack(fill="both", expand=True)
            self._sb_thumb = self._sb_canvas.create_rectangle(0, 0, 12, 40, fill="#333333", outline="", width=0)
            self._sb_dragging = False
            self._sb_last_y = 0
            self._sb_canvas.bind("<ButtonPress-1>", self._sb_press)
            self._sb_canvas.bind("<B1-Motion>", self._sb_drag)
            self._sb_canvas.bind("<ButtonRelease-1>", self._sb_release)
            self._sb_canvas.bind("<MouseWheel>", lambda e: self.lb.yview_scroll(-1 * (e.delta // 120), "units"))
            self.lb.bind("<MouseWheel>", lambda e: self.lb.yview_scroll(-1 * (e.delta // 120), "units"))
            self.lb.bind("<Configure>", lambda e: self._sb_update())
            self.lb.bind("<KeyRelease>", lambda e: self._sb_update())
            self.lb.bind("<ButtonRelease-1>", lambda e: self.r.after(10, self._sb_update))
            self.lb.bind("<<ListboxSelect>>", lambda e: self.r.after(10, self._sb_update))
            self.lb.config(yscrollcommand=self._sb_on_scroll)
        else:
            c = tk.Frame(self.r, bg="#0a0a0a", highlightthickness=1, highlightbackground="#222222")
            c.grid(row=2, column=0, sticky="nsew", padx=15, pady=5)
            c.grid_columnconfigure(0, weight=1)
            c.grid_rowconfigure(0, weight=1)
            self.lb = tk.Listbox(c, font=("Segoe UI", 12), selectmode="extended", bg="#0a0a0a", fg="#dddddd", selectbackground="#ffffff", selectforeground="#000000", activestyle="none", borderwidth=0, highlightthickness=0)
            self.lb.grid(row=0, column=0, sticky="nsew", padx=3, pady=3)
            self.lb.bind("<<ListboxSelect>>", self._on_select)
            sb = tk.Scrollbar(c, command=self.lb.yview, bg="#0a0a0a", troughcolor="#0a0a0a", activebackground="#333333", width=12)
            sb.grid(row=0, column=1, sticky="ns")
            self.lb.configure(yscrollcommand=sb.set)
            self._sb_canvas = None

    def _sb_on_scroll(self, *args):
        if self._sb_canvas is None: return
        self._sb_update()

    def _sb_update(self):
        c = self._sb_canvas
        if c is None: return
        try:
            first, last = self.lb.yview()
        except: return
        c_h = c.winfo_height()
        if c_h < 20: return
        thumb_h = max(20, int(c_h * (last - first)))
        thumb_y = int(c_h * first)
        c.coords(self._sb_thumb, 1, thumb_y, 11, thumb_y + thumb_h)
        if (last - first) >= 1.0:
            c.itemconfigure(self._sb_thumb, state="hidden")
        else:
            c.itemconfigure(self._sb_thumb, state="normal")

    def _sb_press(self, e):
        self._sb_dragging = True
        self._sb_last_y = e.y
        try:
            c_h = self._sb_canvas.winfo_height()
            if c_h < 20: return
            self.lb.yview_moveto(max(0, (e.y - 10) / c_h))
            self._sb_update()
        except: pass

    def _sb_drag(self, e):
        if not self._sb_dragging: return
        try:
            c_h = self._sb_canvas.winfo_height()
            if c_h < 20: return
            self.lb.yview_moveto(max(0, (e.y - 10) / c_h))
            self._sb_update()
        except: pass

    def _sb_release(self, e):
        self._sb_dragging = False

    def _bar(self):
        bg = "#000000"
        b = ctk.CTkFrame(self.r, corner_radius=0, fg_color=bg) if self.u else tk.Frame(self.r, bg=bg)
        b.grid(row=3, column=0, sticky="ew", padx=15, pady=(2, 12))

        def mk(txt, cmd, fg, hg):
            if self.u:
                return ctk.CTkButton(b, text=txt, command=cmd, fg_color=fg, hover_color=hg, font=ctk.CTkFont(size=12, weight="bold"), width=130, height=34, corner_radius=6, border_width=1, border_color="#333333")
            return tk.Button(b, text=txt, command=cmd, bg=fg, fg="white", font=("Segoe UI", 11, "bold"), relief="flat", cursor="hand2", width=14)

        mk("\u0412\u044b\u0431\u0440\u0430\u0442\u044c \u0432\u0441\u0435", self._sel_all, "#222222", "#444444").pack(side="left", padx=4, pady=6)
        mk("\u0421\u043d\u044f\u0442\u044c \u0432\u044b\u0431\u043e\u0440", self._desel, "#222222", "#444444").pack(side="left", padx=4, pady=6)

        self.sel_lbl = ctk.CTkLabel(b, text="", font=ctk.CTkFont(size=11), text_color="#666666") if self.u else tk.Label(b, text="", font=("Segoe UI", 10), bg=bg, fg="#666666")
        self.sel_lbl.pack(side="left", padx=12, pady=6)

        self.prog_lbl = ctk.CTkLabel(b, text="", font=ctk.CTkFont(size=11), text_color="#ffffff") if self.u else tk.Label(b, text="", font=("Segoe UI", 10), bg=bg, fg="#ffffff")
        self.prog_lbl.pack(side="left", padx=8, pady=6)

        self.status_lbl = ctk.CTkLabel(b, text="", font=ctk.CTkFont(size=10), text_color="#555555") if self.u else tk.Label(b, text="", font=("Segoe UI", 9), bg=bg, fg="#555555")
        self.status_lbl.pack(side="left", padx=8, pady=6)

        mk("\u041e\u0431\u043d\u043e\u0432\u0438\u0442\u044c", self._load, "#222222", "#444444").pack(side="right", padx=4, pady=6)
        mk("\u0412\u044b\u0445\u043e\u0434", self._quit, "#333333", "#555555").pack(side="right", padx=4, pady=6)

        self.del_btn = ctk.CTkButton(b, text="\u0423\u0434\u0430\u043b\u0438\u0442\u044c \u0432\u044b\u0431\u0440\u0430\u043d\u043d\u043e\u0435", command=self._del, fg_color="#ffffff", hover_color="#cccccc", text_color="#000000", font=ctk.CTkFont(size=13, weight="bold"), width=180, height=38, corner_radius=6) if self.u else tk.Button(b, text="\u0423\u0434\u0430\u043b\u0438\u0442\u044c \u0432\u044b\u0431\u0440\u0430\u043d\u043d\u043e\u0435", command=self._del, bg="#ffffff", fg="#000000", font=("Segoe UI", 11, "bold"), relief="flat", cursor="hand2")
        self.del_btn.pack(side="right", padx=5, pady=6)

        self.spinner = Spinner(self.prog_lbl)

    def _load(self):
        self.all = get_programs()
        self.filt = list(self.all)
        self._fill()
        self._on_select()

    def _fill(self):
        self.lb.delete(0, tk.END)
        for p in self.filt:
            sz = format_size(p["size"])
            if sz:
                display = f"{p['name']}  -  {sz}"
            else:
                display = p["name"]
            self.lb.insert(tk.END, display)

    def _on_type(self, e=None):
        if self.search_id: self.r.after_cancel(self.search_id)
        self.search_id = self.r.after(120, self._do_search)

    def _do_search(self):
        q = self.search_e.get().strip().lower()
        self.filt = [p for p in self.all if q in p["name"].lower()] if q else list(self.all)
        self._fill()
        self._on_select()

    def _on_select(self, e=None):
        try: sc = len(self.lb.curselection())
        except: sc = 0
        self.cnt_lbl.configure(text=f"{len(self.filt)} / {len(self.all)}")
        self.sel_lbl.configure(text=f"\u0412\u044b\u0431\u0440\u0430\u043d\u043e: {sc}")
        if self._sb_canvas: self.r.after(10, self._sb_update)

    def _sel_all(self):
        self.lb.select_set(0, tk.END)
        self._on_select()

    def _desel(self):
        self.lb.selection_clear(0, tk.END)
        self._on_select()

    def _sel(self):
        try: idx = self.lb.curselection()
        except: return []
        res = []
        for i in sorted(idx):
            n = self.lb.get(i)
            for p in self.filt:
                if p["name"] in n:
                    res.append(p)
                    break
        return res

    def _del(self):
        if self.busy:
            self._show_toast("\u0423\u0434\u0430\u043b\u0435\u043d\u0438\u0435 \u0443\u0436\u0435 \u0432 \u043f\u0440\u043e\u0446\u0435\u0441\u0441\u0435...")
            return
        sel = self._sel()
        if not sel:
            self._show_toast("\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u044b")
            return
        if not custom_confirm(self.r, "\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u0435", f"\u0423\u0434\u0430\u043b\u0438\u0442\u044c {len(sel)} \u043f\u0440\u043e\u0433\u0440\u0430\u043c\u043c?"):
            return
        self.busy = True
        try: self.del_btn.configure(state="disabled")
        except: pass
        self.spinner.start(f"\u0423\u0434\u0430\u043b\u0435\u043d\u0438\u0435 {len(sel)} \u043f\u0440\u043e\u0433\u0440\u0430\u043c\u043c")
        self.r.update_idletasks()
        threading.Thread(target=self._worker, args=(sel,), daemon=True).start()

    def _worker(self, sel):
        ok = fail = 0
        fails = []
        n = len(sel)
        for i, p in enumerate(sel):
            self.r.after(0, lambda ii=i, pp=p: self.status_lbl.configure(text=f"[{ii+1}/{n}] {pp['name'][:40]}..."))
            r = [False]; ev = threading.Event()
            def cb(v, r=r, e=ev): r[0] = v; e.set()
            threading.Thread(target=bg_uninstall, args=(p["cmd"], p["name"], cb), daemon=True).start()
            ev.wait(320)
            if r[0]: ok += 1
            else: fail += 1; fails.append(p["name"])
        self.r.after(0, lambda: self._done(ok, fail, fails))

    def _done(self, ok, fail, fails):
        self.busy = False
        try: self.del_btn.configure(state="normal")
        except: pass
        self.spinner.stop()
        self._load()
        if fail == 0:
            self._show_toast(f"\u0423\u0434\u0430\u043b\u0435\u043d\u043e: {ok}")
        else:
            msg = f"\u0423\u0434\u0430\u043b\u0435\u043d\u043e: {ok} | \u041e\u0448\u0438\u0431\u043a\u0438: {fail}"
            if fails: msg += "\n" + ", ".join(fails[:5])
            self._show_toast(msg)

    def _show_toast(self, text, duration=4000):
        if self.u:
            t = ctk.CTkToplevel(self.r)
            t.title(""); t.overrideredirect(True); t.configure(fg_color="#1a1a1a")
            t.attributes("-topmost", True)
            t.geometry(f"+{self.r.winfo_x()+200}+{self.r.winfo_y()+self.r.winfo_height()-80}")
            ctk.CTkLabel(t, text=text, font=ctk.CTkFont(size=12), text_color="#cccccc", wraplength=500).pack(padx=16, pady=10)
            t.after(duration, t.destroy)
        else:
            self.status_lbl.configure(text=text)
            self.r.after(duration, lambda: self.status_lbl.configure(text=""))

    def _auto_check(self):
        threading.Thread(target=self._bg_check, args=(False,), daemon=True).start()

    def _bg_check(self, show_always):
        result = check_update()
        self.r.after(0, lambda: self._on_check_done(result, show_always))

    def _on_check_done(self, result, show_always):
        if result is None:
            if show_always: self._show_toast("\u0423 \u0432\u0430\u0441 \u043f\u043e\u0441\u043b\u0435\u0434\u043d\u044f\u044f \u0432\u0435\u0440\u0441\u0438\u044f")
            return
        self.update_info = result
        self._show_update_banner(result)

    def _start_download(self, info):
        url = info.get("url")
        if not url:
            self._show_toast("\u0421\u0441\u044b\u043b\u043a\u0430 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u0430")
            return
        self._show_download_progress(info)
        threading.Thread(target=self._bg_download, args=(url, info), daemon=True).start()

    def _bg_download(self, url, info):
        path = do_download(url, lambda p: self.r.after(0, lambda pp=p: self._update_progress(pp)))
        self.r.after(0, lambda: self._on_dl_done(path, info))

    def _on_dl_done(self, path, info):
        if not path:
            self._hide_update_banner()
            self._show_toast("\u041e\u0448\u0438\u0431\u043a\u0430 \u0437\u0430\u0433\u0440\u0443\u0437\u043a\u0438")
            return
        ok = custom_confirm(self.r, "\u0413\u043e\u0442\u043e\u0432\u043e", f"\u0424\u0430\u0439\u043b {info['version']} \u0441\u043a\u0430\u0447\u0430\u043d.\n\u041f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u0430 \u0431\u0443\u0434\u0435\u0442 \u0437\u0430\u043c\u0435\u043d\u0435\u043d\u043e.\n\u041f\u0440\u043e\u0434\u043e\u043b\u043b\u0436\u0438\u0442\u044c?")
        if ok:
            self._show_toast("\u0417\u0430\u043c\u0435\u043d\u0430...")
            self.r.update_idletasks()
            bat = create_update_bat(path)
            subprocess.Popen(["cmd", "/c", bat], creationflags=subprocess.CREATE_NO_WINDOW)
            self.r.after(1000, lambda: os._exit(0))
        else:
            self._hide_update_banner()
            try: os.remove(path)
            except: pass

    def _quit(self):
        self.spinner.stop()
        self.r.destroy()
        sys.exit(0)

    def run(self):
        self.r.mainloop()


if __name__ == "__main__":
    App().run()

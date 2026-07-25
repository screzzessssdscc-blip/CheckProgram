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

VERSION = "1.0.0"
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


def check_update():
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(url, headers={"User-Agent": f"UninstallTool/{VERSION}"})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode("utf-8"))
        tag = data.get("tag_name", "")
        if not tag: return None
        latest_ver = parse_version(tag)
        cur_ver = parse_version(VERSION)
        if latest_ver <= cur_ver: return None
        exe_url = None
        for a in data.get("assets", []):
            if a.get("name", "").endswith(".exe"):
                exe_url = a.get("browser_download_url")
                break
        changelog = data.get("body", "")
        return {"version": tag, "url": exe_url, "changelog": changelog}
    except Exception:
        return None


def do_download(url, progress_fn=None):
    tmp = os.path.join(tempfile.gettempdir(), "UninstallTool_new.exe")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": f"UninstallTool/{VERSION}"})
        resp = urllib.request.urlopen(req, timeout=120)
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 256 * 1024
        with open(tmp, "wb") as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk: break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_fn and total:
                    pct = int(downloaded * 100 / total)
                    progress_fn(pct, downloaded, total)
        return tmp
    except Exception:
        return None


def create_update_bat(new_exe_path):
    current_exe = sys.executable
    bat_path = os.path.join(tempfile.gettempdir(), "uninstall_tool_update.bat")
    bat_content = f'''@echo off
timeout /t 2 /nobreak >nul
taskkill /F /IM "UninstallTool.exe" >nul 2>&1
timeout /t 2 /nobreak >nul
copy /Y "{new_exe_path}" "{current_exe}" >nul 2>&1
if %errorlevel%==0 (
    start "" "{current_exe}"
) else (
    copy /Y "{new_exe_path}" "{os.path.dirname(current_exe)}\\UninstallTool.exe" >nul 2>&1
    start "" "{os.path.dirname(current_exe)}\\UninstallTool.exe"
)
del /f /q "{new_exe_path}" >nul 2>&1
del /f /q "%~f0" >nul 2>&1
'''
    with open(bat_path, "w", encoding="ascii") as f:
        f.write(bat_content)
    return bat_path


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
            dn = us = None
            try: dn, _ = winreg.QueryValueEx(sub, "DisplayName")
            except: pass
            try: us, _ = winreg.QueryValueEx(sub, "UninstallString")
            except: pass
            winreg.CloseKey(sub)
            if dn and us and dn not in seen:
                seen.add(dn)
                progs.append({"name": dn, "cmd": us})
        winreg.CloseKey(root)
    progs.sort(key=lambda x: x["name"].lower())
    return progs


def kill_by_name(name):
    keywords = ["360", "zhuang", "uninst", "helper", "safe", "guard", "shield", "tray", "protect", "av", "total", "security"]
    name_parts = name.lower().split()
    killed = 0
    try:
        r = subprocess.run("tasklist /FO CSV /NH", shell=True, capture_output=True, text=True, timeout=10)
        for line in r.stdout.splitlines():
            parts = line.strip().strip('"').split('","')
            if len(parts) >= 2:
                pname = parts[0].lower()
                pid = parts[1]
                if any(k in pname for k in keywords) or any(np in pname for np in name_parts if len(np) > 3):
                    try:
                        subprocess.run(f"taskkill /F /PID {pid} /T", shell=True, capture_output=True, timeout=10)
                        killed += 1
                    except: pass
    except: pass
    return killed


def send_enter_to_windows():
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
            attempts.append(exe + " /qn /norestart")
            attempts.append(exe + " /passive /norestart")
    else:
        if not any(s in low for s in ["/s", "/silent", "/quiet", "/passive", "/q"]):
            attempts.append(exe + " /S")
            attempts.append(exe + " /silent /quiet")
            attempts.append(exe + " /verysilent /supressmsgboxes /norestart")
            attempts.append(exe + " /S /norestart")

    for a in attempts:
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0
            r = subprocess.run(a, shell=True, capture_output=True, timeout=120, startupinfo=si)
            if r.returncode == 0: return True
        except subprocess.TimeoutExpired:
            return True
        except: pass

    for a in attempts[:2]:
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0
            proc = subprocess.Popen(a, shell=True, startupinfo=si)
            time.sleep(3)
            if proc.poll() is None:
                send_enter_to_windows()
                time.sleep(3)
                send_enter_to_windows()
                time.sleep(3)
            if proc.poll() is None:
                proc.terminate()
                try: proc.wait(timeout=10)
                except: proc.kill()
            if proc.returncode == 0: return True
        except: pass

    kill_by_name(prog_name)
    time.sleep(2)

    for a in attempts[:2]:
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0
            r = subprocess.run(a, shell=True, capture_output=True, timeout=60, startupinfo=si)
            if r.returncode == 0: return True
        except: pass

    return False


def bg_uninstall(cmd, name, cb):
    cb(try_uninstall(cmd, name))


def custom_msg(parent, title, msg, btn="OK", tc="#ffffff"):
    if not CTK:
        messagebox.showinfo(title, msg)
        return
    d = ctk.CTkToplevel(parent)
    d.title("")
    d.geometry("440x280")
    d.configure(fg_color="#0a0a0a")
    d.resizable(False, False)
    d.grab_set()
    top = ctk.CTkFrame(d, fg_color="#111111", corner_radius=0, height=55)
    top.pack(fill="x")
    top.pack_propagate(False)
    ctk.CTkLabel(top, text=title, font=ctk.CTkFont(size=17, weight="bold"), text_color=tc).pack(side="left", padx=18, pady=14)
    ctk.CTkLabel(d, text=msg, font=ctk.CTkFont(size=13), text_color="#cccccc", wraplength=400, justify="left").pack(padx=22, pady=18, anchor="w")
    ctk.CTkButton(d, text=btn, command=d.destroy, fg_color="#ffffff", text_color="#000000", hover_color="#cccccc", width=90, height=32, corner_radius=6, font=ctk.CTkFont(size=12, weight="bold")).pack(pady=8)
    d.wait_window()


def custom_confirm(parent, title, msg, yes="Удалить", no="Отмена"):
    if not CTK:
        return messagebox.askyesno(title, msg)
    d = ctk.CTkToplevel(parent)
    d.title("")
    d.geometry("440x300")
    d.configure(fg_color="#0a0a0a")
    d.resizable(False, False)
    d.grab_set()
    top = ctk.CTkFrame(d, fg_color="#111111", corner_radius=0, height=55)
    top.pack(fill="x")
    top.pack_propagate(False)
    ctk.CTkLabel(top, text=title, font=ctk.CTkFont(size=17, weight="bold"), text_color="#ffffff").pack(side="left", padx=18, pady=14)
    ctk.CTkLabel(d, text=msg, font=ctk.CTkFont(size=13), text_color="#cccccc", wraplength=400, justify="left").pack(padx=22, pady=12, anchor="w")
    result = [False]
    bf = ctk.CTkFrame(d, fg_color="transparent")
    bf.pack(pady=10)
    ctk.CTkButton(bf, text=yes, command=lambda: result.__setitem__(0, True) or d.destroy(), fg_color="#ffffff", text_color="#000000", hover_color="#cccccc", width=140, height=36, corner_radius=6, font=ctk.CTkFont(size=13, weight="bold")).pack(side="left", padx=10)
    ctk.CTkButton(bf, text=no, command=d.destroy, fg_color="#333333", hover_color="#555555", width=140, height=36, corner_radius=6, font=ctk.CTkFont(size=13)).pack(side="left", padx=10)
    d.wait_window()
    return result[0]


class Spinner:
    def __init__(self, update_fn):
        self.fn = update_fn
        self.on = False
        self.base = ""
        self._id = None
        self._fi = 0
        self._frames = ["|", "/", "-", "\\"]

    def start(self, text=""):
        self.base = text
        self.on = True
        self._fi = 0
        self._tick()

    def stop(self):
        self.on = False
        if self._id:
            try: self.fn("")
            except: pass
        self._id = None

    def _tick(self):
        if not self.on: return
        sp = self._frames[self._fi % 4]
        self._fi += 1
        dots = "." * (self._fi % 4)
        self.fn(f"{sp} {self.base}{dots}")
        self._id = self.fn.__self__.after(300, self._tick) if hasattr(self.fn, '__self__') else None


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
        self.r.geometry("920x700")
        self.r.minsize(650, 480)
        self.r.configure(bg="#000000")

        ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trash_can.ico")
        if os.path.exists(ico):
            try: self.r.iconbitmap(default=ico)
            except: pass

        self._ui()
        self._load()
        self.r.after(1500, self._auto_check_update)

    def _ui(self):
        self.r.grid_columnconfigure(0, weight=1)
        self.r.grid_rowconfigure(1, weight=1)
        self._search()
        self._list()
        self._bar()

    def _search(self):
        bg = "#000000"
        w = ctk.CTkFrame(self.r, fg_color=bg) if self.u else tk.Frame(self.r, bg=bg)
        w.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 2))
        if self.u:
            self.search_e = ctk.CTkEntry(w, placeholder_text="Поиск...", width=350, font=ctk.CTkFont(size=14), corner_radius=8, height=36, border_width=1, border_color="#333333", fg_color="#111111")
            self.search_e.pack(side="left", padx=5, pady=5)
            self.cnt_lbl = ctk.CTkLabel(w, text="", font=ctk.CTkFont(size=11), text_color="#555555")
        else:
            self.search_e = tk.Entry(w, font=("Segoe UI", 13), width=35, bg="#111111", fg="#ffffff", insertbackground="white", highlightthickness=1, highlightcolor="#333333", relief="flat")
            self.search_e.pack(side="left", padx=5, pady=5)
            self.cnt_lbl = tk.Label(w, text="", font=("Segoe UI", 10), bg=bg, fg="#555555")
        self.cnt_lbl.pack(side="right", padx=10, pady=5)
        self.search_e.bind("<KeyRelease>", self._on_type)

    def _list(self):
        c = ctk.CTkFrame(self.r, corner_radius=8, fg_color="#0a0a0a", border_width=1, border_color="#222222") if self.u else tk.Frame(self.r, bg="#0a0a0a", highlightthickness=1, highlightbackground="#222222")
        c.grid(row=1, column=0, sticky="nsew", padx=15, pady=5)
        c.grid_columnconfigure(0, weight=1)
        c.grid_rowconfigure(0, weight=1)
        self.lb = tk.Listbox(c, font=("Segoe UI", 12), selectmode="extended", bg="#0a0a0a", fg="#dddddd", selectbackground="#ffffff", selectforeground="#000000", activestyle="none", borderwidth=0, highlightthickness=0)
        self.lb.grid(row=0, column=0, sticky="nsew", padx=3, pady=3)
        self.lb.bind("<<ListboxSelect>>", self._on_select)
        sb = tk.Scrollbar(c, command=self.lb.yview, bg="#0a0a0a", troughcolor="#0a0a0a", activebackground="#333333", width=12)
        sb.grid(row=0, column=1, sticky="ns")
        self.lb.configure(yscrollcommand=sb.set)

    def _bar(self):
        bg = "#000000"
        b = ctk.CTkFrame(self.r, corner_radius=0, fg_color=bg) if self.u else tk.Frame(self.r, bg=bg)
        b.grid(row=2, column=0, sticky="ew", padx=15, pady=(2, 12))

        def mk(txt, cmd, fg, hg):
            if self.u:
                return ctk.CTkButton(b, text=txt, command=cmd, fg_color=fg, hover_color=hg, font=ctk.CTkFont(size=12, weight="bold"), width=130, height=34, corner_radius=6, border_width=1, border_color="#333333")
            return tk.Button(b, text=txt, command=cmd, bg=fg, fg="white", font=("Segoe UI", 11, "bold"), relief="flat", cursor="hand2", width=14)

        mk("Выбрать все", self._sel_all, "#222222", "#444444").pack(side="left", padx=4, pady=6)
        mk("Снять выбор", self._desel, "#222222", "#444444").pack(side="left", padx=4, pady=6)

        self.sel_lbl = ctk.CTkLabel(b, text="", font=ctk.CTkFont(size=11), text_color="#666666") if self.u else tk.Label(b, text="", font=("Segoe UI", 10), bg=bg, fg="#666666")
        self.sel_lbl.pack(side="left", padx=12, pady=6)

        self.prog_lbl = ctk.CTkLabel(b, text="", font=ctk.CTkFont(size=11), text_color="#ffffff") if self.u else tk.Label(b, text="", font=("Segoe UI", 10), bg=bg, fg="#ffffff")
        self.prog_lbl.pack(side="left", padx=8, pady=6)

        self.status_lbl = ctk.CTkLabel(b, text="", font=ctk.CTkFont(size=10), text_color="#555555") if self.u else tk.Label(b, text="", font=("Segoe UI", 9), bg=bg, fg="#555555")
        self.status_lbl.pack(side="left", padx=8, pady=6)

        mk("Обновить", self._load, "#222222", "#444444").pack(side="right", padx=4, pady=6)
        mk("Выход", self._quit, "#333333", "#555555").pack(side="right", padx=4, pady=6)

        self.del_btn = ctk.CTkButton(b, text="Удалить выбранные", command=self._del, fg_color="#ffffff", hover_color="#cccccc", text_color="#000000", font=ctk.CTkFont(size=13, weight="bold"), width=180, height=38, corner_radius=6) if self.u else tk.Button(b, text="Удалить выбранные", command=self._del, bg="#ffffff", fg="#000000", font=("Segoe UI", 11, "bold"), relief="flat", cursor="hand2")
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
            self.lb.insert(tk.END, p["name"])

    def _on_type(self, e=None):
        if self.search_id:
            self.r.after_cancel(self.search_id)
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
        self.sel_lbl.configure(text=f"Выбрано: {sc}")

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
                if p["name"] == n:
                    res.append(p)
                    break
        return res

    def _del(self):
        if self.busy:
            custom_msg(self.r, "Подождите", "Удаление уже в процессе...\nПодождите завершения текущей операции.")
            return
        sel = self._sel()
        if not sel:
            custom_msg(self.r, "Ничего не выбрано", "Вы не выбрали ни одной программы.\n\nВыберите нужные программы\n(Ctrl + клик для нескольких)")
            return
        names = "\n".join(f"  {p['name']}" for p in sel[:15])
        if len(sel) > 15: names += f"\n  ... и ещё {len(sel)-15}"
        if not custom_confirm(self.r, "Подтверждение удаления", f"Будет удалено: {len(sel)} программ\n\n{names}"):
            return
        self.busy = True
        try: self.del_btn.configure(state="disabled")
        except: pass
        self.status_lbl.configure(text=f"Подготовка к удалению...")
        self.spinner.start(f"Удаление {len(sel)} программ")
        self.r.update_idletasks()
        threading.Thread(target=self._worker, args=(sel,), daemon=True).start()

    def _worker(self, sel):
        ok = fail = 0
        fails = []
        n = len(sel)
        for i, p in enumerate(sel):
            self.r.after(0, lambda ii=i, pp=p: self.status_lbl.configure(text=f"[{ii+1}/{n}] {pp['name'][:40]}..."))
            r = [False]
            ev = threading.Event()
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

        if self.u:
            d = ctk.CTkToplevel(self.r)
            d.title("")
            d.geometry("460x340")
            d.configure(fg_color="#0a0a0a")
            d.resizable(False, False)
            d.grab_set()
            top = ctk.CTkFrame(d, fg_color="#111111", corner_radius=0, height=55)
            top.pack(fill="x")
            top.pack_propagate(False)
            if fail == 0:
                ctk.CTkLabel(top, text="Готово", font=ctk.CTkFont(size=17, weight="bold"), text_color="#27ae60").pack(side="left", padx=18, pady=14)
                ctk.CTkLabel(d, text=f"Все {ok} программ\nуспешно удалены", font=ctk.CTkFont(size=14), text_color="#cccccc", justify="center").pack(expand=True, pady=20)
                self.status_lbl.configure(text=f"Удалено: {ok}")
            else:
                ctk.CTkLabel(top, text="Результат", font=ctk.CTkFont(size=17, weight="bold"), text_color="#e67e22").pack(side="left", padx=18, pady=14)
                msg = f"Удалено: {ok}  |  Ошибки: {fail}"
                if fails:
                    msg += "\n\nНе удалось:\n" + "\n".join(f"  {n}" for n in fails[:8])
                ctk.CTkLabel(d, text=msg, font=ctk.CTkFont(size=12), text_color="#cccccc", justify="left", wraplength=420).pack(padx=20, pady=15, anchor="w")
                self.status_lbl.configure(text=f"Ок: {ok} | Ошибки: {fail}")
            ctk.CTkButton(d, text="OK", command=d.destroy, fg_color="#ffffff", text_color="#000000", hover_color="#cccccc", width=90, height=32, corner_radius=6).pack(pady=10)
        else:
            t = "OK" if fail == 0 else "Errors"
            messagebox.showinfo(t, f"OK: {ok}, Errors: {fail}")

    def _auto_check_update(self):
        threading.Thread(target=self._bg_check, args=(False,), daemon=True).start()

    def _check_update_ui(self):
        if self.busy:
            custom_msg(self.r, "Подождите", "Подождите завершения текущей операции.")
            return
        self.spinner.start("Проверка обновлений")
        self.status_lbl.configure(text="Проверка обновлений...")
        threading.Thread(target=self._bg_check, args=(True,), daemon=True).start()

    def _bg_check(self, show_always):
        result = check_update()
        self.r.after(0, lambda: self._on_check_done(result, show_always))

    def _on_check_done(self, result, show_always):
        self.spinner.stop()
        if result is None:
            if show_always:
                self.status_lbl.configure(text="Обновлений нет")
                custom_msg(self.r, "Обновлений нет", f"У вас последняя версия.\n\nТекущая версия: v{VERSION}")
            else:
                self.status_lbl.configure(text="")
            return
        self.update_info = result
        self.status_lbl.configure(text=f"Доступно: {result['version']}")
        self._show_update_dialog(result)

    def _show_update_dialog(self, info):
        ver = info["version"]
        changelog = info.get("changelog", "").strip()
        if not changelog: changelog = "Описание отсутствует."

        d = ctk.CTkToplevel(self.r) if self.u else tk.Toplevel(self.r)
        d.title("")
        d.configure(bg="#0a0a0a")
        d.resizable(False, False)
        d.grab_set()

        if self.u:
            d.geometry("500x420")
            top = ctk.CTkFrame(d, fg_color="#111111", corner_radius=0, height=55)
            top.pack(fill="x")
            top.pack_propagate(False)
            ctk.CTkLabel(top, text="Доступно обновление", font=ctk.CTkFont(size=17, weight="bold"), text_color="#27ae60").pack(side="left", padx=18, pady=14)
            ctk.CTkLabel(d, text=f"Текущая версия: v{VERSION}\nНовая версия: {ver}", font=ctk.CTkFont(size=12), text_color="#aaaaaa").pack(padx=22, pady=(15, 5), anchor="w")

            cl_label = ctk.CTkLabel(d, text="Что нового:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#ffffff")
            cl_label.pack(padx=22, pady=(5, 2), anchor="w")

            cl_box = ctk.CTkTextbox(d, font=ctk.CTkFont(size=11), fg_color="#111111", text_color="#cccccc", wrap="word", height=150, border_width=1, border_color="#333333")
            cl_box.pack(padx=22, pady=(0, 10), fill="both")
            cl_box.insert("1.0", changelog)
            cl_box.configure(state="disabled")

            bf = ctk.CTkFrame(d, fg_color="transparent")
            bf.pack(pady=(5, 12))
            ctk.CTkButton(bf, text="Обновить", command=lambda: (d.destroy(), self._start_download(info)), fg_color="#ffffff", text_color="#000000", hover_color="#cccccc", width=150, height=38, corner_radius=6, font=ctk.CTkFont(size=13, weight="bold")).pack(side="left", padx=10)
            ctk.CTkButton(bf, text="Позже", command=d.destroy, fg_color="#333333", hover_color="#555555", width=120, height=38, corner_radius=6, font=ctk.CTkFont(size=13)).pack(side="left", padx=10)
        else:
            d.geometry("460x400")
            tk.Label(d, text="Доступно обновление", font=("Segoe UI", 14, "bold"), bg="#0a0a0a", fg="#27ae60").pack(padx=18, pady=12, anchor="w")
            tk.Label(d, text=f"Текущая: v{VERSION}  |  Новая: {ver}", font=("Segoe UI", 11), bg="#0a0a0a", fg="#aaaaaa").pack(padx=18, pady=5, anchor="w")
            tk.Label(d, text="Что нового:", font=("Segoe UI", 11, "bold"), bg="#0a0a0a", fg="#ffffff").pack(padx=18, pady=(8, 2), anchor="w")
            cl_box = tk.Text(d, font=("Segoe UI", 10), bg="#111111", fg="#cccccc", wrap="word", height=8, relief="flat", highlightthickness=1, highlightbackground="#333333")
            cl_box.pack(padx=18, pady=(0, 8), fill="both")
            cl_box.insert("1.0", changelog)
            cl_box.configure(state="disabled")
            bf = tk.Frame(d, bg="#0a0a0a")
            bf.pack(pady=10)
            tk.Button(bf, text="Обновить", command=lambda: (d.destroy(), self._start_download(info)), bg="#ffffff", fg="#000000", font=("Segoe UI", 11, "bold"), relief="flat", cursor="hand2", width=16).pack(side="left", padx=8)
            tk.Button(bf, text="Позже", command=d.destroy, bg="#333333", fg="white", font=("Segoe UI", 11), relief="flat", cursor="hand2", width=12).pack(side="left", padx=8)

    def _start_download(self, info):
        url = info.get("url")
        if not url:
            custom_msg(self.r, "Ошибка", "Ссылка на загрузку не найдена.\n\nСкачайте вручную с GitHub.")
            return
        self.spinner.start(f"Загрузка {info['version']}")
        self.status_lbl.configure(text=f"Загрузка {info['version']}...")
        threading.Thread(target=self._bg_download, args=(url, info), daemon=True).start()

    def _bg_download(self, url, info):
        def progress(pct, downloaded, total):
            self.r.after(0, lambda p=pct: self.spinner.start(f"Загрузка {p}%"))
        path = do_download(url, progress)
        self.r.after(0, lambda: self._on_download_done(path, info))

    def _on_download_done(self, path, info):
        self.spinner.stop()
        if not path:
            self.status_lbl.configure(text="Ошибка загрузки")
            custom_msg(self.r, "Ошибка", "Не удалось скачать обновление.\n\nПроверьте соединение с интернетом.")
            return
        ok = custom_confirm(self.r, "Обновление готово", f"Файл {info['version']} скачан.\n\nПрограмма будет закрыта и заменена.\nПродолжить?")
        if ok:
            self.spinner.start("Обновление...")
            bat = create_update_bat(path)
            subprocess.Popen(["cmd", "/c", bat], creationflags=subprocess.CREATE_NO_WINDOW)
            self.spinner.stop()
            sys.exit(0)
        else:
            self.status_lbl.configure(text="Обновление отменено")
            temp = os.path.join(tempfile.gettempdir(), "UninstallTool_new.exe")
            try: os.remove(temp)
            except: pass

    def _quit(self):
        self.spinner.stop()
        self.r.destroy()
        sys.exit(0)

    def run(self):
        self.r.mainloop()


if __name__ == "__main__":
    App().run()

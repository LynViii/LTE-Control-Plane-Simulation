from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

from .config import Settings
from .lan import detect_local_ipv4, lan_ip_pair_hint, test_lan_connection
from .windows_firewall import (
    build_firewall_plan,
    configure_windows_firewall,
    firewall_status_text,
    inspect_windows_firewall,
    is_windows,
)
from .version import __version__

DEFAULT_MANAGEMENT_TOKEN = "lte-sim-demo-2026"


_GUI_FONT_FAMILY = "Microsoft YaHei UI"
_GUI_FONT_SIZE = 13


def configure_windows_gui_environment() -> None:
    """Fix Windows DPI awareness before Tk/WebView create their first window.

    Without this, WebView2 can change process DPI behavior after the first Tk
    selector closes, making the selector appear physically smaller when the user
    exits a mode and returns to it in the same EXE process.
    """
    if os.name != "nt":
        return
    try:
        import ctypes
        # PER_MONITOR_AWARE_V2 when available. It must be configured before any
        # top-level GUI window is created.
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def _apply_tk_typography(root) -> None:
    import tkinter.font as tkfont
    # Keep all native selector widgets on the same family/point-size. Named
    # fonts cover ttk.Label/Button/Entry/Checkbutton unless a style overrides it.
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkCaptionFont", "TkSmallCaptionFont"):
        try:
            tkfont.nametofont(name).configure(family=_GUI_FONT_FAMILY, size=_GUI_FONT_SIZE)
        except Exception:
            pass
    try:
        tkfont.nametofont("TkHeadingFont").configure(family=_GUI_FONT_FAMILY, size=12, weight="bold")
    except Exception:
        pass
    try:
        tkfont.nametofont("TkFixedFont").configure(size=_GUI_FONT_SIZE)
    except Exception:
        pass




def _apply_window_icon(root) -> None:
    try:
        import sys
        package_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
        ico = package_root / "packaging" / "app-icon.ico"
        png = package_root / "packaging" / "app-icon.png"
        if os.name == "nt" and ico.exists():
            try:
                root.iconbitmap(default=str(ico))
                return
            except Exception:
                pass
        if png.exists():
            try:
                import tkinter as tk
                root._lte_icon = tk.PhotoImage(file=str(png))
                root.iconphoto(True, root._lte_icon)
            except Exception:
                pass
    except Exception:
        pass

def _configure_selector_window(root, *, width: int, height: int, min_width: int, min_height: int) -> None:
    _apply_tk_typography(root)
    # Use one deterministic geometry path every time the selector is recreated.
    # Centering after update_idletasks also prevents Tk from briefly reusing a
    # tiny requested size on the second selector in the same process.
    root.update_idletasks()
    screen_w, screen_h = root.winfo_screenwidth(), root.winfo_screenheight()
    # The selector is the primary launch surface.  Use a comfortable fraction of
    # the desktop instead of Tk's tiny requested-size default, while keeping the
    # window bounded on high-resolution monitors.
    preferred_w = max(width, int(screen_w * 0.64))
    preferred_h = max(height, int(screen_h * 0.72))
    target_w = min(max(min_width, preferred_w), min(1360, max(min_width, screen_w - 70)))
    target_h = min(max(min_height, preferred_h), min(880, max(min_height, screen_h - 80)))
    x = max(0, (screen_w - target_w) // 2)
    y = max(0, (screen_h - target_h) // 2)
    root.geometry(f"{target_w}x{target_h}+{x}+{y}")
    root.minsize(min_width, min_height)


LAN_STEPS = (
    "1. 两台电脑连接同一个局域网 / Wi-Fi\n"
    "2. 在电脑 B 启动 LTE-Modem-Node-Agent.exe\n"
    "3. 获取电脑 B 的局域网 IPv4 地址\n"
    "4. 在主控电脑填写 Modem IP，并确认 Controller IP\n"
    "5. 确认端口与 token；Windows 下检查防火墙，必要时一键配置\n"
    "6. 点击“测试连接”\n"
    "7. 确认 Agent ONLINE、Management CONNECTED、两条协议 Socket READY\n"
    "8. 点击“启动 LAN 模式”\n"
    "9. 进入主应用后再进行 Attach / 单次记录"
)


def _base_local() -> Settings:
    try:
        current = Settings.from_env()
        if current.run_mode == "local":
            return current
    except (ValueError, OSError):
        pass
    return Settings()


def _lan_settings(values: dict[str, str], base: Settings) -> Settings:
    controller_ip = values["controller_ip"].strip()
    modem_ip = values["modem_ip"].strip()
    token = values["token"]
    if not controller_ip or not modem_ip:
        raise ValueError("Controller IP 和 Modem IP 都不能为空")
    return replace(
        base,
        run_mode="lan-controller",
        host="127.0.0.1",
        bind_host="0.0.0.0",
        controller_host=controller_ip,
        modem_host=modem_ip,
        http_port=int(values["http_port"]),
        ap_modem_port=int(values["ap_port"]),
        enb_port=int(values["enb_port"]),
        management_port=int(values["management_port"]),
        management_token=token,
    )


def select_main_settings(base: Settings | None = None) -> Settings | None:
    """Two-step Local/LAN selector shown before any simulator socket exists.

    Step 1 only asks for the run mode.  Step 2 changes with the selection so
    LAN-only addresses/ports are never mixed into the Local-mode decision.
    """
    if os.environ.get("LTE_SIM_SKIP_MODE_SELECTOR") == "1":
        return Settings.from_env()
    base = base or _base_local()
    configure_windows_gui_environment()
    import tkinter as tk
    from tkinter import messagebox, ttk

    root = tk.Tk()
    _apply_window_icon(root)
    root.title(f"LTE 控制面系统仿真平台 v{__version__} · 启动")
    _configure_selector_window(root, width=1160, height=760, min_width=980, min_height=680)
    result: dict[str, Settings | None] = {"settings": None}

    style = ttk.Style(root)
    try:
        style.theme_use("vista")
    except tk.TclError:
        pass
    style.configure("TLabel", font=(_GUI_FONT_FAMILY, _GUI_FONT_SIZE))
    style.configure("TButton", font=(_GUI_FONT_FAMILY, _GUI_FONT_SIZE))
    style.configure("TEntry", font=(_GUI_FONT_FAMILY, _GUI_FONT_SIZE))
    style.configure("TCheckbutton", font=(_GUI_FONT_FAMILY, _GUI_FONT_SIZE))
    style.configure("TLabelframe.Label", font=(_GUI_FONT_FAMILY, _GUI_FONT_SIZE, "bold"))
    style.configure("Title.TLabel", font=(_GUI_FONT_FAMILY, 22, "bold"))
    style.configure("Heading.TLabel", font=(_GUI_FONT_FAMILY, 15, "bold"))
    style.configure("Mode.TRadiobutton", font=(_GUI_FONT_FAMILY, 14, "bold"))
    style.configure("Compact.TLabel", font=(_GUI_FONT_FAMILY, 11))

    footer = ttk.Frame(root, padding=(18, 8, 18, 14))
    footer.pack(fill="x", side="bottom")
    shell = ttk.Frame(root)
    shell.pack(fill="both", expand=True)
    canvas = tk.Canvas(shell, highlightthickness=0, borderwidth=0)
    scrollbar = ttk.Scrollbar(shell, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    page = ttk.Frame(canvas, padding=18)
    page_window = canvas.create_window((0, 0), window=page, anchor="nw")
    page.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(page_window, width=e.width))
    canvas.bind_all(
        "<MouseWheel>",
        lambda e: canvas.yview_scroll(int(-getattr(e, "delta", 0) / 120), "units") if getattr(e, "delta", 0) else None,
    )

    hero = tk.Frame(page, bg="#315746", padx=22, pady=14)
    hero.pack(fill="x", pady=(0, 18))
    tk.Label(hero, text="LTE 控制面系统仿真平台", bg="#315746", fg="white",
             font=(_GUI_FONT_FAMILY, 20, "bold")).pack(anchor="w")
    tk.Label(hero, text=f"v{__version__}  ·  选择运行模式后进入工程工作区", bg="#315746", fg="#DCE9E2",
             font=(_GUI_FONT_FAMILY, 11)).pack(anchor="w", pady=(5, 0))
    tk.Label(hero, text="先选 Local / LAN；进入对应模式后再查看详细运行信息。",
             bg="#315746", fg="#EEF5F1", font=(_GUI_FONT_FAMILY, 12), justify="left").pack(anchor="w", pady=(6, 0))

    ttk.Label(page, text="第 1 步 · 选择模式", style="Heading.TLabel").pack(anchor="w", pady=(0, 7))
    mode = tk.StringVar(value="local")
    mode_box = ttk.Frame(page)
    mode_box.pack(fill="x")
    local_card = ttk.LabelFrame(mode_box, text="Local Mode", padding=10)
    local_card.pack(side="left", fill="both", expand=True, padx=(0, 6))
    ttk.Radiobutton(
        local_card, variable=mode, value="local", text="单机模式", style="Mode.TRadiobutton"
    ).pack(anchor="w")
    ttk.Label(
        local_card,
        text="AP + Modem + eNB + Web + Security 全部运行在本机，使用真实 127.0.0.1 TCP/UDP。",
        wraplength=340,
        justify="left",
    ).pack(anchor="w", pady=(5, 0))
    lan_card = ttk.LabelFrame(mode_box, text="LAN Mode", padding=10)
    lan_card.pack(side="left", fill="both", expand=True, padx=(6, 0))
    ttk.Radiobutton(
        lan_card, variable=mode, value="lan", text="双机局域网模式", style="Mode.TRadiobutton"
    ).pack(anchor="w")
    ttk.Label(
        lan_card,
        text="电脑 A 运行主控/Web，电脑 B 运行 Modem Agent；协议 Socket 跨真实局域网。",
        wraplength=340,
        justify="left",
    ).pack(anchor="w", pady=(5, 0))

    ttk.Separator(page).pack(fill="x", pady=15)
    ttk.Label(page, text="第 2 步 · 确认启动参数", style="Heading.TLabel").pack(anchor="w", pady=(0, 7))

    local_panel = ttk.LabelFrame(page, text="Local Mode · 无需额外网络参数", padding=12)
    ttk.Label(
        local_panel,
        text=(
            f"单机回环运行：Web {base.http_port} · AP-Modem {base.ap_modem_port} · Modem-eNB {base.enb_port}。"
            " 进入主界面后再查看 Attach、Trace、Security 和诊断详情。"
        ),
        wraplength=900,
        justify="left",
    ).pack(anchor="w")

    lan_panel = ttk.LabelFrame(page, text="LAN Mode · 电脑 A 主控参数", padding=10)
    fields = {
        "controller_ip": tk.StringVar(value=detect_local_ipv4()),
        "modem_ip": tk.StringVar(value=base.modem_host if not base.modem_host.startswith("127.") else ""),
        "http_port": tk.StringVar(value=str(base.http_port)),
        "ap_port": tk.StringVar(value=str(base.ap_modem_port)),
        "enb_port": tk.StringVar(value=str(base.enb_port)),
        "management_port": tk.StringVar(value=str(base.management_port)),
        "token": tk.StringVar(value=os.environ.get("LTE_SIM_MANAGEMENT_TOKEN", DEFAULT_MANAGEMENT_TOKEN)),
    }
    labels = [
        ("Controller IP（电脑 A）", "controller_ip"), ("Modem IP（电脑 B）", "modem_ip"),
        ("HTTP port", "http_port"), ("AP-Modem port", "ap_port"),
        ("Modem-eNB port", "enb_port"), ("Management port", "management_port"),
        ("Management token（≥16字符）", "token"),
    ]
    form = ttk.Frame(lan_panel)
    form.pack(fill="x")
    token_entry = None
    for row, (label, key) in enumerate(labels):
        ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=4)
        entry = ttk.Entry(form, textvariable=fields[key], width=34, show="•" if key == "token" else "")
        entry.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=4)
        if key == "token":
            token_entry = entry
    token_visible = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        form, text="显示 token", variable=token_visible,
        command=lambda: token_entry.configure(show="" if token_visible.get() else "•") if token_entry else None,
    ).grid(row=len(labels), column=1, sticky="w", padx=(10, 0), pady=(0, 4))
    form.columnconfigure(1, weight=1)

    ttk.Label(
        lan_panel,
        text="电脑 B 需先启动 LTE-Modem-Node-Agent.exe。三个 LAN 端口与 Management token 必须两端一致；token 只是管理通道鉴权，不是 SRTP 密钥。",
        wraplength=860,
        justify="left",
    ).pack(anchor="w", pady=(8, 5))
    status_var = tk.StringVar(value="尚未测试连接")
    firewall_var = tk.StringVar(value="Windows 防火墙：尚未检查" if is_windows() else "Windows 防火墙：非 Windows 环境")
    ttk.Label(lan_panel, textvariable=status_var, wraplength=860, justify="left").pack(anchor="w", pady=(4, 2))
    ttk.Label(lan_panel, textvariable=firewall_var, wraplength=860, justify="left").pack(anchor="w", pady=(2, 6))

    def values() -> dict[str, str]:
        return {key: var.get() for key, var in fields.items()}

    def controller_firewall_plan():
        vals = values()
        return build_firewall_plan(
            "controller",
            local_ip=vals["controller_ip"].strip(),
            peer_ip=vals["modem_ip"].strip(),
            http_port=int(vals["http_port"]),
            enb_port=int(vals["enb_port"]),
        )

    def check_firewall() -> dict:
        try:
            status = inspect_windows_firewall(controller_firewall_plan())
            firewall_var.set(firewall_status_text(status))
            return status
        except Exception as exc:
            status = {"ready": False, "status": "CHECK_FAILED", "advice": str(exc)}
            firewall_var.set(f"Windows 防火墙：CHECK_FAILED（仅诊断）· {exc}")
            return status

    def configure_firewall() -> None:
        if not is_windows():
            firewall_var.set("Windows 防火墙：非 Windows 环境，无需配置")
            return
        try:
            firewall_var.set("Windows 防火墙：正在申请管理员权限，请处理 UAC 弹窗……")
            root.update_idletasks()
            status = configure_windows_firewall(controller_firewall_plan())
            firewall_var.set(firewall_status_text(status))
            if not status.get("ready"):
                messagebox.showwarning("防火墙配置未完成", firewall_status_text(status), parent=root)
        except Exception as exc:
            firewall_var.set(f"Windows 防火墙：配置失败 · {exc}")
            messagebox.showerror("防火墙配置失败", str(exc), parent=root)

    def detect() -> None:
        modem_ip = fields["modem_ip"].get().strip()
        detected = detect_local_ipv4(modem_ip or None)
        fields["controller_ip"].set(detected)
        suffix = "（按到 Modem 的实际路由检测）" if modem_ip else ""
        status_var.set(f"已检测 Controller IP：{detected}{suffix}")

    last_preflight = {"signature": None, "checked_at": 0.0, "result": None}

    def preflight_signature() -> tuple[str, ...]:
        vals = values()
        return tuple(vals[key].strip() for key in ("controller_ip", "modem_ip", "ap_port", "enb_port", "management_port", "token"))

    def run_preflight(settings: Settings, *, allow_cached: bool = True) -> dict:
        import time as _time
        signature = preflight_signature()
        if (allow_cached and last_preflight["result"] and last_preflight["result"].get("ok")
                and last_preflight["signature"] == signature
                and _time.monotonic() - last_preflight["checked_at"] < 12.0):
            return last_preflight["result"]
        check = test_lan_connection(settings)
        last_preflight.update(signature=signature, checked_at=_time.monotonic(), result=check)
        return check

    def test() -> None:
        try:
            settings = _lan_settings(values(), base)
            check = run_preflight(settings, allow_cached=False)
            if check["ok"]:
                status_var.set(
                    f"PASS · Agent ONLINE · Management CONNECTED · AP-Modem READY · Modem-eNB READY · Heartbeat {check['heartbeat']['lastUpdated']}"
                )
            else:
                issues = "；".join(f"{item['code']}: {item['message']}（{item['advice']}）" for item in check.get("issues", []))
                suggested = check.get("suggestedControllerIp")
                if suggested and suggested != settings.controller_host:
                    issues += f"；建议 Controller IP 改为 {suggested}"
                status_var.set(f"FAIL · {issues or '请检查 LAN 参数'}")
            if check["ok"]:
                firewall_var.set("Windows 防火墙：连接已通过；需要审计规则时再点“检查防火墙”")
        except Exception as exc:
            status_var.set(f"FAIL · {exc}")

    action_row = ttk.Frame(lan_panel)
    action_row.pack(fill="x", pady=(3, 0))
    ttk.Button(action_row, text="自动检测本机 IP", command=detect).pack(side="left")
    ttk.Button(action_row, text="检查防火墙", command=check_firewall).pack(side="left", padx=6)
    ttk.Button(action_row, text="一键配置防火墙", command=configure_firewall).pack(side="left", padx=(0, 6))
    ttk.Button(action_row, text="测试连接", command=test).pack(side="left")

    start_label = tk.StringVar(value="启动 Local 模式")

    def refresh_mode(*_args) -> None:
        local_panel.pack_forget()
        lan_panel.pack_forget()
        if mode.get() == "lan":
            lan_panel.pack(fill="x")
            start_label.set("启动 LAN 模式")
        else:
            local_panel.pack(fill="x")
            start_label.set("启动 Local 模式")
        root.after_idle(lambda: canvas.configure(scrollregion=canvas.bbox("all")))

    def start() -> None:
        try:
            if mode.get() == "local":
                result["settings"] = replace(
                    base,
                    run_mode="local",
                    host="127.0.0.1",
                    bind_host="127.0.0.1",
                    controller_host="127.0.0.1",
                    modem_host="127.0.0.1",
                    management_token="",
                )
            else:
                settings = _lan_settings(values(), base)
                check = run_preflight(settings, allow_cached=True)
                if not check.get("ok"):
                    issues = "；".join(f"{item['code']}: {item['advice']}" for item in check.get("issues", []))
                    suggested = check.get("suggestedControllerIp")
                    if suggested and suggested != settings.controller_host:
                        issues += f"；建议 Controller IP 改为 {suggested}，并让电脑 B Agent 使用同一个 Controller IP 后重启 Agent"
                    fw = check_firewall()
                    if fw.get("status") in {"RULES_MISSING", "BLOCK_RULE_DETECTED"}:
                        issues += f"；{fw.get('advice', '')}"
                    raise ValueError("LAN 预检查未通过，未启动：" + (issues or "请先点击测试连接并修复网络配置"))
                result["settings"] = settings
            root.destroy()
        except Exception as exc:
            messagebox.showerror("配置错误", str(exc), parent=root)

    ttk.Button(footer, text="取消", command=root.destroy).pack(side="right")
    ttk.Button(footer, textvariable=start_label, command=start).pack(side="right", padx=8)
    mode.trace_add("write", refresh_mode)
    refresh_mode()

    def close_selector() -> None:
        try:
            canvas.unbind_all("<MouseWheel>")
        except tk.TclError:
            pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close_selector)
    root.mainloop()
    return result["settings"]

def select_agent_settings(base: Settings | None = None) -> Settings | None:
    """Graphical Modem Agent setup so normal LAN use requires no PowerShell env vars."""
    if os.environ.get("LTE_SIM_SKIP_MODE_SELECTOR") == "1":
        settings = Settings.from_env()
        if settings.run_mode != "lan-modem":
            raise ValueError("LTE_SIM_MODE must be lan-modem when selector is skipped")
        return settings

    configure_windows_gui_environment()
    import tkinter as tk
    from tkinter import messagebox, ttk
    default = base or Settings()
    detected = detect_local_ipv4()
    root = tk.Tk()
    _apply_window_icon(root)
    root.title(f"LTE Modem Node Agent v{__version__} · LAN 配置")
    _configure_selector_window(root, width=1040, height=740, min_width=900, min_height=650)
    result: dict[str, Settings | None] = {"settings": None}
    agent_style = ttk.Style(root)
    try:
        agent_style.theme_use("vista")
    except tk.TclError:
        pass
    agent_style.configure("TLabel", font=(_GUI_FONT_FAMILY, _GUI_FONT_SIZE))
    agent_style.configure("TButton", font=(_GUI_FONT_FAMILY, _GUI_FONT_SIZE))
    agent_style.configure("TEntry", font=(_GUI_FONT_FAMILY, _GUI_FONT_SIZE))
    agent_style.configure("TCheckbutton", font=(_GUI_FONT_FAMILY, _GUI_FONT_SIZE))

    agent_footer = ttk.Frame(root, padding=(18, 8, 18, 14))
    agent_footer.pack(fill="x", side="bottom")
    agent_shell = ttk.Frame(root)
    agent_shell.pack(fill="both", expand=True)
    agent_canvas = tk.Canvas(agent_shell, highlightthickness=0, borderwidth=0)
    agent_scroll = ttk.Scrollbar(agent_shell, orient="vertical", command=agent_canvas.yview)
    agent_canvas.configure(yscrollcommand=agent_scroll.set)
    agent_scroll.pack(side="right", fill="y")
    agent_canvas.pack(side="left", fill="both", expand=True)
    frame = ttk.Frame(agent_canvas, padding=18)
    agent_window = agent_canvas.create_window((0, 0), window=frame, anchor="nw")
    frame.bind("<Configure>", lambda _event: agent_canvas.configure(scrollregion=agent_canvas.bbox("all")))
    agent_canvas.bind("<Configure>", lambda event: agent_canvas.itemconfigure(agent_window, width=event.width))
    agent_canvas.bind_all(
        "<MouseWheel>",
        lambda event: agent_canvas.yview_scroll(int(-getattr(event, "delta", 0) / 120), "units") if getattr(event, "delta", 0) else None,
    )

    agent_hero = tk.Frame(frame, bg="#315746", padx=20, pady=16)
    agent_hero.pack(fill="x", pady=(0, 16))
    tk.Label(agent_hero, text="Modem Node Agent", bg="#315746", fg="white",
             font=(_GUI_FONT_FAMILY, 20, "bold")).pack(anchor="w")
    tk.Label(agent_hero, text=f"电脑 B · v{__version__} · LAN 远端节点", bg="#315746", fg="#DCE9E2",
             font=(_GUI_FONT_FAMILY, 11)).pack(anchor="w", pady=(4, 0))
    tk.Label(agent_hero, text="填写电脑 A 与电脑 B 的局域网参数后启动。运行期间只保留 Agent 状态窗口，不需要命令行控制台。",
             bg="#315746", fg="#EEF5F1", font=(_GUI_FONT_FAMILY, 12), wraplength=780, justify="left").pack(anchor="w", pady=(8, 0))

    agent_overview = ttk.LabelFrame(frame, text="电脑 B 启动前核对", padding=12)
    agent_overview.pack(fill="x", pady=(0, 14))
    agent_overview_grid = ttk.Frame(agent_overview)
    agent_overview_grid.pack(fill="x")
    for col in range(3):
        agent_overview_grid.columnconfigure(col, weight=1)
    ttk.Label(
        agent_overview_grid,
        text=(
            "角色\n"
            "- 本机承担 Modem Agent\n"
            "- 接收主控下发的 AP-Modem、Modem-eNB 与 Management 指令"
        ),
        justify="left",
        wraplength=220,
    ).grid(row=0, column=0, sticky="nsew", padx=(0, 8))
    ttk.Label(
        agent_overview_grid,
        text=(
            "默认端口\n"
            "- AP-Modem 5000\n"
            "- Modem-eNB 5001\n"
            "- Management 5002"
        ),
        justify="left",
        wraplength=180,
    ).grid(row=0, column=1, sticky="nsew", padx=8)
    ttk.Label(
        agent_overview_grid,
        text=(
            "建议顺序\n"
            "1. 先填 Controller IP\n"
            "2. 再自动匹配电脑 B IPv4\n"
            "3. 测试连通性后启动 Agent"
        ),
        justify="left",
        wraplength=220,
    ).grid(row=0, column=2, sticky="nsew", padx=(8, 0))

    vars_ = {
        "modem_ip": tk.StringVar(value=detected),
        "controller_ip": tk.StringVar(value=""),
        "ap_port": tk.StringVar(value=str(default.ap_modem_port)),
        "enb_port": tk.StringVar(value=str(default.enb_port)),
        "management_port": tk.StringVar(value=str(default.management_port)),
        "token": tk.StringVar(value=os.environ.get("LTE_SIM_MANAGEMENT_TOKEN", DEFAULT_MANAGEMENT_TOKEN)),
    }
    form = ttk.Frame(frame)
    form.pack(fill="x")
    labels = [
        ("Controller / 电脑 A IPv4", "controller_ip"),
        ("Modem / 电脑 B IPv4（自动匹配）", "modem_ip"),
        ("AP-Modem port", "ap_port"),
        ("Modem-eNB port", "enb_port"),
        ("Management port", "management_port"),
        ("Management token（与主控一致，≥16字符）", "token"),
    ]
    token_entry = None
    for row, (label, key) in enumerate(labels):
        ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=5)
        entry = ttk.Entry(form, textvariable=vars_[key], show="•" if key == "token" else "")
        entry.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=5)
        if key == "token":
            token_entry = entry
    token_visible = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        form, text="显示 token", variable=token_visible,
        command=lambda: token_entry.configure(show="" if token_visible.get() else "•") if token_entry else None,
    ).grid(row=len(labels), column=1, sticky="w", padx=(10, 0), pady=(0, 5))
    form.columnconfigure(1, weight=1)
    ttk.Label(
        frame,
        text=(
            "端口通常保持 5000 / 5001 / 5002；两端必须一致。先填写 Controller IP，再自动匹配电脑 B IPv4。"
            "Management token 已填入测试默认值，可直接联调，也可以删除后自定义。"
        ),
        wraplength=780,
        justify="left",
    ).pack(anchor="w", pady=(8, 2))

    detected_var = tk.StringVar(value=f"初始检测本机 IP：{detected}。请先填写 Controller IP，再自动匹配一次。")
    ttk.Label(frame, textvariable=detected_var, wraplength=780, justify="left").pack(anchor="w", pady=(10, 4))

    def redetect() -> None:
        controller_ip = vars_["controller_ip"].get().strip()
        ip = detect_local_ipv4(controller_ip or None)
        vars_["modem_ip"].set(ip)
        suffix = "（按到 Controller 的实际系统路由匹配）" if controller_ip else "（尚未填写 Controller，只能做普通检测）"
        detected_var.set(f"电脑 B IPv4：{ip}{suffix}")

    network_row = ttk.Frame(frame)
    network_row.pack(fill="x")
    ttk.Button(network_row, text="按 Controller IP 自动匹配电脑 B IPv4", command=redetect).pack(side="left")

    firewall_var = tk.StringVar(value="Windows 防火墙：尚未检查" if is_windows() else "Windows 防火墙：非 Windows 环境")
    ttk.Label(frame, textvariable=firewall_var, wraplength=780, justify="left").pack(anchor="w", pady=(10, 4))

    def agent_firewall_plan():
        return build_firewall_plan(
            "agent",
            local_ip=vars_["modem_ip"].get().strip(),
            peer_ip=vars_["controller_ip"].get().strip(),
            ap_modem_port=int(vars_["ap_port"].get()),
            management_port=int(vars_["management_port"].get()),
        )

    def check_agent_firewall() -> dict:
        try:
            status = inspect_windows_firewall(agent_firewall_plan())
            firewall_var.set(firewall_status_text(status))
            return status
        except Exception as exc:
            status = {"ready": False, "status": "CHECK_FAILED", "advice": str(exc)}
            firewall_var.set(f"Windows 防火墙：CHECK_FAILED（仅诊断）· {exc}")
            return status

    def configure_agent_firewall() -> None:
        if not is_windows():
            firewall_var.set("Windows 防火墙：非 Windows 环境，无需配置")
            return
        try:
            firewall_var.set("Windows 防火墙：正在申请管理员权限，请处理 UAC 弹窗……")
            root.update_idletasks()
            status = configure_windows_firewall(agent_firewall_plan())
            firewall_var.set(firewall_status_text(status))
            if not status.get("ready"):
                messagebox.showwarning("防火墙配置未完成", firewall_status_text(status), parent=root)
        except Exception as exc:
            firewall_var.set(f"Windows 防火墙：配置失败 · {exc}")
            messagebox.showerror("防火墙配置失败", str(exc), parent=root)

    firewall_buttons = ttk.Frame(frame)
    firewall_buttons.pack(fill="x", pady=(0, 2))
    ttk.Button(firewall_buttons, text="检查防火墙", command=check_agent_firewall).pack(side="left")
    ttk.Button(firewall_buttons, text="一键配置防火墙", command=configure_agent_firewall).pack(side="left", padx=6)

    ttk.Label(
        frame,
        text="启动后会进入独立 Agent 状态窗口；主控“测试连接”应看到 Agent ONLINE、Management CONNECTED、AP-Modem READY、Modem-eNB READY。",
        wraplength=780,
        justify="left",
    ).pack(anchor="w", pady=(16, 10))

    def start() -> None:
        try:
            modem_ip = vars_["modem_ip"].get().strip()
            controller_ip = vars_["controller_ip"].get().strip()
            if not controller_ip:
                raise ValueError("请先填写 Controller / 电脑 A IPv4")
            routed_ip = detect_local_ipv4(controller_ip)
            if routed_ip and not routed_ip.startswith("127."):
                modem_ip = routed_ip
                vars_["modem_ip"].set(modem_ip)
            if not modem_ip:
                raise ValueError("无法确定电脑 B 的局域网 IPv4，请检查网络后重新检测")
            pair_hint = lan_ip_pair_hint(controller_ip, modem_ip)
            if pair_hint:
                raise ValueError(pair_hint)
            # Firewall diagnostics are optional; never block Modem Agent startup.
            result["settings"] = replace(
                default,
                run_mode="lan-modem",
                host=modem_ip,
                bind_host=modem_ip,
                modem_host=modem_ip,
                controller_host=controller_ip,
                ap_modem_port=int(vars_["ap_port"].get()),
                enb_port=int(vars_["enb_port"].get()),
                management_port=int(vars_["management_port"].get()),
                management_token=vars_["token"].get(),
            )
            root.destroy()
        except Exception as exc:
            messagebox.showerror("配置错误", str(exc), parent=root)

    ttk.Button(agent_footer, text="取消", command=root.destroy).pack(side="right")
    ttk.Button(agent_footer, text="启动 Modem Agent", command=start).pack(side="right", padx=8)

    def close_agent_selector() -> None:
        try:
            agent_canvas.unbind_all("<MouseWheel>")
        except tk.TclError:
            pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close_agent_selector)
    root.mainloop()
    return result["settings"]

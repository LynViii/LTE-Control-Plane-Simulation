from __future__ import annotations

import os
import queue
import threading
import time
from dataclasses import replace
from pathlib import Path

from .config import Settings
from .lan import ModemNodeAgent, agent_local_self_check
from .startup_ui import _apply_window_icon, configure_windows_gui_environment, select_agent_settings
from .version import __version__
from .windows_firewall import build_firewall_plan, firewall_status_text, inspect_windows_firewall


AGENT_DATA_DIRNAME = "LTEControlPlaneSimulatorModemAgent"


def resolve_agent_data_dir(environment: dict[str, str] | None = None) -> Path:
    """Return a writable directory for temporary Agent diagnostics/state.

    The Agent deliberately does not create a formal Run Repository; official
    Runs/Trace/Statistics/PCAP remain on the controller.
    """
    env = os.environ if environment is None else environment
    override = env.get("LTE_SIM_AGENT_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    local_app_data = env.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / AGENT_DATA_DIRNAME
    return Path.home() / ".lte-control-plane-simulator-modem-agent"


def prepare_agent_runtime(settings: Settings, data_dir: Path) -> Settings:
    data_dir = data_dir.resolve()
    (data_dir / "var").mkdir(parents=True, exist_ok=True)
    return replace(
        settings,
        state_file=data_dir / "var" / "simulation-state.json",
        # Kept only to satisfy the shared Settings contract. ModemNodeAgent does
        # not instantiate RunRepository or create this directory.
        runs_dir=data_dir / "runs-not-used-on-agent",
    )


def _run_agent_status_window(settings: Settings, node: ModemNodeAgent) -> None:
    """Keep a native status window alive without exposing a console window."""
    configure_windows_gui_environment()
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    _apply_window_icon(root)
    root.title(f"LTE Modem Node Agent v{__version__}")
    root.update_idletasks()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    width = min(1040, max(900, int(sw * 0.55)))
    height = min(760, max(660, int(sh * 0.68)))
    x, y = max(0, (sw - width) // 2), max(0, (sh - height) // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")
    root.minsize(860, 620)

    style = ttk.Style(root)
    try:
        style.theme_use("vista")
    except tk.TclError:
        pass
    family = "Microsoft YaHei UI"
    style.configure("TLabel", font=(family, 12))
    style.configure("TButton", font=(family, 12))
    style.configure("AgentTitle.TLabel", font=(family, 20, "bold"))
    style.configure("AgentHeading.TLabel", font=(family, 13, "bold"))

    shell = ttk.Frame(root, padding=18)
    shell.pack(fill="both", expand=True)
    hero = tk.Frame(shell, bg="#315746", padx=20, pady=16)
    hero.pack(fill="x")
    tk.Label(hero, text="Modem Node Agent", bg="#315746", fg="white", font=(family, 20, "bold")).pack(anchor="w")
    tk.Label(
        hero,
        text=f"ONLINE · {settings.modem_host}  →  Controller {settings.controller_host}",
        bg="#315746", fg="#E6F1EA", font=(family, 12),
    ).pack(anchor="w", pady=(5, 0))

    status_grid = ttk.Frame(shell)
    status_grid.pack(fill="x", pady=(14, 10))
    values = {
        "agent": tk.StringVar(value="ONLINE"),
        "ap": tk.StringVar(value="LISTENING"),
        "management": tk.StringVar(value="LISTENING"),
        "enb": tk.StringVar(value="READY"),
    }
    cards = [
        ("Agent", "agent", f"{settings.modem_host}"),
        ("AP-Modem", "ap", f"{settings.modem_host}:{settings.ap_modem_port}"),
        ("Management", "management", f"{settings.modem_host}:{settings.management_port}"),
        ("Modem-eNB", "enb", f"{settings.controller_host}:{settings.enb_port}"),
    ]
    for col, (title, key, endpoint) in enumerate(cards):
        card = ttk.LabelFrame(status_grid, text=title, padding=10)
        card.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 5, 0 if col == 3 else 5))
        ttk.Label(card, textvariable=values[key], style="AgentHeading.TLabel").pack(anchor="w")
        ttk.Label(card, text=endpoint, foreground="#66756F").pack(anchor="w", pady=(4, 0))
        status_grid.columnconfigure(col, weight=1)

    detail = ttk.LabelFrame(shell, text="运行状态", padding=12)
    detail.pack(fill="x", pady=(4, 10))
    flow_var = tk.StringVar(value="等待主控发起 Attach")
    selfcheck_var = tk.StringVar(value="本机监听自检：检查中…")
    firewall_var = tk.StringVar(value="Windows 防火墙：后台检查中…")
    ttk.Label(detail, textvariable=flow_var, style="AgentHeading.TLabel").pack(anchor="w")
    ttk.Label(detail, textvariable=selfcheck_var, wraplength=880, justify="left").pack(anchor="w", pady=(8, 0))
    ttk.Label(detail, textvariable=firewall_var, wraplength=880, justify="left").pack(anchor="w", pady=(5, 0))

    log_frame = ttk.LabelFrame(shell, text="Agent 日志", padding=8)
    log_frame.pack(fill="both", expand=True)
    log = tk.Text(log_frame, height=10, wrap="word", font=("Cascadia Mono", 11), relief="flat", bg="#F6F8F7")
    log.pack(fill="both", expand=True)
    log.configure(state="disabled")

    def append_log(message: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        log.configure(state="normal")
        log.insert("end", f"[{stamp}] {message}\n")
        log.see("end")
        log.configure(state="disabled")

    append_log("Agent 已启动；正式 Runs / Trace / Statistics / PCAP 保存在电脑 A。")
    append_log(f"电脑 A 的 Modem IP 应填写: {settings.modem_host}")
    append_log(f"AP-Modem listener {settings.modem_host}:{settings.ap_modem_port}")
    append_log(f"Management listener {settings.modem_host}:{settings.management_port}")
    append_log(f"Modem-eNB target {settings.controller_host}:{settings.enb_port}")

    ui_updates: queue.Queue[tuple[str, str]] = queue.Queue()

    def background_checks() -> None:
        # Firewall inspection is advisory and must never prevent startup; listeners are already live.
        # Worker threads only enqueue text. Tk widgets are updated by the main UI thread below.
        try:
            check = agent_local_self_check(settings)
            ui_updates.put((
                "selfcheck",
                f"本机监听自检：{'PASS' if check.get('ok') else 'FAIL'} · AP-Modem / Management 已监听"
                if check.get("ok") else f"本机监听自检：FAIL · {check}",
            ))
            ui_updates.put(("log", f"本机监听自检 {'PASS' if check.get('ok') else 'FAIL'}"))
        except Exception as exc:
            ui_updates.put(("selfcheck", f"本机监听自检：FAIL · {exc}"))
        try:
            firewall = inspect_windows_firewall(build_firewall_plan(
                "agent",
                local_ip=settings.modem_host,
                peer_ip=settings.controller_host,
                ap_modem_port=settings.ap_modem_port,
                management_port=settings.management_port,
            ))
            ui_updates.put(("firewall", firewall_status_text(firewall)))
        except Exception as exc:
            ui_updates.put(("firewall", f"Windows 防火墙：检查跳过 · {exc}"))

    def drain_ui_updates() -> None:
        try:
            while True:
                kind, message = ui_updates.get_nowait()
                if kind == "selfcheck":
                    selfcheck_var.set(message)
                elif kind == "firewall":
                    firewall_var.set(message)
                elif kind == "log":
                    append_log(message)
        except queue.Empty:
            pass
        if root.winfo_exists():
            root.after(120, drain_ui_updates)

    threading.Thread(target=background_checks, name="Agent UI Checks", daemon=True).start()
    root.after(120, drain_ui_updates)

    last_attach = {"value": None}
    def refresh_runtime() -> None:
        try:
            snapshot = node.store.snapshot()
            sockets = snapshot.get("sockets", {})
            values["ap"].set(sockets.get("apModem", {}).get("status") or "LISTENING")
            values["enb"].set(sockets.get("modemEnb", {}).get("status") or "READY")
            values["management"].set("LISTENING")
            modem = snapshot.get("modem", {})
            attach = modem.get("attachStatus") or snapshot.get("flow", {}).get("status") or "DETACHED"
            step = snapshot.get("flow", {}).get("currentStep") or snapshot.get("flow", {}).get("step")
            flow_var.set(f"Attach：{attach}" + (f" · {step}" if step else " · 等待主控操作"))
            if attach != last_attach["value"]:
                append_log(f"Attach 状态 → {attach}")
                last_attach["value"] = attach
        except Exception as exc:
            flow_var.set(f"状态读取失败：{exc}")
        root.after(500, refresh_runtime)

    footer = ttk.Frame(shell)
    footer.pack(fill="x", pady=(10, 0))
    ttk.Label(footer, text="关闭此窗口会停止 Modem Agent。", foreground="#66756F").pack(side="left")

    def stop_agent() -> None:
        try:
            node.stop()
        finally:
            root.destroy()

    ttk.Button(footer, text="停止并退出", command=stop_agent).pack(side="right")
    root.protocol("WM_DELETE_WINDOW", stop_agent)
    root.after(300, refresh_runtime)
    root.mainloop()


def main() -> None:
    selected = select_agent_settings()
    if selected is None:
        return
    settings = prepare_agent_runtime(selected, resolve_agent_data_dir())
    node = ModemNodeAgent(settings).start(block=False)
    try:
        _run_agent_status_window(settings, node)
    finally:
        try:
            node.stop()
        except Exception:
            pass


if __name__ == "__main__":
    main()

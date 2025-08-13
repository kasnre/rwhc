from lut import *
from meta_data import *
from matrix import *
from convert_utils import *
from delteE import *
from icc_rw import ICCProfile
from color_test_suit import *

# from icc_dispatch import *
from win_display import (
    get_all_display_config,
    get_monitor_rect_by_gdi_name,
    cp_add_display_association,
)
from win_display import (
    install_icc,
    uninstall_icc,
    cp_remove_display_association,
    luid_from_dict,
)


from color_rw import ColorReader, ColorWriter
from log import logging, TextHandler

from tkinter import filedialog, ttk, Canvas
import tkinter.font as tkfont
import tkinter as tk
import numpy as np
import webbrowser
import subprocess
import threading
import traceback
import tempfile
import ctypes
import time
import uuid
import copy
import sys
import re
import os


class HDRCalibrationUI:
    def __init__(self, root):
        self.init_base_icc()
        self.target_xyz = []
        self.convert_command = []
        self.measured_xyz = {}

        self.gamut_test_rgb = {
            "red": [592, 0, 0],
            "green": [0, 592, 0],
            "blue": [0, 0, 592],
            "white": [1023, 1023, 1023],
            "white_200nit": [592, 592, 592],
            "black": [0, 0, 0],
        }
        self.measure_gamut_xyz = {}

        self.preview_icc_name = None
        self.measured_pq = {"red": [], "green": [], "blue": []}

        self.proc_color_write = None
        self.proc_color_reader = None

        self.icc_change_delay = 0

        self.eetf_args = {
            "source_max": 10000,
            "source_min": 0,
            "monitor_max": None,
            "monitor_min": None,
        }
        self._eetf_window = None

        self.project_url = "https://github.com/forbxy/rwhc"
        self.argyll_download_url = "https://www.argyllcms.com/downloadwin.html"

        self.root = root
        self.root.title("RealWindowsHDRCalibrator")
        self.set_dpi_awareness()

        self.displays_config = get_all_display_config()
        hc = {}
        for itm in self.displays_config:
            product_id = itm["target"]["device_path"].split("#")[1]
            f_name = itm["target"].get("friendly_name") or "none"
            h_dname = f"{itm['path_index']}_{f_name}_{product_id}"
            hc[h_dname] = copy.deepcopy(itm)
            hc[h_dname]["monitor_rect"] = get_monitor_rect_by_gdi_name(
                itm["source"]["gdi_name"]
            )
            hc[h_dname]["color_work_status"] = "sdr"
            # Generate the screen's address in the Windows registry
            t = itm["target"]["device_path"].split("\\")[-1].split("#")[:-1]
            hc[h_dname]["pnp_device_id"] = "\\".join(t)
            """SDR_ACM = advanced_color  & wide_color_enforced
               HDR =     advanced_color  & !wide_color_enforced
               SDR =     !advanced_color & !wide_color_enforced
            """
            if hc[h_dname]["target"]["advanced_color"]["enabled"]:
                hc[h_dname]["color_work_status"] = "hdr"
                if hc[h_dname]["target"]["advanced_color"]["wide_color_enforced"]:
                    hc[h_dname]["color_work_status"] = "sdr_acm"
        self.human_display_config_map = hc

        self.build_ui()
        self.init_logging()
        self.on_monitor_changed()
        

    def init_logging(self):
        th = TextHandler(self.log_text)
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
        th.setFormatter(fmt)
        root_logger = logging.getLogger()
        root_logger.addHandler(th)

        log_path = os.path.join(os.path.dirname(__file__), "hc.log")
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setFormatter(fmt)
        fh.setLevel(logging.DEBUG)
        root_logger.addHandler(fh)

        root_logger.setLevel(logging.INFO)
        logging.info("Application started")

    def build_ui(self):
        self.root.geometry("960x1000")
        self.root.configure(bg="#f8f8f8")
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)
        intro_font = ("Microsoft YaHei", 16)

        style = ttk.Style()
        style.theme_use("vista")
        style.configure(
            "TopBar.TMenubutton",
            font=("Microsoft YaHei", 14),
            padding=(5, 4),
            background="#f8f8f8",
            relief="flat",
            borderwidth=0,
        )
        style.map(
            "TopBar.TMenubutton",
            background=[("active", "#e9eff5"), ("pressed", "#dbe6f0")],
            relief=[("pressed", "flat"), ("!pressed", "flat")],
        )
        try:
            style.layout(
                "TopBar.TMenubutton",
                [
                    (
                        "Menubutton.padding",
                        {
                            "children": [("Menubutton.label", {"sticky": "nswe"})],
                            "sticky": "nswe",
                        },
                    )
                ],
            )
        except tk.TclError:
            pass

        top_bar = tk.Frame(root, bg="#f8f8f8")
        top_bar.pack(fill="x", padx=36, pady=(0, 4))

        tk.Frame(top_bar, bg="#dcdcdc", height=1).pack(fill="x", side="bottom")

        tools_btn = ttk.Menubutton(top_bar, text="工具", style="TopBar.TMenubutton")
        tools_btn.pack(side="left", padx=(0, 24))
        tools_menu = tk.Menu(tools_btn, tearoff=0, font=("Microsoft YaHei", 14))
        tools_menu.add_command(label="ICC修改器", command=self.open_icc_modifier)
        tools_menu.add_command(label="色域浏览器", command=self.open_gamut_browser)
        tools_menu.add_command(label="查看灰阶", command=self.grayscale_view)
        tools_menu.add_command(label="手动测量", command=self.open_manual_measure)
        tools_btn["menu"] = tools_menu  # or tools_btn.config(menu=tools_menu)

        help_btn = ttk.Menubutton(top_bar, text="帮助", style="TopBar.TMenubutton")
        help_btn.pack(side="left")
        help_menu = tk.Menu(help_btn, tearoff=0, font=("Microsoft YaHei", 14))
        help_menu.add_command(label="使用教程", command=self.open_user_guide_window)
        help_menu.add_command(label="项目主页", command=self.open_project_homepage)
        help_btn["menu"] = help_menu
        self.help_window = None

        # 程序介绍
        intro = (
            "使用前请先阅读帮助页面！！！\n"
            "只适用于windows11 22H2及以上的版本\n"
            "色彩生成器: dogegen\n"
            "校色仪驱动: argyllcms spotread"
        )
        tk.Label(
            root,
            text=intro,
            font=intro_font,
            justify="left",
            bg="#f8f8f8",
            fg="#333333",
            anchor="w",
            pady=12,
            wraplength=2150,
        ).pack(pady=(0, 10), padx=36, anchor="w")

        # 使用方法
        self.instructions = (
            "1.使用爱色丽校色仪和罗技鼠标，先在设备管理器中将鼠标的驱动更换为windows默认驱动，"
            "然后在服务中停止Logitech LampArray Service。\n\n"
            "2.使用datacolor-spyder校色仪,先安装argyll驱动程序,然后在设备管理器中找到spyder设备(通用串行总线控制器下)"
            "->右键更新驱动->浏览我的电脑->让我从计算机的可用驱动程序列表中选取->选择argyll\n\n"
            "3..灰阶采样数:10bit hdr有1024级灰阶(R=G=B 0-1023)，"
            "程序会等距离的在1024级灰阶中采集指定数量的灰阶，并对未测量的灰阶进行插值。"
            "采集数量越多，PQ曲线校准越精准，但需要的时间也越久。目前LUT只对亮度进行校准\n\n"
            "4.色彩采样集:程序会在所选色域内生成一个测试集，保证80%灰阶准确的前提下，按测试集预期XYZ和实测XYZ进行拟合得到矩阵。"
            "如果你的屏幕在打开HDR后桌面色彩很鲜艳，选择sRGB。如果颜色暗淡，则选择sRGB+DisplayP3更优。\n\n"
            "5.明亮模式: 对生成的LUT进行整体提升，适用于强环境光下观看电影。\n\n"
            "6.预览校准结果：当执行了校准后，矩阵和LUT会存储在程序中，选中该选项会生成临时icc文件并加载到选中的屏幕，"
            "取消选中后自动移除。未执行校准时加载的是理想HDR icc(bt2020色域，10000nit，无需矩阵和lut校准)\n\n"
            "7.校准: 生成矩阵和LUT\n\n"
            "8.测量色准:测量屏幕的色准(选中预览校准可以将矩阵和LUT临时加载到屏幕)\n\n"
            "9.保存: 将矩阵和LUT保存为ICC配置文件\n\n"
        )

        # 分隔线
        tk.Frame(root, height=1, bg="#dcdcdc").pack(fill="x", padx=36, pady=(4, 8))

        style.configure(
            "TButton", font=("Microsoft YaHei", 16), padding=(12, 8), width=20
        )
        style.configure(
            "TCheckbutton",
            font=("Microsoft YaHei", 16),  # 设置字体大小
            padding=(8, 4),  # 可选：调整内边距
        )

        # 按钮区域
        button_frame = tk.Frame(root, bg="#f8f8f8")
        button_frame.pack(pady=20, anchor="w", padx=36)
        self.root.option_add("*TCombobox*Listbox*Font", ("Microsoft YaHei", 15))

        self.monitor_list = list(self.human_display_config_map.keys())
        self.monitor_list.sort()
        self.monitor_var = tk.StringVar(
            value=self.monitor_list[0] if self.monitor_list else "No Monitor Found"
        )
        tk.Label(
            button_frame, text="选择屏幕：", font=("Microsoft YaHei", 16), bg="#f8f8f8"
        ).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=(0, 12), columnspan=3)
        monitor_menu = ttk.Combobox(
            button_frame,
            textvariable=self.monitor_var,
            values=self.monitor_list,
            font=("Microsoft YaHei", 16),
            width=40,
            state="readonly",
        )
        monitor_menu.grid(
            row=0, column=0, sticky="we", padx=(120, 0), pady=(0, 12), columnspan=3
        )
        monitor_menu.bind("<<ComboboxSelected>>", lambda e: self.on_monitor_changed())

        im = self.get_instrument_mode_options()
        self.instrument_desc = [itm[1] for itm in im[0]]
        self.instrument_choose = [itm[0] for itm in im[0]]
        self.mode_desc = [itm[1] for itm in im[1]]
        self.mode_choose = [itm[0] for itm in im[1]]

        self.instrument_var = tk.StringVar(value=self.instrument_desc[0])
        tk.Label(
            button_frame, text="选择设备：", font=("Microsoft YaHei", 16), bg="#f8f8f8"
        ).grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(0, 12), columnspan=3)
        instrument_menu = ttk.Combobox(
            button_frame,
            textvariable=self.instrument_var,
            values=self.instrument_desc,
            font=("Microsoft YaHei", 16),
            width=40,
            state="readonly",
        )
        instrument_menu.grid(
            row=1, column=0, sticky="we", padx=(120, 0), pady=(0, 12), columnspan=3
        )

        self.mode_var = tk.StringVar(value=self.mode_desc[0])
        tk.Label(
            button_frame, text="设备模式：", font=("Microsoft YaHei", 16), bg="#f8f8f8"
        ).grid(row=2, column=0, sticky="w", padx=(0, 10), pady=(0, 12), columnspan=3)
        mode_menu = ttk.Combobox(
            button_frame,
            textvariable=self.mode_var,
            values=self.mode_desc,
            font=("Microsoft YaHei", 16),
            width=40,
            state="readonly",
        )
        mode_menu.grid(
            row=2, column=0, sticky="we", padx=(120, 0), pady=(0, 12), columnspan=3
        )

        self.pq_points_var = tk.StringVar(value="128")  # 默认值为 128
        tk.Label(
            button_frame,
            text="灰阶采样数：",
            font=("Microsoft YaHei", 16),
            bg="#f8f8f8",
        ).grid(row=3, column=0, sticky="w", padx=(0, 10), pady=(0, 12))
        pq_points_menu = ttk.Combobox(
            button_frame,
            textvariable=self.pq_points_var,
            values=["128", "256", "512", "1024"],
            font=("Microsoft YaHei", 16),
            width=6,
            state="readonly",
        )
        pq_points_menu.grid(row=3, column=0, sticky="we", padx=(120, 33), pady=(0, 12))

        self.color_space_var = tk.StringVar(value="sRGB")
        tk.Label(
            button_frame,
            text="色彩采样集：",
            font=("Microsoft YaHei", 16),
            bg="#f8f8f8",
        ).grid(row=3, column=1, sticky="w", padx=(0, 10), pady=(0, 12))
        color_space_menu = ttk.Combobox(
            button_frame,
            textvariable=self.color_space_var,
            values=["sRGB", "sRGB+DisplayP3"],
            font=("Microsoft YaHei", 16),
            width=6,
            state="readonly",
        )
        color_space_menu.grid(
            row=3, column=1, sticky="we", padx=(120, 33), pady=(0, 12)
        )

        self.eetf_var = tk.BooleanVar(value=False)
        self.eetf_check = ttk.Checkbutton(
            button_frame,
            text="亮度映射",
            variable=self.eetf_var,
            style="TCheckbutton",
            command=self.on_eetf_toggle,
        )
        # self.eetf_check.grid(row=3, column=2, sticky="w", padx=(0, 10), pady=(0, 12))
        # eetf功能，需要重构
        
        self.bright_var = tk.BooleanVar(value=False) 
        self.bright_checkbutton = ttk.Checkbutton(
            button_frame,
            text="明亮模式",
            variable=self.bright_var,
            style="TCheckbutton",
        )
        self.bright_checkbutton.grid(
            row=3, column=2, sticky="w", padx=(0, 0), pady=(0, 14)
        )

        self.preview_var = tk.BooleanVar(value=False) 
        self.preview_var.trace_add("write", lambda *a: self.on_preview_toggle())
        self.preview_checkbutton = ttk.Checkbutton(
            button_frame,
            text="预览校准结果",
            variable=self.preview_var,
            style="TCheckbutton",
        )
        self.preview_checkbutton.grid(
            row=4, column=0, sticky="w", padx=(0, 0), pady=(0, 14)
        )

        self.icc_set_var = tk.BooleanVar(value=True) 
        self.icc_set_checkbutton = ttk.Checkbutton(
            button_frame,
            text="保存后加载为默认ICC",
            variable=self.icc_set_var,
            style="TCheckbutton",
        )
        self.icc_set_checkbutton.grid(
            row=4, column=2, sticky="w", padx=(0, 0), pady=(0, 14)
        )

        ttk.Button(
            button_frame,
            text="校准",
            command=self.calibrate_monitor,
            style="TButton",  
            
            width=20,
        ).grid(row=5, column=0, padx=(0, 30), pady=(10, 0), sticky="w")

        ttk.Button(
            button_frame,
            text="测量色准",
            command=self.measure_pq,
            style="TButton",
            width=20,
        ).grid(row=5, column=1, padx=(0, 30), pady=(10, 0), sticky="w")

        ttk.Button(
            button_frame,
            text="保存为icc文件",
            command=self.generate_and_save_icc,
            style="TButton",
            width=20,
        ).grid(row=5, column=2, pady=(10, 0), sticky="w")

        ttk.Button(
            button_frame,
            text="打开设备管理器",
            command=lambda: os.system("start devmgmt.msc"),
            style="TButton",
            width=20,
        ).grid(row=6, column=0, columnspan=2, pady=(20, 0), sticky="w")
        ttk.Button(
            button_frame,
            text="打开windows服务",
            command=lambda: os.system("start services.msc"),
            style="TButton",
            width=20,
        ).grid(row=6, column=1, columnspan=2, pady=(20, 0), sticky="w")

        ttk.Button(
            button_frame,
            text="安装spyder驱动",
            command=lambda: webbrowser.open(self.argyll_download_url),
            style="TButton",
            width=20,
        ).grid(row=6, column=2, columnspan=2, pady=(20, 0), sticky="w")

        log_frame = ttk.LabelFrame(root, text="日志")
        log_frame.pack(fill="both", expand=True, padx=36, pady=(0, 20))
        self.log_text = tk.Text(
            log_frame,
            height=12,
            wrap="word",
            state="disabled",
            font=("Microsoft YaHei", 12),
            bg="#ffffff",
        )
        scrollbar = ttk.Scrollbar(
            log_frame, orient="vertical", command=self.log_text.yview
        )
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True, padx=6, pady=6)

    def init_base_icc(self):
        self.icc_handle = ICCProfile("hdr_empty.icc")
        self.icc_data = self.icc_handle.read_all()
        self.MHC2 = copy.deepcopy(self.icc_data["MHC2"])
        if self.MHC2["red_lut"] == [0, 1]:
            self.MHC2["red_lut"] = generate_pq_lut().tolist()
            self.MHC2["green_lut"] = generate_pq_lut().tolist()
            self.MHC2["blue_lut"] = generate_pq_lut().tolist()
            self.MHC2["entry_count"] = len(self.MHC2["red_lut"])

    def set_dpi_awareness(self):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # PROCESS_SYSTEM_DPI_AWARE
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    def run_in_thread(self, worker, on_done):
        """
        worker: a function that takes no arguments (or only uses closure variables) — returns a result
        on_done(result): callback executed on the main (GUI) thread
        """

        def _wrap():
            try:
                res = worker()
            except Exception as e:
                res = e
            # 回到主线程执行 GUI 回调
            self.root.after(0, lambda: on_done(res))

        threading.Thread(target=_wrap, daemon=True).start()

    def get_instrument_mode_options(self):
        """
        Dynamically parse the output of spotread.exe --help
        to extract available instruments and their device file names.
        """
        exe_path = os.path.join(os.path.dirname(__file__), "bin", "spotread.exe")
        if not os.path.isfile(exe_path):
            return ([], [])
        try:
            proc = subprocess.run(
                [exe_path, "--help"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=os.environ.copy(),
                check=False,
            )
            output = proc.stdout
        except Exception as e:
            return ([], [])

        lines = [itm.strip() for itm in output.splitlines()]

        c_list = []
        # -c
        for i, ln in enumerate(lines):
            if "-c listno" in ln:
                # 向下收集, 直到遇到下一参数(行以 '-' 开头且不是空格缩进)
                j = i
                while j < len(lines):
                    l2 = lines[j]
                    if j != i and re.match(r"^-\w", l2):
                        break
                    # 匹配 "  1 = 'xxxx'"
                    m = re.match(r"\s*(\d+)\s*=\s*'(.+)'", l2)
                    if m:
                        c_list.append([m.group(1), m.group(2)])
                    j += 1
                break  # 完成后退出

        # -y
        y_list = []
        start_idx = None
        for i, ln in enumerate(lines):
            if re.match(r"^-y\s+", ln):
                start_idx = i
                break
        if start_idx is not None:
            # 收集块
            block = []
            for j in range(start_idx, len(lines)):
                l2 = lines[j]
                if j == start_idx:
                    l2 = l2[3:]  # 去掉 "-y " 前缀
                if j > start_idx and re.match(r"^-\w", l2):  # 下一参数开始
                    break
                block.append(l2.rstrip())
            for raw in block:
                if not raw.strip():
                    continue
                m = raw.split("    ")
                code = m[0].strip()
                desc = m[-1].strip()
                y_list.append([code, desc])
        if not y_list:
            logging.error("未解析到spotread -y 模式, 原始输出可能格式变化")
        return c_list, y_list

    def get_spotread_args(self):
        args = []
        instrument_idx = self.instrument_desc.index(self.instrument_var.get())
        mode_idx = self.mode_desc.index(self.mode_var.get())
        args.append("-x")
        args.extend(["-c", self.instrument_choose[instrument_idx]])
        args.extend(["-y", self.mode_choose[mode_idx].split("|")[0]])
        return " ".join(args)

    def open_icc_modifier(self):
        try:
            script = os.path.join(os.path.dirname(__file__), "icc_rw_app.py")
            if not os.path.isfile(script):
                tk.messagebox.showerror("错误", f"未找到文件: {script}")
                return
            subprocess.Popen([sys.executable, script], cwd=os.path.dirname(script))
        except Exception as e:
            tk.messagebox.showerror("错误", f"启动 icc_rw_app 失败: {e}")

    def open_manual_measure(self):
        try:
            script = os.path.join(os.path.dirname(__file__), "manual_measure_color_app.py")
            if not os.path.isfile(script):
                tk.messagebox.showerror("错误", f"未找到文件: {script}")
                return
            subprocess.Popen([sys.executable, script], cwd=os.path.dirname(script))
        except Exception as e:
            tk.messagebox.showerror("错误", f"启动 manual_measure_color_app 失败: {e}")

    def open_gamut_browser(self):
        try:
            script = os.path.join(os.path.dirname(__file__), "color_space_view_app.py")
            if not os.path.isfile(script):
                tk.messagebox.showerror("错误", f"未找到文件: {script}")
                return
            subprocess.Popen([sys.executable, script], cwd=os.path.dirname(script))
        except Exception as e:
            tk.messagebox.showerror("错误", f"启动 color_space_view_app 失败: {e}")

    def open_project_homepage(self):
        webbrowser.open(self.project_url)

    def grayscale_view(self):
        try:
            script = os.path.join(os.path.dirname(__file__), "visual_check_app.py")
            if not os.path.isfile(script):
                tk.messagebox.showerror("错误", f"未找到文件: {script}")
                return
            subprocess.Popen([sys.executable, script], cwd=os.path.dirname(script))
        except Exception as e:
            tk.messagebox.showerror("错误", f"启动 visual_check_app 失败: {e}")

    def open_user_guide_window(self):
        if self.help_window and tk.Toplevel.winfo_exists(self.help_window):
            self.help_window.lift()
            return
        self.help_window = tk.Toplevel(self.root)
        self.help_window.title("使用教程")
        self.help_window.geometry("720x520")
        self.help_window.configure(bg="#f8f8f8")
        txt_frame = tk.Frame(self.help_window, bg="#f8f8f8")
        txt_frame.pack(fill="both", expand=True, padx=12, pady=12)
        scrollbar = tk.Scrollbar(txt_frame)
        scrollbar.pack(side="right", fill="y")
        help_text = tk.Text(
            txt_frame,
            font=("Microsoft YaHei", 16),
            bg="#f8f8f8",
            fg="#333333",
            wrap="char",
            borderwidth=0,
            yscrollcommand=scrollbar.set,
        )
        help_text.pack(fill="both", expand=True)
        help_text.insert("1.0", self.instructions)
        help_text.config(state="disabled")
        scrollbar.config(command=help_text.yview)

        def on_close():
            win = self.help_window
            if win and win.winfo_exists():
                win.destroy()
            self.help_window = None

        self.help_window.protocol("WM_DELETE_WINDOW", on_close)

    def set_icc(self, path):
        """
        path: The file path of the ICC profile to install.
        Install the specified ICC file, 
        associate it with the currently selected display, 
        and set it as that display's default ICC.
        """
        install_icc(path)
        icc_name = os.path.basename(path)
        monitor = self.monitor_var.get()
        info = self.human_display_config_map.get(monitor)
        luid = luid_from_dict(info["adapter_luid"])
        sid = info["source"]["id"]
        hdr = False
        if info["color_work_status"] == "hdr":
            hdr = True
        cp_add_display_association(
            luid, sid, icc_name, set_as_default=True, associate_as_advanced_color=hdr
        )

    def clean_icc(self, name):
        """
        name: The name of the ICC profile to clean (without .icc or .icm).
        Unassociate the specified ICC file from the currently selected display, 
        unset it as that display's default profile, 
        and remove the ICC file from the system.
        """
        path = f"{name}.icc"
        monitor = self.monitor_var.get()
        info = self.human_display_config_map.get(monitor)
        luid = luid_from_dict(info["adapter_luid"])
        sid = info["source"]["id"]
        hdr = False
        if info["color_work_status"] == "hdr":
            hdr = True
        cp_remove_display_association(luid, sid, path, associate_as_advanced_color=hdr)
        uninstall_icc(path, force=True)

    def freeze_ui(self):
        """
        Disable all interactive controls in the window; 
        save their original states (including Combobox 'readonly' state).
        """
        if getattr(self, "_ui_frozen", False):
            return
        self._ui_frozen = True
        self._disabled_widgets = []

        def add(widget, prev_state):
            self._disabled_widgets.append((widget, prev_state))

        def walk(w):
            for child in w.winfo_children():
                walk(child)
                if isinstance(
                    child,
                    (
                        tk.Button,
                        tk.Checkbutton,
                        tk.Radiobutton,
                        tk.Scale,
                        tk.Entry,
                        tk.Text,
                    ),
                ):
                    prev = child.cget("state")
                    if prev != "disabled":
                        add(child, prev)
                        child.config(state="disabled")
                elif isinstance(
                    child,
                    (
                        ttk.Button,
                        ttk.Checkbutton,
                        ttk.Radiobutton,
                        ttk.Entry,
                        ttk.Menubutton,
                    ),
                ):
                    try:
                        prev = child.cget("state")
                    except Exception:
                        try:
                            prev = (
                                "disabled" if "disabled" in child.state() else "normal"
                            )
                        except Exception:
                            prev = "normal"
                    if prev != "disabled":
                        add(child, prev)
                        child.configure(state="disabled")
                elif isinstance(child, ttk.Combobox):
                    prev = child.cget("state")  # 可能是 'readonly' 或 'normal'
                    if prev != "disabled":
                        add(child, prev)
                        child.configure(state="disabled")
                if isinstance(child, ttk.Menubutton):
                    m = child["menu"] if "menu" in child.keys() else None
                    if isinstance(m, tk.Menu):
                        entry_states = []
                        end = m.index("end")
                        if end is not None:
                            for i in range(end + 1):
                                try:
                                    st = m.entrycget(i, "state")
                                    entry_states.append(st)
                                    m.entryconfig(i, state="disabled")
                                except Exception:
                                    entry_states.append(None)
                        add(m, entry_states)

        walk(self.root)
        self.root.configure(cursor="wait")
        self.root.update_idletasks()

    def unfreeze_ui(self):
        """
        Restore the interactive controls' states that were saved prior to calling freeze_ui.
        """
        if not getattr(self, "_ui_frozen", False):
            return
        for widget, prev in getattr(self, "_disabled_widgets", []):
            if isinstance(widget, tk.Menu):
                for i, st in enumerate(prev):
                    if st is not None:
                        try:
                            widget.entryconfig(i, state=st)
                        except Exception:
                            pass
                continue
            try:
                if prev != "disabled":
                    widget.configure(state=prev)
            except Exception:
                pass
        self._disabled_widgets.clear()
        self._ui_frozen = False
        self.root.configure(cursor="")
        self.root.update_idletasks()

    @staticmethod
    def safe_call(func):
        """
        Decorator for GUI action methods that:
        - Catches and logs any exception raised by the wrapped function.
        - Ensures cleanup steps run on error (unfreeze UI, stop reader/writer processes).
        - Resets transient ICC/preview state to a safe default.
        - Prevents the exception from propagating to the caller (avoids crashing the GUI thread).
        """
        def wrapper(*args, **kwargs):
            self = args[0]
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logging.error(f"执行 {func.__name__} 时发生错误: {e}")
                logging.error(traceback.format_exc())
                try:
                    self.unfreeze_ui()
                except Exception:
                    pass
                try:
                    self.clean_color_rw_process()
                except Exception:
                    pass
                self.icc_change_delay = 0
                if self.preview_icc_name:
                    try:
                        self.preview_var.set(False)
                    except Exception:
                        pass

        return wrapper

    def clean_color_rw_process(self):
        try:
            if self.proc_color_write:
                self.proc_color_write.terminate()
                self.proc_color_write = None
            if self.proc_color_reader:
                self.proc_color_reader.terminate()
                self.proc_color_reader = None
        except Exception as e:
            logging.error(f"清理颜色读写进程时发生错误: {e}")
            logging.error(traceback.format_exc())

    def on_exit(self):
        # exit clean
        try:
            if self.preview_icc_name:
                self.clean_icc(self.preview_icc_name)
            self.clean_color_rw_process()
        except Exception as e:
            logging.error(f"执行 on_exit 时发生错误: {e}")
            logging.error(traceback.format_exc())
        try:
            self.root.destroy()
        except Exception:
            pass

    def on_monitor_changed(self, event=None):
        """
        Display change notification: 
        show a short, undecorated overlay centered on the selected monitor 
        """
        sel = self.monitor_var.get()
        info = self.human_display_config_map.get(sel)
        if not info:
            return

        mon = info.get("monitor_rect")
        if not mon:
            try:
                mon = get_monitor_rect_by_gdi_name(info["source"]["gdi_name"])
            except Exception:
                return

        box_w = 500
        box_h = 300
        duration_ms = 1500
        text = "已选择该屏幕"

        mon_left = int(mon.get("left", 0))
        mon_top = int(mon.get("top", 0))
        mon_right = int(mon.get("right", mon_left + box_w))
        mon_bottom = int(mon.get("bottom", mon_top + box_h))
        mon_w = max(1, mon_right - mon_left)
        mon_h = max(1, mon_bottom - mon_top)

        x = mon_left + (mon_w - box_w) // 2
        y = mon_top + (mon_h - box_h) // 2

        try:
            prev_top = self.root.attributes("-topmost")
        except Exception:
            prev_top = False

        def _to_bool(v):
            if isinstance(v, str):
                return v in ("1", "true", "True")
            return bool(v)

        prev_top_bool = _to_bool(prev_top)

        overlay = tk.Toplevel(self.root)
        overlay.overrideredirect(True)
        overlay.transient(self.root)
        overlay.attributes("-topmost", True)
        overlay.configure(bg="white")
        overlay.geometry(f"{box_w}x{box_h}+{x}+{y}")
        overlay.lift(self.root)

        frm = tk.Frame(
            overlay, bg="white", highlightthickness=1, highlightbackground="#888888"
        )
        frm.pack(fill="both", expand=True)

        canvas = tk.Canvas(
            frm, width=box_w, height=box_h, highlightthickness=0, bg="white"
        )
        canvas.pack(fill="both", expand=True)

        canvas.create_text(
            box_w // 2,
            box_h // 2,
            text=text,
            fill="black",
            font=("Segoe UI", 16, "bold"),
        )

        def _cleanup():
            try:
                if overlay.winfo_exists():
                    overlay.destroy()
            except Exception:
                pass
            try:
                self.root.attributes("-topmost", True)
                self.root.lift()
                # try:
                #     self.root.focus_force()
                # except Exception:
                #     pass

                def _restore():
                    try:
                        self.root.attributes("-topmost", prev_top_bool)
                    except Exception:
                        pass

                self.root.after(10, _restore)
            except Exception:
                pass

        overlay.after(duration_ms, _cleanup)

    def on_eetf_toggle(self):
        if self.eetf_var.get():
            self.open_eetf_window()
        else:
            self.eetf_args = {
                "source_max": 10000,
                "source_min": 0,
                "monitor_max": None,
                "monitor_min": None,
            }

    def open_eetf_window(self):
        if self._eetf_window and self._eetf_window.winfo_exists():
            self._eetf_window.lift()
            return

        win = tk.Toplevel(self.root)
        win.title("EETF 参数")
        win.geometry("360x330")
        win.resizable(True, True)
        self._eetf_window = win

        frm = tk.Frame(win, padx=14, pady=12)
        frm.pack(fill="both", expand=True)

        src_max_default = self.eetf_args.get("source_max", 10000)
        src_min_default = self.eetf_args.get("source_min", 0)
        mon_max_default = self.eetf_args.get("monitor_max")
        mon_min_default = self.eetf_args.get("monitor_min")

        v_src_max = tk.StringVar(
            value=str(src_max_default if src_max_default is not None else "10000")
        )
        v_src_min = tk.StringVar(
            value=str(src_min_default if src_min_default is not None else "0")
        )
        v_max = tk.StringVar(
            value=("" if mon_max_default is None else f"{mon_max_default}")
        )
        v_min = tk.StringVar(
            value=("" if mon_min_default is None else f"{mon_min_default}")
        )

        tk.Label(frm, text="源最大亮度 (nit)：", font=("Microsoft YaHei", 13)).grid(
            row=0, column=0, sticky="w", pady=6
        )
        e1 = ttk.Entry(frm, textvariable=v_src_max, width=18)
        e1.grid(row=0, column=1, sticky="w", pady=6)

        tk.Label(frm, text="源最小亮度 (nit)：", font=("Microsoft YaHei", 13)).grid(
            row=1, column=0, sticky="w", pady=6
        )
        e2 = ttk.Entry(frm, textvariable=v_src_min, width=18)
        e2.grid(row=1, column=1, sticky="w", pady=6)

        tk.Label(frm, text="显示器最大亮度 (nit)：", font=("Microsoft YaHei", 13)).grid(
            row=2, column=0, sticky="w", pady=6
        )
        e3 = ttk.Entry(frm, textvariable=v_max, width=18)
        e3.grid(row=2, column=1, sticky="w", pady=6)

        tk.Label(frm, text="显示器最小亮度 (nit)：", font=("Microsoft YaHei", 13)).grid(
            row=3, column=0, sticky="w", pady=6
        )
        e4 = ttk.Entry(frm, textvariable=v_min, width=18)
        e4.grid(row=3, column=1, sticky="w", pady=6)

        tk.Label(
            frm,
            text="提示：显示器最大/最小亮度留空时，将使用测量值。",
            font=("Microsoft YaHei", 13),
            fg="#333333",
            wraplength=320,
            justify="left",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))

        btns = tk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=2, pady=(14, 0), sticky="e")

        def on_ok():
            # 解析为浮点；允许空值 -> None
            try:
                smx = float(v_src_max.get())
                smn = float(v_src_min.get())
            except Exception:
                tk.messagebox.showerror("错误", "源亮度需为数字")
                return
            try:
                mmx = float(v_max.get()) if v_max.get().strip() != "" else None
                mmn = float(v_min.get()) if v_min.get().strip() != "" else None
            except Exception:
                tk.messagebox.showerror("错误", "显示器亮度需为数字或留空")
                return

            if smx <= 0 or smn < 0 or smn > smx:
                tk.messagebox.showerror(
                    "错误", "源亮度需大于0, 源最小亮度需小于等于源最大亮度"
                )
                return

            if mmx is not None and mmx <= 0:
                tk.messagebox.showerror("错误", "显示器最大亮度需大于 0")
                return
            if (mmx is not None and mmn is not None) and (mmn < 0 or mmn > mmx):
                tk.messagebox.showerror("错误", "最小亮度需在 [0, 最大亮度] 区间内")
                return

            self.eetf_args = {
                "source_max": smx,
                "source_min": smn,
                "monitor_max": mmx,
                "monitor_min": mmn,
            }
            logging.info("EETF 参数: %s", self.eetf_args)
            win.destroy()

        def on_cancel():
            self.eetf_var.set(False)
            win.destroy()

        ttk.Button(btns, text="确定", command=on_ok, width=10).pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(btns, text="取消", command=on_cancel, width=10).pack(side="right")

        win.bind("<Return>", lambda e: on_ok())
        win.bind("<Escape>", lambda e: on_cancel())

    def on_preview_toggle(self):
        """
        Implement a preview: loading a temporary ICC profile onto the selected display.
        before measurement load hdr_empty.icc as a preview; 
        after measurement preview the measured results 
        """
        state = self.preview_var.get()
        if state:
            if self.preview_icc_name:
                self.clean_icc(self.preview_icc_name)
                self.preview_icc_name = None
                time.sleep(self.icc_change_delay)
            self.preview_icc_name = "CC_" + str(uuid.uuid4())
            temp_dir = tempfile.gettempdir()
            icc_file_name = self.preview_icc_name + ".icc"
            path = os.path.join(temp_dir, icc_file_name)
            desc = [{"lang": "en", "country": "US", "text": self.preview_icc_name}]
            self.icc_handle.write_desc(desc)
            self.icc_handle.rebuild()
            self.icc_handle.save(path)
            self.set_icc(path)
            os.remove(path)
            time.sleep(self.icc_change_delay)
        else:
            if self.preview_icc_name:
                self.clean_icc(self.preview_icc_name)
                self.preview_icc_name = None
                time.sleep(self.icc_change_delay)

    def temp_save_icc(self, path):
        # debug only
        filename = os.path.basename(path)
        name_without_ext = os.path.splitext(filename)[0]
        desc = [{"lang": "en", "country": "US", "text": name_without_ext}]
        self.icc_handle.write_desc(desc)
        self.icc_handle.rebuild()
        self.icc_handle.save(path)

    @safe_call
    def calibrate_monitor(self):
        logging.info("开始校准")
        self.freeze_ui()
        hdr_status = self.human_display_config_map[self.monitor_var.get()]["color_work_status"]
        logging.info(f"所选屏幕工作状态: {hdr_status}")
        if hdr_status != "hdr":
            msg = "选中的屏幕未开启HDR，请在系统设置中开启HDR后再执行校准。"
            tk.messagebox.showerror("错误", msg)
            logging.error(msg)
            self.clean_color_rw_process()
            self.unfreeze_ui()
            return

        self.proc_color_write = ColorWriter()
        args = self.get_spotread_args()
        self.proc_color_reader = ColorReader(args)
        # 向子进程写入命令
        self.proc_color_write.write_rgb([800, 800, 800])
        msg = "将白色窗口移动到需要校准的屏幕上，调整窗口大小以确保能够完全覆盖校色仪，然后将校色仪放置在窗口上并点击确定。"
        answer = tk.messagebox.askokcancel("放置校色仪", msg)
        if not answer:
            logging.info("用户取消校准")
            self.clean_color_rw_process()
            self.unfreeze_ui()
            return

        self.init_base_icc()
        origin_preview_status = self.preview_var.get()

        self.icc_change_delay = 0.5
    
        def calibrate_control():
            self.measure_gamut_before()
            self.calibrate_pq()
            self.calibrate_chromaticity()
            # self.calibrate_white_by_lut()
            self.measure_gamut_after()
            
            return
            
            self.calibrate_chromaticity()

        def measure_control_cb(result):
            if isinstance(result, Exception):
                msg = f"matrix lut 生成失败: {result}"
                logging.error(msg)
                tk.messagebox.showerror("错误", msg)
            else:
                logging.info("matrix lut 已生成")
            self.unfreeze_ui()
            self.clean_color_rw_process()
            self.icc_change_delay = 0
            self.preview_var.set(origin_preview_status)
            if isinstance(result, Exception):
                raise result
            

        self.run_in_thread(calibrate_control, measure_control_cb)

    def measure_gamut_before(self):
        self.preview_var.set(True)
        max_lumi = 0
        min_lumi = 0
        for color, rgb in self.gamut_test_rgb.items():
            self.proc_color_write.write_rgb(rgb, delay=0.1)
            XYZ = self.proc_color_reader.read_XYZ()
            logging.info(f"色彩: {color} 测量值：{XYZ}")
            eetf = self.eetf_var.get()
            # If EETF is enabled, 
            # set the luminance parameters in the ICC 
            # to avoid double mapping.
            if color == "white":
                if eetf and self.eetf_args["monitor_max"] != 10000 and \
                    self.eetf_args["monitor_max"] is not None:
                    max_lumi = self.eetf_args["monitor_max"]
                else:
                    max_lumi = XYZ[1]
            if color == "black":
                if eetf and self.eetf_args["monitor_min"] != 0:
                    min_lumi = 0
                else:
                    min_lumi = XYZ[1]
            self.measure_gamut_xyz[color] = XYZ
            
            
        start_lumi = self.measure_gamut_xyz["black"][1]
        delta = max(start_lumi * 0.01, 0.0005)  # 可按需要调整阈值
        logging.info(f"开始二分查找激活黑: start_lumi={start_lumi} delta={delta}")

        def measure_gray(code):
            rgb = [code, code, code]
            self.proc_color_write.write_rgb(rgb, delay=0.1)
            XYZ = self.proc_color_reader.read_XYZ()
            logging.info(f"灰阶测试 code={code} RGB={rgb} 测量值: {XYZ}")
            return XYZ

        high_XYZ = measure_gray(255)
        if high_XYZ[1] <= start_lumi + delta:
            logging.info("未在 0-255 范围内检测到亮度显著提升，跳过激活黑判定")
            self.measure_gamut_xyz["min_activated_black"] = self.measure_gamut_xyz["black"]
        else:
            lo, hi = 1, 255
            found_code = None
            found_XYZ = None
            while lo <= hi:
                mid = (lo + hi) // 2
                XYZ = measure_gray(mid)
                if XYZ[1] > start_lumi + delta:
                    found_code = mid
                    found_XYZ = XYZ
                    hi = mid - 1  
                else:
                    lo = mid + 1
            if found_XYZ is not None:
                self.measure_gamut_xyz["min_activated_black"] = found_XYZ
                logging.info(f"测得激活黑电平: code={found_code} XYZ={found_XYZ}")
            else:
                logging.info("未找到激活黑（可能所有灰阶差异都低于阈值）")

        """
        FIXME 
        The full‑frame luminance of an OLED may be lower than the maximum luminance of a patch, 
        but currently I can't get dogegen to display in fullscreen.
        """
        peak_lumi = max_lumi
        logging.info(f"写入最大亮度{max_lumi},全帧最大亮度{peak_lumi}, 最低亮度{min_lumi}")
        self.MHC2["min_luminance"] = min_lumi
        self.MHC2["peak_luminance"] = peak_lumi
        self.icc_handle.write_XYZType("lumi", [[max_lumi, max_lumi, max_lumi]])
        
        r = l2_normalize_XYZ(self.measure_gamut_xyz["red"])
        g = l2_normalize_XYZ(self.measure_gamut_xyz["green"])
        b = l2_normalize_XYZ(self.measure_gamut_xyz["blue"])
        w = l2_normalize_XYZ(self.measure_gamut_xyz["white_200nit"])
        logging.info(f"写入RGBW XYZ:\n {r}\n {g}\n {b}\n {w}")
        self.icc_handle.write_XYZType("rXYZ", [r])
        self.icc_handle.write_XYZType("gXYZ", [g])
        self.icc_handle.write_XYZType("bXYZ", [b])
        self.icc_handle.write_XYZType("wtpt", [w])
        
        self.icc_handle.write_MHC2(self.MHC2)

        logging.info("色域测量完成")
    
    def measure_gamut_after(self):
        self.preview_var.set(True)
        max_lumi = 0
        min_lumi = 0
        for color, rgb in self.gamut_test_rgb.items():
            self.proc_color_write.write_rgb(rgb, delay=0.1)
            XYZ = self.proc_color_reader.read_XYZ()
            logging.info(f"色彩: {color} 测量值：{XYZ}")
            if color == "white":
                max_lumi = XYZ[1]
            if color == "black":
                min_lumi = XYZ[1]
            self.measure_gamut_xyz[color] = XYZ

        """
        FIXME 
        The full‑frame luminance of an OLED may be lower than the maximum luminance of a patch, 
        but currently I can't get dogegen to display in fullscreen.
        """
        if self.bright_var.get():
            lut = generate_inversed_lut(generate_bright_pq_lut())
            bright_lut_inv = {"red_lut": lut.tolist(),
                              "green_lut": lut.tolist(),
                              "blue_lut": lut.tolist()}

            white_rgb_fix = apply_lut(XYZ_to_BT2020_PQ_rgb(self.measure_gamut_xyz["white"]/10000), bright_lut_inv)
            black_rgb_fix = apply_lut(XYZ_to_BT2020_PQ_rgb(self.measure_gamut_xyz["black"]/10000), bright_lut_inv)
            white_xyz_fix = BT2020_PQ_rgb_to_XYZ(white_rgb_fix)
            black_xyz_fix = BT2020_PQ_rgb_to_XYZ(black_rgb_fix)
            logging.info(f"亮度修正后白点RGB: {white_rgb_fix} XYZ: {white_xyz_fix}")
            logging.info(f"亮度修正后黑点RGB: {black_rgb_fix} XYZ: {black_xyz_fix}")
            max_lumi = white_xyz_fix[1]*10000
            min_lumi = black_xyz_fix[1]*10000
        peak_lumi = max_lumi
        logging.info(f"写入最大亮度{max_lumi},全帧最大亮度{peak_lumi}, 最低亮度{min_lumi}")
        self.MHC2["min_luminance"] = min_lumi
        self.MHC2["peak_luminance"] = peak_lumi
        self.icc_handle.write_XYZType("lumi", [[max_lumi, max_lumi, max_lumi]])
        
        r = l2_normalize_XYZ(self.measure_gamut_xyz["red"])
        g = l2_normalize_XYZ(self.measure_gamut_xyz["green"])
        b = l2_normalize_XYZ(self.measure_gamut_xyz["blue"])
        w = l2_normalize_XYZ(self.measure_gamut_xyz["white_200nit"])
        logging.info(f"写入RGBW XYZ:\n {r}\n {g}\n {b}\n {w}")
        self.icc_handle.write_XYZType("rXYZ", [r])
        self.icc_handle.write_XYZType("gXYZ", [g])
        self.icc_handle.write_XYZType("bXYZ", [b])
        self.icc_handle.write_XYZType("wtpt", [w])
        
        self.icc_handle.write_MHC2(self.MHC2)

        logging.info("色域测量完成")

    def calibrate_chromaticity(self):
        # measure and build matrix
        self.preview_var.set(True)
        logging.info("开始测量彩色并生成矩阵")
        self.target_xyz = get_srgb_calibrate_XYZ_suit(self.measure_gamut_xyz)
        if self.color_space_var.get() == "sRGB+DisplayP3":
            self.target_xyz.extend(get_P3D65_calibrate_XYZ_suit(self.measure_gamut_xyz))
        white_points = get_D65_white_calibrate_test_XYZ_suit(self.measure_gamut_xyz)
        self.target_xyz.extend(white_points)
        self.measured_xyz = []
        i = 1
        l = len(self.target_xyz)
        for itm in self.target_xyz:
            pq = XYZ_to_BT2020_PQ_rgb(itm)
            rgb = (pq * 1023).round().astype(int)
            self.proc_color_write.write_rgb(rgb, delay=0.1)
            XYZ = self.proc_color_reader.read_XYZ()
            XYZ = [float(itm) / 10000 for itm in XYZ]
            logging.info(f"({i}/{l}) 色彩: {rgb} {itm} 测量值：{XYZ}")
            self.measured_xyz.append(XYZ)
            i += 1
        matrix = fit_XYZ2XYZ_wlock_dropY(self.measured_xyz, self.target_xyz,self.measured_xyz[-1], self.target_xyz[-1])
        # matrix = fit_XYZ2XYZ(self.measure_convert_xyz, self.convert_xyz)
        ori_matrix = np.array(self.MHC2["matrix"]).reshape(3, 3)
        matrix2 = ori_matrix @ matrix
        self.MHC2["matrix"] = matrix2.flatten().tolist()
        self.icc_handle.write_MHC2(self.MHC2)
        logging.info(f"测量矩阵结束，测得矩阵: {self.MHC2['matrix']}")
    
    def calibrate_white_by_lut(self):
        logging.info("开始校准灰阶色度至D65")
        MEASURE_POINTS_COUNT = 32
        pq_lut_origin = {"red": copy.deepcopy(self.MHC2["red_lut"]),
                         "green": copy.deepcopy(self.MHC2["green_lut"]),
                         "blue": copy.deepcopy(self.MHC2["blue_lut"])}
        max_nit = 0
        self.proc_color_write.write_rgb([1023,1023,1023], delay=0.3)
        XYZ = self.proc_color_reader.read_XYZ()
        max_nit = XYZ[1]
        min_nit = 10
        logging.info(f"测得显示器最大亮度: {max_nit} nit")
        measure_points_t = np.linspace(0, 1023, MEASURE_POINTS_COUNT, dtype=int)
        measure_points = [i for i in measure_points_t if min_nit < pq_eotf(i / 1023) < max_nit*0.8]
        
        measure_points = [719]
        
        measure_points.insert(0, 0)
        measure_points.append(1023)
        logging.info("本次测量灰阶点{}个: {}".format(len(measure_points), measure_points))
        scales = []
        for grayscale in measure_points:
            nit = pq_eotf(grayscale / 1023)
            if nit > max_nit:
                logging.info(f"灰阶{grayscale} 目标nit{nit} 超过显示器最大亮度的90% {max_nit*0.9}, 跳过")
                scales.append({"grayscale":grayscale, "red": None, "green": None, "blue": None})
                continue
            if grayscale == 0:
                logging.info(f"灰阶{grayscale} 目标nit{nit} 为0, 跳过")
                scales.append({"grayscale":grayscale, "red": None, "green": None, "blue": None})
                continue
            self.MHC2["red_lut"]     = copy.deepcopy(pq_lut_origin["red"])
            self.MHC2["green_lut"]   = copy.deepcopy(pq_lut_origin["green"])
            self.MHC2["blue_lut"]    = copy.deepcopy(pq_lut_origin["blue"])
            self.MHC2["entry_count"] = len(pq_lut_origin["red"])
            self.icc_handle.write_MHC2(self.MHC2)
            rgb_pq = [int(grayscale)] * 3
            target_rgb_pq = np.array(rgb_pq)/1023
            channel_scale = {"grayscale": grayscale, "red": 1, "green": 1, "blue": 1}
            for loop_count in range(2):
                for idx, channel in enumerate(["red","green", "blue"]):
                    logging.info(f"调整{channel}通道")
                    total_scale = channel_scale[channel]
                    current_scale = 1
                    step = 0.00390625
                    target = target_rgb_pq[idx]
                    done = False
                    last_ratio = None
                    while 1:
                        self.preview_var.set(True)
                        logging.info(f"灰阶{grayscale}循环{loop_count}通道{channel} 目标：PQ->{target_rgb_pq} {rgb_pq}")
                        self.proc_color_write.write_rgb(rgb_pq, delay=0.1)
                        measure_xyz = np.array(self.proc_color_reader.read_XYZ())
                        measure_rgb_pq = XYZ_to_BT2020_PQ_rgb(measure_xyz/10000)
                        measure = measure_rgb_pq[idx]
                        ratio = measure / target
                        total_ratio = (measure_rgb_pq / target_rgb_pq).round(4).tolist()
                        if last_ratio is None:
                            last_ratio = ratio
                        logging.info(f"灰阶{grayscale}循环{loop_count}通道{channel} 实测:XYZ->{measure_xyz.round(4).tolist()} PQ->{measure_rgb_pq} \n"
                                     f"ratio->{round(ratio, 4)} total_ratio->{total_ratio} scale->{round(current_scale, 4)}")

                        if ratio > 1:
                            if current_scale > 1:
                                # 加超了
                                last = abs(last_ratio - 1)
                                current = abs(ratio - 1)
                                if current >= last:
                                    current_scale -= step
                                done = True
                            else:
                                current_scale -= step
                        elif ratio < 1:
                            if current_scale < 1:
                                # 减超了
                                last = abs(last_ratio - 1)
                                current = abs(ratio - 1)
                                if current >= last:
                                    current_scale += step
                                done = True
                            else:
                                current_scale += step
                        else:
                            done = True
                        scale = total_scale + current_scale - 1
                        pq_lut_scale = lut_scale(pq_lut_origin[channel], scale)
                        pq_lut_scale[0] = 0
                        self.MHC2[f"{channel}_lut"] = pq_lut_scale.tolist()
                        self.icc_handle.write_MHC2(self.MHC2)
                        last_ratio = ratio
                        if done:
                            channel_scale[channel] = scale
                            logging.info(f"灰阶{grayscale}循环{loop_count} {channel}通道调整完成, scale {scale}")
                            break
                logging.info(f"\n\n\n\n灰阶{grayscale}循环{loop_count} 校准结束, red {channel_scale['red']} green {channel_scale['green']} blue {channel_scale['blue']}")
            scales.append(channel_scale)
            self.proc_color_write.write_rgb(rgb_pq, delay=0.3)
            measure_xyz = np.array(self.proc_color_reader.read_XYZ())
            measure_rgb_pq = XYZ_to_bt2020_linear(measure_xyz/10000)
            logging.info(f"灰阶{grayscale} 校准后实测: \nCIEXYZ->{measure_xyz} \n线性RGB:{target_rgb_pq}->{measure_rgb_pq}")
        logging.info(f"所有灰阶校准完成, scales: {scales}")
        last_activated_scale = None
        target_pq_lut_red = copy.deepcopy(pq_lut_origin["red"])
        target_pq_lut_green = copy.deepcopy(pq_lut_origin["green"])
        target_pq_lut_blue = copy.deepcopy(pq_lut_origin["blue"])
        if scales[0]["grayscale"] == 0:
            scales[0] = copy.deepcopy(scales[1])
            scales[0]["grayscale"] = 0
        lrscale = None
        lgscale = None
        lbscale = None
        lgrayscale = None
        for scale in scales:
            cgrayscale = scale["grayscale"]
            if scale["red"] is None:
                crscale = last_activated_scale["red"]
                cgscale = last_activated_scale["green"]
                cbscale = last_activated_scale["blue"]
            else:
                last_activated_scale = scale
                crscale = scale["red"]
                cgscale = scale["green"]
                cbscale = scale["blue"]
            if lgrayscale is None:
                lrscale = crscale
                lgscale = cgscale
                lbscale = cbscale
                lgrayscale = 0
            logging.info(f"灰阶{cgrayscale} RED插值区间 {lgrayscale}-{cgrayscale} scale {lrscale}-{crscale}")
            logging.info(f"灰阶{cgrayscale} GREEN插值区间 {lgrayscale}-{cgrayscale} scale {lgscale}-{cgscale}")
            logging.info(f"灰阶{cgrayscale} BLUE插值区间 {lgrayscale}-{cgrayscale} scale {lbscale}-{cbscale}")
            for idx in range(lgrayscale, cgrayscale):
                
                num = cgrayscale - lgrayscale
                rstep = (crscale - lrscale) / num if num != 0 else 0
                gstep = (cgscale - lgscale) / num if num != 0 else 0
                bstep = (cbscale - lbscale) / num if num != 0 else 0
                r = idx - lgrayscale
                target_pq_lut_red[idx] = lut_scale(target_pq_lut_red[idx], lrscale + r*rstep) 
                target_pq_lut_green[idx] = lut_scale(target_pq_lut_green[idx], lgscale + r*gstep)
                target_pq_lut_blue[idx] = lut_scale(target_pq_lut_blue[idx], lbscale + r*bstep)

            target_pq_lut_red[cgrayscale] = lut_scale(target_pq_lut_red[cgrayscale], crscale)
            target_pq_lut_green[cgrayscale] = lut_scale(target_pq_lut_green[cgrayscale], cgscale)
            target_pq_lut_blue[cgrayscale] = lut_scale(target_pq_lut_blue[cgrayscale], cbscale)

            lrscale = crscale
            lgscale = cgscale
            lbscale = cbscale
            lgrayscale = cgrayscale
        self.MHC2["red_lut"]     = target_pq_lut_red
        self.MHC2["green_lut"]   = target_pq_lut_green
        self.MHC2["blue_lut"]    = target_pq_lut_blue
        self.MHC2["entry_count"] = len(target_pq_lut_red)
        self.icc_handle.write_MHC2(self.MHC2)

        return
    
    def calibrate_pq(self, eetf=False):
        self.preview_var.set(True)
        logging.info("开始校准PQ灰阶曲线")
        self.measured_pq["red"] = []
        self.measured_pq["green"] = []
        self.measured_pq["blue"] = []
        num = int(self.pq_points_var.get())
        for idx, grayscale in enumerate(np.linspace(0, 1023, num, endpoint=True).round().astype(np.int32)):
            grayscale = int(grayscale)
            rgb = [grayscale, grayscale, grayscale]
            self.proc_color_write.write_rgb(rgb, delay=0.03)
            XYZ = self.proc_color_reader.read_XYZ()
            rgb_measured = XYZ_to_BT2020_PQ_rgb(XYZ/10000)
            logging.info(f"({idx+1}/{num}) 输出RGB: {rgb} 测得XYZ: {XYZ} RGB: {rgb_measured*1023}")
            self.measured_pq["red"].append(float(rgb_measured[0]))
            self.measured_pq["green"].append(float(rgb_measured[1]))
            self.measured_pq["blue"].append(float(rgb_measured[2]))

        eetf_args = None
        if eetf:
            eetf_args = copy.deepcopy(self.eetf_args)
            if self.eetf_args["monitor_max"] is None:
                eetf_args["monitor_max"] = self.measure_gamut_xyz["white"][1]
            if self.eetf_args["monitor_min"] is None:
                eetf_args["monitor_min"] = self.measure_gamut_xyz["min_activated_black"][1]
        target_pq = self.MHC2
        if self.bright_var.get():
            target_pq = {"red_lut": generate_bright_pq_lut().tolist(),
                         "green_lut": generate_bright_pq_lut().tolist(),
                         "blue_lut": generate_bright_pq_lut().tolist()}
        
        red_lut = generate_mhc2_lut_from_measured_pq(
            self.measured_pq["red"], target_pq=target_pq["red_lut"])
        blue_lut = generate_mhc2_lut_from_measured_pq(
            self.measured_pq["blue"], target_pq=target_pq["blue_lut"])
        green_lut = generate_mhc2_lut_from_measured_pq(
            self.measured_pq["green"], target_pq=target_pq["green_lut"])
        
        
            
            # red_lut = generate_mhc2_lut_from_measured_pq(
            #     red_lut, target_pq=target_pq["red_lut"])
            # blue_lut = generate_mhc2_lut_from_measured_pq(
            #     blue_lut, target_pq=target_pq["blue_lut"])
            # green_lut = generate_mhc2_lut_from_measured_pq(
            #     green_lut, target_pq=target_pq["green_lut"])

        self.MHC2["red_lut"] = red_lut.tolist()
        self.MHC2["green_lut"] = green_lut.tolist()
        self.MHC2["blue_lut"] = blue_lut.tolist()
        self.MHC2["entry_count"] = len(red_lut)
        self.icc_handle.write_MHC2(self.MHC2)
        logging.info(f"测量PQ LUT结束")

    
    @safe_call
    def measure_pq(self):
        self.proc_color_write = ColorWriter()
        args = self.get_spotread_args()
        self.proc_color_reader = ColorReader(args)
        self.proc_color_write.write_rgb([800, 800, 800])
        answer = tk.messagebox.askokcancel(
            "注意",
            "如果你想测量校准后但未保存和加载的配置数据,请先打开预览开关。\n\n"
            "调整白色窗口大小位置后将校色仪放置在窗口上，然后点击确认",
        )
        if not answer:
            self.clean_color_rw_process()
            logging.info("用户取消测量")
            return
        self.freeze_ui()
        logging.info("开始测量PQ响应")
        def m():
            target_white_xyz = []
            target_pq = []
            measured_pq = []
            measured_white_xyz = []
            num = 256

            for idx, grayscale in enumerate(np.linspace(0, 1023, num, endpoint=True).round().astype(np.int32)):
                grayscale = int(grayscale)
                pq = grayscale / 1023
                target_white_xyz.append(BT2020_PQ_rgb_to_XYZ([pq, pq, pq]))
                target_pq.append(pq)
                rgb = [grayscale, grayscale , grayscale]
                self.proc_color_write.write_rgb(rgb, delay=0.1)
                XYZ = np.array(self.proc_color_reader.read_XYZ())
                logging.info(f"({idx+1}/{num}) 测量RGB: {rgb} 测量值: {XYZ}")
                measured_white_xyz.append([itm/10000 for itm in XYZ])
                nit = float(XYZ[1])
                measured_pq.append(float(pq_oetf(nit)))
            
            max_nit = max([itm[1] for itm in measured_white_xyz])
            color_gamut = {"red": xyY_to_XYZ([*BT2020_xy["red"], max_nit*10000]),
                           "green": xyY_to_XYZ([*BT2020_xy["green"], max_nit*10000]),
                           "blue": xyY_to_XYZ([*BT2020_xy["blue"], max_nit*10000]),
                           "white": xyY_to_XYZ([*BT2020_xy["white"], max_nit*10000])}
            target_colored_xyz = get_srgb_measure_XYZ_suit(color_gamut)
            # target_colored_xyz.extend(get_P3D65_test_XYZ_suit(color_gamut))
            measured_colored_xyz = []
            num = len(target_colored_xyz)
            logging.info("开始测量彩色点")
            for idx, xyz in enumerate(target_colored_xyz):
                rgb = (XYZ_to_BT2020_PQ_rgb(xyz) * 1023).round().astype(int).tolist()
                self.proc_color_write.write_rgb(rgb, delay=0.1)
                XYZ = np.array(self.proc_color_reader.read_XYZ())
                logging.info(f"({idx+1}/{num}) 测量RGB: {rgb} 测量值: {XYZ}")
                measured_colored_xyz.append([itm/10000 for itm in XYZ])
            
            logging.info(f"测量完成: {measured_colored_xyz}")

            return {
                "target_xyz": np.array(target_white_xyz),
                "measured_xyz": np.array(measured_white_xyz),
                "target_pq": np.array(target_pq),
                "measured_pq": np.array(measured_pq),
                "target_colored_xyz": np.array(target_colored_xyz),
                "measured_colored_xyz": np.array(measured_colored_xyz),
            }
        
        def cb(result):
            self.unfreeze_ui()
            self.clean_color_rw_process()
            if isinstance(result, Exception):
                msg = f"测量PQ响应失败: {result}"
                logging.error(msg)
                tk.messagebox.showerror("错误", msg)
                raise result
            else:
                logging.info("测量PQ响应完成")
                try:
                    self._show_pq_plot(result["target_pq"], result["measured_pq"])
                except Exception as e:
                    logging.error(f"绘制PQ曲线失败: {e}")
            min_care_nit = max(1/10000, result["measured_xyz"][0][1] * 1.1)
            max_care_nit = result["measured_xyz"][-1][1] * 0.9
            logging.info(f"测得最小亮度: {min_care_nit*10000} nit, 最大亮度: {max_care_nit*10000} nit")
            white_de_result = []
            logging.info("开始计算灰阶deltaE_ITP")
            for idx in range(len(result["measured_xyz"])):
                if min_care_nit < result["measured_xyz"][idx][1] < max_care_nit:
                    t = result["target_xyz"][idx]
                    m = result["measured_xyz"][idx]
                    de = XYZdeltaE_ITP(t, m)
                    white_de_result.append([t, m, de])
                    logging.info(f"目标: {t} 测量: {m} dE_ITP: {de.round(2)}")
            colored_de_result = []
            logging.info("开始计算彩色deltaE_ITP")
            for idx in range(len(result["measured_colored_xyz"])):
                t = result["target_colored_xyz"][idx]
                m = result["measured_colored_xyz"][idx]
                de = XYZdeltaE_ITP(t, m)
                colored_de_result.append([t, m, de])
                logging.info(f"目标: {t} 测量: {m} dE_ITP: {de.round(2)}")
            white_de_avg = np.mean([itm[2] for itm in white_de_result]).round(2)
            white_de_max = np.max([itm[2] for itm in white_de_result]).round(2)
            colored_de_avg = np.mean([itm[2] for itm in colored_de_result]).round(2)
            colored_de_max = np.max([itm[2] for itm in colored_de_result]).round(2)
            logging.info(f"亮度范围({round(min_care_nit*10000,2)}-{round(max_care_nit*10000, 2)}内,灰阶平均deltaE_ITP: {white_de_avg},最大deltaE_ITP: {white_de_max}")
            logging.info(f"200nit D65白点下,彩色平均deltaE_ITP: {colored_de_avg},最大deltaE_ITP: {colored_de_max}")

        self.run_in_thread(m, cb)
    
    def _show_pq_plot(self, target_pq, measured_pq):
        """
        绘制 PQ 曲线（自适应窗口大小）:
        - x 轴: 索引/(N-1)*100 (%), 0..100
        - y 轴: PQ*100 (%), 0..100
        在同一图中绘制 target_pq 与 measured_pq
        """
        tp = np.asarray(target_pq, dtype=float).flatten()
        mp = np.asarray(measured_pq, dtype=float).flatten()
        if tp.size != mp.size or tp.size < 2:
            tk.messagebox.showwarning("提示", "数据不足以绘图")
            return
        n = tp.size

        win = tk.Toplevel(self.root)
        win.title("PQ测量曲线")
        w, h = 760, 460
        win.geometry(f"{w}x{h}")
        frm = tk.Frame(win, bg="white")
        frm.pack(fill="both", expand=True, padx=8, pady=8)

        canvas = Canvas(frm, bg="white", highlightthickness=0)
        canvas.pack(fill="both", expand=True)

        def draw():
            canvas.delete("all")
            # 当前画布大小
            cw = max(200, canvas.winfo_width())
            ch = max(160, canvas.winfo_height())
            margin_l = 60
            margin_r = 20
            margin_t = 20
            margin_b = 50
            x0, y0 = margin_l, ch - margin_b
            x1, y1 = cw - margin_r, margin_t
            plot_w = max(1, x1 - x0)
            plot_h = max(1, y0 - y1)

            # 轴线
            canvas.create_line(x0, y0, x1, y0, fill="#444")  # x 轴
            canvas.create_line(x0, y0, x0, y1, fill="#444")  # y 轴

            # 刻度与标签（0..100 每 20）
            for p in range(0, 101, 20):
                # x 轴刻度
                xx = x0 + plot_w * (p / 100.0)
                canvas.create_line(xx, y0, xx, y0 + 5, fill="#444")
                canvas.create_text(xx, y0 + 18, text=str(p), fill="#444", font=("Segoe UI", 10))
                # y 轴刻度
                yy = y0 - plot_h * (p / 100.0)
                canvas.create_line(x0 - 5, yy, x0, yy, fill="#444")
                canvas.create_text(x0 - 28, yy, text=str(p), fill="#444", font=("Segoe UI", 10))

            # 标签
            canvas.create_text((x0 + x1) // 2, y1 - 6, text="PQ (%)", fill="#333", font=("Microsoft YaHei", 11))
            canvas.create_text((x0 + x1) // 2, y0 + 35, text="位置 (%)", fill="#333", font=("Microsoft YaHei", 11))

            def to_points(arr):
                pts = []
                for i, v in enumerate(arr):
                    fx = i / (n - 1)                  # 0..1
                    xx = x0 + fx * plot_w
                    fy = np.clip(float(v), 0.0, 1.0)  # v in [0,1]
                    yy = y0 - (fy * plot_h)
                    pts.append((xx, yy))
                return pts

            pts_t = to_points(tp)
            pts_m = to_points(mp)

            def draw_poly(points, color, width=2):
                flat = []
                for (px, py) in points:
                    flat.extend([px, py])
                if len(flat) >= 4:
                    canvas.create_line(*flat, fill=color, width=width, smooth=True)

            draw_poly(pts_t, "#1f77b4", 2)  # target: 蓝
            draw_poly(pts_m, "#d62728", 2)  # measured: 红

            # 图例
            box_w = 160
            box_h = 44
            canvas.create_rectangle(x1 - box_w, y1 + 8, x1 - 20, y1 + 8 + box_h, outline="#ccc", fill="#fff")
            canvas.create_line(x1 - box_w + 10, y1 + 20, x1 - box_w + 40, y1 + 20, fill="#1f77b4", width=2)
            canvas.create_text(x1 - box_w + 50, y1 + 20, text="target_pq", anchor="w", fill="#333", font=("Segoe UI", 10))
            canvas.create_line(x1 - box_w + 10, y1 + 36, x1 - box_w + 40, y1 + 36, fill="#d62728", width=2)
            canvas.create_text(x1 - box_w + 50, y1 + 36, text="measured_pq", anchor="w", fill="#333", font=("Segoe UI", 10))

        # 绑定自适应重绘
        canvas.bind("<Configure>", lambda e: draw())
        # 初次绘制
        win.after(10, draw)
    
    @safe_call
    def measure_color_accuracy(self):
        with open("verify_video_extended_smpte2084_1000_p3_2020.ti1", "r") as f:
            lines = f.readlines()
        data_section = False
        rgb_list = []
        xyz_list = []
        for line in lines:
            line = line.strip()
            if line == "BEGIN_DATA":
                data_section = True
                continue
            elif line == "END_DATA":
                break
            if data_section:
                parts = line.split()
                t = list(map(float, parts))
                xyz = [itm * 6 / 10000 for itm in t[4:7]]
                xyz_list.append(xyz)
                rgb_list.append(
                    [
                        round(float(itm) * 1023)
                        for itm in XYZ_to_BT2020_PQ_rgb(xyz).tolist()
                    ]
                )

        self.proc_color_write = ColorWriter()
        args = self.get_spotread_args()
        self.proc_color_reader = ColorReader(args)

        self.proc_color_write.write_rgb([800, 800, 800])
        answer = tk.messagebox.askokcancel(
            "注意",
            "如果你想测量校准后但未保存和加载的配置数据,请先打开预览开关。\n\n"
            "调整白色窗口大小位置后将校色仪放置在窗口上，然后点击确认",
        )
        if not answer:
            self.clean_color_rw_process()
            logging.info("用户取消测量")
            return
        def cb(result):
            pass
        def m():
            real_xyz = []
            logging.info(f"测量的RGB列表: {rgb_list}")
            l = len(rgb_list)
            for i, rgb in enumerate(rgb_list):
                self.proc_color_write.write_rgb(rgb, delay=0.1)
                XYZ = self.proc_color_reader.read_XYZ()
                logging.info(f"({i}/{l}) 测量RGB: {rgb} {xyz_list[i]} 测量值: {XYZ}")
                real_xyz.append([float(itm) / 10000 for itm in XYZ])

            self.clean_color_rw_process()
            de_list = []
            for idx in range(len(real_xyz)):
                de = XYZdeltaE_ITP(real_xyz[idx], xyz_list[idx])
                de_list.append(de)
                logging.info(f"{xyz_list[idx]}: {de}")
            logging.info(f"测量的XYZ列表: {xyz_list}")
            logging.info(f"测量的真实XYZ值: {real_xyz}")
            logging.info(f"测量的色差: {de_list}")
            logging.info(f"平均色差: {sum(de_list) / len(de_list)}，最大色差: {max(de_list)}")
            return rgb_list, xyz_list
        self.run_in_thread(m, cb)

    def generate_and_save_icc(self):
        path = filedialog.asksaveasfilename(
            initialdir=os.path.expanduser("~/Documents"),
            title="保存 ICC 文件",
            defaultextension=".icc",
            filetypes=[("ICC 文件", "*.icc"), ("所有文件", "*.*")],
        )
        if not path:
            return
        filename = os.path.basename(path)
        name_without_ext = os.path.splitext(filename)[0]
        desc = [{"lang": "en", "country": "US", "text": name_without_ext}]
        self.icc_handle.write_desc(desc)
        self.icc_handle.rebuild()
        self.icc_handle.save(path)
        if self.icc_set_var.get():
            self.preview_var.set(False)
            self.set_icc(path)


if __name__ == "__main__":
    root = tk.Tk()
    app = HDRCalibrationUI(root)
    root.mainloop()

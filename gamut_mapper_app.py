import tkinter as tk
import os
import copy
import re
import tempfile
from tkinter import ttk, messagebox,filedialog
from meta_data import *
from icc_rw import ICCProfile
from win_display import get_all_display_config,get_monitor_rect_by_gdi_name,cp_add_display_association
from win_display import install_icc,uninstall_icc,cp_remove_display_association, luid_from_dict
from convert_utils import *
from matrix import *
from lut import convert_transfer
from monitor_info import get_edid_info

class GamutMapperApp(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.displays_config = get_all_display_config()
        self.human_display_config_map = {}
        for itm in self.displays_config:
            product_id = itm["target"]["device_path"].split("#")[1]
            friendly_name = itm["target"].get("friendly_name") or "none"
            human_dname = f"{itm['path_index']}_{friendly_name}_{product_id}"
            self.human_display_config_map[human_dname] = copy.deepcopy(itm)
            self.human_display_config_map[human_dname]["monitor_rect"] = get_monitor_rect_by_gdi_name(itm["source"]["gdi_name"])
            self.human_display_config_map[human_dname]["color_work_status"] = "sdr"
            t = itm["target"]["device_path"].split("\\")[-1].split("#")[:-1]
            self.human_display_config_map[human_dname]["pnp_device_id"] = "\\".join(t)
            if self.human_display_config_map[human_dname]["target"]["advanced_color"]["enabled"]:
                self.human_display_config_map[human_dname]["color_work_status"] = "hdr"
                if self.human_display_config_map[human_dname]["target"]["advanced_color"]["wide_color_enforced"]:
                    self.human_display_config_map[human_dname]["color_work_status"] = "sdr_acm"
        
        # 警告跳过记录（键为 "monitor::tag"）
        self._warn_skip = {}
        
        # 默认警告文本（你可以在外部修改这些属性的文本）
        self.warn_text_adv_enabled = "SDR下自动色彩管理处于开启状态。\n如果显示器EDID色域数据准确，开启自动色彩管理是最佳选择。\n如果不准确，测量后修改窗口的RGBW xy坐标位置后生成\n该程序将生成一个校色文件来覆盖EDID中的色域定义以适配自动色彩管理"
        self.warn_text_adv_supported_disabled = "ADV supported but disabled warning text (edit me)"
        
        self.title("色域映射工具")
        self.resizable(True, True)

        # 状态变量
        self.gamut_var = tk.StringVar(value="sRGB")
        self.tone_var = tk.StringVar(value="不做修改")
        # 新增：显示器选择
        self.monitor_list = list(self.human_display_config_map.keys())
        self.monitor_list.sort()
        self.monitor_var = tk.StringVar(value=self.monitor_list[0] if self.monitor_list else "No Monitor Found")

        self.edid_xy_vars = {
            "R": tk.StringVar(value=""),
            "G": tk.StringVar(value=""),
            "B": tk.StringVar(value=""),
            "W": tk.StringVar(value=""),
        }
        self.gamma_var = tk.StringVar(value="")

        self._build_ui()
        # 窗口居中
        self._center_window(380, 340)

    def _center_window(self, w=340, h=340):
        # 计算屏幕中心并设置窗口位置
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        pad = {"padx": 14, "pady": 10}
        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, **pad)

        # 显示器选择（占位，放最上面）
        ttk.Label(frm, text="显示器：", font=("Microsoft YaHei", 11)).grid(row=0, column=0, sticky="w") 
        monitor_box = ttk.Combobox(
            frm,
            textvariable=self.monitor_var,
            values=self.monitor_list,
            state="readonly", width=16
        )
        monitor_box.grid(row=0, column=1, sticky="w")
        monitor_box.bind("<<ComboboxSelected>>", self.on_display_change)

        # 目标色域
        ttk.Label(frm, text="目标色域：", font=("Microsoft YaHei", 11)).grid(row=1, column=0, sticky="w")
        gamut_box = ttk.Combobox(
            frm,
            textvariable=self.gamut_var,
            values=["sRGB", "BT2020", "P3D65", "AdobeRGB"],
            state="readonly", width=16
        )
        gamut_box.grid(row=1, column=1, sticky="w")

        # 目标色调曲线
        ttk.Label(frm, text="修改色调曲线：", font=("Microsoft YaHei", 11)).grid(row=2, column=0, sticky="w")
        tone_box = ttk.Combobox(
            frm,
            textvariable=self.tone_var,
            values=["不做修改", "sRGB", "gamma 2.0", "gamma 2.2", "gamma 2.4", "HDR-PQ"],
            state="readonly", width=16
        )
        tone_box.grid(row=2, column=1, sticky="w")
        # 按钮
        btns = ttk.Frame(frm)
        btns.grid(row=3, column=0, columnspan=2, sticky="w", pady=(18, 0)) 
        ttk.Button(btns, text="生成并加载icc", command=self.on_generate, width=12).pack(side="left")
        ttk.Button(btns, text="取消加载", command=self.on_cancel_load, width=12).pack(side="left", padx=(8, 0))
        
        edid_frame = ttk.LabelFrame(frm, text="EDID RGBW (x,y) + Gamma")
        edid_frame.grid(row=4, column=0, columnspan=2, sticky="we", padx=0, pady=(6, 6))
        edid_frame.columnconfigure(2, weight=1)
        self._add_xy_onefield_row(edid_frame, 0, "R", self.edid_xy_vars["R"])
        self._add_xy_onefield_row(edid_frame, 1, "G", self.edid_xy_vars["G"])
        self._add_xy_onefield_row(edid_frame, 2, "B", self.edid_xy_vars["B"])
        self._add_xy_onefield_row(edid_frame, 3, "W", self.edid_xy_vars["W"])

        ttk.Label(edid_frame, text="Gamma:").grid(row=4, column=0, sticky="w", padx=(8, 4), pady=6)
        ttk.Entry(edid_frame, textvariable=self.gamma_var, width=14).grid(row=4, column=1, sticky="w", padx=(4, 12))
        ttk.Button(edid_frame, text="刷新EDID", width=10, command=self.read_edid_to_fields)\
            .grid(row=0, column=3, rowspan=2, sticky="ne", padx=(12, 6), pady=6)

        # 初始化时填充一次
        self.after(100, self.read_edid_to_fields)
    
    def _add_xy_onefield_row(self, parent, row: int, name: str, var: tk.StringVar):
        ttk.Label(parent, text=f"{name}:").grid(row=row, column=0, sticky="w", padx=(8, 4), pady=6)
        ttk.Entry(parent, textvariable=var, width=22).grid(row=row, column=1, columnspan=2, sticky="w", padx=(4, 12))

    # 选择显示器事件占位：当前仅刷新 EDID 区域
    def on_display_change(self, event=None):
        self.read_edid_to_fields()
        
    # 读取所选显示器的 EDID 并填充 UI（写回由你实现）
    def read_edid_to_fields(self):
        p = self.get_selected_pnp_device_id()
        if not p:
            self._fill_xy_fields(None)
            return
        try:
            info = get_edid_info(p)
        except Exception:
            info = None
        self._fill_xy_fields(info)

    # 将 EDID 信息填充到 R/G/B/W 的 "x,y" 输入框及 gamma
    def _fill_xy_fields(self, edid_info: dict | None):
        def fmt_xy(xy):
            try:
                x, y = float(xy[0]), float(xy[1])
                return f"{x:.6f},{y:.6f}"
            except Exception:
                return ""
        if not edid_info:
            for v in self.edid_xy_vars.values():
                v.set("")
            self.gamma_var.set("")
            return
        self.edid_xy_vars["R"].set(fmt_xy(edid_info.get("red",   (None, None))))
        self.edid_xy_vars["G"].set(fmt_xy(edid_info.get("green", (None, None))))
        self.edid_xy_vars["B"].set(fmt_xy(edid_info.get("blue",  (None, None))))
        self.edid_xy_vars["W"].set(fmt_xy(edid_info.get("white", (None, None))))
        g = edid_info.get("gamma", None)
        self.gamma_var.set("" if g is None else f"{float(g):.4f}")
    
    # 解析 "x,y" 文本为 [x, y]；解析失败返回 None（不做任何回退）
    def _parse_xy_text(self, text: str):
        try:
            parts = [p.strip() for p in (text or "").split(",")]
            if len(parts) != 2:
                return None
            x = float(parts[0]); y = float(parts[1])
            # 可选校验：xy 合法范围
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 and x + y <= 1.0):
                return None
            return [x, y]
        except Exception:
            return None
    
    def read_xy_gamma(self):
        """
        一次性读入当前 UI 中的 R/G/B/W 的 'x,y' 与 gamma。
        - 不回退到 EDID；任何解析错误该项返回 None。
        返回:
          {
            "red":   [x, y] | None,
            "green": [x, y] | None,
            "blue":  [x, y] | None,
            "white": [x, y] | None,
            "gamma": float | None
          }
        """
        vals = {
            "red":   self._parse_xy_text(self.edid_xy_vars["R"].get()),
            "green": self._parse_xy_text(self.edid_xy_vars["G"].get()),
            "blue":  self._parse_xy_text(self.edid_xy_vars["B"].get()),
            "white": self._parse_xy_text(self.edid_xy_vars["W"].get()),
        }
        # gamma
        g_text = (self.gamma_var.get() or "").strip()
        try:
            gamma = float(g_text) if g_text != "" else None
        except Exception:
            gamma = None
        vals["gamma"] = gamma
        return vals

    def set_icc(self, path):
        install_icc(path)
        icc_name = os.path.basename(path)
        monitor = self.monitor_var.get()
        info = self.human_display_config_map.get(monitor)
        luid = luid_from_dict(info["adapter_luid"])
        sid  = info["source"]["id"]
        hdr = False
        if info["color_work_status"] == "hdr":
            hdr = True
        cp_add_display_association(luid, sid, icc_name, set_as_default=True, associate_as_advanced_color=hdr)
    
    def clean_icc(self, name):
        path = f"{name}.icc"
        monitor = self.monitor_var.get()
        info = self.human_display_config_map.get(monitor)
        luid = luid_from_dict(info["adapter_luid"])
        sid  = info["source"]["id"]
        hdr = False
        if info["color_work_status"] == "hdr":
            hdr = True
        cp_remove_display_association(luid, sid, path, associate_as_advanced_color=hdr)
        uninstall_icc(path, force=True)
    # 新增：可模态询问的自定义警告对话框，支持“不再提示”
    def _ask_warning_confirm(self, title: str, message: str, monitor_key: str, tag: str) -> bool:
        """
        弹出一个模态对话框，显示 message，包含 'Do not ask again' 复选框和两个按钮：
        - Continue -> 返回 True
        - Cancel   -> 返回 False
        如果勾选了 'Do not ask again' 会把结果记录到 self._warn_skip["{monitor_key}::{tag}"]
        """
        key = f"{monitor_key}::{tag}"
        # 若已选择不再提示，直接同意（或直接返回 True 也可按需求改）
        if self._warn_skip.get(key):
            return True

        dlg = tk.Toplevel(self)
        dlg.transient(self)
        dlg.grab_set()
        dlg.title(title)
        dlg.resizable(False, False)

        # Message
        frm = ttk.Frame(dlg, padding=12)
        frm.pack(fill="both", expand=True)
        lbl = ttk.Label(frm, text=message, wraplength=420, justify="left")
        lbl.pack(fill="x", pady=(0, 10))

        # Do not ask again
        dont_var = tk.BooleanVar(value=False)
        chk = ttk.Checkbutton(frm, text="Do not ask again", variable=dont_var)
        chk.pack(anchor="w", pady=(0, 8))

        res = {"ok": False}

        def on_continue():
            res["ok"] = True
            if dont_var.get():
                self._warn_skip[key] = True
            dlg.destroy()

        def on_cancel():
            res["ok"] = False
            dlg.destroy()

        btn_fr = ttk.Frame(frm)
        btn_fr.pack(fill="x", pady=(6, 0))
        ttk.Button(btn_fr, text="Continue", command=on_continue).pack(side="right", padx=(6, 0))
        ttk.Button(btn_fr, text="Cancel", command=on_cancel).pack(side="right")

        # keyboard bindings
        dlg.bind("<Return>", lambda e: on_continue())
        dlg.bind("<Escape>", lambda e: on_cancel())

        # center dialog on main window
        self.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - dlg.winfo_reqwidth()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - dlg.winfo_reqheight()) // 2
        dlg.geometry(f"+{x}+{y}")

        self.wait_window(dlg)
        return bool(res["ok"])
    
    def get_selected_pnp_device_id(self):
        monitor = self.monitor_var.get()
        return self.human_display_config_map[monitor]["pnp_device_id"]

    def on_generate(self):
        monitor = self.monitor_var.get()
        display_config = self.human_display_config_map.get(monitor)
        adv = display_config.get("target", {}).get("advanced_color", None)
        # 若存在 advanced_color 字段，区分已开启/未开启两种警告场景
        if display_config["color_work_status"] != "hdr":
            if isinstance(adv, dict):
                # 场景 A：支持并已启用（adv['enabled'] == True）
                if adv.get("enabled", False):
                    ok = self._ask_warning_confirm(
                        "Warning",
                        getattr(self, "warn_text_adv_enabled"),
                        monitor,
                        "adv_enabled"
                    )
                    if not ok:
                        return
                # 场景 B：支持但未启用（adv 存在但 enabled False）
                else:
                    # 仅当 advanced_color 信息存在且表明支持时才提示
                    # 依据实现可调整判断条件；这里若字段存在则提示
                    ok = self._ask_warning_confirm(
                        "Warning",
                        getattr(self, "warn_text_adv_supported_disabled"),
                        monitor,
                        "adv_supported_but_disabled"
                    )
                    if not ok:
                        return

        icc_handle = ICCProfile("hdr_empty.icc")
        icc_data = icc_handle.read_all()
        MHC2 = copy.deepcopy(icc_data["MHC2"])
        
        gamut_mapping = {
        "sRGB": sRGB_xy,
        "BT2020": BT2020_xy,
        "P3D65": P3D65_xy,
        "AdobeRGB": AdobeRGB_xy
        }
        info = {
            "target_gamut": self.gamut_var.get(),
            "target_tone": self.tone_var.get(),
            "display": self.get_selected_pnp_device_id()
        }
        edid_info = get_edid_info(info["display"])
        # source_gamut["white"] = [0.320002,0.342283]
        cl_sdr = {
                  "red":   [0.6900 , 0.3100],
                  "green": [0.2626 , 0.7007],
                  "blue":  [0.1455 , 0.0512],
                  "white": [0.3272 , 0.3487]
                  }
        source_info = edid_info
        source_info = self.read_xy_gamma()
        source = xy_primaries_to_XYZ_normed(source_info, 1)
        matrix = None
        print(display_config["color_work_status"])
        print(adv.get("enabled", False))
        if (display_config["color_work_status"] == "hdr") or (not adv.get("enabled", False)):
            target = xy_primaries_to_XYZ_normed(gamut_mapping[info["target_gamut"]], 1)
            matrix = calc_rgb_mapping_matrix_non_normalized(source, target)
        
        icc_handle = ICCProfile("hdr_empty.icc")
        icc_data = icc_handle.read_all()
        MHC2 = copy.deepcopy(icc_data["MHC2"])

        icc_handle.write_XYZType('rXYZ', [l2_normalize_XYZ(source["red"])])
        icc_handle.write_XYZType('gXYZ', [l2_normalize_XYZ(source["green"])])
        icc_handle.write_XYZType('bXYZ', [l2_normalize_XYZ(source["blue"])])
        icc_handle.write_XYZType('wtpt', [l2_normalize_XYZ(source["white"])])
        print("matrix:", matrix)
        if matrix is not None:
            MHC2['matrix'] = matrix.flatten().tolist()
        
        if info["target_tone"] != "不做修改":
            eo_map = {"sRGB":("srgb", None),
                       "gamma 2.0":("gamma", 2.0),
                       "gamma 2.2":("gamma", 2.2),
                       "gamma 2.4":("gamma", 2.4),
                       "HDR-PQ":("pq", None)}
            source_args = None
            gamma = edid_info.get("gamma", None)
            if gamma:
                source_args = ("gamma", gamma)
            if source_args:
                dest_args = eo_map.get(info["target_tone"])
                lut = np.linspace(0, 1, 4096)
                target = convert_transfer(lut, source_args, dest_args)
                MHC2["red_lut"] = target.tolist()
                MHC2["green_lut"] = target.tolist()
                MHC2["blue_lut"] = target.tolist()
                MHC2["entry_count"] = 4096

        icc_handle.write_MHC2(MHC2)

        display = self.monitor_var.get()
        name = f"{display}-EDID-to-{info['target_gamut']}"
        
        name = "SDR_ACM"
        
        temp_dir = tempfile.gettempdir()
        icc_file_name = name + ".icc"
        path = os.path.join(temp_dir, icc_file_name)
        desc = [{'lang': 'en', 'country': 'US', 'text': name}]
        icc_handle.write_desc(desc)
        icc_handle.rebuild()
        icc_handle.save(path)
        self.set_icc(path)
        os.remove(path)

    def on_cancel_load(self):
        info = {
            "target_gamut": self.gamut_var.get(),
            "target_tone": self.tone_var.get(),
            "display": self.get_selected_pnp_device_id()
        }
        display = self.monitor_var.get()
        name = f"{display}-EDID-to-{info['target_gamut']}"
        
        self.clean_icc(name)

if __name__ == "__main__":
    app = GamutMapperApp()
    app.mainloop()
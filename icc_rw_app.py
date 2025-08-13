import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from icc_rw import ICCProfile  
from convert_utils import l2_normalize_XYZ

class ICCRWApp:
    def __init__(self, root):
        self.root = root
        self.root.title("HDR icc编辑器 (未加载)")
        self.profile: ICCProfile | None = None
        self.current_path: str | None = None
        self.modified = False

        self._build_ui()
        self._set_style()
        self._auto_fit()

    # ---------- UI ----------
    def _set_style(self):
        style = ttk.Style()
        try:
            style.theme_use("vista")
        except Exception:
            pass
        style.configure("TButton", padding=(10, 4))
        style.configure("TLabel", anchor="w")
    
    def _auto_fit(self):
        # 计算所有控件所需尺寸，设置窗口与最小尺寸
        self.root.update_idletasks()
        w = self.root.winfo_reqwidth()
        h = self.root.winfo_reqheight()
        self.root.geometry(f"{w}x{h}")
        self.root.minsize(w, h)

    def _build_ui(self):
        top = ttk.Frame(self.root)
        top.pack(fill="x", padx=10, pady=6)

        ttk.Button(top, text="打开 ICC", command=self.open_icc).pack(side="left")
        ttk.Button(top, text="保存", command=self.save_icc).pack(side="left", padx=6)
        ttk.Button(top, text="另存为", command=self.save_as).pack(side="left")
        ttk.Button(top, text="退出", command=self.root.destroy).pack(side="left")

        # 删除原 path_frame，避免 file_info_var 被重复定义而顶部那个不更新的问题

        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        base_page = ttk.Frame(self.nb, padding=10)
        self.nb.add(base_page, text="基础标签")

        for c in range(4):
            base_page.columnconfigure(c, weight=0)

        # 单一 file_info_var（不要再次赋值）
        self.file_info_var = tk.StringVar(value="(未加载)")
        ttk.Label(base_page, text="file:").grid(row=0, column=0, sticky="w", pady=2)
        self.file_info_entry = ttk.Entry(base_page, textvariable=self.file_info_var,
                                         state="readonly", width=56)
        self.file_info_entry.grid(row=0, column=1, columnspan=3, sticky="w", pady=2)

        ttk.Label(base_page, text="desc:").grid(row=1, column=0, sticky="w", pady=2)
        self.desc_var = tk.StringVar()
        self.desc_entry = ttk.Entry(base_page, textvariable=self.desc_var, width=56)
        self.desc_entry.grid(row=1, column=1, columnspan=3, sticky="w", pady=2)

        ttk.Label(base_page, text="cprt:").grid(row=2, column=0, sticky="w", pady=2)
        self.cprt_var = tk.StringVar()
        self.cprt_entry = ttk.Entry(base_page, textvariable=self.cprt_var, width=56)
        self.cprt_entry.grid(row=2, column=1, columnspan=3, sticky="w", pady=2)

        def xyz_row(r, tag_label, vars_store):
            ttk.Label(base_page, text=tag_label).grid(row=r, column=0, sticky="w", pady=2)
            for i in range(3):
                v = tk.StringVar()
                vars_store.append(v)
                ttk.Entry(base_page, width=18, textvariable=v).grid(
                    row=r, column=1 + i, padx=0, pady=2, sticky="w"
                )

        self.rxyz_vars, self.gxyz_vars, self.bxyz_vars = [], [], []
        self.wtpt_vars, self.lumi_vars = [], []
        xyz_row(3, "rXYZ:", self.rxyz_vars)
        xyz_row(4, "gXYZ:", self.gxyz_vars)
        xyz_row(5, "bXYZ:", self.bxyz_vars)
        xyz_row(6, "wtpt:", self.wtpt_vars)
        xyz_row(7, "lumi:", self.lumi_vars)

        ttk.Label(base_page,
                  text="(数值留空表示不修改该 XYZ)").grid(row=8, column=0, columnspan=4, sticky="w", pady=(6,0))

        # MHC2 页保持原样（行号不变，可继续使用）
        mhc2_page = ttk.Frame(self.nb, padding=10)
        self.nb.add(mhc2_page, text="MHC2")

        ttk.Label(mhc2_page, text="3x3 矩阵:").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
        self.m_matrix_vars = [tk.StringVar() for _ in range(9)]
        for i in range(3):
            for j in range(3):
                ttk.Entry(mhc2_page, width=8, textvariable=self.m_matrix_vars[i*3+j]).grid(row=i+1, column=j, padx=2, pady=2, sticky="w")

        ttk.Label(mhc2_page, text="Min Luminance:").grid(row=4, column=0, sticky="e", pady=(8,2))
        self.min_lum_var = tk.StringVar()
        ttk.Entry(mhc2_page, width=10, textvariable=self.min_lum_var).grid(row=4, column=1, sticky="w", padx=4, pady=(8,2))
        ttk.Label(mhc2_page, text="Peak Luminance:").grid(row=4, column=2, sticky="e", pady=(8,2))
        self.peak_lum_var = tk.StringVar()
        ttk.Entry(mhc2_page, width=10, textvariable=self.peak_lum_var).grid(row=4, column=3, sticky="w", padx=4, pady=(8,2))

        ttk.Label(mhc2_page, text="Red LUT:").grid(row=5, column=0, sticky="e", pady=4)
        self.red_lut_var = tk.StringVar()
        ttk.Entry(mhc2_page, width=56, textvariable=self.red_lut_var).grid(row=5, column=1, columnspan=3, sticky="w")

        ttk.Label(mhc2_page, text="Green LUT:").grid(row=6, column=0, sticky="e", pady=4)
        self.green_lut_var = tk.StringVar()
        ttk.Entry(mhc2_page, width=56, textvariable=self.green_lut_var).grid(row=6, column=1, columnspan=3, sticky="w")

        ttk.Label(mhc2_page, text="Blue LUT:").grid(row=7, column=0, sticky="e", pady=4)
        self.blue_lut_var = tk.StringVar()
        ttk.Entry(mhc2_page, width=56, textvariable=self.blue_lut_var).grid(row=7, column=1, columnspan=3, sticky="w")
        # ttk.Label(mhc2_page, text="(LUT 逗号分隔或留空保留原值)").grid(row=8, column=0, columnspan=4, sticky="w", pady=(4,0))

        # ttk.Button(mhc2_page, text="标记修改 (MHC2)", command=self.mark_modified).grid(row=9, column=0, columnspan=2, sticky="w", pady=(10,0))

        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(self.root, textvariable=self.status_var, anchor="w").pack(fill="x", side="bottom")
        
    def _lut_row(self, parent, name, var, r):
        ttk.Label(parent, text=f"{name} LUT:").grid(row=r, column=0, sticky="e", padx=2, pady=2)
        ttk.Entry(parent, width=28, textvariable=var).grid(row=r, column=1, padx=2)
        ttk.Button(parent, text="选择文件", command=lambda v=var: self.pick_lut_file(v)).grid(row=r, column=2, padx=4)

    # ---------- 事件 ----------
    def pick_lut_file(self, var):
        path = filedialog.askopenfilename(title="选择 LUT 文本文件")
        if path:
            var.set(path)
            self.mark_modified()

    def open_icc(self):
        path = filedialog.askopenfilename(title="打开 ICC 文件",
                                          filetypes=[("ICC/ICM", "*.icc *.icm"), ("All", "*.*")])
        if not path:
            return
        try:
            self.profile = ICCProfile(path)
            self.current_path = path
            self.modified = False
            self.load_profile_data()
            self._update_titles()
            self.status(f"已加载: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("错误", f"无法加载: {e}")

    def save_icc(self):
        if not self.profile:
            return
        if not self.current_path:
            return

        if not self.apply_changes():
            return
        try:
            self.profile.save(self.current_path)
            self.status("已保存")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")

    def save_as(self):
        if not self.profile:
            return
        if not self.apply_changes():
            return
        path = filedialog.asksaveasfilename(defaultextension=".icc",
                                            filetypes=[("ICC", "*.icc"), ("ICM", "*.icm")])
        if not path:
            return
        try:
            self.profile.save(path)
            self.current_path = path
            self._update_titles()
            self.status("已另存")
        except Exception as e:
            messagebox.showerror("错误", f"另存失败: {e}")
    
    def _update_titles(self):
        if self.current_path:
            name = os.path.basename(self.current_path)
            self.root.title(f"HDR icc编辑器 - {name}")
            self.file_info_var.set(f"{self.current_path}")
        else:
            self.root.title("HDR icc编辑器 (未加载)")
            self.file_info_var.set("(未加载)")


    def on_tag_open(self, _):
        if not self.profile:
            return
        sel = self.tag_list.curselection()
        if not sel:
            return
        tag = self.tag_list.get(sel[0])
        self.show_tag(tag)

    def mark_modified(self):
        self.modified = True
        self.status("已标记修改 (待应用)")

    def refresh_view(self):
        if self.profile:
            self.load_profile_data()
            self.status("已刷新")

    # ---------- 数据加载 ----------
    def load_profile_data(self):
        try:
            data = self.profile.read_all()
            # desc
            desc_text = ""
            d = data.get('desc')
            if isinstance(d, dict):  # 可能是 {'localizations':[...]}
                locs = d.get('localizations') or d.get('entries')
                if locs and isinstance(locs, list):
                    first = locs[0]
                    if isinstance(first, dict):
                        desc_text = first.get('text', "")
            elif isinstance(d, list):
                # list of dict
                if d:
                    first = d[0]
                    if isinstance(first, dict):
                        desc_text = first.get('text', "")
                    else:
                        desc_text = str(first)
            elif isinstance(d, str):
                desc_text = d
            self.desc_var.set(desc_text)

            # cprt
            c = data.get('cprt')
            cprt_val = ""
            if isinstance(c, str):
                cprt_val = c
            elif isinstance(c, list) and c:
                first = c[0]
                if isinstance(first, dict):
                    cprt_val = first.get('text', "")
                else:
                    cprt_val = str(first)
            self.cprt_var.set(cprt_val)

            # XYZ helpers
            def fill_xyz(tag_key, vars_list):
                vals = data.get(tag_key)
                if vals and isinstance(vals, list) and len(vals) > 0:
                    x, y, z = vals[0]
                    vars_list[0].set(f"{x:.6f}")
                    vars_list[1].set(f"{y:.6f}")
                    vars_list[2].set(f"{z:.6f}")
                else:
                    for v in vars_list: v.set("")

            fill_xyz('rXYZ', self.rxyz_vars)
            fill_xyz('gXYZ', self.gxyz_vars)
            fill_xyz('bXYZ', self.bxyz_vars)
            fill_xyz('wtpt', self.wtpt_vars)
            fill_xyz('lumi', self.lumi_vars)

            # MHC2
            mhc2 = data.get('MHC2')
            if mhc2:
                m = mhc2.get('matrix') or []
                for i in range(9):
                    self.m_matrix_vars[i].set(f"{m[i]:.6f}" if i < len(m) else "")
                self.min_lum_var.set(str(mhc2.get('min_luminance', "")))
                self.peak_lum_var.set(str(mhc2.get('peak_luminance', "")))
                for (lut_name, var) in (("red_lut", self.red_lut_var),
                                        ("green_lut", self.green_lut_var),
                                        ("blue_lut", self.blue_lut_var)):
                    arr = mhc2.get(lut_name)
                    if arr:
                        # var.set("")
                        # FIXME，很卡
                        var.set(",".join(f"{v:.6f}" for v in arr))
                    else:
                        var.set("")
            else:
                for v in self.m_matrix_vars: v.set("")
                self.min_lum_var.set("")
                self.peak_lum_var.set("")
                self.red_lut_var.set("")
                self.green_lut_var.set("")
                self.blue_lut_var.set("")
        except Exception as e:
            self.status(f"解析失败: {e}")

    def show_tag(self, tag):
        display = ""
        if tag == 'desc':
            val = self.profile.read_desc()
            if isinstance(val, list):
                display = "desc (mluc):\n" + "\n".join(
                    f"  {r['lang']}-{r['country']}: {r['text']}" for r in val
                )
            else:
                display = f"desc (ascii): {val}"
        elif tag in ('rXYZ', 'gXYZ', 'bXYZ', 'wtpt', 'lumi'):
            vals = self.profile.read_XYZType(tag)
            if vals:
                display = f"{tag} (XYZType):"
                for i, (x, y, z) in enumerate(vals):
                    display += f"\n  [{i}] X={x:.6f} Y={y:.6f} Z={z:.6f}"
            else:
                display = f"{tag}: (empty)"
        elif tag == 'MHC2':
            mhc2 = self.profile.read_MHC2()
            if mhc2:
                display = "MHC2:\n"
                display += f"  entry_count = {mhc2.get('entry_count')}\n"
                display += f"  min_luminance = {mhc2.get('min_luminance')}\n"
                display += f"  peak_luminance = {mhc2.get('peak_luminance')}\n"
                m = mhc2.get('matrix') or []
                if m:
                    display += "  matrix:\n"
                    for i in range(3):
                        display += "    " + " ".join(f"{m[i*3+j]:.6f}" for j in range(3)) + "\n"
                for ch in ('red_lut', 'green_lut', 'blue_lut'):
                    lut = mhc2.get(ch)
                    if lut:
                        display += f"  {ch} ({len(lut)}): first 16 -> " + ", ".join(
                            f"{v:.6f}" for v in lut[:16]
                        )
                        if len(lut) > 16:
                            display += f" ... (total {len(lut)})"
                        display += "\n"
            else:
                display = "MHC2: (not present)"
        elif tag == 'MSCA':
            msca = self.profile.read_MSCA()
            if msca:
                display = "MSCA (Microsoft private tag):\n"
                display += f"  size = {msca['size']}\n"
                display += f"  type_signature = {msca['type_signature'] or '(unknown / binary)'}\n"
                display += "  (content kept opaque; not parsed)"
            else:
                display = "MSCA: (not present)"
        else:
            # 其他未解析标签：只给出存在信息，不显示十六进制
            info = self.profile.tags.get(tag)
            if info:
                display = f"{tag}: size={info['size']} (raw / unparsed)"
            else:
                display = f"{tag}: (not present)"

        self.text_view.configure(state="normal")
        self.text_view.delete("1.0", "end")
        self.text_view.insert("1.0", display if display else "(空)")
        self.text_view.configure(state="disabled")

    # ---------- 应用修改 ----------
    def apply_changes(self):
        if not self.profile:
            return False
        try:
            # desc
            desc = self.desc_var.get().strip()
            if desc:
                self.profile.write_desc([{'lang': 'en', 'country': 'US', 'text': desc}])

            # cprt
            cprt = self.cprt_var.get().strip()
            if cprt:
                self.profile.write_cprt([{'lang': 'en', 'country': 'US', 'text': cprt}])

            # XYZ 写入（非空即写）
            def collect_xyz(vars_list):
                if any(v.get().strip() for v in vars_list):
                    xyz = [float(vars_list[0].get()), float(vars_list[1].get()), float(vars_list[2].get())]
                    return [xyz]
                return None

            xyz_map = {
                'rXYZ': collect_xyz(self.rxyz_vars),
                'gXYZ': collect_xyz(self.gxyz_vars),
                'bXYZ': collect_xyz(self.bxyz_vars),
                'wtpt': collect_xyz(self.wtpt_vars),
                'lumi': collect_xyz(self.lumi_vars),
            }
            for tag_name, triplets in xyz_map.items():
                if triplets:
                    self.profile.write_XYZType(tag_name, triplets)

            # MHC2
            matrix_vals = []
            has_matrix_input = any(v.get().strip() for v in self.m_matrix_vars)
            if has_matrix_input:
                for v in self.m_matrix_vars:
                    matrix_vals.append(float(v.get()))
                if len(matrix_vals) != 9:
                    raise ValueError("MHC2 矩阵需要 9 个数字")
            else:
                matrix_vals = [1,0,0, 
                               0,1,0, 
                               0,0,1]

            def parse_lut(s):
                s = s.strip()
                if not s:
                    return None
                return [float(x) for x in s.replace(';', ',').split(',') if x.strip()]

            red = parse_lut(self.red_lut_var.get())
            green = parse_lut(self.green_lut_var.get())
            blue = parse_lut(self.blue_lut_var.get())
            entry_count = len(red)
            if entry_count != len(green) or entry_count != len(blue):
                raise ValueError("所有 LUT 必须具有相同的条目数")
            if entry_count < 2 or entry_count > 4096:
                raise ValueError("LUT 条目数必须在 2 到 4096 之间")
            min_lum = self._try_float(self.min_lum_var.get())
            peak_lum = self._try_float(self.peak_lum_var.get())

            mhc2 = {"entry_count": entry_count,
                    "min_luminance": min_lum,
                    "peak_luminance": peak_lum,
                    "matrix": matrix_vals,
                    "red_lut": red,
                    "green_lut": green,
                    "blue_lut": blue
                    }

            self.profile.write_MHC2(mhc2)
            self.profile.rebuild()
            self.modified = False
            return True
        except Exception as e:
            messagebox.showerror("应用失败", str(e))
            return False

    # ---------- 辅助 ----------
    def _try_float(self, s):
        s = s.strip()
        if not s:
            return None
        return float(s)

    def status(self, msg):
        self.status_var.set(msg)

def main():
    root = tk.Tk()
    # root.geometry("580x400")
    app = ICCRWApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
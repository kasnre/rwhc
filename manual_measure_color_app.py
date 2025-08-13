import tkinter as tk
from tkinter import ttk, messagebox
import traceback
import threading
import queue
import time
import sys
import json

from color_rw import ColorReader, ColorWriter
from convert_utils import *

class ColorMeasureApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("色彩测量工具")
        self.resizable(False, False)

        # 状态
        self.reader = None
        self.writer = None
        self.read_queue = queue.Queue()
        self._build_ui()
        self._center_window(520, 400)

    def _center_window(self, w, h):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        pad = {"padx": 12, "pady": 8}
        root = ttk.Frame(self)
        root.pack(fill="both", expand=True, **pad)

        # 行0：ColorReader 参数 + ColorWriter 模式
        row0 = ttk.Frame(root)
        row0.pack(fill="x", pady=(0, 4))
        ttk.Label(row0, text="spotread参数:", width=12).pack(side="left")
        self.args_var = tk.StringVar(value="-x -y e")  # 按需改成你的参数
        ttk.Entry(row0, textvariable=self.args_var, width=42).pack(side="left", padx=(0, 0))

        ttk.Label(row0, text="输出模式:").pack(side="left")
        self.mode_var = tk.StringVar(value="hdr_10")
        ttk.Combobox(
            row0, textvariable=self.mode_var,
            width=18,                      # 放大下拉框宽度，避免被遮挡
            values=["hdr_10","hdr_8", "sdr_8", "sdr_10"], state="readonly"
        ).pack(side="left", padx=(4, 0))

        # 行1：按钮 行
        row1 = ttk.Frame(root)
        row1.pack(fill="x", pady=(0, 6))
        ttk.Button(row1, text="初始化连接", width=14, command=self.on_init).pack(side="left")
        ttk.Button(row1, text="关闭连接", width=12, command=self.on_close_conn).pack(side="left", padx=(8, 0))

        # 行2：RGB 输入
        row2 = ttk.Frame(root)
        row2.pack(fill="x", pady=(0, 4))
        ttk.Label(row2, text="RGB(0-1023):", width=14).pack(side="left")
        self.r_var = tk.IntVar(value=1023)
        self.g_var = tk.IntVar(value=1023)
        self.b_var = tk.IntVar(value=1023)
        ttk.Spinbox(row2, from_=0, to=1023, textvariable=self.r_var, width=6).pack(side="left")
        ttk.Spinbox(row2, from_=0, to=1023, textvariable=self.g_var, width=6).pack(side="left", padx=(6, 0))
        ttk.Spinbox(row2, from_=0, to=1023, textvariable=self.b_var, width=6).pack(side="left", padx=(6, 0))
        ttk.Button(row2, text="发送RGB", width=10, command=self.on_send_rgb).pack(side="left", padx=(12, 0))
        ttk.Button(row2, text="写入并测量", width=12, command=self.on_send_and_measure).pack(side="left", padx=(6, 0))

         # 行3：测量
        row3 = ttk.Frame(root)
        row3.pack(fill="x", pady=(0, 4))
        ttk.Button(row3, text="读取 XYZ", width=12, command=self.on_measure_once).pack(side="left")
        ttk.Button(row3, text="测量 RGBW", width=14, command=self.on_measure_rgbw).pack(side="left", padx=(6,0))
        ttk.Button(row3, text="亮度曲线测量", width=14, command=self.on_measure_luma_curve).pack(side="left", padx=(6,0))
        self.xyz_label = ttk.Label(row3, text="XYZ: -/-/-")
        self.xyz_label.pack(side="left", padx=(12, 0))
        self.xyy_var = tk.StringVar(value="xyY: -/-/-")
        self.xyy_entry = ttk.Entry(row3, textvariable=self.xyy_var, width=36, state="readonly")
        self.xyy_entry.pack(side="left", padx=(10, 0))
        self._enable_select_copy(self.xyy_entry)
        ttk.Button(row3, text="复制", width=6, command=lambda: self._copy_to_clipboard(self.xyy_var.get())).pack(side="left", padx=(6, 0))

        # 日志
        frm_log = ttk.LabelFrame(root, text="日志")
        frm_log.pack(fill="both", expand=True, pady=(6, 0))
        self.log_txt = tk.Text(frm_log, height=10, width=64)
        self.log_txt.pack(fill="both", expand=True, padx=6, pady=6)

        # 关闭事件
        self.protocol("WM_DELETE_WINDOW", self.on_exit)

    # 连接与关闭
    def on_init(self):
        try:
            self._ensure_writer(recreate=True)
            self._ensure_reader(recreate=True)
            self._log("已初始化 ColorWriter 与 ColorReader")
        except Exception as e:
            messagebox.showerror("错误", f"初始化失败: {e}")

    def on_close_conn(self):
        self._terminate_reader()
        self._terminate_writer()
        self._log("已关闭连接")

    # 发送与测量
    def on_send_rgb(self):
        try:
            self._ensure_writer()
            rgb = self._get_rgb()
            self.writer.write_rgb(rgb, delay=0.1)
            self._log(f"已发送 RGB: {rgb}")
        except Exception as e:
            messagebox.showerror("错误", f"发送失败: {e}")

    def on_measure_once(self):
        """同步读取一次 XYZ"""
        try:
            self._ensure_reader()
            xyz = self.reader.read_XYZ()
            self._apply_xyz(xyz)
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("错误", f"读取失败: {e}")

    def on_send_and_measure(self):
        """发送当前 RGB 并同步测量"""
        try:
            self._ensure_writer()
            self._ensure_reader()
            rgb = self._get_rgb()
            self.writer.write_rgb(rgb)
            self._log(f"已发送 RGB: {rgb}")
            xyz = self.reader.read_XYZ()
            self._apply_xyz(xyz)
        except Exception as e:
            messagebox.showerror("错误", f"写入/读取失败: {e}")

    def on_measure_rgbw(self):
        """同步测量 R/G/B/W（可能阻塞 UI，必要时可放线程）"""
        try:
            self._ensure_writer()
            self._ensure_reader()
        except Exception as e:
            messagebox.showerror("错误", f"初始化失败: {e}")
            return
        m = self.writer.mode.split("_")[1]  # 8 or 10
        max = 255 if m == "8" else 1023
        samples = [
            ("R", [max, 0, 0]),
            ("G", [0, max, 0]),
            ("B", [0, 0, max]),
            ("W", [max, max, max]),
        ]
        lines = []
        for name, rgb in samples:
            try:
                self.writer.write_rgb(rgb, delay=0.1)
                time.sleep(0.12)
                xyz = self.reader.read_XYZ()
                print(xyz)
                if xyz.size == 3 and np.isfinite(xyz[:3]).all():
                    X, Y, Z = map(float, xyz[:3])
                    x, y = XYZ_to_xy([X, Y, Z])
                    self._log(f"{name}: XYZ {X:.4f},{Y:.4f},{Z:.4f} xy {x:.4f},{y:.4f}")
                    lines.append(f"{x:.4f},{y:.4f}")
                else:
                    self._log(f"{name}: 读取失败")
                    lines.append(f"{name}:failed")
            except Exception as e:
                self._log(f"{name} 测量异常: {e}")
                lines.append(f"{name}:error")
        self._log("RGBW 汇总:\n" + "\n".join(lines))
    
    def on_measure_luma_curve(self):
        """启动 128 点亮度曲线测量"""
        try:
            self._ensure_writer()
            self._ensure_reader()
        except Exception as e:
            messagebox.showerror("错误", f"初始化失败: {e}")
            return
        threading.Thread(target=self._measure_luma_curve_worker, daemon=True).start()

    def _measure_luma_curve_worker(self):
        try:
            mode = (self.writer.mode or "").lower()
            is_hdr = mode.startswith("hdr")
            bits = 10 if mode.endswith("10") else 8
            max_code = 1023 if bits == 10 else 255

            # 1) 测满白
            self.writer.write_rgb([max_code]*3, delay=0.1)
            xyz_white = self.reader.read_XYZ()
            if xyz_white.size != 3:
                self._log("白场测量失败")
                return
            Y_white = float(xyz_white[1])
            if Y_white <= 0:
                self._log("白场亮度无效")
                return
            self._log(f"峰值亮度(白): {Y_white:.2f} nits")

            # 2) 准备 128 个灰阶码值
            NUM = 64
            codes = np.linspace(0, max_code, NUM).round().astype(int)
            meas_Y = []
            l = len(codes)
            for idx, c in enumerate(codes):
                self.writer.write_rgb([int(c)]*3, delay=0.1)
                xyz = self.reader.read_XYZ()
                xy = XYZ_to_xy(xyz)
                self._log(f"({idx+1}/{l}) 灰阶 {c}: XYZ {xyz} xy {xy}")
                if xyz.size == 3:
                    meas_Y.append(float(xyz[1]))
                else:
                    meas_Y.append(np.nan)
            meas_Y = np.array(meas_Y, dtype=float)
            print(meas_Y)
            

            # 3) 生成目标曲线 (t 为输入归一化)
            t = np.linspace(0, 1, NUM)
            if is_hdr:
                # HDR: 目标使用设备实测峰值映射 (相对 -> 绝对 nits)
                linear_target = t
                encoded_measured = np.clip(meas_Y / 10000, 0, None)
                linear_measured = pq_oetf(np.clip(meas_Y, 0, None))
                encoded_target = pq_eotf(t)/10000
                encoded_sRGB = srgb_encode(t)
            else:
                linear_target = t
                encoded_measured = np.clip(meas_Y / Y_white, 0, None)  # 相对线性亮度 (EOTF 输出)
                print("encoded_measured json type:\n", json.dumps(encoded_measured.astype(float).tolist()))
                linear_measured = gamma_decode(np.clip(encoded_measured, 0, 1), 2.2)
                encoded_target = gamma_encode(t, 2.2)
                encoded_sRGB = srgb_encode(t)

            # 自定义纵轴断点示例（可按需替换或改成用户输入）
            # 例: 将 [0,0.01,0.05,0.1,0.3,1.0] 每段等长显示，有助观察低亮差异
            custom_breaks_gamma22 = [0.0, 0.029, 0.133, 0.325, 0.61, 1.0]
            custom_breaks_pq = [0.0, 0.0002429, 0.0032448, 0.0244005, 0.1555178, 1.0]  
            self.after(0, lambda: self._show_luma_curve_plots(
                t, linear_target, linear_measured,
                encoded_target, encoded_measured, encoded_sRGB,
                is_hdr, bits, Y_white,
                custom_breaks_pq if is_hdr else custom_breaks_gamma22
            ))
        except Exception as e:
            traceback.print_exc()
            self._log(f"亮度曲线测量异常: {e}")

    # --- 新增：分段等长轴转换 ---
    def _segment_equal_transform(self, y, breaks):
        b = np.asarray(breaks, float)
        y = np.asarray(y, float)
        y_clip = np.clip(y, b[0], b[-1])
        idx = np.searchsorted(b, y_clip, side="right") - 1
        idx = np.clip(idx, 0, b.size - 2)
        seg_span = b[idx+1] - b[idx]
        seg_span = np.where(seg_span == 0, 1, seg_span)
        frac = (y_clip - b[idx]) / seg_span
        seg_len = 1.0 / (b.size - 1)
        return (idx + frac) * seg_len

    def _show_luma_curve_plots(self, t, linear_target, linear_measured,
                               encoded_target, encoded_measured, encoded_sRGB,
                               is_hdr, bits, Y_white,
                               encoded_axis_breaks=None):
        try:
            import matplotlib
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            import matplotlib.pyplot as plt
        except Exception:
            messagebox.showerror("缺少依赖", "需要安装 matplotlib\npip install matplotlib")
            return

        win = tk.Toplevel(self)
        win.title(f"亮度曲线 ({'HDR' if is_hdr else 'SDR'} {bits}bit)")
        win.geometry("900x620")

        nb = ttk.Notebook(win); nb.pack(fill="both", expand=True)

        # 线性视图
        frm_o = ttk.Frame(nb); nb.add(frm_o, text="linear")
        fig_o, ax_o = plt.subplots(figsize=(7.5,4.6), dpi=100)
        ax_o.plot(t, linear_target, label="target", linewidth=2)
        ax_o.plot(t, linear_measured, label="measured", linestyle="--")
        ax_o.set_xlabel("input"); ax_o.set_ylabel("linear")
        ax_o.set_title(f"linear ({'PQ' if is_hdr else 'Gamma2.2'})")
        ax_o.grid(alpha=0.3)
        ax_o.legend(loc="lower right")
        FigureCanvasTkAgg(fig_o, master=frm_o).get_tk_widget().pack(fill="both", expand=True)

        # 编码视图
        frm_e = ttk.Frame(nb); nb.add(frm_e, text="encoded")
        fig_e, ax_e = plt.subplots(figsize=(7.5,4.6), dpi=100)

        # --- 自定义曲线输入区域（放在顶部工具区） ---
        control_bar = ttk.Frame(frm_e)
        control_bar.pack(fill="x", pady=(2, 2))
        ttk.Label(control_bar, text="自定义曲线(JSON数组):").pack(side="left")
        custom_json_var = tk.StringVar()
        entry_custom = ttk.Entry(control_bar, textvariable=custom_json_var, width=46)
        entry_custom.pack(side="left", padx=(4, 4))

        # 说明按钮（弹窗提示格式）
        def show_format_help():
            msg = (
                "输入示例:\n"
                "1) 单条曲线: [0,0.1,0.2,...]\n"
                "2) 多条曲线: [[...],[...]]\n"
                "3) 命名曲线: [{\"name\":\"curveA\",\"values\":[...]}, {\"name\":\"B\",\"values\":[...]}]\n"
                "长度需与采样点数相同 (当前: %d)。支持 0-1 数值。\n"
                "添加后会套用当前分段轴变换(若启用)。"
            ) % (len(t),)
            messagebox.showinfo("格式说明", msg)
        ttk.Button(control_bar, text="格式", width=5, command=show_format_help).pack(side="left", padx=(0,4))

        # 占位: 添加曲线按钮稍后在绘制基础曲线后 pack
        btn_add_curve = ttk.Button(control_bar, text="添加曲线")
        btn_add_curve.pack(side="left")

        custom_axis = (encoded_axis_breaks is not None
                       and len(encoded_axis_breaks) >= 2)

        # 保存已绘制的自定义线条引用，便于后续扩展（如需要清除）
        added_lines = []

        def _transform_if_needed(y_arr):
            if custom_axis:
                return self._segment_equal_transform(y_arr, encoded_axis_breaks)
            return y_arr

        # 添加曲线逻辑
        def on_add_curve():
            txt = custom_json_var.get().strip()
            if not txt:
                return
            try:
                data = json.loads(txt)
            except Exception as e:
                messagebox.showerror("JSON错误", f"解析失败: {e}")
                return

            curves = []

            def ensure_list_numbers(arr):
                arr_np = np.asarray(arr, dtype=float)
                if arr_np.shape != (len(t),):
                    raise ValueError(f"曲线长度必须为 {len(t)} (当前 {arr_np.shape})")
                arr_np = np.clip(arr_np, 0.0, 10.0)  # 允许>1的值(例如 PQ 编码 0-1 已经处理, 这里防爆)
                return arr_np

            # 判定结构
            if isinstance(data, list):
                if len(data) == 0:
                    messagebox.showwarning("提示", "空数组")
                    return
                # case A: list of numbers
                if all(isinstance(x, (int, float)) for x in data):
                    curves.append(("curve1", ensure_list_numbers(data)))
                # case B: list of list numbers
                elif all(isinstance(x, list) and len(x) > 0 and all(isinstance(v, (int,float)) for v in x) for x in data):
                    for i, arr in enumerate(data, 1):
                        curves.append((f"curve{i}", ensure_list_numbers(arr)))
                # case C: list of dicts
                elif all(isinstance(x, dict) for x in data):
                    for i, obj in enumerate(data, 1):
                        if "values" not in obj:
                            raise ValueError("对象需包含 'values'")
                        name = str(obj.get("name", f"curve{i}"))
                        vals = ensure_list_numbers(obj["values"])
                        curves.append((name, vals))
                else:
                    raise ValueError("不支持的数组结构")
            else:
                raise ValueError("根级必须是数组")

            # 绘制
            for name, arr in curves:
                y_plot = _transform_if_needed(arr)
                ln, = ax_e.plot(t, y_plot, label=name, linewidth=1.2)
                added_lines.append(ln)

            # 重新放置 legend 到右下
            ax_e.legend(loc="lower right")
            canvas_e.draw()
            self._log(f"已添加 {len(curves)} 条自定义曲线")
            # 清空输入
            # custom_json_var.set("")  # 如需保留可注释

        btn_add_curve.config(command=on_add_curve)

        # ===== 原有绘制逻辑 =====
        if custom_axis:
            brks = encoded_axis_breaks
            enc_t_plot = self._segment_equal_transform(encoded_target, brks)
            enc_m_plot = self._segment_equal_transform(encoded_measured, brks)
            ax_e.plot(t, enc_t_plot, label="target", linewidth=2)
            ax_e.plot(t, enc_m_plot, label="measured", linestyle="--")
            if encoded_sRGB is not None:
                enc_srgb_plot = self._segment_equal_transform(encoded_sRGB, brks)
                ax_e.plot(t, enc_srgb_plot, label="sRGB", linestyle=":")
            tick_pos = self._segment_equal_transform(brks, brks)
            ax_e.set_yticks(tick_pos)
            ax_e.set_yticklabels([f"{v:g}" for v in brks])
            ax_e.set_ylim(0, 1)
            ax_e.set_ylabel("encoded (segmented)")
            ax_e.set_title(f"{'PQ' if is_hdr else 'Gamma2.2'} segmented axis")
            ax_e.grid(alpha=0.3, which="both")
            ax_e.legend(loc="lower right")
            ax_e.text(0.02, 0.97,
                      f"segments: {brks}",
                      transform=ax_e.transAxes,
                      fontsize=8, va="top", ha="left",
                      bbox=dict(boxstyle="round", fc="white", ec="#888", alpha=0.7))
        else:
            ax_e.plot(t, encoded_target, label="target", linewidth=2)
            ax_e.plot(t, encoded_measured, label="measured", linestyle="--")
            if encoded_sRGB is not None:
                ax_e.plot(t, encoded_sRGB, label="sRGB", linestyle=":")
            ax_e.set_ylim(0,1)
            ax_e.set_ylabel("encoded")
            ax_e.set_title(f"{'PQ' if is_hdr else 'Gamma2.2'} (Peak {Y_white:.1f} nits)")
            if not is_hdr:
                def toggle_zoom():
                    cur = getattr(ax_e, "_zoom_low", False)
                    if not cur:
                        ax_e.set_ylim(0,0.3)
                        btn_zoom.config(text="全范围")
                        ax_e._zoom_low = True
                    else:
                        ax_e.set_ylim(0,1)
                        btn_zoom.config(text="放大低亮")
                        ax_e._zoom_low = False
                    canvas_e.draw()
                zoom_bar = ttk.Frame(frm_e); zoom_bar.pack(fill="x", pady=(0,2))
                btn_zoom = ttk.Button(zoom_bar, text="放大低亮", width=10, command=toggle_zoom)
                btn_zoom.pack(side="left", padx=6)
                ax_e.set_yticks([0,0.01,0.02,0.05,0.1,0.2,0.3,0.5,0.7,1.0])
            ax_e.legend(loc="lower right")

        ax_e.set_xlabel("input")
        canvas_e = FigureCanvasTkAgg(fig_e, master=frm_e)
        canvas_e.get_tk_widget().pack(fill="both", expand=True)
        canvas_e.draw()

        self._log("亮度曲线测量完成: 曲线已显示")

    # 工具
    def _get_rgb(self):
        r = max(0, min(1023, int(self.r_var.get())))
        g = max(0, min(1023, int(self.g_var.get())))
        b = max(0, min(1023, int(self.b_var.get())))
        return [r, g, b]

    def _ensure_writer(self, recreate=False):
        if recreate and self.writer:
            self._terminate_writer()
        if self.writer is None:
            print(self.mode_var.get())
            self.writer = ColorWriter(mode=self.mode_var.get())
            time.sleep(0.05)

    def _ensure_reader(self, recreate=False):
        if recreate and self.reader:
            self._terminate_reader()
        if self.reader is None:
            # 注意：color_rw.ColorReader 期望传入的参数对象在其内部会作为单一参数使用
            args_str = self.args_var.get().strip()
            self.reader = ColorReader(args=args_str)
            time.sleep(0.05)

    def _terminate_writer(self):
        try:
            if self.writer:
                # 若内部有子进程可在 ColorWriter 实现里增加 terminate()
                self.writer.terminate()
                # 可选: getattr(self.writer,'proc',None) and self.writer.proc.kill()
        except Exception as e:
            self._log(f"终止 writer 异常: {e}")
        finally:
            self.writer = None

    def _terminate_reader(self):
        try:
            if self.reader:
                self.reader.terminate()
                # 同理如果有子进程句柄可尝试 kill
        except Exception as e:
            self._log(f"终止 reader 异常: {e}")
        finally:
            self.reader = None

    def _apply_xyz(self, xyz):
        if xyz.size < 3 or not np.isfinite(xyz[:3]).all():
            self._log("读取失败: 数据不足")
            return

        X, Y, Z = xyz[:3]
        self.xyz_label.config(text=f"XYZ: {X:.4f} , {Y:.4f} , {Z:.4f}")
        x, y, capY = XYZ_to_xyY([X, Y, Z])
        self.xyy_var.set(f"xyY: {x:.4f} , {y:.4f} , {capY:.4f}")
        self._log(f"读取成功 XYZ: {X:.4f},{Y:.4f},{Z:.4f} xy: {x:.4f},{y:.4f}")

    # 使只读 Entry 支持选中/复制的便捷绑定
    def _enable_select_copy(self, entry: ttk.Entry):
        entry.bind("<Control-a>", lambda e: (entry.select_range(0, 'end'), 'break'))
        entry.bind("<Button-1>", lambda e: entry.focus_set())
        entry.bind("<FocusIn>", lambda e: entry.select_range(0, 'end'))

    def _copy_to_clipboard(self, text: str):
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self._log("已复制 xyY 到剪贴板")
        except Exception as e:
            self._log(f"复制失败: {e}")
    

    def _log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.log_txt.insert("end", f"[{ts}] {msg}\n")
        self.log_txt.see("end")

    def on_exit(self):
        # 防重复
        if getattr(self, "_exiting", False):
            return
        self._exiting = True
        self._log("正在退出，清理资源...")
        try:
            self._terminate_reader()
            self._terminate_writer()
            # 关闭所有可能的 matplotlib 窗口（如果已导入）
            try:
                import matplotlib.pyplot as plt
                plt.close('all')
            except Exception:
                pass
            # 打印存活线程调试（可注释）
            alive = [t.name for t in threading.enumerate() if t is not threading.current_thread()]
            if alive:
                self._log(f"剩余线程: {alive}")
            # 退出 Tk
            try:
                self.quit()
            except Exception:
                pass
            try:
                self.destroy()
            except Exception:
                pass
        finally:
            # 保底强制退出
            sys.exit(0)

if __name__ == "__main__":
    app = ColorMeasureApp()
    app.mainloop()
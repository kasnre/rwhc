# -*- coding: utf-8 -*-
"""
!!!这个文件应该逐渐被 win_display.py 取代
"""

import argparse
import ctypes
from ctypes import wintypes
import json
import re
import sys
import winreg

USER32   = ctypes.WinDLL("user32", use_last_error=True)
KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)

# ---------- flags & error codes ----------
QDC_ONLY_ACTIVE_PATHS   = 0x00000002
QDC_VIRTUAL_MODE_AWARE  = 0x00000010
ERROR_SUCCESS           = 0
ERROR_INSUFFICIENT_BUFFER = 122

# DISPLAYCONFIG_DEVICE_INFO_TYPE
DISPLAYCONFIG_DEVICE_INFO_GET_SOURCE_NAME         = 1
DISPLAYCONFIG_DEVICE_INFO_GET_TARGET_NAME         = 2
DISPLAYCONFIG_DEVICE_INFO_GET_ADVANCED_COLOR_INFO = 9

# Advanced Color bits
ADV_COLOR_SUPPORTED      = 0x1
ADV_COLOR_ENABLED        = 0x2
ADV_COLOR_WIDE_ENFORCED  = 0x4
ADV_COLOR_FORCE_DISABLED = 0x8

# DISPLAYCONFIG_COLOR_ENCODING (for display text)
DISPLAYCONFIG_COLOR_ENCODING_RGB      = 0
DISPLAYCONFIG_COLOR_ENCODING_YCBCR444 = 1
DISPLAYCONFIG_COLOR_ENCODING_YCBCR422 = 2
DISPLAYCONFIG_COLOR_ENCODING_YCBCR420 = 3
DISPLAYCONFIG_COLOR_ENCODING_INTENSITY= 4

# ---------- base structs ----------
class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD),
                ("HighPart", wintypes.LONG)]

class DISPLAYCONFIG_RATIONAL(ctypes.Structure):
    _fields_ = [("Numerator", wintypes.UINT),
                ("Denominator", wintypes.UINT)]

class POINTL(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG),
                ("y", wintypes.LONG)]

class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG)]

class DISPLAYCONFIG_2DREGION(ctypes.Structure):
    _fields_ = [("cx", wintypes.UINT),
                ("cy", wintypes.UINT)]

# ---------- PATH structs ----------
class DISPLAYCONFIG_PATH_SOURCE_INFO(ctypes.Structure):
    _fields_ = [("adapterId", LUID),
                ("id", wintypes.UINT),
                ("modeInfoIdx", wintypes.UINT),
                ("statusFlags", wintypes.UINT)]

class DISPLAYCONFIG_PATH_TARGET_INFO(ctypes.Structure):
    _fields_ = [("adapterId", LUID),
                ("id", wintypes.UINT),
                ("modeInfoIdx", wintypes.UINT),
                ("outputTechnology", wintypes.UINT),
                ("rotation", wintypes.UINT),
                ("scaling", wintypes.UINT),
                ("refreshRate", DISPLAYCONFIG_RATIONAL),
                ("scanLineOrdering", wintypes.UINT),
                ("targetAvailable", wintypes.BOOL),
                ("statusFlags", wintypes.UINT)]

class DISPLAYCONFIG_PATH_INFO(ctypes.Structure):
    _fields_ = [("sourceInfo", DISPLAYCONFIG_PATH_SOURCE_INFO),
                ("targetInfo", DISPLAYCONFIG_PATH_TARGET_INFO),
                ("flags", wintypes.UINT)]

# ---------- MODE structs (required by QueryDisplayConfig) ----------
class DISPLAYCONFIG_VIDEO_SIGNAL_INFO(ctypes.Structure):
    _fields_ = [("pixelRate", ctypes.c_uint64),
                ("hSyncFreq", DISPLAYCONFIG_RATIONAL),
                ("vSyncFreq", DISPLAYCONFIG_RATIONAL),
                ("activeSize", DISPLAYCONFIG_2DREGION),
                ("totalSize", DISPLAYCONFIG_2DREGION),
                ("videoStandard", wintypes.UINT),
                ("scanLineOrdering", wintypes.UINT)]

class DISPLAYCONFIG_TARGET_MODE(ctypes.Structure):
    _fields_ = [("targetVideoSignalInfo", DISPLAYCONFIG_VIDEO_SIGNAL_INFO)]

class DISPLAYCONFIG_SOURCE_MODE(ctypes.Structure):
    _fields_ = [("width", wintypes.UINT),
                ("height", wintypes.UINT),
                ("pixelFormat", wintypes.UINT),
                ("position", POINTL)]

class DISPLAYCONFIG_DESKTOP_IMAGE_INFO(ctypes.Structure):
    _fields_ = [("PathSourceSize", POINTL),
                ("DesktopImageRegion", RECT),
                ("DesktopImageClip", RECT)]

DISPLAYCONFIG_MODE_INFO_TYPE_SOURCE = 1
DISPLAYCONFIG_MODE_INFO_TYPE_TARGET = 2
DISPLAYCONFIG_MODE_INFO_TYPE_DESKTOP_IMAGE = 3

class DISPLAYCONFIG_MODE_INFO_UNION(ctypes.Union):
    _fields_ = [("targetMode", DISPLAYCONFIG_TARGET_MODE),
                ("sourceMode", DISPLAYCONFIG_SOURCE_MODE),
                ("desktopImageInfo", DISPLAYCONFIG_DESKTOP_IMAGE_INFO)]

class DISPLAYCONFIG_MODE_INFO(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("infoType", wintypes.UINT),
                ("id", wintypes.UINT),
                ("adapterId", LUID),
                ("u", DISPLAYCONFIG_MODE_INFO_UNION)]

# ---------- Device info (names / HDR) ----------
class DISPLAYCONFIG_DEVICE_INFO_HEADER(ctypes.Structure):
    _fields_ = [("type", wintypes.UINT),
                ("size", wintypes.UINT),
                ("adapterId", LUID),
                ("id", wintypes.UINT)]

class DISPLAYCONFIG_TARGET_DEVICE_NAME_FLAGS(ctypes.Structure):
    _fields_ = [("value", wintypes.UINT)]

class DISPLAYCONFIG_TARGET_DEVICE_NAME(ctypes.Structure):
    _fields_ = [
        ("header", DISPLAYCONFIG_DEVICE_INFO_HEADER),
        ("flags", DISPLAYCONFIG_TARGET_DEVICE_NAME_FLAGS),
        ("outputTechnology", wintypes.UINT),
        ("edidManufactureId", wintypes.USHORT),
        ("edidProductCodeId", wintypes.USHORT),
        ("connectorInstance", wintypes.UINT),
        ("monitorFriendlyDeviceName", wintypes.WCHAR * 64),
        ("monitorDevicePath", wintypes.WCHAR * 128),
    ]

class DISPLAYCONFIG_GET_ADVANCED_COLOR_INFO(ctypes.Structure):
    _fields_ = [
        ("header", DISPLAYCONFIG_DEVICE_INFO_HEADER),
        ("value", wintypes.UINT),     # bit flags
        ("colorEncoding", wintypes.UINT),
        ("bitsPerColorChannel", wintypes.UINT),
    ]

# ---------- API prototypes ----------
GetDisplayConfigBufferSizes = USER32.GetDisplayConfigBufferSizes
GetDisplayConfigBufferSizes.argtypes = (wintypes.UINT,
                                        ctypes.POINTER(wintypes.UINT),
                                        ctypes.POINTER(wintypes.UINT))
GetDisplayConfigBufferSizes.restype = wintypes.LONG

QueryDisplayConfig = USER32.QueryDisplayConfig
QueryDisplayConfig.argtypes = (wintypes.UINT,
                               ctypes.POINTER(wintypes.UINT),
                               ctypes.POINTER(DISPLAYCONFIG_PATH_INFO),
                               ctypes.POINTER(wintypes.UINT),
                               ctypes.POINTER(DISPLAYCONFIG_MODE_INFO),
                               ctypes.POINTER(wintypes.UINT))
QueryDisplayConfig.restype = wintypes.LONG

DisplayConfigGetDeviceInfo = USER32.DisplayConfigGetDeviceInfo
DisplayConfigGetDeviceInfo.argtypes = (ctypes.POINTER(DISPLAYCONFIG_DEVICE_INFO_HEADER),)
DisplayConfigGetDeviceInfo.restype  = wintypes.LONG

# ---------- helpers ----------
def _format_err(code: int) -> str:
    buf = ctypes.create_unicode_buffer(1024)
    KERNEL32.FormatMessageW(0x00001000, None, code, 0, buf, len(buf), None)
    return buf.value.strip()

def _monitor_name_and_path(adapterId: LUID, targetId: int):
    dn = DISPLAYCONFIG_TARGET_DEVICE_NAME()
    dn.header.type = DISPLAYCONFIG_DEVICE_INFO_GET_TARGET_NAME
    dn.header.size = ctypes.sizeof(DISPLAYCONFIG_TARGET_DEVICE_NAME)
    dn.header.adapterId = adapterId
    dn.header.id = targetId
    ret = DisplayConfigGetDeviceInfo(ctypes.byref(dn.header))
    if ret != ERROR_SUCCESS:
        return f"Target-{targetId}", None
    name = dn.monitorFriendlyDeviceName or f"Target-{targetId}"
    path = dn.monitorDevicePath or None
    return name, path

def _parse_pnpid_from_monitor_path(path: str):
    """
    "\\?\DISPLAY#BOE0C87#5&34b29bae&0&UID4355#{GUID}"
      -> "DISPLAY\\BOE0C87\\5&34b29bae&0&UID4355"
    仅保留 DISPLAY\<HWID>\<Instance> 三段
    """
    if not path:
        return None
    p = path
    if p.startswith("\\\\?\\"):
        p = p[4:]
    # 去掉尾部 \{GUID}
    p = re.sub(r"\\\{[0-9a-fA-F\-]{36}\}$", "", p)
    # '#' -> '\'
    p = p.replace("#", "\\")
    if not p.upper().startswith("DISPLAY\\"):
        return None
    parts = p.split("\\")
    if len(parts) >= 3:
        return "\\".join(parts[:3])
    return p

def _reg_open_64(hive, subkey):
    # 强制读取 64 位视图，避免 32 位 Python 读不到
    return winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)

def _reg_read_device_params(pnpid: str):
    """
    读取 exact 实例：HKLM\SYSTEM\CurrentControlSet\Enum\<pnpid>\Device Parameters
    返回 dict 或 None
    """
    if not pnpid:
        return None
    base = rf"SYSTEM\CurrentControlSet\Enum\{pnpid}\Device Parameters"
    try:
        hive = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
        with _reg_open_64(hive, base) as k:
            def _get_dword(name):
                try:
                    v, t = winreg.QueryValueEx(k, name)
                    return int(v) if t == winreg.REG_DWORD else None
                except FileNotFoundError:
                    return None
            sup = _get_dword("AdvancedColorSupported")
            ena = _get_dword("AdvancedColorEnabled")
            bpc = _get_dword("AdvancedColorBitsPerChannel")
            enc = _get_dword("AdvancedColorEncoding")
            return {
                "supported": None if sup is None else bool(sup),
                "enabled":   None if ena is None else bool(ena),
                "bits_per_channel": bpc,
                "color_encoding":   enc,
                "source": "registry",
                "registry_instance": pnpid,
            }
    except FileNotFoundError:
        return None
    except PermissionError:
        return None

def _reg_read_device_params_fuzzy_from_pnpid(pnpid: str):
    """
    exact 失败时，模糊遍历同一 HWID 下的所有实例：
    - 如果 pnpid 实例部分含 'UIDxxxx'，优先匹配含相同 UID 的实例
    - 退而求其次：找到任一包含 AdvancedColor* 的实例
    """
    if not pnpid:
        return None
    m = re.match(r"^DISPLAY\\([^\\]+)\\(.+)$", pnpid, re.IGNORECASE)
    if not m:
        return None
    hwid, instance_hint = m.group(1), m.group(2)
    uid_match = re.search(r"(UID[0-9A-Fa-f]+)", instance_hint)
    want_uid = uid_match.group(1) if uid_match else None

    hive = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
    base = rf"SYSTEM\CurrentControlSet\Enum\DISPLAY\{hwid}"
    try:
        with _reg_open_64(hive, base) as parent:
            best = None
            i = 0
            while True:
                try:
                    subname = winreg.EnumKey(parent, i)
                except OSError:
                    break
                i += 1
                pnp_try = rf"DISPLAY\{hwid}\{subname}"
                data = _reg_read_device_params(pnp_try)
                if not data:
                    continue
                # 完全匹配同 UID 优先
                if want_uid and want_uid.upper() in subname.upper():
                    data["source"] = "registry(fuzzy-uid)"
                    return data
                # 先记录一个可用项，若后续找不到 UID 完全匹配就用它
                if (data.get("supported") is not None) or (data.get("enabled") is not None):
                    best = data
            if best:
                best["source"] = "registry(fuzzy)"
            return best
    except FileNotFoundError:
        return None

def _get_adv_color_via_dc(adapterId: LUID, targetId: int):
    ac = DISPLAYCONFIG_GET_ADVANCED_COLOR_INFO()
    ac.header.type = DISPLAYCONFIG_DEVICE_INFO_GET_ADVANCED_COLOR_INFO
    ac.header.size = ctypes.sizeof(DISPLAYCONFIG_GET_ADVANCED_COLOR_INFO)
    ac.header.adapterId = adapterId
    ac.header.id = targetId
    ret = DisplayConfigGetDeviceInfo(ctypes.byref(ac.header))
    if ret != ERROR_SUCCESS:
        raise OSError(ret, _format_err(ret))
    v = ac.value
    return {
        "supported": bool(v & ADV_COLOR_SUPPORTED),
        "enabled":   bool(v & ADV_COLOR_ENABLED),
        "wide_color_enforced": bool(v & ADV_COLOR_WIDE_ENFORCED),
        "force_disabled":      bool(v & ADV_COLOR_FORCE_DISABLED),
        "bits_per_channel": ac.bitsPerColorChannel,
        "color_encoding":   ac.colorEncoding,
        "source": "displayconfig",
    }

def _query_paths():
    """
    更稳健的 QueryDisplayConfig：
    - 分配 path + mode 两个数组
    - 先带 QDC_VIRTUAL_MODE_AWARE；失败则去掉
    - 尝试带/不带 currentTopology 指针
    - 122 缓冲不足重试
    返回: list[DISPLAYCONFIG_PATH_INFO]
    """
    def _try(flags, use_topology_ptr):
        numPaths = wintypes.UINT(0)
        numModes = wintypes.UINT(0)
        ret = GetDisplayConfigBufferSizes(flags, ctypes.byref(numPaths), ctypes.byref(numModes))
        if ret != ERROR_SUCCESS:
            return ret, None
        if numPaths.value == 0:
            return ERROR_SUCCESS, []
        paths = (DISPLAYCONFIG_PATH_INFO * numPaths.value)()
        modes = (DISPLAYCONFIG_MODE_INFO * max(1, numModes.value))()
        topo = wintypes.UINT(0) if use_topology_ptr else None
        ret = QueryDisplayConfig(flags,
                                 ctypes.byref(numPaths), paths,
                                 ctypes.byref(numModes), modes,
                                 (ctypes.byref(topo) if topo is not None else None))
        if ret != ERROR_SUCCESS:
            return ret, None
        return ERROR_SUCCESS, [paths[i] for i in range(numPaths.value)]

    for flags in (QDC_ONLY_ACTIVE_PATHS | QDC_VIRTUAL_MODE_AWARE, QDC_ONLY_ACTIVE_PATHS):
        for use_topo in (True, False):
            for attempt in range(3):
                ret, paths = _try(flags, use_topo)
                if ret == ERROR_SUCCESS and paths is not None:
                    return paths
                if ret == ERROR_INSUFFICIENT_BUFFER and attempt < 2:
                    continue
                # 其他错误：换个组合
                break
    raise OSError("QueryDisplayConfig failed under all combinations")

def query_display_info():
    enc_map = {
        DISPLAYCONFIG_COLOR_ENCODING_RGB: "RGB",
        DISPLAYCONFIG_COLOR_ENCODING_YCBCR444: "YCbCr 4:4:4",
        DISPLAYCONFIG_COLOR_ENCODING_YCBCR422: "YCbCr 4:2:2",
        DISPLAYCONFIG_COLOR_ENCODING_YCBCR420: "YCbCr 4:2:0",
        DISPLAYCONFIG_COLOR_ENCODING_INTENSITY: "Intensity",
    }

    results = []
    any_enabled = False

    try:
        paths = _query_paths()
    except Exception as e:
        # 如果连路径都拿不到，直接返回空
        return False, [{"index": -1, "name": "n/a", "supported": None, "enabled": None, "error": str(e)}]

    for idx, p in enumerate(paths):
        t = p.targetInfo
        if not t.targetAvailable:
            continue

        name, monitor_path = _monitor_name_and_path(t.adapterId, t.id)
        pnpid = _parse_pnpid_from_monitor_path(monitor_path) if monitor_path else None

        # 1) 首选 DisplayConfig
        st = None
        try:
            dc = _get_adv_color_via_dc(t.adapterId, t.id)
            st = dc
        except Exception:
            # 2) 回退 注册表（精确）
            st = _reg_read_device_params(pnpid)
            if not st:
                # 3) 回退 注册表（模糊遍历）
                st = _reg_read_device_params_fuzzy_from_pnpid(pnpid)
        if not st:
            st = {"supported": None, "enabled": None, "bits_per_channel": None, "color_encoding": None, "source": "unknown"}

        enabled = st.get("enabled")

        out = {
            "index": idx,
            "name": name,
            "pnp_device_id": pnpid,
            "supported": st.get("supported"),
            "enabled": enabled,
            "bits_per_channel": st.get("bits_per_channel"),
            "color_encoding": st.get("color_encoding"),
            "color_encoding_text": enc_map.get(st.get("color_encoding"), None),
            "source": st.get("source", "unknown"),
        }
        if "registry_instance" in st:
            out["registry_instance"] = st["registry_instance"]
        results.append(out)

    return results

def _find_edid_bytes_by_device_id(device_id: str):
    """
    device_id 形如: DISPLAY\\XXXXYYY\\INSTANCE  (即 list_displays / monitor_var 返回的)
    从注册表 HKLM\SYSTEM\CurrentControlSet\Enum\DISPLAY 下匹配并读取 EDID (首块 128/256 字节)
    """
    if not device_id or not device_id.upper().startswith("DISPLAY\\"):
        return None
    parts = device_id.split("\\")
    if len(parts) < 3:
        return None
    hwid = parts[1].upper()     # XXXXYYY
    # 允许实例模糊匹配 (第三段可能不完全一致)
    hive_path = r"SYSTEM\\CurrentControlSet\\Enum\\DISPLAY"
    try:
        hive = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
        with _reg_open_64(hive, hive_path) as root:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(root, i)
                except OSError:
                    break
                i += 1
                if sub.upper() != hwid:
                    continue
                # 进入 HWID 下各实例
                with _reg_open_64(hive, f"{hive_path}\\{sub}") as hwkey:
                    j = 0
                    while True:
                        try:
                            inst = winreg.EnumKey(hwkey, j)
                        except OSError:
                            break
                        j += 1
                        # 只要 Device Parameters/EDID 存在就取
                        dp_path = f"{hive_path}\\{sub}\\{inst}\\Device Parameters"
                        try:
                            with _reg_open_64(hive, dp_path) as dp:
                                edid_raw, regtype = winreg.QueryValueEx(dp, "EDID")
                                if isinstance(edid_raw, (bytes, bytearray)):
                                    return bytes(edid_raw)
                        except FileNotFoundError:
                            continue
    except Exception:
        return None
    return None

def _parse_cta861_hdr_info(edid: bytes):
    """
    解析 CTA-861 扩展中的 HDR Static Metadata Data Block，提取支持的 EOTF 列表，
    以及可选的“期望内容亮度”字段（并非显示器能力）。
    返回:
      {
        "eotf_supported": [...],
        "desired_content_max_luminance": float|None,   # nit
        "desired_content_max_fall": float|None,        # nit
        "desired_content_min_luminance": float|None    # nit
      }
    """
    out = {}
    if not edid or len(edid) < 128:
        return out
    ext_count = edid[0x7E]
    for i in range(ext_count):
        base = 128 * (i + 1)
        if base + 4 > len(edid):
            break
        if edid[base + 0] != 0x02:  # CTA-861
            continue
        dtd_start = edid[base + 2]
        data_end = base + dtd_start if (dtd_start and base + dtd_start <= len(edid)) else min(base + 127, len(edid))
        p = base + 4
        found = False
        while p < data_end:
            if p >= len(edid): break
            hb = edid[p]; p += 1
            blk_tag = (hb >> 5) & 0x07
            blk_len = hb & 0x1F
            if blk_len == 0 or p + blk_len > len(edid):
                p += max(0, blk_len); continue
            if blk_tag == 0x07 and blk_len >= 2:
                # Extended Tag
                ext_tag = edid[p]
                if ext_tag == 0x06:
                    # HDR Static Metadata Data Block
                    eotf_flags = edid[p + 1]
                    eotf_list = []
                    if eotf_flags & 0x01: eotf_list.append("traditional_sdr")
                    if eotf_flags & 0x02: eotf_list.append("traditional_hdr")
                    if eotf_flags & 0x04: eotf_list.append("pq")
                    if eotf_flags & 0x08: eotf_list.append("hlg")
                    out["eotf_supported"] = eotf_list
                    # 可选亮度字段：Byte3..5（块内偏移），需长度≥6
                    if blk_len >= 6:
                        c_max  = edid[p + 3]
                        c_fall = edid[p + 4]
                        c_min  = edid[p + 5]
                        # CTA-861-G/H: 映射
                        # Desired Max/MaxFALL = (code + 1) * 50 nit
                        # Desired Min = Desired Max * (code / 100)
                        max_lum  = (c_max + 1) * 50.0 if c_max or c_fall or c_min else None
                        max_fall = (c_fall + 1) * 50.0 if c_max or c_fall or c_min else None
                        min_lum  = (max_lum * (c_min / 100.0)) if (max_lum is not None) else None
                        out["desired_content_max_luminance"] = max_lum
                        out["desired_content_max_fall"] = max_fall
                        out["desired_content_min_luminance"] = min_lum
                    found = True
            p += blk_len
        if found:
            break
    return out

def _parse_edid_primaries(edid: bytes):
    """
    解析 EDID v1.x 基本色度原色 + gamma/传递函数信息:
    - 基本色度坐标位于 0x19..0x22，每个坐标 10bit，需 /1024
    - 显示 gamma (EDID 1.3/1.4): byte 0x17 = round(gamma*100) - 100
        * 若值为 0xFF 表示未定义/由扩展决定
    - Feature Support (0x18) bit2 = 1 表示 sRGB 作为默认色彩空间
    - CTA-861 扩展的 HDR Static Metadata Data Block（若存在）：提供 eotf_supported 列表
    返回:
      {
        "red": (rx,ry), "green": (gx,gy), "blue": (bx,by), "white": (wx,wy),
        "gamma": float|None,
        "srgb_default": bool|None,
        "eotf_supported": list[str]  # 可能缺省
      }
    """
    if not edid or len(edid) < 0x23:
        return None

    # 基本色度
    lb1 = edid[0x19]
    lb2 = edid[0x1A]
    def _coord(hi, shift_low, lb):
        return ((hi << 2) | ((lb >> shift_low) & 0x03)) / 1024.0

    rx = _coord(edid[0x1B], 6, lb1)
    ry = _coord(edid[0x1C], 4, lb1)
    gx = _coord(edid[0x1D], 2, lb1)
    gy = _coord(edid[0x1E], 0, lb1)
    bx = _coord(edid[0x1F], 6, lb2)
    by = _coord(edid[0x20], 4, lb2)
    wx = _coord(edid[0x21], 2, lb2)
    wy = _coord(edid[0x22], 0, lb2)

    # Gamma（0x17）
    gamma_raw = edid[0x17] if len(edid) > 0x17 else 0xFF
    if gamma_raw == 0xFF:
        gamma_val = None
    else:
        # EDID spec: gamma = (raw + 100) / 100
        gamma_val = round((gamma_raw + 100) / 100.0, 4)

    # Feature support（0x18）bit2: sRGB default color space
    srgb_default = None
    if len(edid) > 0x18:
        srgb_default = bool(edid[0x18] & 0x04)

    out = {
        "red":   (rx, ry),
        "green": (gx, gy),
        "blue":  (bx, by),
        "white": (wx, wy),
        "gamma": gamma_val,
        "srgb_default": srgb_default
    }

    # CTA-861 扩展中的 HDR EOTF 支持
    hdr_info = _parse_cta861_hdr_info(edid)
    if hdr_info:
        out.update(hdr_info)

    return out

def get_edid_info(device_id: str):
    """
    外部调用: 传入 DISPLAY\\XXXXYYY\\INSTANCE
    返回 dict {red:(x,y), green:(x,y), blue:(x,y), white:(x,y)} 或 None
    """
    edid = _find_edid_bytes_by_device_id(device_id)
    if not edid:
        return None
    return _parse_edid_primaries(edid)

def get_advance_color_status(monitor):
    pnp_target = monitor.split("\\")[1]
    hdrs = query_display_info()
    pnps = [1 for itm in hdrs if itm["pnp_device_id"].split("\\")[1] == pnp_target]
    if len(pnps) >1:
        return None
    for itm in hdrs:
        id_ = itm.get("pnp_device_id")
        if id_ and id_.split("\\")[1] == pnp_target:
            if itm.get("enabled"):
                return True
    return False

if __name__ == "__main__":
    print(get_advance_color_status("MONITOR\\BOE0C87\\{4d36e96e-e325-11ce-bfc1-08002be10318}\\0007"))
    print(query_display_info())
    print(get_edid_info("DISPLAY\\CSF0120\\5&34b29bae&0&UID4353"))
    print(get_edid_info("DISPLAY\\BOE0C87\\5&34b29bae&0&UID4355"))
    # raise SystemExit(main())

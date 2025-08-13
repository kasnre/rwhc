"""
windows display-related functions and structures.
get_all_display_config
get_monitor_rect_by_gdi_name
mscms color management functions and structures
"""

import ctypes
import os
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
mscms = ctypes.WinDLL("mscms", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
kernel32.LocalFree.restype  = wintypes.HLOCAL

ERROR_SUCCESS = 0
ERROR_INSUFFICIENT_BUFFER = 122

QDC_ALL_PATHS = 0x00000001
QDC_ONLY_ACTIVE_PATHS = 0x00000002
QDC_VIRTUAL_MODE_AWARE = 0x00000010

MONITORINFOF_PRIMARY = 0x00000001


DISPLAYCONFIG_VIDEO_OUTPUT_TECHNOLOGY = wintypes.UINT
DISPLAYCONFIG_ROTATION = wintypes.UINT
DISPLAYCONFIG_SCALING = wintypes.UINT
DISPLAYCONFIG_SCANLINE_ORDERING = wintypes.UINT
DISPLAYCONFIG_MODE_INFO_TYPE = wintypes.UINT
DISPLAYCONFIG_PIXELFORMAT = wintypes.UINT

DISPLAYCONFIG_DEVICE_INFO_GET_SOURCE_NAME = 1
DISPLAYCONFIG_DEVICE_INFO_GET_TARGET_NAME = 2
DISPLAYCONFIG_DEVICE_INFO_GET_TARGET_PREFERRED_MODE = 3
DISPLAYCONFIG_DEVICE_INFO_GET_ADAPTER_NAME = 4
DISPLAYCONFIG_DEVICE_INFO_GET_TARGET_BASE_TYPE = 6
DISPLAYCONFIG_DEVICE_INFO_GET_ADVANCED_COLOR_INFO = 9
DISPLAYCONFIG_DEVICE_INFO_GET_SDR_WHITE_LEVEL = 11

# DISPLAYCONFIG_MODE_INFO_TYPE
DISPLAYCONFIG_MODE_INFO_TYPE_SOURCE = 1
DISPLAYCONFIG_MODE_INFO_TYPE_TARGET = 2

# WCS_PROFILE_MANAGEMENT_SCOPE
WCS_PROFILE_MANAGEMENT_SCOPE_SYSTEM_WIDE  = 0
WCS_PROFILE_MANAGEMENT_SCOPE_CURRENT_USER = 1
# https://learn.microsoft.com/en-us/windows/win32/api/icm/ne-icm-wcs_profile_management_scope :contentReference[oaicite:1]{index=1}

# COLORPROFILETYPE（这里只会用到 CPT_ICC）
CPT_ICC  = 0
CPT_DMP  = 1
CPT_CAMP = 2
CPT_GMMP = 3
# https://learn.microsoft.com/en-us/windows/win32/api/icm/ne-icm-colorprofiletype :contentReference[oaicite:2]{index=2}

# COLORPROFILESUBTYPE（与显示默认 ICC 相关的两个子类）
CPST_STANDARD_DISPLAY_COLOR_MODE = 7  # SDR/标准色彩模式
CPST_EXTENDED_DISPLAY_COLOR_MODE = 8  # HDR/高级色彩模式
# 官方枚举页目前文本是 TBD，但这两个枚举是在 16232 SDK 中新增的，常量即为 7/8。参考 SDK 变更记录。 :contentReference[oaicite:3]{index=3}
class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]

class DISPLAYCONFIG_RATIONAL(ctypes.Structure):
    _fields_ = [
        ("Numerator", ctypes.c_uint32),
        ("Denominator", ctypes.c_uint32),
    ]

class DISPLAYCONFIG_2DREGION(ctypes.Structure):
    _fields_ = [("cx", wintypes.UINT), ("cy", wintypes.UINT)]

class DISPLAYCONFIG_VIDEO_SIGNAL_INFO(ctypes.Structure):
    _fields_ = [
        ("pixelRate", ctypes.c_uint64),
        ("hSyncFreq", DISPLAYCONFIG_RATIONAL),
        ("vSyncFreq", DISPLAYCONFIG_RATIONAL),
        ("activeSize", DISPLAYCONFIG_2DREGION),
        ("totalSize", DISPLAYCONFIG_2DREGION),
        ("videoStandard", wintypes.UINT),
        ("scanLineOrdering", DISPLAYCONFIG_SCANLINE_ORDERING),
    ]

class DISPLAYCONFIG_TARGET_MODE(ctypes.Structure):
    _fields_ = [("targetVideoSignalInfo", DISPLAYCONFIG_VIDEO_SIGNAL_INFO)]

class POINTL(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

class DISPLAYCONFIG_SOURCE_MODE(ctypes.Structure):
    _fields_ = [
        ("width", wintypes.UINT),
        ("height", wintypes.UINT),
        ("pixelFormat", DISPLAYCONFIG_PIXELFORMAT),
        ("position", POINTL),
    ]

class DISPLAYCONFIG_MODE_INFO_UNION(ctypes.Union):
    _fields_ = [("targetMode", DISPLAYCONFIG_TARGET_MODE),
                ("sourceMode", DISPLAYCONFIG_SOURCE_MODE)]

class DISPLAYCONFIG_MODE_INFO(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [
        ("infoType", DISPLAYCONFIG_MODE_INFO_TYPE),
        ("id", wintypes.UINT),
        ("adapterId", LUID),
        ("u", DISPLAYCONFIG_MODE_INFO_UNION),
    ]

class DISPLAYCONFIG_PATH_SOURCE_INFO(ctypes.Structure):
    _fields_ = [
        ("adapterId", LUID),
        ("id", wintypes.UINT),
        ("modeInfoIdx", wintypes.UINT),
        ("statusFlags", wintypes.UINT),
    ]

class DISPLAYCONFIG_PATH_TARGET_INFO(ctypes.Structure):
    _fields_ = [
        ("adapterId", LUID),
        ("id", wintypes.UINT),
        ("modeInfoIdx", wintypes.UINT),
        ("outputTechnology", DISPLAYCONFIG_VIDEO_OUTPUT_TECHNOLOGY),
        ("rotation", DISPLAYCONFIG_ROTATION),
        ("scaling", DISPLAYCONFIG_SCALING),
        ("refreshRate", DISPLAYCONFIG_RATIONAL),
        ("scanLineOrdering", DISPLAYCONFIG_SCANLINE_ORDERING),
        ("targetAvailable", wintypes.BOOL),
        ("statusFlags", wintypes.UINT),
    ]

class DISPLAYCONFIG_PATH_INFO(ctypes.Structure):
    _fields_ = [
        ("sourceInfo", DISPLAYCONFIG_PATH_SOURCE_INFO),
        ("targetInfo", DISPLAYCONFIG_PATH_TARGET_INFO),
        ("flags", wintypes.UINT),
    ]

class DISPLAYCONFIG_DEVICE_INFO_HEADER(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.UINT),
        ("size", wintypes.UINT),
        ("adapterId", LUID),
        ("id", wintypes.UINT),
    ]

class DISPLAYCONFIG_TARGET_DEVICE_NAME_FLAGS(ctypes.Structure):
    _fields_ = [("value", wintypes.UINT)]

class DISPLAYCONFIG_TARGET_DEVICE_NAME(ctypes.Structure):
    _fields_ = [
        ("header", DISPLAYCONFIG_DEVICE_INFO_HEADER),
        ("flags", DISPLAYCONFIG_TARGET_DEVICE_NAME_FLAGS),
        ("outputTechnology", DISPLAYCONFIG_VIDEO_OUTPUT_TECHNOLOGY),
        ("edidManufactureId", wintypes.USHORT),
        ("edidProductCodeId", wintypes.USHORT),
        ("connectorInstance", wintypes.UINT),
        ("monitorFriendlyDeviceName", wintypes.WCHAR * 64),
        ("monitorDevicePath", wintypes.WCHAR * 128),
    ]

class DISPLAYCONFIG_ADAPTER_NAME(ctypes.Structure):
    _fields_ = [
        ("header", DISPLAYCONFIG_DEVICE_INFO_HEADER),
        ("adapterDevicePath", wintypes.WCHAR * 128),
    ]
    
class DISPLAYCONFIG_GET_ADVANCED_COLOR_INFO(ctypes.Structure):
    _fields_ = [
        ("header", DISPLAYCONFIG_DEVICE_INFO_HEADER),
        # wingdi.h: union { struct { UINT32 _bitfield; } Anonymous; UINT32 value; }
        ("value", ctypes.c_uint32),            # 按位标志：见下面的掩码
        ("colorEncoding", ctypes.c_int32),     # DISPLAYCONFIG_COLOR_ENCODING
        ("bitsPerColorChannel", ctypes.c_uint32),
    ]

class DISPLAYCONFIG_SDR_WHITE_LEVEL(ctypes.Structure):
    _fields_ = [
        ("header", DISPLAYCONFIG_DEVICE_INFO_HEADER),
        ("SDRWhiteLevel", ctypes.c_uint32),    # value/1000 * 80 = nits
    ]

class DISPLAYCONFIG_TARGET_BASE_TYPE(ctypes.Structure):
    _fields_ = [
        ("header", DISPLAYCONFIG_DEVICE_INFO_HEADER),
        ("baseOutputTechnology", ctypes.c_int32),  # DISPLAYCONFIG_VIDEO_OUTPUT_TECHNOLOGY
    ]
    
# 源设备名（\\.\DISPLAYx）
class DISPLAYCONFIG_SOURCE_DEVICE_NAME(ctypes.Structure):
    _fields_ = [
        ("header", DISPLAYCONFIG_DEVICE_INFO_HEADER),
        ("viewGdiDeviceName", wintypes.WCHAR * 32),
    ]

class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long)]

class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * 32),  # 形如 \\.\DISPLAY1
    ]

MonitorEnumProc = ctypes.WINFUNCTYPE(
    wintypes.BOOL,
    wintypes.HDC,
    wintypes.HDC,
    ctypes.POINTER(RECT),
    wintypes.LPARAM
)

EnumDisplayMonitors = user32.EnumDisplayMonitors
EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.c_void_p, MonitorEnumProc, wintypes.LPARAM]
EnumDisplayMonitors.restype  = wintypes.BOOL

GetMonitorInfoW = user32.GetMonitorInfoW
GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFOEXW)]
GetMonitorInfoW.restype  = wintypes.BOOL

# 目标“首选模式”（面板 native）
class DISPLAYCONFIG_TARGET_PREFERRED_MODE(ctypes.Structure):
    _fields_ = [
        ("header", DISPLAYCONFIG_DEVICE_INFO_HEADER),
        ("targetMode", DISPLAYCONFIG_TARGET_MODE),
    ]

user32.GetDisplayConfigBufferSizes.argtypes = [
    wintypes.UINT,
    ctypes.POINTER(wintypes.UINT),
    ctypes.POINTER(wintypes.UINT),
]
user32.GetDisplayConfigBufferSizes.restype = wintypes.LONG

user32.QueryDisplayConfig.argtypes = [
    wintypes.UINT,
    ctypes.POINTER(wintypes.UINT),
    ctypes.POINTER(DISPLAYCONFIG_PATH_INFO),   # ← expects LP_DISPLAYCONFIG_PATH_INFO
    ctypes.POINTER(wintypes.UINT),
    ctypes.POINTER(DISPLAYCONFIG_MODE_INFO),   # ← expects LP_DISPLAYCONFIG_MODE_INFO
    ctypes.c_void_p,                           # optional
]
user32.QueryDisplayConfig.restype = wintypes.LONG

user32.DisplayConfigGetDeviceInfo.argtypes = [ctypes.POINTER(DISPLAYCONFIG_DEVICE_INFO_HEADER)]
user32.DisplayConfigGetDeviceInfo.restype = wintypes.LONG

# 安装/卸载 ICC（复制/删除 系统色彩目录 的文件）
InstallColorProfileW = mscms.InstallColorProfileW
InstallColorProfileW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
InstallColorProfileW.restype = wintypes.BOOL

UninstallColorProfileW = mscms.UninstallColorProfileW
UninstallColorProfileW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.BOOL)
UninstallColorProfileW.restype = wintypes.BOOL

# HRESULT ColorProfileGetDisplayUserScope(LUID adapter, UINT32 sourceId, WCS_PROFILE_MANAGEMENT_SCOPE* scope);
mscms.ColorProfileGetDisplayUserScope.argtypes = [LUID, wintypes.UINT, ctypes.POINTER(wintypes.DWORD)]
mscms.ColorProfileGetDisplayUserScope.restype  = ctypes.HRESULT
# https://learn.microsoft.com/en-us/windows/win32/api/icm/nf-icm-colorprofilegetdisplayuserscope :contentReference[oaicite:4]{index=4}

# HRESULT ColorProfileGetDisplayDefault(scope, LUID adapter, UINT32 sourceId, COLORPROFILETYPE t, COLORPROFILESUBTYPE st, LPWSTR* profileName);
mscms.ColorProfileGetDisplayDefault.argtypes = [wintypes.DWORD, LUID, wintypes.UINT,
                                                wintypes.DWORD, wintypes.DWORD,
                                                ctypes.POINTER(ctypes.c_wchar_p)]
mscms.ColorProfileGetDisplayDefault.restype  = ctypes.HRESULT
# https://learn.microsoft.com/en-us/windows/win32/api/icm/nf-icm-colorprofilegetdisplaydefault :contentReference[oaicite:5]{index=5}

# HRESULT ColorProfileSetDisplayDefaultAssociation(scope, PCWSTR profileName, COLORPROFILETYPE t, COLORPROFILESUBTYPE st, LUID adapter, UINT32 sourceId);
mscms.ColorProfileSetDisplayDefaultAssociation.argtypes = [wintypes.DWORD, wintypes.LPCWSTR,
                                                           wintypes.DWORD, wintypes.DWORD,
                                                           LUID, wintypes.UINT]
mscms.ColorProfileSetDisplayDefaultAssociation.restype  = ctypes.HRESULT
# https://learn.microsoft.com/en-us/windows/win32/api/icm/nf-icm-colorprofilesetdisplaydefaultassociation :contentReference[oaicite:6]{index=6}

# HRESULT ColorProfileAddDisplayAssociation(scope, PCWSTR profileName, LUID adapter, UINT32 sourceId, BOOL setAsDefault, BOOL associateAsAdvancedColor);
mscms.ColorProfileAddDisplayAssociation.argtypes = [wintypes.DWORD, wintypes.LPCWSTR,
                                                    LUID, wintypes.UINT,
                                                    wintypes.BOOL, wintypes.BOOL]
mscms.ColorProfileAddDisplayAssociation.restype  = ctypes.HRESULT
# https://learn.microsoft.com/en-us/windows/win32/api/icm/nf-icm-colorprofileadddisplayassociation :contentReference[oaicite:7]{index=7}

# HRESULT ColorProfileRemoveDisplayAssociation(scope, PCWSTR profileName, LUID adapter, UINT32 sourceId, BOOL associateAsAdvancedColor);
mscms.ColorProfileRemoveDisplayAssociation.argtypes = [wintypes.DWORD, wintypes.LPCWSTR,
                                                       LUID, wintypes.UINT, wintypes.BOOL]
mscms.ColorProfileRemoveDisplayAssociation.restype  = ctypes.HRESULT
# 该函数在 mscms 导出中可见，官方入口见 API 列表。 :contentReference[oaicite:8]{index=8}

# HRESULT ColorProfileGetDisplayList(scope, LUID adapter, UINT32 sourceId, LPWSTR** profileList, PDWORD profileCount);
mscms.ColorProfileGetDisplayList.argtypes = [wintypes.DWORD, LUID, wintypes.UINT,
                                             ctypes.POINTER(ctypes.POINTER(ctypes.c_wchar_p)),
                                             ctypes.POINTER(wintypes.DWORD)]
mscms.ColorProfileGetDisplayList.restype  = ctypes.HRESULT
# https://learn.microsoft.com/en-us/windows/win32/api/icm/nf-icm-colorprofilegetdisplaylist :contentReference[oaicite:9]{index=9}

ROTATION_MAP = {
    1: "0°(Landscape)", 2: "90°(Portrait)", 3: "180°", 4: "270°"
}
SCALING_MAP = {
    1: "Identity", 2: "Centered", 3: "Stretched",
    4: "AspectRatioCenteredMax", 5: "Custom", 128: "Preferred"
}
COLOR_ENCODING_MAP = {
    0: "RGB", 1: "YCbCr 4:4:4", 2: "YCbCr 4:2:2", 3: "YCbCr 4:2:0", 4: "Intensity"
}
# 常见的视频输出技术（并不穷举）
OUTPUT_TECH_MAP = {
    0: "Other", 3: "Component", 4: "DVI", 5: "HDMI", 6: "LVDS",
    8: "SDI", 9: "DisplayPort(external?)", 10: "DisplayPort", 11: "DisplayPort(eDP)"
}
# DISPLAYCONFIG_GET_ADVANCED_COLOR_INFO 的 bit 含义（来自 SDK/实现示例）
ADV_COLOR_SUPPORTED     = 0x1
ADV_COLOR_ENABLED       = 0x2
WIDE_COLOR_ENFORCED     = 0x4
ADV_COLOR_FORCE_DISABLED= 0x8



def _safe_map(d, v): return d.get(int(v), f"UNKNOWN({int(v)})")

def _check(api_name, ret):
    if ret != 0:
        raise OSError(f"{api_name} failed with error {ret}")

def _make_header(struct_type, dtype, adapterId, did):
    obj = struct_type()
    obj.header.type = dtype
    obj.header.size = ctypes.sizeof(obj)
    obj.header.adapterId = adapterId
    obj.header.id = did
    return obj

def _rational_to_float(r):
    try:
        return r.Numerator / r.Denominator if r.Denominator else 0.0
    except Exception:
        return 0.0

def _mode_from_idx(modes, idx, expect):  # expect: 'target'/'source'/'desktop'
    if idx == 0xFFFFFFFF or idx < 0 or idx >= len(modes):
        return None
    mi = modes[idx]
    # mi.infoType: 2=TARGET, 1=SOURCE, 3=DESKTOP_IMAGE_INFO（Windows 10+）
    return mi

def _hr_u32(x: int) -> int:
    return x & 0xFFFFFFFF  # ctypes 可能给你有符号数，统一转无符号

HR_FILE_NOT_FOUND = 0x80070002  # HRESULT_FROM_WIN32(ERROR_FILE_NOT_FOUND)
HR_ERROR_NOT_FOUND = 0x80070490 # HRESULT_FROM_WIN32(ERROR_NOT_FOUND)

def _hr_from_exc(e) -> int:
    w = getattr(e, "winerror", None)
    if w is None:
        w = getattr(e, "errno", 0)
    return (w or 0) & 0xFFFFFFFF

def _check_hr(api: str, hr: int):
    if hr != 0:  # S_OK == 0
        raise OSError(f"{api} failed, HRESULT=0x{hr & 0xFFFFFFFF:08X}")

def check_result(api: str, code: int):
    if code != ERROR_SUCCESS:
        raise OSError(f"{api} failed with error {code}")
    
def luid_from_dict(d: dict) -> LUID:
    l = LUID()
    l.LowPart  = int(d["low"])
    l.HighPart = int(d["high"])
    return l

def _get_last_error():
    code = ctypes.get_last_error()
    return f"WinErr={code}"

def get_monitor_rect_by_gdi_name(gdi_name: str):
    monitors = []
    def _cb(hMonitor, hdcMonitor, lprcMonitor, dwData):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if GetMonitorInfoW(ctypes.c_void_p(hMonitor), ctypes.byref(info)):
            r = info.rcMonitor
            monitors.append({
                "gdi_name": info.szDevice,
                "left":   r.left,
                "top":    r.top,
                "right":  r.right,
                "bottom": r.bottom,
                "is_primary": bool(info.dwFlags & MONITORINFOF_PRIMARY),
            })
        return True
    cb = MonitorEnumProc(_cb)
    if not EnumDisplayMonitors(0, None, cb, 0):
        raise OSError("EnumDisplayMonitors failed")
    
    for m in monitors:
        if m["gdi_name"].lower() == gdi_name.lower():
            return m
    return None

def install_icc(profile_path):
    """
    将本地 ICC/ICM 文件复制到系统色彩目录。成功返回目标路径。
    """
    profile_path = os.path.abspath(profile_path)
    if not os.path.isfile(profile_path):
        raise FileNotFoundError(profile_path)
    ok = InstallColorProfileW(None, profile_path)
    if not ok:
        raise OSError(f"InstallColorProfileW failed: {_get_last_error()}")
    # 复制后文件位于系统色彩目录（通常 C:\Windows\System32\spool\drivers\color）
    # 为稳妥，调用方应传入系统色彩目录内的完整路径用于后续关联/默认设置
    return True

def uninstall_icc(profile_fullpath, force=False):
    """
    从系统色彩目录删除 ICC（要求传入系统目录内的完整路径）。
    force=True 将强制删除（如仍有关联）。
    """
    ok = UninstallColorProfileW(None, profile_fullpath, wintypes.BOOL(force))
    if not ok:
        raise OSError(f"UninstallColorProfileW failed: {_get_last_error()}")
    return True

def cp_get_display_user_scope(adapter_luid: LUID, source_id: int) -> int:
    scope = wintypes.DWORD()
    hr = mscms.ColorProfileGetDisplayUserScope(adapter_luid, wintypes.UINT(source_id), ctypes.byref(scope))
    _check_hr("ColorProfileGetDisplayUserScope", hr)
    return scope.value  # 0=SYSTEM_WIDE, 1=CURRENT_USER

def cp_get_display_default_profile(adapter_luid, source_id,
                                   scope=WCS_PROFILE_MANAGEMENT_SCOPE_CURRENT_USER,
                                   advanced=False) -> str | None:
    out = ctypes.c_wchar_p()
    subtype = CPST_EXTENDED_DISPLAY_COLOR_MODE if advanced else CPST_STANDARD_DISPLAY_COLOR_MODE
    try:
        # 注意：restype=HRESULT 时，失败会在这里直接抛异常
        mscms.ColorProfileGetDisplayDefault(
            scope, adapter_luid, wintypes.UINT(source_id),
            CPT_ICC, subtype, ctypes.byref(out)
        )
        return out.value  # S_OK
    except (FileNotFoundError, OSError) as e:
        hr = _hr_from_exc(e)
        if hr in (HR_FILE_NOT_FOUND, HR_ERROR_NOT_FOUND):
            return None  # 没有默认 ICC → 返回 None
        raise  # 其它异常继续抛出
    finally:
        if out:
            kernel32.LocalFree(out)

def cp_set_display_default_profile(adapter_luid: LUID, source_id: int, profile_path: str,
                                   scope: int = WCS_PROFILE_MANAGEMENT_SCOPE_CURRENT_USER,
                                   advanced: bool = False) -> None:
    subtype = CPST_EXTENDED_DISPLAY_COLOR_MODE if advanced else CPST_STANDARD_DISPLAY_COLOR_MODE
    hr = mscms.ColorProfileSetDisplayDefaultAssociation(
        wintypes.DWORD(scope), wintypes.LPCWSTR(profile_path),
        wintypes.DWORD(CPT_ICC), wintypes.DWORD(subtype),
        adapter_luid, wintypes.UINT(source_id)
    )
    _check_hr("ColorProfileSetDisplayDefaultAssociation", hr)

def cp_add_display_association(adapter_luid: LUID, source_id: int, profile_path: str,
                               scope: int = WCS_PROFILE_MANAGEMENT_SCOPE_CURRENT_USER,
                               set_as_default: bool = False,
                               associate_as_advanced_color: bool = False) -> None:
    hr = mscms.ColorProfileAddDisplayAssociation(
        wintypes.DWORD(scope), wintypes.LPCWSTR(profile_path),
        adapter_luid, wintypes.UINT(source_id),
        wintypes.BOOL(bool(set_as_default)),
        wintypes.BOOL(bool(associate_as_advanced_color))
    )
    _check_hr("ColorProfileAddDisplayAssociation", hr)

def cp_remove_display_association(adapter_luid: LUID, source_id: int, profile_path: str,
                                  scope: int = WCS_PROFILE_MANAGEMENT_SCOPE_CURRENT_USER,
                                  associate_as_advanced_color: bool = False) -> None:
    hr = mscms.ColorProfileRemoveDisplayAssociation(
        wintypes.DWORD(scope), wintypes.LPCWSTR(profile_path),
        adapter_luid, wintypes.UINT(source_id),
        wintypes.BOOL(bool(associate_as_advanced_color))
    )
    _check_hr("ColorProfileRemoveDisplayAssociation", hr)

def cp_get_display_profile_list(adapter_luid, source_id,
                                scope=WCS_PROFILE_MANAGEMENT_SCOPE_CURRENT_USER) -> list[str]:
    # FIXME not work, always return []
    pp_list = ctypes.POINTER(ctypes.c_wchar_p)()
    count   = wintypes.DWORD(0)
    try:
        mscms.ColorProfileGetDisplayList(
            scope, adapter_luid, wintypes.UINT(source_id),
            ctypes.byref(pp_list), ctypes.byref(count)
        )
        n = count.value or 0
        print(count.value)
        if n == 0 or not pp_list:
            return []
        ArrT = ctypes.c_wchar_p * n
        arr = ctypes.cast(pp_list, ctypes.POINTER(ArrT)).contents
        return [arr[i] for i in range(n)]
    except (FileNotFoundError, OSError) as e:
        hr = _hr_from_exc(e)
        if hr in (HR_FILE_NOT_FOUND, HR_ERROR_NOT_FOUND):
            return []  # 没有关联 → 空列表
        raise
    finally:
        if pp_list:
            kernel32.LocalFree(pp_list)

def get_all_display_config():
    """
    获取所有激活中显示器的设置
    """
    flags = QDC_ONLY_ACTIVE_PATHS | QDC_VIRTUAL_MODE_AWARE

    path_count = wintypes.UINT(0)
    mode_count = wintypes.UINT(0)
    check_result(
        "GetDisplayConfigBufferSizes",
        user32.GetDisplayConfigBufferSizes(flags, ctypes.byref(path_count), ctypes.byref(mode_count))
    )
    while True:
        PathArray = DISPLAYCONFIG_PATH_INFO * path_count.value
        ModeArray  = DISPLAYCONFIG_MODE_INFO * mode_count.value
        paths = PathArray()
        modes = ModeArray()

        pc = wintypes.UINT(path_count.value)
        mc = wintypes.UINT(mode_count.value)

        # *** KEY FIX: pass arrays directly (paths, modes), NOT byref(paths/modes)
        result = user32.QueryDisplayConfig(
            flags,
            ctypes.byref(pc),
            paths,                 # <-- pass array instance
            ctypes.byref(mc),
            modes,                 # <-- pass array instance
            None
        )

        if result == ERROR_INSUFFICIENT_BUFFER:
            # sizes changed during the call; retry with new sizes
            path_count = pc
            mode_count = mc
            continue
        break
    
    paths = paths[:pc.value]
    modes = modes[:mc.value]
    
    results = []

    for pi, p in enumerate(paths):
        t = p.targetInfo
        s = p.sourceInfo

        # 适配器名
        aname = _make_header(DISPLAYCONFIG_ADAPTER_NAME,
                             DISPLAYCONFIG_DEVICE_INFO_GET_ADAPTER_NAME,
                             t.adapterId, 0)
        _check("DisplayConfigGetDeviceInfo(AdapterName)",
               user32.DisplayConfigGetDeviceInfo(ctypes.byref(aname.header)))

        # 目标（显示器）名
        tname = _make_header(DISPLAYCONFIG_TARGET_DEVICE_NAME,
                             DISPLAYCONFIG_DEVICE_INFO_GET_TARGET_NAME,
                             t.adapterId, t.id)
        _check("DisplayConfigGetDeviceInfo(TargetName)",
               user32.DisplayConfigGetDeviceInfo(ctypes.byref(tname.header)))

        # 源（GDI 名）
        sname = _make_header(DISPLAYCONFIG_SOURCE_DEVICE_NAME,
                             DISPLAYCONFIG_DEVICE_INFO_GET_SOURCE_NAME,
                             s.adapterId, s.id)
        _check("DisplayConfigGetDeviceInfo(SourceName)",
               user32.DisplayConfigGetDeviceInfo(ctypes.byref(sname.header)))

        # 目标基础输出类型
        base_out = None
        btype = _make_header(DISPLAYCONFIG_TARGET_BASE_TYPE,
                             DISPLAYCONFIG_DEVICE_INFO_GET_TARGET_BASE_TYPE,
                             t.adapterId, t.id)
        if user32.DisplayConfigGetDeviceInfo(ctypes.byref(btype.header)) == 0:
            base_out = _safe_map(OUTPUT_TECH_MAP, btype.baseOutputTechnology)

        # 首选目标模式（面板 native）
        preferred_mode = None
        pref = _make_header(DISPLAYCONFIG_TARGET_PREFERRED_MODE,
                            DISPLAYCONFIG_DEVICE_INFO_GET_TARGET_PREFERRED_MODE,
                            t.adapterId, t.id)
        if user32.DisplayConfigGetDeviceInfo(ctypes.byref(pref.header)) == 0:
            tm = pref.targetMode.targetVideoSignalInfo
            rr = tm.vSyncFreq.Numerator / tm.vSyncFreq.Denominator if tm.vSyncFreq.Denominator else 0.0
            preferred_mode = {
                "width": int(tm.activeSize.cx),
                "height": int(tm.activeSize.cy),
                "refresh_hz": float(rr),
            }

        # 高级色彩（HDR/WCG/位深/编码/标志）
        adv = None
        ac = _make_header(DISPLAYCONFIG_GET_ADVANCED_COLOR_INFO,
                          DISPLAYCONFIG_DEVICE_INFO_GET_ADVANCED_COLOR_INFO,
                          t.adapterId, t.id)
        if user32.DisplayConfigGetDeviceInfo(ctypes.byref(ac.header)) == 0:
            vals = ac.value
            adv = {
                "supported": bool(vals & ADV_COLOR_SUPPORTED),
                "enabled": bool(vals & ADV_COLOR_ENABLED),
                "wide_color_enforced": bool(vals & WIDE_COLOR_ENFORCED),
                "force_disabled": bool(vals & ADV_COLOR_FORCE_DISABLED),
                "encoding": _safe_map(COLOR_ENCODING_MAP, ac.colorEncoding),
                "bits_per_channel": int(ac.bitsPerColorChannel),
            }

        # SDR 白场
        sdr_white_raw = None
        sdr_white_nits = None
        sdr = _make_header(DISPLAYCONFIG_SDR_WHITE_LEVEL,
                           DISPLAYCONFIG_DEVICE_INFO_GET_SDR_WHITE_LEVEL,
                           t.adapterId, t.id)
        if user32.DisplayConfigGetDeviceInfo(ctypes.byref(sdr.header)) == 0:
            sdr_white_raw = int(sdr.SDRWhiteLevel)
            sdr_white_nits = float((sdr.SDRWhiteLevel / 1000.0) * 80.0)

        # 当前路径的 timing/state
        rr_now = _rational_to_float(t.refreshRate)

        # 从 modes[] 取 source/target 模式（如果可用）
        source_mode = None
        if hasattr(s, "modeInfoIdx") and s.modeInfoIdx != 0xFFFFFFFF:
            mi = _mode_from_idx(modes, s.modeInfoIdx, "source")
            if mi and mi.infoType == DISPLAYCONFIG_MODE_INFO_TYPE_SOURCE:
                sm = mi.sourceMode
                source_mode = {
                    "width": int(sm.width),
                    "height": int(sm.height),
                    "pixel_format": int(sm.pixelFormat),
                    "position": {"x": int(sm.position.x), "y": int(sm.position.y)},
                }


        target_mode = None
        if hasattr(t, "modeInfoIdx") and t.modeInfoIdx != 0xFFFFFFFF:
            mi = _mode_from_idx(modes, t.modeInfoIdx, "target")
            if mi and mi.infoType == DISPLAYCONFIG_MODE_INFO_TYPE_TARGET:
                tv = mi.targetMode.targetVideoSignalInfo
                rr2 = tv.vSyncFreq.Numerator / tv.vSyncFreq.Denominator if tv.vSyncFreq.Denominator else 0.0
                target_mode = {
                    "width": int(tv.activeSize.cx),
                    "height": int(tv.activeSize.cy),
                    "refresh_hz": float(rr2),
                }
        item = {
            "path_index": pi,
            "adapter_device_path": aname.adapterDevicePath,            # str
            "adapter_luid": {
                "low":  int(t.adapterId.LowPart),
                "high": int(t.adapterId.HighPart),
            },
            "source": {
                "id": int(s.id),
                "gdi_name": sname.viewGdiDeviceName,                  # str
                "mode": source_mode,
            },
            "target": {
                "id": int(t.id),
                "friendly_name": tname.monitorFriendlyDeviceName,     # str
                "device_path": tname.monitorDevicePath,               # str
                "output_technology": _safe_map(OUTPUT_TECH_MAP, t.outputTechnology),
                "base_output_type": base_out,
                "rotation": _safe_map(ROTATION_MAP, t.rotation),
                "scaling": _safe_map(SCALING_MAP, t.scaling),
                "scanline_ordering": int(t.scanLineOrdering),
                "refresh_hz": float(rr_now),
                "available": bool(t.targetAvailable),
                "status_flags_hex": f"0x{t.statusFlags:08X}",
                "preferred_mode": preferred_mode,
                "advanced_color": adv,
                "sdr_white_level_raw": sdr_white_raw,
                "sdr_white_level_nits": sdr_white_nits,
                "mode": target_mode,
            },
        }

        results.append(item)

    return results


if __name__ == "__main__":
    import json
    ret = get_all_display_config()
    for itm in ret:
        print(json.dumps(itm, indent=2, ensure_ascii=False))
    exit()
    cfgs = get_all_display_config()
    d0 = cfgs[0]
    luid = luid_from_dict(d0["adapter_luid"])
    sid  = d0["source"]["id"]

    # 查询当前作用域（用户/系统）
    scope = cp_get_display_user_scope(luid, sid)  # 0=系统 1=当前用户
    # print(scope)
    # 取默认 ICC（标准/高级二选一）
    sdr_icc = cp_get_display_default_profile(luid, sid,
        scope=WCS_PROFILE_MANAGEMENT_SCOPE_CURRENT_USER, advanced=False)
    hdr_icc = cp_get_display_default_profile(luid, sid,
        scope=WCS_PROFILE_MANAGEMENT_SCOPE_CURRENT_USER, advanced=True)
    print(sdr_icc,hdr_icc)

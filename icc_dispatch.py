# -*- coding: utf-8 -*-
"""
Windows: 管理显示器与 ICC/ICM 配置文件的关联（安装、关联、设为默认、移除）
依赖: 仅标准库 (ctypes, argparse)
"""

import argparse
import os
import sys
import ctypes
from ctypes import wintypes

# ---- 常量定义 ----
MSCMS = ctypes.WinDLL("mscms", use_last_error=True)
USER32 = ctypes.WinDLL("user32", use_last_error=True)

# WCS Profile Management Scope
WCS_PROFILE_MANAGEMENT_SCOPE_SYSTEM_WIDE = 0x00000002
WCS_PROFILE_MANAGEMENT_SCOPE_CURRENT_USER = 0x00000001

# Profile type/subtype（用于“设为默认”）
CPT_ICC = 1
CPST_NONE = 0

# EnumDisplayDevices flags/struct
DISPLAY_DEVICE_ATTACHED_TO_DESKTOP = 0x00000001
DISPLAY_DEVICE_PRIMARY_DEVICE = 0x00000004

class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("DeviceName", wintypes.WCHAR * 32),
        ("DeviceString", wintypes.WCHAR * 128),
        ("StateFlags", wintypes.DWORD),
        ("DeviceID", wintypes.WCHAR * 128),     # 包含 PnP ID（用作 WCS 的 deviceName）
        ("DeviceKey", wintypes.WCHAR * 128),
    ]

EnumDisplayDevicesW = USER32.EnumDisplayDevicesW
EnumDisplayDevicesW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(DISPLAY_DEVICEW), wintypes.DWORD)
EnumDisplayDevicesW.restype = wintypes.BOOL

# ---- mscms.dll 函数绑定 ----

# 安装/卸载 ICC（复制/删除 系统色彩目录 的文件）
InstallColorProfileW = MSCMS.InstallColorProfileW
InstallColorProfileW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
InstallColorProfileW.restype = wintypes.BOOL

UninstallColorProfileW = MSCMS.UninstallColorProfileW
UninstallColorProfileW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.BOOL)
UninstallColorProfileW.restype = wintypes.BOOL

# 关联/取消关联（旧 API，足够好用且简单）
AssociateColorProfileWithDeviceW = MSCMS.AssociateColorProfileWithDeviceW
AssociateColorProfileWithDeviceW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR)
AssociateColorProfileWithDeviceW.restype = wintypes.BOOL

DisassociateColorProfileFromDeviceW = MSCMS.DisassociateColorProfileFromDeviceW
DisassociateColorProfileFromDeviceW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR)
DisassociateColorProfileFromDeviceW.restype = wintypes.BOOL

# 设为默认（WCS API）
WcsSetDefaultColorProfile = MSCMS.WcsSetDefaultColorProfile
WcsSetDefaultColorProfile.argtypes = (
    wintypes.DWORD,          # scope
    wintypes.LPCWSTR,        # pDeviceName
    wintypes.DWORD,          # profile type (CPT_ICC)
    wintypes.DWORD,          # profile subtype (CPST_NONE)
    wintypes.DWORD,          # dwProfileID (一般 0)
    wintypes.LPCWSTR,        # pProfileName
)
WcsSetDefaultColorProfile.restype = wintypes.BOOL

# 枚举已关联配置（可选，用于检查）（WCS）
# 为简化，这里不做完整枚举实现；默认依赖你传入路径正确性。


def _get_last_error():
    code = ctypes.get_last_error()
    return f"WinErr={code}"

# ---- 显示器枚举 ----


def _dd_to_dict(idx, dd: DISPLAY_DEVICEW):
    return {
        "index": idx,
        "DeviceName": dd.DeviceName.rstrip("\x00"),
        "DeviceString": dd.DeviceString.rstrip("\x00"),
        "StateFlags": int(dd.StateFlags),
        "DeviceID": dd.DeviceID.rstrip("\x00"),
        "DeviceKey": dd.DeviceKey.rstrip("\x00"),
    }

def list_active_monitors():
    """
    返回仅真实存在且激活（attached）的显示器列表。
    每项包含:
      - index: 序号
      - display: e.g. '\\\\.\\DISPLAY1' （EnumDisplayDevices 的 DeviceName）
      - display_device: DISPLAY_DEVICEW 的全部字段（dict）
      - monitor: 附属 monitor 的 DISPLAY_DEVICEW 字段（dict）
      - name: monitor 的 DeviceString（快捷字段）
      - device_id: monitor 的 DeviceID
      - stateflags: monitor 的 StateFlags
    """
    results = []
    i = 0
    try:
        while True:
            dd = DISPLAY_DEVICEW()
            dd.cb = ctypes.sizeof(DISPLAY_DEVICEW)
            if not EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
                break
            # 只考虑附着到桌面的 display device
            if not (dd.StateFlags & DISPLAY_DEVICE_ATTACHED_TO_DESKTOP):
                i += 1
                continue

            display_name = dd.DeviceName  # e.g. \\.\DISPLAY1
            parent_dd = _dd_to_dict(i, dd)
            j = 0
            # 在该 display 下枚举 monitor（attached monitors）
            while True:
                md = DISPLAY_DEVICEW()
                md.cb = ctypes.sizeof(DISPLAY_DEVICEW)
                if not EnumDisplayDevicesW(display_name, j, ctypes.byref(md), 0):
                    break
                # 只选择真正附着并具有 DeviceID/DeviceString 的 monitor
                if (md.StateFlags & DISPLAY_DEVICE_ATTACHED_TO_DESKTOP) and md.DeviceID.strip() and md.DeviceString.strip():
                    monitor_dd = _dd_to_dict(j, md)
                    results.append({
                        "index": len(results) + 1,
                        "display": display_name,
                        "display_device": parent_dd,
                        "monitor": monitor_dd,
                        "name": monitor_dd.get("DeviceString"),
                        "device_id": monitor_dd.get("DeviceID"),
                        "stateflags": monitor_dd.get("StateFlags"),
                    })
                j += 1

            i += 1
    except Exception:
        return []
    return results



def list_monitors():
    """
    返回列表: [{ 'display': '\\\\.\\DISPLAY1', 'name': '显示器名称', 'device_id': 'DISPLAY\\BOE0C87\\...UID...' }]
    其中 device_id 即可作为 WCS 的 deviceName 使用。
    """
    results = []
    i = 0
    while True:
        dd = DISPLAY_DEVICEW()
        dd.cb = ctypes.sizeof(DISPLAY_DEVICEW)
        if not EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
            break
        # 过滤非桌面设备
        if dd.StateFlags & DISPLAY_DEVICE_ATTACHED_TO_DESKTOP:
            display_name = dd.DeviceName  # e.g. \\.\DISPLAY1
            # 再枚举该显示器下的“监视器”以拿更友好的字符串和 PnP ID
            j = 0
            while True:
                md = DISPLAY_DEVICEW()
                md.cb = ctypes.sizeof(DISPLAY_DEVICEW)
                if not EnumDisplayDevicesW(display_name, j, ctypes.byref(md), 0):
                    break
                if md.StateFlags & DISPLAY_DEVICE_ATTACHED_TO_DESKTOP:
                    results.append({
                        "display": display_name,
                        "name": md.DeviceString.strip(),
                        "device_id": md.DeviceID.strip(),  # 形如 DISPLAY\BOE0C87\5&...&UID4355
                    })
                j += 1
        i += 1
    return results

# ---- 核心操作 ----

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

def associate_icc(device_name, profile_fullpath):
    ok = AssociateColorProfileWithDeviceW(None, profile_fullpath, device_name)
    if not ok:
        raise OSError(f"AssociateColorProfileWithDeviceW failed: {_get_last_error()}")
    return True

def disassociate_icc(device_name, profile_fullpath):
    ok = DisassociateColorProfileFromDeviceW(None, profile_fullpath, device_name)
    if not ok:
        raise OSError(f"DisassociateColorProfileFromDeviceW failed: {_get_last_error()}")
    return True

def set_default_icc(device_name, profile_fullpath, scope="user"):
    scope_val = WCS_PROFILE_MANAGEMENT_SCOPE_CURRENT_USER if scope == "user" else WCS_PROFILE_MANAGEMENT_SCOPE_SYSTEM_WIDE
    ok = WcsSetDefaultColorProfile(scope_val, device_name, CPT_ICC, CPST_NONE, 0, profile_fullpath)
    if not ok:
        raise OSError(f"WcsSetDefaultColorProfile failed: {_get_last_error()}")
    return True

# ---- CLI ----

def main():
    parser = argparse.ArgumentParser(description="Windows 显示器 ICC 管理（安装/关联/默认/移除）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="列出显示器及可用的 device_id")

    p_add = sub.add_parser("add", help="安装 ICC 并关联到设备，可选设为默认")
    p_add.add_argument("--device", required=True, help="WCS deviceName（形如 DISPLAY\\XYZ\\...UID...）。可先用 list 获取")
    p_add.add_argument("--icc", required=True, help="ICC/ICM 文件路径（本地路径，将被复制到系统色彩目录）")
    p_add.add_argument("--set-default", action="store_true", help="安装后设为默认")

    p_asso = sub.add_parser("associate", help="将已在系统色彩目录中的 ICC 关联到设备")
    p_asso.add_argument("--device", required=True)
    p_asso.add_argument("--icc", required=True, help="系统色彩目录内的 ICC 完整路径")

    p_dis = sub.add_parser("disassociate", help="取消设备与 ICC 的关联")
    p_dis.add_argument("--device", required=True)
    p_dis.add_argument("--icc", required=True, help="系统色彩目录内的 ICC 完整路径")

    p_def = sub.add_parser("set-default", help="将某 ICC 设为设备默认")
    p_def.add_argument("--device", required=True)
    p_def.add_argument("--icc", required=True, help="系统色彩目录内的 ICC 完整路径")
    p_def.add_argument("--scope", choices=["user", "system"], default="user")

    p_rm = sub.add_parser("remove", help="移除 ICC：先尝试取消关联，再从系统目录卸载")
    p_rm.add_argument("--device", required=True)
    p_rm.add_argument("--icc", required=True, help="系统色彩目录内的 ICC 完整路径")
    p_rm.add_argument("--force", action="store_true", help="强制卸载（即便仍被关联）")

    args = parser.parse_args()

    try:
        if args.cmd == "list":
            items = list_monitors()
            if not items:
                print("未发现已连接的桌面显示器。")
                return 0
            for idx, it in enumerate(items, 1):
                print(f"[{idx}] name='{it['name']}' display='{it['display']}' device_id='{it['device_id']}'")
            return 0

        if args.cmd == "add":
            # 1) 安装（复制到系统目录）
            install_icc(args.icc)
            # Windows 不返回复制后的确切路径；一般色彩目录为：
            color_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"),
                                     r"System32\spool\drivers\color")
            icc_name = os.path.basename(args.icc)
            installed_path = os.path.join(color_dir, icc_name)
            # 2) 关联
            associate_icc(args.device, installed_path)
            # 3) 设为默认（可选）
            if args.set_default:
                set_default_icc(args.device, installed_path, scope="user")
            print("完成：已安装并关联。", "已设为默认。" if args.set_default else "")
            return 0

        if args.cmd == "associate":
            associate_icc(args.device, args.icc)
            print("完成：已关联。")
            return 0

        if args.cmd == "disassociate":
            disassociate_icc(args.device, args.icc)
            print("完成：已取消关联。")
            return 0

        if args.cmd == "set-default":
            set_default_icc(args.device, args.icc, scope=args.scope)
            print(f"完成：已将默认配置文件设置为（scope={args.scope}）：{args.icc}")
            return 0

        if args.cmd == "remove":
            # 优先尝试解除关联（不强制失败）
            try:
                disassociate_icc(args.device, args.icc)
            except OSError:
                pass
            uninstall_icc(args.icc, force=args.force)
            print("完成：已卸载 ICC。")
            return 0

    except Exception as e:
        print("出错：", e)
        return 1

if __name__ == "__main__":
    import json
    ret = list_active_monitors()
    for itm in ret:
        print(json.dumps(itm, ensure_ascii=False, indent=2))
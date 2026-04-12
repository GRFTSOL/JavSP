import os
import sys
import subprocess
import shutil
import tkinter
from pathlib import Path

# 强制设置控制台编码
if sys.stdout.encoding != 'utf-8':
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except Exception: pass

def get_resource_config():
    """动态获取当前环境的 Tcl/Tk 路径"""
    tcl_root, tk_root = None, None
    try:
        tcl_root = tkinter.Tcl().eval('info library')
        tk_root = tkinter.Tk().tk.eval('info library')
    except Exception:
        base = Path(sys.base_prefix)
        for cand in [base / "tcl" / "tcl8.6", base / "Library" / "lib" / "tcl8.6"]:
            if (cand / "init.tcl").exists(): tcl_root = cand; break
        for cand in [base / "tcl" / "tk8.6", base / "Library" / "lib" / "tk8.6"]:
            if (cand / "tk.tcl").exists(): tk_root = cand; break
                
    found_dlls = {}
    if sys.platform == 'win32':
        base = Path(sys.base_prefix)
        dll_folders = [base, base / "Library" / "bin", base / "DLLs", Path(sys.executable).parent]
        dll_names = ["ffi.dll", "libffi-7.dll", "libffi-8.dll", "libssl-3-x64.dll", "libcrypto-3-x64.dll", "zlib.dll", "sqlite3.dll", "tcl86t.dll", "tk86t.dll", "liblzma.dll", "libbz2.dll"]
        for folder in dll_folders:
            if not folder.exists(): continue
            for n in dll_names:
                if n in found_dlls: continue
                p = folder / n
                if p.exists(): found_dlls[n] = p
    return Path(tcl_root) if tcl_root else None, Path(tk_root) if tk_root else None, found_dlls

def run_build():
    tcl_path, tk_path, dlls = get_resource_config()
    
    # 1. 获取版本号并注入运行时钩子
    sys.path.append(os.path.join(os.path.dirname(__file__)))
    try:
        from version import get_version
        current_ver = get_version()
    except ImportError:
        current_ver = "0.0.0-dev"
    
    print(f"Build Version: {current_ver}")
    hook_path = Path("ver_hook.py")
    hook_path.write_text(f"import sys\nsys.javsp_version = '{current_ver}'\n", encoding='utf-8')

    # 2. 构造打包命令
    cmd = [
        sys.executable, "-m", "PyInstaller", "--onefile", "--name", "JavSP",
        "--icon", "image/JavSP.ico" if sys.platform == 'win32' else "image/JavSP.svg",
        "--add-data", "config.yml;." if sys.platform == 'win32' else "config.yml:.",
        "--add-data", "data;data" if sys.platform == 'win32' else "data:data",
        "--add-data", "image;image" if sys.platform == 'win32' else "image:image",
        "--runtime-hook", str(hook_path),
        "--collect-submodules", "javsp",
    ]
    
    if tcl_path and tk_path:
        sep = ";" if sys.platform == 'win32' else ":"
        cmd.extend(["--add-data", f"{tcl_path}{sep}tcl_tk/{tcl_path.name}"])
        cmd.extend(["--add-data", f"{tk_path}{sep}tcl_tk/{tk_path.name}"])
    
    for p in dlls.values():
        cmd.extend(["--add-binary", f"{p};."])
    
    cmd.append("javsp/__main__.py")
    
    # 3. 执行编译
    print(f"🚀 Building on platform: {sys.platform}")
    subprocess.run(cmd, check=True)
    
    if hook_path.exists(): os.remove(hook_path)
    print("\n✅ Build Complete! File is at: " + str(Path("dist/JavSP.exe" if sys.platform == 'win32' else "dist/JavSP").absolute()))

if __name__ == "__main__":
    run_build()

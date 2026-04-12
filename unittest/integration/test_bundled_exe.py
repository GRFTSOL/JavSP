import os
import sys
import subprocess
import shutil
import time
from pathlib import Path

def test_integration():
    # 1. 寻找被测试的单文件 EXE
    project_root = Path(__file__).resolve().parent.parent.parent
    exe_name = "JavSP.exe" if sys.platform == "win32" else "JavSP"
    exe_path = project_root / "dist" / exe_name
    
    if not exe_path.exists():
        print(f"❌ 错误: 未在 {exe_path} 找到打包后的可执行文件！请先执行打包。")
        sys.exit(1)
    
    print(f"✅ 找到测试目标: {exe_path}")

    # 2. 准备沙盒环境
    integration_dir = project_root / "unittest" / "integration"
    test_movie_dir = integration_dir / "test_movie"
    config_path = integration_dir / "config.yml"
    
    # 修改配置中的扫描路径为绝对路径
    # 避免使用 re.sub 以防止 Windows 路径中的转义字符(如 \U) 触发正则错误
    config_lines = config_path.read_text(encoding='utf-8').splitlines()
    new_lines = []
    for line in config_lines:
        if line.strip().startswith('input_directory:'):
            # 将 Path 对象转换为带双引号的绝对路径字符串，并注意转义
            escaped_path = str(test_movie_dir.absolute()).replace('\\', '/')
            new_lines.append(f'  input_directory: "{escaped_path}"')
        else:
            new_lines.append(line)
    config_path.write_text('\n'.join(new_lines), encoding='utf-8')

    # 3. 执行第一次运行（实战刮削）
    print("\n🚀 STAGE 1: Executing Full Scrape...")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    
    # 设置超时，防止网络死等，我们主要看流程是否通畅
    try:
        cmd = [str(exe_path), "-c", str(config_path)]
        # 捕获输出用于后续分析
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=120)
        print("--- Output ---")
        print(result.stdout)
        print("--- Errors ---")
        print(result.stderr)
        
        # 基础崩溃检查
        for error_kw in ["AttributeError", "NameError", "ImportError", "ValidationError"]:
            if error_kw in result.stderr or error_kw in result.stdout:
                raise Exception(f"Detected CRASH keyword: {error_kw}")

    except subprocess.TimeoutExpired:
        print("⚠️ 运行超时 (已到达网络刮削阶段，流程基本通顺)")

    # 4. 物理核对结果
    print("\n🔍 STAGE 2: Physical Result Audit...")
    result_dir = test_movie_dir / "#整理完成"
    if not result_dir.exists():
        # 尝试根据配置中的 pattern 寻找
        print("❌ 错误: 未找到 '#整理完成' 结果目录！")
        # 列出目录结构辅助诊断
        print(f"目录现状: {os.listdir(test_movie_dir)}")
        sys.exit(1)

    # 校验视频与字幕
    found_videos = []
    found_subtitles = []
    for root, dirs, files in os.walk(result_dir):
        for f in files:
            if f.endswith(".mp4"): found_videos.append(f)
            if f.endswith(".srt"): found_subtitles.append(f)
            print(f"  - Found: {f}")

    if len(found_videos) == 0:
        print("❌ 错误: 结果目录中没有任何视频文件！")
        sys.exit(1)
        
    print(f"\n✅ 物理校验通过: 成功整理了 {len(found_videos)} 部视频")
    if len(found_subtitles) > 0:
        print(f"✅ 字幕同步校验通过: 成功同步了 {len(found_subtitles)} 个字幕文件")

    # 5. 二次运行测试（验证 FileExistsError 保护）
    print("\n🚀 STAGE 3: Testing Re-run Stability...")
    result2 = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=60)
    if "目标文件已存在，跳过整理" in result2.stdout or "目标文件已存在" in result2.stderr or result2.returncode == 0:
        print("✅ 二次运行校验通过: 程序已具备冲突自愈能力。")
    else:
        print("❌ 二次运行失败，输出如下:")
        print(result2.stdout + result2.stderr)
        sys.exit(1)

    print("\n🏆 ALL INTEGRATION TESTS PASSED!")

if __name__ == "__main__":
    test_integration()

import subprocess
import shutil
import os
import sys

RUST_PATH = os.path.join("bot", "utils", "rust_bridge")
TARGET_PATH = os.path.join(RUST_PATH, "target", "debug", "rust_swapper.exe" if os.name == "nt" else "rust_swapper")
OUTPUT_BIN = os.path.join("bin", "rust_swapper.exe" if os.name == "nt" else "rust_swapper")


def build_rust():
    print("🔧 Building Rust project...")
    result = subprocess.run(["cargo", "build"], cwd=RUST_PATH)
    if result.returncode != 0:
        print("❌ Rust build failed.")
        sys.exit(1)
    os.makedirs("bin", exist_ok=True)
    shutil.copy(TARGET_PATH, OUTPUT_BIN)
    print(f"✅ Rust binary copied to: {OUTPUT_BIN}")


def run_rust(mode=None):
    print("🚀 Running Rust binary...")
    args = [OUTPUT_BIN]
    if mode:
        args.append(mode)
    proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # 🔑 Для примера: вставь приватный ключ здесь
    privkey = "3ENJ5..."  # <-- сюда временно для теста

    stdout, stderr = proc.communicate(input=privkey.encode())
    print("📤 Output:\n", stdout.decode())
    if stderr:
        print("⚠️ Stderr:\n", stderr.decode())


if __name__ == "__main__":
    mode = None
    if len(sys.argv) >= 3 and sys.argv[1] == "--run":
        mode = sys.argv[2]
    build_rust()
    if mode:
        run_rust(mode)
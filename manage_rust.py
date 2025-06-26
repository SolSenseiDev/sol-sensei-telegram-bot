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


def run_server():
    print("🌐 Starting Rust Axum server on localhost:3030...")
    subprocess.run([OUTPUT_BIN], cwd="bin")


if __name__ == "__main__":
    if "--run" in sys.argv:
        build_rust()
        run_server()
    else:
        build_rust()

import os
import shutil
import subprocess
import sys

def main():
    test_name = "rajagopal2015"

    # Get current directory
    curr_dir = os.getcwd()
    print(curr_dir)

    test_dir = os.path.join(curr_dir, "tests", "data", test_name)
    original_dir = f"{test_dir}_original"

    # Remove test directory if it exists
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

    # Copy original test data
    shutil.copytree(original_dir, test_dir)
    print(curr_dir)

    # Run engine.py with the test path
    try:
        result = subprocess.run(
            [sys.executable, "src/engine.py", test_dir],
            check=True
        )
        print(result.returncode)
    except subprocess.CalledProcessError as e:
        print(f"Script failed with return code {e.returncode}")
        sys.exit(e.returncode)

    # Optionally run with gdb or lldb (commented out)
    # subprocess.run(["gdb", "-ex", "r", "--args", "python3", "src/engine.py", test_dir])
    # subprocess.run(["sudo", "lldb", "-f", "python3", "--", "src/engine.py", test_dir])

if __name__ == "__main__":
    main()

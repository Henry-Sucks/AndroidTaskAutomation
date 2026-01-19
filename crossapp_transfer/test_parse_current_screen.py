import subprocess
from pathlib import Path
import base64
import tempfile
import sys

from utils import parse_current_screen


MOCK_XML = """
<hierarchy>
  <node text="Play" resource-id="btn_play" clickable="true" bounds="[0,0][100,100]" />
</hierarchy>
""".strip()

MOCK_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8Xw8AAgMBgT1yR+QAAAAASUVORK5CYII="
)
MOCK_PNG_BYTES = base64.b64decode(MOCK_PNG_BASE64)


def mock_subprocess_run(cmd, check=False, stdout=None):
    """
    Mock adb behavior based on command pattern
    """
    if "screencap" in cmd:
        # adb exec-out screencap -p
        if stdout is None:
            raise RuntimeError("stdout is required for screencap")
        stdout.write(MOCK_PNG_BYTES)

    elif "uiautomator" in cmd and "dump" in cmd:
        # adb shell uiautomator dump /sdcard/ui.xml
        return

    elif "pull" in cmd:
        # adb pull /sdcard/ui.xml <dst>
        dst = Path(cmd[-1])
        dst.write_text(MOCK_XML, encoding="utf-8")

    else:
        raise RuntimeError(f"Unexpected adb command: {cmd}")


def main():
    # print("=== test parse_current_screen (mock adb) ===")

    # 保存原始 subprocess.run
    real_run = subprocess.run
    # subprocess.run = mock_subprocess_run

    try:
        out_dir = Path("test_output")
        result = parse_current_screen(
            adb_serial="emulator-5554",
            output_dir=out_dir,
        )

        # ---- validations ----
        assert "hash" in result, "missing hash"
        assert len(result["hash"]) == 40, "hash should be 40-char SHA1"

        xml_path = Path(result["xml_path"])
        png_path = Path(result["screenshot_path"])

        assert xml_path.exists(), "XML file should exist"
        assert png_path.exists(), "Screenshot file should exist"

        assert result["xml"].strip() == MOCK_XML, "XML content mismatch"

        # hash-based filenames
        assert xml_path.name == f"{result['hash']}.xml"
        assert png_path.name == f"{result['hash']}.png"

        print("hash:", result["hash"])
        print("xml_path:", xml_path)
        print("screenshot_path:", png_path)

    except Exception as e:
        print("TEST FAILED:", e, file=sys.stderr)
        sys.exit(1)

    finally:
        # 恢复 subprocess.run
        subprocess.run = real_run

    print("TEST PASSED")


if __name__ == "__main__":
    main()

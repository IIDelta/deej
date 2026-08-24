import subprocess
import time
import serial

SERIAL_PORT = "/dev/serial/by-id/usb-Adafruit_ItsyBitsy_32u4_5V_16MHz-if00"
BAUD_RATE = 9600

ORDERED_MAP = {
    3: ["discord", "webrtc", "vesktop.bin", "vesktop"],
    2: ["brave", "firefox"],
    4: [
        "musikcube",
        "sone",
        "io.github.lullabyx.sone",
        "feishin",
        "mpv",
        "spotify",
    ],
}
MISC_SLIDER = 1

# Flatten all mapped targets into a single lookup set for the MISC check
ALL_MAPPED_TARGETS = {
    target
    for app_list in ORDERED_MAP.values()
    for target in app_list
}


def scale_value(val):
    normalized = max(0, min(100, int((val / 1023.0) * 100)))
    return 100 - normalized  # Inverted


def set_misc_volume(volume_percent):
    """Sets the volume for all sink-inputs NOT explicitly listed in ORDERED_MAP."""
    try:
        output = subprocess.check_output(
            ["pactl", "list", "sink-inputs"], universal_newlines=True
        )
        blocks = output.split("Sink Input #")
        for block in blocks:
            if not block.strip():
                continue

            # Extract the index from the first line of the block
            index = block.split("\n")[0].strip()
            block_lower = block.lower()

            # If NONE of the explicitly mapped targets are in this stream block, it's a "MISC" app
            if not any(target in block_lower for target in ALL_MAPPED_TARGETS):
                subprocess.run(
                    [
                        "pactl",
                        "set-sink-input-volume",
                        index,
                        f"{volume_percent}%",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
    except Exception:
        pass


def set_application_volume(app_names, volume_percent):
    """Sets the volume for specific sink-inputs matching the app_names."""
    try:
        output = subprocess.check_output(
            ["pactl", "list", "sink-inputs"], universal_newlines=True
        )
        blocks = output.split("Sink Input #")
        for block in blocks:
            if not block.strip():
                continue

            index = block.split("\n")[0].strip()

            # If ANY of the targets for this slider are found, adjust the volume
            if any(target in block.lower() for target in app_names):
                subprocess.run(
                    [
                        "pactl",
                        "set-sink-input-volume",
                        index,
                        f"{volume_percent}%",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
    except Exception:
        pass


def main():
    print(f"Connecting to Arduino on {SERIAL_PORT}...")
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
    except Exception as e:
        print(f"Failed to open serial port: {e}")
        return

    print("Deej full-control daemon running successfully!")
    last_volumes = {}

    while True:
        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            parts = line.split("|")
            if len(parts) < 5:
                continue

            slider_values = [int(p) for p in parts if p.isdigit()]
            if len(slider_values) < 5:
                continue

            # 1. Unmapped (Misc) Apps Slider
            if MISC_SLIDER < len(slider_values):
                misc_vol = scale_value(slider_values[MISC_SLIDER])
                last_misc = last_volumes.get("misc", -1)
                if abs(misc_vol - last_misc) >= 2:
                    last_volumes["misc"] = misc_vol
                    set_misc_volume(misc_vol)

            # 2. App-Specific Sliders
            for slider_idx, app_list in ORDERED_MAP.items():
                if slider_idx >= len(slider_values):
                    continue
                target_volume = scale_value(slider_values[slider_idx])
                last_vol = last_volumes.get(slider_idx, -1)
                if abs(target_volume - last_vol) >= 2:
                    last_volumes[slider_idx] = target_volume
                    set_application_volume(app_list, target_volume)

        except KeyboardInterrupt:
            print("\nExiting deej daemon.")
            break
        except Exception:
            time.sleep(0.02)
            continue


if __name__ == "__main__":
    main()

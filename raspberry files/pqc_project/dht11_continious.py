import time
import os

# Paths to the Linux kernel driver files for DHT11
TEMP_PATH = "/sys/bus/iio/devices/iio:device0/in_temp_input"
HUM_PATH = "/sys/bus/iio/devices/iio:device0/in_humidityrelative_input"

def read_sensor_file(file_path):
    """Reads the raw file and returns the integer value divided by 1000."""
    try:
        if not os.path.exists(file_path):
            return None
        with open(file_path, "r") as f:
            raw_value = f.read().strip()
            return float(raw_value) / 1000.0
    except (IOError, ValueError):
        # Handles momentary hardware read hiccups gracefully
        return None

print("Starting DHT11 Continuous Reader... Press Ctrl+C to stop.")
print("-" * 50)

try:
    while True:
        temperature = read_sensor_file(TEMP_PATH)
        humidity = read_sensor_file(HUM_PATH)

        if temperature is not None and humidity is not None:
            # Print data cleanly formatted to 1 decimal place
            print(f"Temp: {temperature:.1f}°C  |  Humidity: {humidity:.1f}%")
        else:
            print("Reading failed or sensor busy... retrying.")

        # DHT11 requires at least a 2-second pause between hardware reads
        time.sleep(2.5)

except KeyboardInterrupt:
    print("\nScript stopped by user.")

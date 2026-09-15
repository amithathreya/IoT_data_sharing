import time
import sys
import os

print("Initializing Sensor Debugger...")

try:
    from gpiozero import DigitalInputDevice
except ImportError:
    print("❌ Error: gpiozero module not found.")
    print("Run: pip install gpiozero")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

IR_PIN = 23
PIR_PIN = 24

# Setup pins
# Setting pull_up=False to match the previous pull-down behavior
ir_sensor = DigitalInputDevice(IR_PIN, pull_up=False)
pir_sensor = DigitalInputDevice(PIR_PIN, pull_up=False)

print(f"✅ GPIO Initialized Successfully!")
print(f"Reading from IR (BCM {IR_PIN}), PIR (BCM {PIR_PIN}), and DHT11 (IIO Overlay)")
print("Press Ctrl+C to exit.\n")

try:
    while True:
        ir_val = ir_sensor.value
        pir_val = pir_sensor.value
        
        # Most IR sensors go LOW (0) when an object is detected, and HIGH (1) otherwise.
        # PIR sensors typically go HIGH (1) when motion is detected.
        ir_status = "DETECTED (0)" if ir_val == 0 else "CLEAR (1)"
        pir_status = "MOTION (1)" if pir_val == 1 else "STILL (0)"
        
        # Read DHT11 from kernel IIO overlay
        try:
            with open("/sys/bus/iio/devices/iio:device0/in_temp_input", "r") as f:
                temp_val = float(f.read().strip()) / 1000.0
            with open("/sys/bus/iio/devices/iio:device0/in_humidityrelative_input", "r") as f:
                hum_val = float(f.read().strip()) / 1000.0
            dht_status = f"{temp_val:.1f}°C, {hum_val:.1f}%"
        except Exception as e:
            dht_status = "Not Found / Error"

        # Overwrite the same line in the console
        sys.stdout.write(f"\r[Status] IR: {ir_status:<15} | PIR: {pir_status:<15} | DHT11: {dht_status:<20}   ")
        sys.stdout.flush()
        
        time.sleep(0.5)

except KeyboardInterrupt:
    print("\nExiting Debugger...")
finally:
    ir_sensor.close()
    pir_sensor.close()
    print("Sensors Cleaned Up.")

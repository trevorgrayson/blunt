#!/usr/bin/env python3
"""
Receive statsd metrics, and send to instrumentation
cpu.load:255|g

To Map meters to values:
    map:METER1=cpu.load
    map:METER2=gpu.temp
    map:METER3=fan.speed
"""
#!/usr/bin/env python3
import sys, time
import argparse
import serial

def parse_statsd_line(line):
    """
    Parse a statsd gauge metric of the form: metric.name:value|g
    Returns (metric, value) or (None, None) if invalid.
    """
    try:
        name_part, rest = line.split(":", 1)
        value_part, type_part = rest.split("|", 1)
        if type_part != "g":
            return None, None
        value = float(value_part)
        return name_part, value
    except ValueError:
        return None, None

def scale_value(value, max_input):
    """
    Scale value to 0-255 given max_input.
    If max_input is None, just return the value (clamped 0–255).
    """
    if max_input is None:
        return int(max(0, min(255, value)))
    scaled = int((value / max_input) * 255)
    return max(0, min(255, scaled))

def main():
    parser = argparse.ArgumentParser(description="Send statsd gauge metrics to Arduino over serial.")
    parser.add_argument("port", nargs="?", help="Serial port (e.g. /dev/ttyUSB0, COM3)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--scale", type=float, default=None,
                        help="Max expected input value for scaling to 0–255")
    parser.add_argument("--dryrun", action="store_true",
                        help="Print values instead of sending over serial (port not required)")
    parser.add_argument("--map", action="append", default=[],
                        help="Mapping command, e.g. --map METER1=cpu.load")
    parser.add_argument("--echo", 
                        help="Write stats to stdout as they are sent")
    args = parser.parse_args()

    ser = None
    if not args.dryrun:
        if not args.port:
            sys.stderr.write("Error: Must specify a serial port unless using --dryrun\n")
            sys.exit(1)
        try:
            ser = serial.Serial(args.port, args.baud,
                                # bytesize=serial.EIGHTBITS,
                                # parity=serial.PARITY_NONE,
                                # stopbits=serial.STOPBITS_ONE,
                                timeout=1)
            time.sleep(3)
        except serial.SerialException as e:
            sys.stderr.write(f"Error opening serial port {args.port}: {e}\n")
            sys.exit(1)

    # Send mapping commands first
    for mapping in args.map:
        message = f"map:{mapping}"
        if args.dryrun:
            print(f"(map) {message}")
        else:
            ser.write((message + "\n").encode("ascii"))

    # Now process stdin metrics
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        metric, value = parse_statsd_line(line)
        if metric is None:
            sys.stderr.write(f"Skipping invalid line: {line}\n")
            continue

        scaled_value = scale_value(value, args.scale)
        message = f"{metric}:{scaled_value}"

        if args.dryrun:
            print(message)
        else:
            if args.echo:
                print(message)
            ser.write((message + "\r\n").encode("ascii"))
            time.sleep(1)
            resp = ser.readall()
            print(resp)

if __name__ == "__main__":
    main()

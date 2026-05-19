# Arduino PT100 Reader

Arduino-based PT100 temperature sensor reader with serial communication and a PC-side manager application.

The project allows dynamic configuration of multiple PT100 sensors connected to Arduino analog inputs. Sensors can be created, removed, configured, listed, and read through a simple Serial/USART command interface.

## Features

- Dynamic sensor configuration over Serial/USART
- Support for up to 8 sensors
- Two-point calibration
- Averaged analog readings
- Periodic automatic temperature reporting
- JSON-like responses for PC-side parsing
- Python PC-side manager script

## Project Structure

```text
Arduino-PT100-Reader/
├── Arduino_PT100_src/
│   ├── LineHandler.cpp
│   ├── LineHandler.h
│   ├── SensorManager.cpp
│   ├── SensorManager.h
│   ├── Sensors.cpp
│   ├── Sensors.h
│   └── main.cpp
├── PT100_Manager.py
└── README.md
```

## Firmware Overview

The Arduino firmware is split into several modules:

- `SensorPT100` — represents a single PT100 sensor and handles temperature reading
- `SensorManager` — manages sensor slots, creation, deletion and lookup
- `LineHandler` — parses Serial commands and returns responses
- `main.cpp` — initializes Serial communication and runs the main loop

Each sensor stores its ID, analog pin, name, calibration values, active state and reporting interval. Temperature is calculated using simple two-point calibration based on ADC readings.

## Serial Command Protocol

Commands are sent as text lines using `key=value` parameters.

### Create a sensor

```text
NEW id=1 pin=A0 name=PT100_1 active=1 t1=0 q1=100 t2=100 q2=800 interval=1000
```

Example response:

```json
{"ok":true}
```

### Read a sensor

```text
READ id=1
```

Example response:

```json
{"ok":true,"id":1,"name":"PT100_1","t":24.53}
```

### Modify a sensor

```text
SET id=1 active=1 interval=2000
```

Example response:

```json
{"ok":true}
```

### Delete a sensor

```text
DEL id=1
```

Example response:

```json
{"ok":true}
```

### List sensors

```text
LIST
```

Example response:

```json
{"s":[{"id":1,"name":"PT100_1","pin":14,"active":1}]}
```

## Automatic Reporting

Active sensors can automatically report temperature at a configured interval.

Example output:

```json
{"id":1,"name":"PT100_1","t":24.53}
```

## Requirements

### Hardware

- Arduino-compatible board
- PT100 temperature sensor
- PT100 analog measurement circuit
- USB/Serial connection to PC

### Software

- Arduino IDE or compatible build environment
- Python 3

## Usage

1. Upload the firmware from `Arduino_PT100_src/` to the Arduino board.
2. Open Serial Monitor or run the Python manager script.
3. Use baud rate `9600`.
4. Send commands through the Serial interface.

Example workflow:

```text
NEW id=1 pin=A0 name=PT100_1 active=1 t1=0 q1=100 t2=100 q2=800 interval=1000
READ id=1
SET id=1 interval=5000
LIST
DEL id=1
```

## Python Manager Application

The project includes a PC-side Python application: `PT100_Manager.py`.

It communicates with the Arduino through a serial port and provides a simple way to manage PT100 sensors without manually typing commands in the Serial Monitor.

The application can be used to:

- connect to the Arduino
- send Serial commands
- create, modify, delete and list sensors
- request temperature readings
- display responses from the firmware

Communication is based on the same text command protocol described above. The Arduino handles the sensor logic, while the Python application acts as a PC-side control tool.

## Notes

This project is intended as a lightweight embedded system example showing:

- Arduino C++ programming
- Serial communication
- command parsing
- sensor abstraction
- dynamic sensor management
- ADC-based measurements
- PC-to-microcontroller communication

## Possible Future Improvements

- Save sensor configuration in EEPROM
- Add more detailed error handling
- Improve JSON response formatting
- Add circuit diagram documentation
- Improve the Python manager interface
- Add tests for command parsing logic

## Author

Created by [royalewski](https://github.com/royalewski).

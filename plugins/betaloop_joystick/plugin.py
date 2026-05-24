import serial

class JoystickInterface:
    def __init__(self, port='/dev/ttyUSB0', baudrate=9600):
        self.ser = serial.Serial(port, baudrate)

    def read_joystick(self):
        if self.ser.in_waiting > 0:
            data = self.ser.readline().decode('utf-8').strip()
            return data
        return None

    def close(self):
        self.ser.close()
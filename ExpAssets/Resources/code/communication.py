import time

from klibs import P
from klibs.KLInternal import package_available



LABJACK_REGISTERS = {
    'FIO': 6700,
    'EIO': 6701,
    'CIO': 6702, # Note: 4 pins, only supports values 0-15
}


def get_trigger_port():
    """Retrieves a TriggerPort object for writing digital trigger codes.

    If a supported hardware trigger port is available, it will be
    initialized and configured for sending trigger codes. If no digital
    trigger hardware is available, a virtual trigger port will be returned.

    """
    # Try loading the LabLack U3 as a trigger port
    if package_available('u3'):
        import u3
        if u3.deviceCount(devType=3) > 0:
            dev = u3.U3()
            return U3Port(dev)

    # If no physical trigger port available, return a virtual one
    return VirtualPort(device=None)



class TriggerPort(object):
    """A class for sending digital trigger codes to external hardware.

    Args:
        device: The object representing the hardware device to use for sending
            digital triggers (e.g. ``u3.U3``). Can be None.

    """
    def __init__(self, device):
        # NOTE: Codes may be implementation-specific to allow for preprocessing
        self.codes = {}
        self._device = device
        self._hardware_init()

    def _hardware_init(self):
        # Initialize the hardware for the trigger device
        pass

    def add_code(self, name, value):
        """Adds a new code to the list of triggers.

        Once a trigger code has been added, it can be written to the trigger
        port using the ``write`` method. Trigger codes must be whole numbers
        between 0 and 255, inclusive.

        Args:
            name (str): The name of the trigger code (e.g. 'trial_start').
            value (int): The digital value to write for the trigger code.

        """
        if not isinstance(value, int) or not (0 <= value <= 255):
            e = "Trigger codes must be whole numbers between 0 and 255, inclusive"
            raise ValueError(e + " (got {0})".format(value))
        self.codes[name] = value

    def add_codes(self, mapping):
        """Adds a set of codes to the list of triggers.

        For example::

           trigger.add_codes({
               'trial_start': 4,
               'figure_on': 8,
               'trial_end': 12,
           })

        Args:
            mapping (dict): A dictionary in the form ``{'name': value}``
                containing the names and digital triggers to add.

        """
        for name, value in mapping.items():
            self.add_code(name, value)

    def send(self, name, duration=4):
        """Sends a given trigger code to the trigger port.

        This method sends the requested trigger code to the hardware, waits a
        given duration (default: 4ms), and then resets the trigger pins to 0.
        The wait interval is because some hardware requires a delay between
        sending the 'trigger on' and 'trigger off' signals to reliably detect
        the triggers.

        Args:
            name (str): The name of the trigger code to write to the port.
            duration (int, optional): The number of milliseconds to wait between
                writing the trigger code and resetting the trigger pins to 0.
                Defaults to 4 ms.
        
        """
        self._write_trigger(self.codes[name])
        time.sleep(duration / 1000.0)
        self._write_trigger(0)

    def _write_trigger(self, value):
        # Device-specific trigger code implementation. This actually sends a
        # given code to the hardware.
        pass



class U3Port(TriggerPort):
    """A TriggerPort implementation for LabJack U3 devices.

    """
    def _hardware_init(self):
        self._write_reg = LABJACK_REGISTERS[P.labjack_port]
        self._device.getCalibrationData()
        # Configure all IO pins to be digital outputs set to 0
        self._device.configU3(
            FIODirection=255, FIOState=0, FIOAnalog=0,
            EIODirection=255, EIOState=0, EIOAnalog=0,
            CIODirection=255, CIOState=0,
        )

    def _write_trigger(self, value):
        # Fast method from Appelhoff & Stenner (2021), may be erratic on Windows
        self._device.writeRegister(self._write_reg, 0xFF00 + (value & 0xFF))



class VirtualPort(TriggerPort):
    
    def _hardware_init(self):
        print("\nNOTE: No hardware trigger device, using virtual triggers...\n")


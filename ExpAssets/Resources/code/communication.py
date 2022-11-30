import time

from klibs import P
from klibs.KLInternal import package_available



LABJACK_REGISTERS = {
    'FIO': 6700,
    'EIO': 6701,
    'CIO': 6702, # Note: 4 pins, only supports values 0-15
}


def _raise_err(task, msg=None):
    e = "Error encountered {0}".format(task)
    if msg:
        e += ": {0}".format(msg)
    raise RuntimeError(e)


def _check_labjack_driver():
    # LabJackPython requires a driver to work and errors out if not installed,
    # so make sure it exists and print an informative message if it isn't
    import u3
    has_driver = False
    try:
        u3.deviceCount(devType=3)
        has_driver = True
    except AttributeError:
        pass
    return has_driver


def get_trigger_port():
    """Retrieves a TriggerPort object for writing digital trigger codes.

    If a supported hardware trigger port is available, it will be
    initialized and configured for sending trigger codes. If no digital
    trigger hardware is available, a virtual trigger port will be returned.

    """
    # Try loading the LabLack U3 as a trigger port
    if package_available('u3'):
        import u3
        has_driver = _check_labjack_driver()
        if has_driver and u3.deviceCount(devType=3) > 0:
            dev = u3.U3()
            return U3Port(dev)

    # If no physical trigger port available, return a virtual one
    return VirtualPort(device=None)


def _poke_magstim(port, timeout=1.0):
    # Workaround for a MagPy bug on Linux until magneto is done: without
    # this, MagPy hangs indefinitely the first time it tris to connect.
    import serial
    com = serial.Serial(
        port,
        baudrate=9600,
        bytesize=serial.EIGHTBITS,
        stopbits=serial.STOPBITS_ONE,
        parity=serial.PARITY_NONE,
    )
    com.write_timeout = 0.5
    # Write a 'get parameters' command to the Magstim and wait for a response
    com.write(b"J@u")
    wait_start = time.time()
    while not com.in_waiting:
        if (time.time() - wait_start) > timeout:
            raise RuntimeError("Connection with Magstim timed out.")
        time.sleep(0.1)
    return com.read(com.in_waiting)


def get_tms_controller():
    """Retrieves a TMSController object for controlling a TMS system.

    If a supported stimulator is available, it will be initialized
    and configured. If no supported stimulator is connected, a virtual TMS
    controller will be returned.

    """
    if package_available('magpy'):
        # NOTE: Currently no way of autodetecting Magstim model
        from serial.tools.list_ports import comports
        available_ports = [p.device for p in comports()]
        if P.tms_serial_port in available_ports:
            from magpy.magstim import BiStim
            _poke_magstim(P.tms_serial_port)
            dev = BiStim(P.tms_serial_port)
            return MagPyController(dev)
    
    # If no hardware stimulator available, return a virtual one
    return VirtualTMSController(None)


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

    def close(self):
        """Closes the connection with the trigger port hardware.

        Should be called at the end of the experiment, when the trigger port is
        no longer needed.

        """
        pass

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

    def close(self):
        # Needs to be called on Linux and macOS in order for the LabJack to be
        # able to be opened again reliably without reconnecting the cable.
        self._device.close()



class VirtualPort(TriggerPort):

    def _hardware_init(self):
        print("\nNOTE: No hardware trigger device, using virtual triggers...\n")



class TMSController(object):
    """A class for configuring and controlling TMS systems in Python.

    Args:
        device: The object representing the stimulator for a given backend. Can
            be None.

    """
    def __init__(self, device):
        self._device = device
        self._hardware_init()

    def _hardware_init(self):
        # Initialize the connection to the TMS system
        pass

    def _set_power(self, level):
        # Actually sets the power level for the stimulator
        pass

    def _arm(self):
        # Actually arms the stimulator
        pass

    def set_power(self, level):
        """Sets the power level for the primary coil of the stimulator.

        Note that the stimulator requires time to charge or discharge to a new
        power level once one has been set, with the time required depending on the
        magnitude of and direction of the change (e.g. 20% to 40% would take
        approximately 200ms, whereas 40% to 20% would take approximately 2000ms).

        To make sure the stimulator is ready to fire after changing the power
        level, check the `ready` attribute once the stimulator has been armed.

        Args:
            level (int): The power level (from 0 to 100) to set for the stimulator's
                primary coil.

        """
        non_int = int(level) != level
        if non_int or not (0 <= int(level) <= 100):
            e = "Power level must be an integer between 0 and 1 (got {0})"
            raise ValueError(e.format(level))
        self._set_power(int(level))

    def get_power(self):
        """Gets the current power level for the primary coil of the stimulator.

        """
        pass

    def arm(self, wait=False):
        """Arms the stimulator.

        Must be called at least one second before the stimulator can be fired.
        Note that the stimulator will stay armed after firing, so you may need
        to manually disarm between trials depending on the nature of your study.

        Once armed, the Magstim will disarm automatically if the stimulator has
        not been fired for over 1 minute.
 
        Args:
            wait (bool, optional): If True, this method will wait up to 2 seconds
                for the stimulator to arm successfully before returning. Defaults
                to False.

        """
        self._arm()
        if wait:
            timeout = 2.0
            start = time.time()
            while not self.ready:
                time.sleep(0.1)
                if (time.time() - start) > timeout:
                    e = "Arming the stimulator timed out (2 seconds)"
                    raise RuntimeError(e)

    def disarm(self):
        """Disarms the stimulator.
        
        """
        pass

    def fire(self):
        """Commands the stimulator to fire.

        NOTE: This commands the TMS to fire via the serial port, which has
        a delay of 5-10ms and can be delayed by other commands to the device.
        As such, this function should *only* be used for testing or for 
        tasks where precise timing is not important. In all other cases,
        the stimulator should be triggered via TTL using a TriggerPort object.

        """
        pass

    @property
    def ready(self):
        """bool: True if the stimulator is ready to fire, otherwise False.
        """
        pass


class VirtualTMSController(TMSController):
    """A dummy TMSController implementation.

    This class allows writing/testing experiments involving TMS control without
    needing to be connnected to an actual stimulator.

    """
    def _hardware_init(self):
        self._info = {
            'pwr_a': 30, 'pwr_b': 0, 'interval': 0, 'armed': False,
        }
        print("\nNOTE: No TMS hardware connected, using virtual stimulator...\n")

    def _set_power(self, level):
        self._info['pwr_a'] = level

    def get_power(self):
        return self._info['pwr_a']

    def arm(self, wait=False):
        if wait:
            # Simulate usual delay between arming and ready to fire
            time.sleep(1.0)
        self._info['armed'] = True

    def disarm(self):
        self._info['armed'] = False

    def fire(self):
        pass

    @property
    def ready(self):
        return self._info['armed']



class MagPyController(TMSController):
    """A TMSController implementation for Magstim TMS systems using MagPy.

    Currently only Magstim 200 and BiStim stimulators are supported, but
    Magstim Rapid stimulators should be usable with some extra work.

    """
    def _hardware_init(self):
        self._device.connect()
        # If BiStim, configure to start in single-pulse mode
        err, msg = self._device.highResolutionMode(False, receipt=True)
        if err != 3:
            self._device.setPowerB(0)
            self._device.setPulseInterval(0)

    def _set_power(self, level):
        err, msg = self._device.setPower(level, receipt=True)
        if err:
            _raise_err("setting power for the primary coil", msg)

    def _arm(self):
        err, msg = self._device.arm(receipt=True)
        if err:
            _raise_err("arming the stimulator", msg)

    def get_power(self):
        err, info = self._device.getParameters()
        if err:
            _raise_err("retrieving the current stimulator settings", info)
        return int(info['bistimParam']['powerA'])

    def disarm(self):
        self._device.disarm()

    def fire(self):
        self._device.fire()

    @property
    def ready(self):
        return self._device.isReadyToFire()

import ctypes
import sys
import os
from enum import IntEnum
from mytypes import DeviceListInfo


class FtdiError(Exception):
    """Base exception for this module"""
    pass


# Get the directory of the current script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Load the DLL. Right now, only Windows is supported
if sys.platform == 'win32':
    dll = ctypes.CDLL(os.path.join(script_dir, 'libmpsse.dll'))
else:
    raise NotImplementedError(f'OS "{sys.platform}" not supported')


# define the FT_Status enum

class FT_Status(IntEnum):
    """Status of the I2C/D2XX Call"""
    FT_OK = 0
    FT_INVALID_HANDLE = 1
    FT_DEVICE_NOT_FOUND = 2
    FT_DEVICE_NOT_OPENED = 3
    FT_IO_ERROR = 4
    FT_INSUFFICIENT_RESOURCES = 5
    FT_INVALID_PARAMETER = 6
    FT_INVALID_BAUD_RATE = 7
    FT_DEVICE_NOT_OPENED_FOR_ERASE = 8
    FT_DEVICE_NOT_OPENED_FOR_WRITE = 9
    FT_FAILED_TO_WRITE_DEVICE = 10
    FT_EEPROM_READ_FAILED = 11
    FT_EEPROM_WRITE_FAILED = 12
    FT_EEPROM_ERASE_FAILED = 13
    FT_EEPROM_NOT_PRESENT = 14
    FT_EEPROM_NOT_PROGRAMMED = 15
    FT_INVALID_ARGS = 16
    FT_NOT_SUPPORTED = 17
    FT_OTHER_ERROR = 18

    def __str__(self):
        """Return the enum name minus the 'FT_' start, convert the underscores to spaces, and represent in title case"""
        return self.name[3:].replace('_', ' ').title()


# Define FT_HANDLE as a ctypes type
FT_HANDLE = ctypes.c_void_p


class FT_DEVICE_LIST_INFO_NODE(ctypes.Structure):
    """The device information structure"""
    _fields_ = [
        ("Flags", ctypes.c_uint32),  # DWORD is typically represented as ctypes.c_uint32
        ("Type", ctypes.c_uint32),
        ("ID", ctypes.c_uint32),
        ("LocId", ctypes.c_uint32),
        ("SerialNumber", ctypes.c_char * 16),  # char array of length 16
        ("Description", ctypes.c_char * 64),  # char array of length 64
        ("ftHandle", FT_HANDLE)  # Handle to a device, represented as a pointer type
    ]

    def to_dataclass(self):
        """Convert the ctypes structure into a DeviceListInfo dataclass"""
        return DeviceListInfo(
            flags=self.Flags,
            type=self.Type,
            id=self.ID,
            loc_id=self.LocId,
            serial=(ctypes.string_at(self.SerialNumber)).decode('utf8'),
            description=ctypes.string_at(self.Description).decode('utf8'),
            handle=self.ftHandle
        )


class ChannelConfig(ctypes.Structure):
    _fields_ = [
        ("ClockRate", ctypes.c_uint32),  # Assuming I2C_CLOCKRATE is a uint32, adjust if necessary
        ("LatencyTimer", ctypes.c_ubyte),  # UCHAR is an unsigned byte
        ("Options", ctypes.c_uint32),  # DWORD is typically a uint32
        ("Pin", ctypes.c_uint32),  # DWORD, adjust if needed
        ("currentPinState", ctypes.c_uint16)  # USHORT is typically a uint16
    ]


def _wrap_dll_func(func_name: str, *argtypes):
    global dll
    func = getattr(dll, func_name)
    func.restype = ctypes.c_int
    func.argtypes = argtypes

    def _check_ftdi_status(status):
        """Check the FT_Status and raise an exception if it's not FT_OK."""
        status_enum = FT_Status(status)  # Convert integer to enum
        if status_enum != FT_Status.FT_OK:
            raise FtdiError(str(status_enum))

    def wrapped_function(*args):
        status = func(*args)
        _check_ftdi_status(status)
        return status

    return wrapped_function


# define the raw function inputs
_I2C_GetNumChannels = _wrap_dll_func('I2C_GetNumChannels', ctypes.POINTER(ctypes.c_uint32))
_I2C_GetChannelInfo = _wrap_dll_func('I2C_GetChannelInfo', ctypes.c_uint32,
                                     ctypes.POINTER(FT_DEVICE_LIST_INFO_NODE))
_I2C_OpenChannel = _wrap_dll_func('I2C_OpenChannel', ctypes.c_uint32, ctypes.POINTER(FT_HANDLE))
_I2C_InitChannel = _wrap_dll_func('I2C_InitChannel', FT_HANDLE, ctypes.POINTER(ChannelConfig))
_I2C_CloseChannel = _wrap_dll_func('I2C_CloseChannel', FT_HANDLE)
_I2C_DeviceRead = _wrap_dll_func('I2C_DeviceRead', FT_HANDLE, ctypes.c_uint32, ctypes.c_uint32,
                                 ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32), ctypes.c_uint32)
_I2C_DeviceWrite = _wrap_dll_func('I2C_DeviceWrite', FT_HANDLE, ctypes.c_uint32, ctypes.c_uint32,
                                  ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32),
                                  ctypes.c_uint32)


# define the real functions that handle the arguments with Python types
def get_num_channels() -> int:
    """
    This function gets the number of I2C channels that are connected to the host system. The number
of ports available in each of these chips is different.
    :return: The number of channels
    """
    num_channels = ctypes.c_uint32()
    _I2C_GetNumChannels(ctypes.byref(num_channels))
    return num_channels.value


def get_channel_info(index: int = 0) -> DeviceListInfo:
    """
    This function takes a channel index and provides information about the channel in the form of a populated
DeviceListInfo dataclass structure.
    :param index: Index of the channel
    :return: DeviceListInfo dataclass representing the qualities of the channel
    """
    chan_info = FT_DEVICE_LIST_INFO_NODE()
    _I2C_GetChannelInfo(ctypes.c_uint32(index), ctypes.byref(chan_info))
    return chan_info.to_dataclass()


def open_channel(index: int) -> int:
    handle = FT_HANDLE()
    _I2C_OpenChannel(ctypes.c_uint32(index), ctypes.byref(handle))
    return handle.value


def init_channel(handle, frequency: int | float = 100000, latency=16, options=0) -> None:
    config = ChannelConfig()
    config.ClockRate = int(frequency)
    config.LatencyTimer = latency
    config.Options = options
    _I2C_InitChannel(FT_HANDLE(handle), ctypes.byref(config))


def close_channel(handle) -> None:
    _I2C_CloseChannel(FT_HANDLE(handle))


def read_device(handle: int, device_address: int, bytes_to_read, start=True, stop=True) -> bytes:
    """
    This function reads the specified number of bytes from an addressed I2C slave.

    :param handle: Handle of opened I2C channel
    :param device_address: Device address in 7-bit format
    :param bytes_to_read: Number of bytes to read
    :param start: Send a start before the operation (default True)
    :param stop: Send a stop after the operation (default True)
    :return: Bytes read from the device
    """
    # Create a buffer to hold the data
    buffer = ctypes.c_char_p()
    buffer.value = bytes(bytes_to_read)
    options = ctypes.c_uint32(start + 2 * stop + (0 << 4))

    # Create a variable to hold the size of data actually transferred
    size_transferred = ctypes.c_uint32()

    # Call the function
    _I2C_DeviceRead(FT_HANDLE(handle), device_address, bytes_to_read, buffer, ctypes.byref(size_transferred), options)
    actually_written = size_transferred.value
    assert actually_written == bytes_to_read, f"Did not read {bytes_to_read} bytes. Only read {actually_written} bytes"
    return bytes(buffer.value)


def write_device(handle: int, device_address: int, bytes_to_write: bytes, start=True, stop=True) -> None:
    size_transferred = ctypes.c_uint32()
    _I2C_DeviceWrite(FT_HANDLE(handle), device_address, len(bytes_to_write), bytes_to_write,
                     ctypes.byref(size_transferred), start + 2 * stop + (1 << 4))
    assert size_transferred.value == len(bytes_to_write), "Not all values were written"


__all__ = ['get_num_channels', 'get_channel_info', 'open_channel', 'close_channel', 'init_channel', 'read_device',
           'write_device']


def main():
    print(get_num_channels())
    print(get_channel_info(0))
    c = open_channel(0)
    init_channel(c)
    write_device(c, 0x54, bytes([0x00, 0x00]))
    print(read_device(c, 0x54, 20))
    close_channel(c)


if __name__ == '__main__':
    main()

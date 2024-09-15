import ctypes_veneer as li2c
from typing import Self
from mytypes import DeviceListInfo


def get_channels() -> [DeviceListInfo]:
    """Get channel information for all channels"""
    num_channels = li2c.get_num_channels()
    results = []
    for c in range(num_channels):
        results.append(li2c.get_channel_info(c))

    return results


class FtdiI2C:
    """
    A simple class to wrap the i2c interface with a context manager.

    Example::
        with FtdiI2C(channel=0) as i2c:
            i2c.write(0x12, b'bytes to write')
            print(i2c.read(0x12, 10)

    """

    def __init__(self, frequency: int | float = 100e3, channel: int = 0):
        self.hi2c = li2c.open_channel(channel)
        li2c.init_channel(self.hi2c, frequency=frequency)

    # context manager
    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        li2c.close_channel(self.hi2c)

    def write(self, address: int, data: bytes, start: bool = True, stop: bool = True) -> None:
        li2c.write_device(self.hi2c, address, data, start=start, stop=stop)

    def read(self, address: int, length: int, start=bool, stop=bool):
        return

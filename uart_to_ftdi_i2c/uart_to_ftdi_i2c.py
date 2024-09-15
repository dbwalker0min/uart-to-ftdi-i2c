import uart_to_ftdi_i2c.pylibmpsse_i2c as i2c
import serial
from loguru import logger
import argparse
import os
import pickle

I2C_FREQUENCY = 100e3

PROG_NAME: str = 'uart_to_ftdi_i2c'


def _process_arguments():
    # read the variables from the application file
    app_file_path = os.path.join(os.path.expanduser("~"), 'eplant')
    app_file_name = os.path.join(app_file_path, PROG_NAME)
    try:
        with open(app_file_name, 'rb') as fid:
            obj: dict[str, str | int] = pickle.load(fid)
    except FileNotFoundError:
        # It will exist, but for now, make sure the directory is created
        os.makedirs(app_file_path, exist_ok=True)
        # set the variables
        obj = dict()

    # com port
    port = getattr(obj, 'com')

    """Process the arguments and store them to disk for potential later reuse"""
    argument_parser = argparse.ArgumentParser(
        prog=PROG_NAME,
        description='Emulate an NXP SC18IM704 UART to I2C interface using an FTDI MPSSE cable'
    )

    # Serial port id
    argument_parser.add_argument(
        '-u', '--uart',
        help='UART port to open (ex. COM1). The default uses the previous value.',
        required=port is None
    )

    argument_parser.add_argument(
        '-i', '--i2c_chan',
        help='I2C Channel to open.',
        default=0,
        type=int
    )

    # control the debug level
    argument_parser.add_argument(
        '-d', '--debug',
        help='Debug level (default ERROR)',
        choices=['TRACE', 'DEBUG', 'INFO', 'SUCCESS', 'WARNING', 'ERROR', 'CRITICAL'],
        default='error',
        required=False,
        type=str.upper,
    )
    args = argument_parser.parse_args()

    if args.uart is None:
        args.uart = port
    else:
        # there is a value specified. Save it to the configuration file for next time
        with open(app_file_name, 'wb') as fid:
            pickle.dump(dict(
                com=args.uart
            ), fid)

    return args


def main():
    arguments = _process_arguments()

    # open the I2C device and uart
    with (i2c.FtdiI2C(channel=arguments.i2c_chan) as hi2c,
          serial.Serial(arguments.port, baudrate=9600) as uart):

        # Go forever (or until the user hits Ctrl-C)
        while True:
            try:
                # wait forever for a command of the form "S..."
                uart.timeout = None
                char: bytes = uart.read(1)
                if char == b'S':
                    while True:
                        # start character received. The next bytes are the address (with read/write) and the byte count
                        uart.timeout = 0.7
                        try:
                            addr, length = uart.read(2)
                            write = addr % 1 == 0
                            addr = addr // 2
                        except serial.Timeout:
                            continue

                        # try to get the next start or stop bit
                        # set the timeout to 15 bit times
                        if write:
                            # get write data from UART (and the trailing start or stop command)
                            try:
                                uart.timeout = 0.7
                                *data, next_char = uart.read(length + 1)
                            except serial.Timeout:
                                # wait for the next command
                                break

                            next_char_stop = next_char == ord('S')
                            # perform the I2C write
                            hi2c.write(addr, bytes(data), stop=next_char_stop)

                        else:
                            try:
                                uart.timeout = 0.7
                                next_char_stop = uart.read(1) == b'S'
                            except serial.Timeout:
                                # wait for the next command
                                break
                            data = hi2c.read(addr, length, stop=next_char_stop)

                            # shove it out the serial port
                            uart.write(data)
                        if next_char_stop:
                            break
                else:
                    logger.debug(f'Control character "{next_char}" found')


            except KeyboardInterrupt:
                break


if __name__ == '__main__':
    main()

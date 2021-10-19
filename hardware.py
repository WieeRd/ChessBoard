import asyncio
import numpy as np
import gpiozero as gp

from typing import List, Tuple


class DummyLED(gp.LED):
    """
    Inherited from gpiozero.LED but methods do nothing
    """

    def __init__(self):
        self._led_state = False

    def on(self):
        self._led_state = True

    def off(self):
        self._led_state = False

    def close(self):
        pass

    @property
    def value(self) -> bool:
        return self._led_state


class IODevice:
    """
    GPIO device that can do both input and output
    """

    _input: gp.InputDevice
    _output: gp.OutputDevice

    def __init__(self, pin: int):
        self.pin = pin

    def on(self):
        if hasattr(self, "_input"):
            del self._input
            self._output = gp.OutputDevice(self.pin)
        self._output.on()

    def off(self):
        if hasattr(self, "_input"):
            del self._input
            self._output = gp.OutputDevice(self.pin)
        self._output.off()

    def read(self) -> int:
        if hasattr(self, "_output"):
            del self._output
            self._input = gp.InputDevice(self.pin, pull_up=True)
        return self._input.value


class MatrixBase:
    data: np.ndarray

    def status(self, on: str, off: str) -> str:
        ret = []
        for row in self.data:
            ret.append(" ".join((on if col else off) for col in row))
        return "\n".join(ret)

    def __str__(self) -> str:
        return self.status("O", ".")


class Electrode(MatrixBase):
    def __init__(self, send: List[gp.OutputDevice], recv: List[IODevice]):
        """
        Make sure recv[0] is closest row to sending side
        """
        self.data = np.full((len(send), len(recv)), False)
        self.send = send
        self.recv = recv

    async def scan(self) -> List[Tuple[int, int]]:
        diff = []

        for y, send in enumerate(self.send):
            send.on()

            for x, recv in enumerate(self.recv):
                await asyncio.sleep(0.001)
                read = recv.read()
                if self.data[y][x] != read:
                    self.data[y][x] = read
                    diff.append((x, y))
                recv.on()

            # for recv in self.recv:
            #     recv.off()

            send.off()

        return diff


class LEDmatrix(MatrixBase):
    """
    Base class for LED matrix control.
    By default methods just store state data
    """

    def __init__(self):
        self.data = np.full((8, 8), False)

    def on(self, x: int, y: int):
        self.data[y][x] = True

    def off(self, x: int, y: int):
        self.data[y][x] = False

    def toggle(self, x: int, y: int):
        self.data[y][x] = not self.data[y][x]

    def flush(self):
        pass


try:
    from luma.core.interface.serial import spi, noop  # type: ignore
    from luma.core.render import canvas  # type: ignore
    from luma.led_matrix.device import max7219  # type: ignore
except ImportError:
    LUMA = False
else:
    LUMA = True

    class MatrixChain(LEDmatrix):
        """
        Control multiple daisy-chained max7219 LED matrix
        """

        def __init__(self, serial: spi, cascaded: int = 1):
            self.cascaded = cascaded
            self.device = max7219(serial, cascaded=cascaded)

            self.height = 8
            self.width = 8 * cascaded

            self.data = np.full((self.height, self.width), False)

        def __getitem__(self, offset: int):
            return SingleMatrix(self, offset)

        def flush(self):
            with canvas(self.device) as draw:
                for y in range(self.height):
                    for x in range(self.width):
                        if self.data[y][x]:
                            draw.point((x, y), fill="white")

    class SingleMatrix(LEDmatrix):
        """
        Control single LED matrix in MatrixChain
        """

        def __init__(self, chain: MatrixChain, offset: int):
            self.chain = chain
            self.offset = offset
            self.data = np.array([row[offset:] for row in chain.data])

        def flush(self):
            self.chain.flush()

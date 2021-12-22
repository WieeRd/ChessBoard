import asyncio
import numpy as np
import gpiozero as gp

from aioconsole import ainput
from typing import List, Tuple


class VirtualLED(gp.LED):
    """
    Dummy GPIO LED class used for testing
    Methods just store device state data
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

    def __repr__(self) -> str:
        return str(self.data)

    def __str__(self) -> str:
        return self.status("O", ".")


class Scanner(MatrixBase):
    """
    Find out which squares have piece on it
    """

    async def scan(self) -> List[Tuple[int, int]]:
        """
        Returns list of squares that has changed since last scan
        """
        raise NotImplementedError


class Electrode(Scanner):
    def __init__(self, send: List[int], recv: List[int], pull_up=True):
        self.data = np.full((len(send), len(recv)), False)
        self.send = [gp.OutputDevice(pin) for pin in send]
        self.recv = [gp.InputDevice(pin, pull_up=pull_up) for pin in recv]

    async def scan(self) -> List[Tuple[int, int]]:
        diff = []

        for y, send in enumerate(self.send):
            send.on()

            await asyncio.sleep(0.001)
            for x, recv in enumerate(self.recv):
                read = recv.value
                if self.data[y][x] != read:
                    self.data[y][x] = read
                    diff.append((x, y))

            send.off()

        return diff


class ConsoleInput(Scanner):
    def __init__(self, prompt: str):
        self.prompt = prompt
        self.data = np.array(
            [
                [True] * 8,
                [True] * 8,
                [False] * 8,
                [False] * 8,
                [False] * 8,
                [False] * 8,
                [True] * 8,
                [True] * 8,
            ]
        )

    async def scan(self) -> List[Tuple[int, int]]:
        diff = []

        line = await ainput(self.prompt)
        for word in line.split():
            file, rank = word
            x = ord(file) - 97  # 'a' -> 0
            y = int(rank) - 1  # '1' -> 0
            diff.append((x, y))
            self.data[y][x] = not self.data[y][x]

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
    # looks like luma can be only installed on RPI.
    from luma.core.interface.serial import spi, noop  # type: ignore [reportMissingImports]
    from luma.core.render import canvas  # type: ignore [reportMissingImports]
    from luma.led_matrix.device import max7219  # type: ignore [reportMissingImports]
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

        def __len__(self) -> int:
            return self.cascaded

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

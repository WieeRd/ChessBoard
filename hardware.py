import asyncio
import numpy as np
import gpiozero as gp

from typing import List, Sequence, Union, Any, Sequence, Tuple, Union


class OffsetArray(Sequence):
    """
    a: numpy.ndarray
    b = OffsetArray(a, (1,2))
    a[i+2][j+1] == b[i][j]
    """

    def __init__(self, array: np.ndarray, offset: Tuple[int, ...]):
        if len(array.shape) != len(offset):
            raise ValueError("Dimension of array and offset doesn't match")
        self.array = array
        self.offset = offset

    def __len__(self) -> int:
        return len(self.array) - self.offset[0]

    def __getitem__(self, index: int) -> Union["OffsetArray", Any]:
        elem = self.array[index + self.offset[0]]
        if len(self.array.shape) >= 2:
            return OffsetArray(elem, self.offset[1:])
        return elem

    def __setitem__(self, index: int, value):
        self.array[index + self.offset[0]] = value


LED = gp.LED
Button = gp.Button


class dummyLED(LED):
    def __init__(self):
        pass

    def on(self):
        pass

    def off(self):
        pass

    def close(self):
        pass


class Electrode:
    def __init__(self, send: List[LED], recv: List[Button]):
        self.data = np.full((len(send), len(recv)), False)
        self.send = send
        self.recv = recv

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


class LEDmatrix:
    """
    Base class for LED matrix controlling
    Modifity data with on(), off(), toggle()
    apply it with flush()
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


class DummyMatrix(LEDmatrix):
    """
    Virtual device that doesn't do anything
    other than just storing LED states
    """


try:
    from luma.core.interface.serial import spi, noop  # type: ignore
    from luma.core.render import canvas  # type: ignore
    from luma.led_matrix.device import max7219  # type: ignore
except ImportError:
    LUMA = False
else:
    LUMA = True

    class MatrixChain(LEDmatrix):
        """Controls multiple daisy-chained max7219 LED matrix"""

        data: np.ndarray

        def __init__(self, serial: spi, chained: int = 1):
            self.chained = chained
            self.device = max7219(serial, cascaded=chained)

            self.height = 8
            self.width = 8 * chained

            self.data = np.full((self.height, self.width), False)

        def flush(self):
            with canvas(self.device) as draw:
                for y in range(self.height):
                    for x in range(self.width):
                        if self.data[y][x]:
                            draw.point((x, y), fill="white")

    class SingleMatrix(LEDmatrix):
        """Control single LED matrix in MatrixChain"""

        data: OffsetArray

        def __init__(self, chain: MatrixChain, offset: int):
            self.chain = chain
            self.data = OffsetArray(self.chain.data, (0, offset * 8))

        def flush(self):
            self.chain.flush()

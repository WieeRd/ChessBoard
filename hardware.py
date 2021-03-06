#!/usr/bin/env python3
"""
Deals with physical chessboard itself
Provides interface to LED/Electrode 8x8 matrix
"""
import asyncio
import numpy as np
import gpiozero as gp
from typing import List, Sequence, Union, Any, Sequence, Tuple, Union

class OffsetArray(Sequence):
    """
    arr: numpy.ndarray
    oa = OffsetArray(arr, (1,2))
    oa[i][j] == arr[i+2][j+1]
    >>> True
    """
    def __init__(self, array: np.ndarray, offset: Tuple[int, ...]):
        if len(array.shape)!=len(offset):
            raise ValueError("Dimension of array and offset doesn't match")
        self.array = array
        self.offset = offset

    def __len__(self) -> int:
        return len(self.array) - self.offset[0]

    def __getitem__(self, index: int) -> Union['OffsetArray', Any]:
        ret = self.array[index + self.offset[0]]
        if len(self.array.shape)==1:
            return ret
        else:
            return OffsetArray(ret, self.offset[1:])

    def __setitem__(self, index: int, value):
        self.array[index + self.offset[0]] = value

LED = gp.LED
Button = gp.Button

class dummyLED(LED):
    def __init__(self): pass
    def on(self): pass
    def off(self): pass
    def close(self): pass

class Electrode:
    def __init__(self, send: List[LED], receive: List[Button]):
        self.data = np.full((len(send),len(receive)), False)
        self.send = send
        self.receive = receive

    def scan(self):
        for i, s in enumerate(self.send):
            s.on()
            for j, r in enumerate(self.receive):
                self.data[i][j] = r.value
            s.off()

class LEDmatrix:
    """
    Base class for LED matrix controlling
    Modifity data with on(), off(), toggle()
    apply it with flush()
    """

    data: Union[List, np.ndarray]

    def on(self, x:int, y:int):
        self.data[y][x] = True

    def off(self, x:int, y:int):
        self.data[y][x] = False

    def toggle(self, x:int, y:int):
        self.data[y][x] = not self.data[y][x]

    def flush(self):
        pass

class DummyMatrix(LEDmatrix):
    """
    Virtual device that doesn't do anything
    other than just storing changes made
    """

    def __init__(self):
        self.data = np.full((8, 8), False)

try:
    from luma.core.interface.serial import spi, noop
    from luma.core.render import canvas
    from luma.led_matrix.device import max7219
    
except ImportError:
    LUMA = False

else:
    LUMA = True

    class MatrixChain(LEDmatrix):
        """ Controls multiple daisy-chained max7219 LED matrix """

        data: np.ndarray

        def __init__(self, serial: spi, chained: int = 1):
            self.chained = chained
            self.device = max7219(serial, cascaded=chained)

            self.height = 8
            self.width = 8*chained

            self.data = np.full((self.height, self.width), False)

        def flush(self):
            with canvas(self.device) as draw:
                for y in range(self.height):
                    for x in range(self.width):
                        if self.data[y][x]:
                            draw.point((x, y), fill="white")

    class SingleMatrix(LEDmatrix):
        """ Control single LED matrix in MatrixChain """

        data: OffsetArray

        def __init__(self, chain: MatrixChain, offset: int):
            self.chain = chain
            self.data = OffsetArray(self.chain.data, (0, offset*8))

        def flush(self):
            self.chain.flush()


#!/usr/bin/env python3
"""
Deals with physical chessboard itself
Provides interface to LED/Electrode 8x8 matrix
"""
import numpy as np
import gpiozero as gp
from abc import ABCMeta, abstractmethod
from typing import Sequence, Union, Any, Sequence, Tuple, Union

from luma.core.interface.serial import spi
from luma.core.render import canvas
from luma.led_matrix.device import max7219

class OffsetArray(Sequence):
    """
    <Example>
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

class LED(gp.LED):
    pass

class Electrode:
    def __init__(self):
        self.data = np.full((8,8), False)

    def scan(self) -> np.ndarray:
        raise NotImplementedError

class LEDmatrix(metaclass=ABCMeta):
    """
    Abstract base class for controlling LED matrix
    Modifity data with on(), off(), toggle()
    apply it with flush()
    """

    data: Union[Sequence, np.ndarray]

    def on(self, x:int, y:int):
        self.data[y][x] = True

    def off(self, x:int, y:int):
        self.data[y][x] = False

    def toggle(self, x:int, y:int):
        self.data[y][x] = not self.data[y][x]

    @abstractmethod
    def flush(self): pass

class MatrixChain(LEDmatrix):
    """ Controls multiple daisy-chained max7219 LED matrix """

    data: np.ndarray

    def __init__(self, serial: spi, cascaded: int = 1):
        self.cascaded = cascaded
        self.device = max7219(serial, cascaded=cascaded)

        self.height = 8
        self.width = 8*cascaded
        self.data = np.full((self.width, self.height), False)

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
        self.data = OffsetArray(self.chain.data, (offset*8, 0))

    def flush(self):
        self.chain.flush()

# Dummy classses used for software debugging
# ( Fake devices that doesn't do anything )

class dummyLED(LED):
    def __init__(self): pass
    def on(self): pass
    def off(self): pass

class DummyMatrix(LEDmatrix):
    """
    Virtual device that doesn't do anything
    other than just storing changes made
    """

    def __init__(self):
        self.data = np.full((8, 8), False)

    def flush(self):
        pass

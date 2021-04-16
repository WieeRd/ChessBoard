from abc import ABCMeta, abstractmethod

from luma.core.interface.serial import spi, noop
from luma.core.render import canvas
from luma.led_matrix.device import max7219

# serial = spi(port=0, device=0, gpio=noop())
# device = max7219(serial)

# with canvas(device) as draw:
#         draw.rectangle(device.bounding_box, outline="white", fill="black")

class LEDmatrix(metaclass=ABCMeta):
    """
    Abstract base class for controlling LED matrix
    """
    @abstractmethod
    def on(self, x:int, y:int): pass

    @abstractmethod
    def off(self, x:int, y:int): pass

    @abstractmethod
    def toggle(self, x:int, y:int): pass

    @abstractmethod
    def flush(self): pass

class DummyMatrix(LEDmatrix):
    """
    Virtual device that doesn't do anything
    other than just storing changes made
    """
    def __init__(self):
        self.data = [[False]*8]*8

    def on(self, x:int, y:int):
        self.data[y][x] = True

    def off(self, x:int, y:int):
        self.data[y][x] = False

    def toggle(self, x:int, y:int):
        self.data[y][x] = not self.data[y][x]

    def flush(self):
        pass

class MatrixChain(LEDmatrix):
    """
    Controls multiple daisy-chained max7219 LED matrix
    Change data attribute via on(), off(), toggle()
    and apply it with flush()
    """
    def __init__(self, serial: spi, cascaded: int = 1):
        self.cascaded = cascaded
        self.device = max7219(serial, cascaded=cascaded)

        self.height = 8
        self.width = 8*cascaded
        self.data = [[False]*self.width]*self.height

    def flush(self):
        with canvas(self.device) as draw:
            for y in range(self.height):
                for x in range(self.width):
                    if self.data[y][x]:
                        draw.point((x, y), fill="white")

    def on(self, x:int, y:int):
        self.data[y][x] = True

    def off(self, x:int, y:int):
        self.data[y][x] = False

    def toggle(self, x:int, y:int):
        self.data[y][x] = not self.data[y][x]

class SingleMatrix(LEDmatrix):
    """
    Control single LED matrix among daisy-chained devices
    """
    def __init__(self, chain: MatrixChain, offset: int):
        self.chain = chain
        self.offset = offset*8

    def on(self, x:int, y:int):
        self.chain.on(x+self.offset, y)

    def off(self, x:int, y:int):
        self.chain.off(x+self.offset, y)

    def toggle(self, x:int, y:int):
        self.chain.toggle(x+self.offset, y)

    def flush(self):
        self.chain.flush()

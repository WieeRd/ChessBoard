from luma.core.interface.serial import spi, noop
from luma.core.render import canvas
from luma.led_matrix.device import max7219

serial = spi(port=0, device=0, gpio=noop())
device = max7219(serial)

with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="white", fill="black")

import numpy as np

class MatrixChain:
    def __init__(self, serial: spi, chain: int = 1):
        self.chain = chain
        self.device = max7219(serial, cascaded=chain)
        self.data = np.full((8*chain, 8), True)

    def flush(self):
        with canvas(self.device) as draw:
            for y in range(8):
                for x in range(8*self.chain):
                    if self.data[y][x]:
                        draw.point((x, y), fill="white")

    def on(self, x:int, y:int):
        self.data[y][x] = True

    def off(self, x:int, y:int):
        self.data[y][x] = False

    def toggle(self, x:int, y:int):
        self.data[y][x] = not self.data[y][x]

class SingleMatrix:
    def __init__(self, chain: MatrixChain, offset: int):
        pass

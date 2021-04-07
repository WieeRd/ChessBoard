#!/usr/bin/env python3
"""
Deals with physical chessboard itself
Provides interface to LED/Electrode 8x8 matrix
"""
import numpy as np
# import gpiozero as gp

class LEDmatrix:
    def __init__(self):
        self.data = np.full((8,8), False)

    def on(self, x:int, y:int):
        self.data[y][x] = True

    def off(self, x:int, y:int):
        self.data[y][x] = False

class Electrode:
    def __init__(self):
        self.data = np.full((8,8), False)

    def scan(self):
        raise NotImplementedError

class LED:
    def __init__(self): self.state = False
    def on(self): self.state = True
    def off(self): self.state = False


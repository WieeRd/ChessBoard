#!/usr/bin/env python3
import numpy as np
import gpiozero as gp

class LEDmatrix:
    def __init__(self):
        self.data = np.full((8,8), False)
 
    def __str__(self) -> str:
        ret = ""
        for row in self.data:
            for col in row:
                ret += '0' if col else '.'
            ret += '\n'
        return ret

    def on(self, x:int, y:int):
        self.data[y][x] = True

    def off(self, x:int, y:int):
        self.data[y][x] = False

class Detector:
    def __init__(self):
        self.data = np.full((8,8), False)

    def __str__(self) -> str:
        ret = ""
        for row in self.data:
            for col in row:
                ret += '@' if col else '.'
            ret += '\n'
        return ret

    def scan(self) -> np.ndarray:
        txt = input('>').split()
        cmd = txt[0]
        x, y = int(txt[1]), int(txt[2])
        if cmd=='lift':
            self.data[y][x] = False 
        elif cmd=='place':
            self.data[y][x] = True
        return self.data

red = LEDmatrix()
blue = LEDmatrix()
electrode = Detector()

#!/usr/bin/env python3
"""
Deals with physical chessboard itself
Provides interface to LED/Electrode 8x8 matrix
"""
import numpy as np
import gpiozero as gp

class LEDmatrix:
    def __init__(self):
        self.data = np.full((8,8), False)
 
    def status(self) -> str:
        ret = ""
        for row in self.data:
            for col in row:
                ret += '0' if col else '.'
                ret += ' '
            ret += '\n'
        return ret

    def on(self, x:int, y:int):
        self.data[y][x] = True

    def off(self, x:int, y:int):
        self.data[y][x] = False

class Electrode:
    def __init__(self):
        self.data = np.full((8,8), False)

    def status(self) -> str:
        ret = ""
        for row in self.data:
            for col in row:
                ret += '@' if col else '.'
                ret += ' '
            ret += '\n'
        return ret

    def scan(self) -> np.ndarray:
        txt = input('>')
        try:
            cmd = txt[0]
            x, y = int(txt[1]), int(txt[2])
        except:
            print("WTF")
        else:
            if cmd=='l':
                self.data[y][x] = False 
            elif cmd=='p':
                self.data[y][x] = True
        finally:
            return self.data

red = LEDmatrix()
blue = LEDmatrix()
detector = Electrode()

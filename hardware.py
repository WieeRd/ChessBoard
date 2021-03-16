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

    def __getitem__(self, key):
        return self.data[key]
 
    def on(self, x:int, y:int):
        self.data[y][x] = True

    def off(self, x:int, y:int):
        self.data[y][x] = False

    def status(self) -> str:
        ret = ""
        for row in self.data:
            for col in row:
                ret += '0' if col else '.'
                ret += ' '
            ret += '\n'
        return ret

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

def LEDstatus() -> str:
    '''
    Returns string representation
    of red/blue LED matrix
    '''
    ret = [[' ']*8]*8
    for y in range(8):
        for x in range(8):
            if red[y][x]:
                if blue[y][x]:
                    ret[y][x] = 'P'
                else:
                    ret[y][x] = 'R'
            else:
                if blue[y][x]:
                    ret[y][x] = 'B'
                else:
                    ret[y][x] = '.'
        ret[y] = ' '.join(ret[y])
    ret = '\n'.join(ret)
    return ret
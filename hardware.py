#!/usr/bin/env python3
"""
Deals with physical chessboard itself
Provides interface to LED/Electrode 8x8 matrix
"""
import chess
import numpy as np
# import gpiozero as gp
from typing import Any, Callable

def gen_status_str(data: np.ndarray, what: Callable[[Any], str]) -> str:
    ret = []
    for row in data:
        ret.append(' '.join(what(x) for x in row))
    return '\n'.join(ret)

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
        return gen_status_str(self.data, lambda x: '0' if x else '.')

class Electrode:
    def __init__(self):
        self.data = np.array([
            [True]*8,
            [True]*8,
            [False]*8,
            [False]*8,
            [False]*8,
            [False]*8,
            [True]*8,
            [True]*8,
        ])

    def __getitem__(self, key):
        return self.data[key]

    def scan(self) -> np.ndarray:
        txt = input('>').split()
        try:
            cmd = txt[0]
            square = chess.parse_square(txt[1])
            y, x = divmod(square, 8)
            if cmd=='L':
                self.data[y][x] = False 
            elif cmd=='P':
                self.data[y][x] = True
            else:
                raise ValueError
        except:
            print("Invalid command")
        finally:
            return self.data

    def status(self) -> str:
        return gen_status_str(self.data, lambda x: '@' if x else '.')

class fakeLED:
    def __init__(self): self.state = False
    def on(self): self.state = True
    def off(self): self.state = False

red = LEDmatrix()
blue = LEDmatrix()
detector = Electrode()
turnLED = [fakeLED(), fakeLED()]

def gen_color_char(red: bool, blue: bool) -> str:
    if red:
        if blue:
            return 'P' # Purple
        else:
            return 'R' # Red
    else:
        if blue:
            return 'B' # Blue
        else:
            return '.' # Turned off

def LEDstatus() -> str:
    ret = ""
    for y in range(8):
        for x in range(8):
            ret += gen_color_char(red[y][x], blue[y][x])
            ret += ' '
        ret += '\n'
    return ret

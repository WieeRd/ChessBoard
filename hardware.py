#!/usr/bin/env python3
"""
Deals with physical chessboard itself
Provides interface to LED/Electrode 8x8 matrix
"""
import numpy as np
# import gpiozero as gp
from typing import Any, Callable

def gen_status_str(data: np.ndarray, what: Callable[[Any], str]) -> str:
    '''Generates str representation of 8x8 matrix data'''
    ret = ""
    for row in data:
        for col in row:
            ret += what(col)
            ret += ' '
        ret += '\n'
    return ret

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
        # TODO: SAN support
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

    def status(self) -> str:
        return gen_status_str(self.data, lambda x: '@' if x else '.')

red = LEDmatrix()
blue = LEDmatrix()
detector = Electrode()

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

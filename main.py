#!/usr/bin/env pyton3
import chess
import numpy as np
import itertools as it

import hardware as hw
import software as sw

from typing import Callable, Any

def gen_status_str(data: np.ndarray, what: Callable[[Any], str]) -> str:
    ret = []
    for row in data:
        ret.append(' '.join(what(x) for x in row))
    return '\n'.join(ret)

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

def main():
    red = hw.LEDmatrix()
    blue = hw.LEDmatrix()
    turn = ( hw.LED(), hw.LED() )
    detector = hw.Electrode()
    game = sw.ChessBoard(blue, red, turn)

    event_occured = True
    while True:


def play(self):
    prev = hw.detector.data.copy()
    event_occured = True
    while True:
        if event_occured:
            event_occured = False
            print(self.status())
        curr = hw.detector.scan()
        for y, x in it.product(range(8), range(8)):
            if curr[y][x]!=prev[y][x]:
                event_occured = True
                if curr[y][x]:
                    self.on_place(x, y)
                else:
                    self.on_lift(x, y)
        prev = curr.copy()


def status(self) -> str:
    sp_brd = str(self.board).split(sep='\n')
    sp_det = hw.detector.status().split(sep='\n')
    sp_led = hw.LEDstatus().split(sep='\n')
    sp_til = hw.gen_status_str(self.tiles, lambda x: x.value).split(sep='\n')
    ret = ''
    for i in range(8):
        ret += str(8-i) + ' '
        ret += '  '.join((sp_brd[i], sp_led[7-i], sp_det[7-i], sp_til[7-i]))
        ret += '\n'
    colorname = {0: 'B', 1: 'W', None:'P'}
    ret += f"  a b c d e f g h  "
    ret += f"T:{colorname[self.turn]} | P:{self.pending} | E:{self.errors} | aW:{len(self.in_air[1])}, aB:{len(self.in_air[0])}"
    return ret


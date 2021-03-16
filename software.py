#!/usr/bin/env python3
import chess
import numpy as np
import itertools as it

import hardware as hw
from enum import Enum
from functools import wraps

class Player:
    """
    Contains player specific info
    such as name, picked up pieces
    """
    def __init__(self, name:str):
        self.name = name
        self.in_air = set()

class Tile(Enum):
    "Tile state (Enum)"
    EMPTY = '.'
    GROUND = 'G'
    MISSING = 'M'
    WRONG = 'W'
    SELECT = 'S'

def event(func):
    "Monitor occured events (Debugging purpose)"
    @wraps(func)
    def ret(*args):
        print(f"Event : {func.__name__}{args[1:]}")
        return func(*args)
    return ret

class Game:
    def __init__(self):
        self.player = [Player("White"), Player("Black")]
        self.turn = -1

        self.pending = True
        self.errors = 0

        self.select = None
        self.all_ps_moves = ()
        self.ps_moves = ()

        self.board = chess.Board()
        self.tiles = np.array([
            [Tile.GROUND]*8,
            [Tile.GROUND]*8,
            [Tile.EMPTY]*8,
            [Tile.EMPTY]*8,
            [Tile.EMPTY]*8,
            [Tile.EMPTY]*8,
            [Tile.GROUND]*8,
            [Tile.GROUND]*8,
        ])

    def TileStatus(self) -> str:
        return hw.gen_status_str(self.tiles, lambda x: x.value)

    def status(self) -> str:
        sp_brd = str(self.board).split(sep='\n')
        sp_det = hw.detector.status().split(sep='\n')
        sp_led = hw.LEDstatus().split(sep='\n')
        sp_til = self.TileStatus().split(sep='\n')
        ret = ''
        for i in range(8):
            ret += sp_det[7-i] + ' ' + sp_brd[i] + '  ' + sp_til[7-i] + ' ' + sp_led[7-i]
            ret += '\n'
        return ret

    def play(self):
        prev = hw.detector.scan().copy()
        while True:
            print(self.status())
            curr = hw.detector.scan()
            for y, x in it.product(range(8), range(8)):
                if curr[y][x]!=prev[y][x]:
                    if curr[y][x]:
                        self.on_place(x, y)
                    else:
                        self.on_lift(x, y)
            prev = curr.copy()

    @event
    def on_place(self, x:int, y:int):
        tile = self.tiles[y][x]
        if   tile==Tile.EMPTY:
            pass
        elif tile==Tile.MISSING:
            pass
        elif tile==Tile.SELECT:
            pass

    @event
    def on_lift(self, x:int, y:int):
        tile = self.tiles[y][x]
        if   tile==Tile.GROUND:
            pass
        elif tile==Tile.WRONG:
            pass

match = Game()
match.play()

#!/usr/bin/env python3
import chess
import numpy as np
import hardware as hw
import itertools as it
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
    '''Tile state (Enum type) '''
    EMPTY = 'E'
    PLACED = 'P'
    MISSING = 'M'
    WRONG = 'W'
    SELECT = 'S'

def event(func):
    '''debugging purpose; monitor occured events'''
    @wraps(func)
    def ret(*args):
        print(f"Event occured: {func.__name__}{args[1:]}")
        return func(*args)
    return ret

class Game:
    def __init__(self):
        self.player = [Player("White"), Player("Black")]
        self.turn = -1

        self.pending = True
        self.errors = 0

        self.select = None
        self.ps_moves = ()

        self.board = chess.Board()
        self.tiles = np.full((8,8), Tile.EMPTY)

    def TileStatus(self) -> str:
        ret = ""
        for row in self.tiles:
            for col in row:
                pass # AHHHHHHHHHH

    def status(self) -> str:
        # TODO: Add tile state status
        sp_brd = str(self.board).split(sep='\n')
        sp_det = hw.detector.status().split(sep='\n')
        sp_led = hw.LEDstatus().split(sep='\n')
        ret = ''
        for i in range(8):
            ret += sp_brd[i] + '  ' + sp_det[7-i] + '  ' + sp_led[7-i]
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
        pass

    @event
    def on_lift(self, x:int, y:int):
        pass

match = Game()
match.play()

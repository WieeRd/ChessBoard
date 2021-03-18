#!/usr/bin/env python3
import chess
import numpy as np
import itertools as it

import hardware as hw
from enum import Enum
from functools import wraps
from typing import Optional, Set, Tuple

class Player:
    """
    Contains player specific info
    such as name, picked up pieces
    """
    def __init__(self, name:str):
        self.name = name
        self.in_air: Set[Tuple[int, int]] = set()

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
        self.players = [Player('Black'), Player('White')]
        self.turn = 0       # game starts at 1(White) not 0(Black)
        self.pending = True # since pending is default set to True 
        self.errors = 0

        self.select = None # position of selected piece
        self.ps_moves = () # possible moves for selected piece

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
            if (x, y) in self.ps_moves:
                self.on_move(x, y)
            else:
                self.on_misplace(x, y)
        elif tile==Tile.MISSING:
            if (x, y) in self.ps_moves:
                self.on_kill(x, y)
            else:
                self.on_retrieve(x, y)
        elif tile==Tile.SELECT:
            self.on_unselect(x, y)

    @event
    def on_lift(self, x:int, y:int):
        tile = self.tiles[y][x]
        if   tile==Tile.GROUND:
            piece = self.board.piece_at(chess.square(x, y))
            owner = self.players[piece.color]
            owner.in_air.add((x, y))
            if self.turn==piece.color and len(owner.in_air)==1:
                self.on_select(x, y)
            else:
                self.on_missing(x, y)
        elif tile==Tile.WRONG:
            self.on_cleanup(x, y)
        else:
            print(f"WTF: on_lift occured at {tile}")
            exit(-1)

    @event
    def on_select(self, x, y): pass
    @event
    def on_unselect(self, x, y): pass

    @event
    def on_missing(self, x, y): pass
    @event
    def on_retrieve(self, x, y): pass
    
    @event
    def on_misplace(self, x, y): pass
    @event
    def on_cleanup(self, x, y): pass

    @event
    def on_move(self, x, y): pass
    @event
    def on_kill(self, x, y): pass

match = Game()
match.play()

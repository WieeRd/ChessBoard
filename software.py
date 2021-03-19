#!/usr/bin/env python3
import chess
import numpy as np
import itertools as it

import hardware as hw
from enum import Enum
from functools import wraps
from typing import Optional, Set, Tuple

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
        # color = turn%2; turn = (turn+1)%2
        self.turn = 1 # 2 1 0 1 0 (white=1, black=0)
        self.pending = True
        self.errors = 0

        self.in_air = [set(), set()]
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
            ret += str(8-i) + ' '
            ret += sp_brd[i] + '  ' + sp_det[7-i] + ' ' + sp_til[7-i] + ' ' + sp_led[7-i]
            ret += '\n'
        ret += '  a b c d e f g h\n'
        return ret

    def color_at(self, x, y) -> chess.Color:
        # piece_at could return None, so have fun with AttributeError
        return self.board.piece_at(chess.square(x, y)).color

    def play(self):
        # prev = hw.detector.scan().copy()
        prev = hw.detector.data.copy()
        while True:
            print(self.status())
            curr = hw.detector.scan()
            for y, x in it.product(range(8), range(8)):
                if curr[y][x]!=prev[y][x]:
                    if prev[y][x]:
                        self.on_lift(x, y)
                    else:
                        self.on_place(x, y)
            prev = curr.copy()

    @event
    def on_lift(self, x:int, y:int):
        tile = self.tiles[y][x]
        if tile not in (Tile.GROUND, Tile.WRONG):
            print(f"WTF: on_lift at {tile}")
            exit(-1)
        elif tile==Tile.GROUND:
            color = self.color_at(x, y)
            self.in_air[color].add((x, y))
            if self.turn==color and len(self.in_air[color])==1:
                self.on_select(x, y)
            else:
                self.on_missing(x, y)
        elif tile==Tile.WRONG:
            self.on_cleanup(x, y)

    @event
    def on_place(self, x:int, y:int):
        tile = self.tiles[y][x]
        if tile not in (Tile.EMPTY, Tile.MISSING, Tile.SELECT):
            print(f"WTF: on_place at {tile}")
            exit(-1)
        elif tile==Tile.EMPTY:
            if (x, y) in self.ps_moves:
                self.on_move(x, y)
            else:
                self.on_misplace(x, y)
        else: # can know the owner of piece
            color = self.color_at(x, y)
            self.in_air[color].remove((x, y))
            if tile==Tile.MISSING:
                if (x, y) in self.ps_moves:
                    self.on_kill(x, y)
                else:
                    self.on_retrieve(x, y)
            elif tile==Tile.SELECT:
                self.on_unselect(x, y)

    @event
    def on_select(self, x, y):
        self.tiles[y][x] = Tile.SELECT
        self.select = (x, y)
        func = lambda m: m.from_square==chess.square(x, y)
        tmp = filter(func, self.board.legal_moves)
        tmp = (divmod(x.to_square, 8) for x in tmp)
        self.ps_moves = tuple((x, y) for y, x in tmp)
        for x, y in self.ps_moves:
            hw.blue.on(x, y)

    @event
    def on_unselect(self, x, y):
        self.tiles[y][x] = Tile.GROUND
        for x, y in self.ps_moves:
            hw.blue.off(x, y)
        self.select = None
        self.ps_moves = ()

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

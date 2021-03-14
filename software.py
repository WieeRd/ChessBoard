#!/usr/bin/env python3
import chess
import numpy as np
import hardware as hw
from enum import Enum

class Team:
    def __init__(self, name:str):
        self.name = name
        self.in_air = set()

class Tile(Enum):
    EMPTY = 0
    PLACED = 1
    MISSING = 2
    MISPLACED = 3
    SELECT = 4

class Game:
    def __init__(self):
        self.team = [Team("White"), Team("Black")]
        self.turn = -1

        self.pending = True
        self.errors = 0

        self.select = None
        self.ps_moves = ()

        self.board = chess.Board()
        self.tiles = np.full((8,8), Tile.EMPTY)

    def play(self):
        pass

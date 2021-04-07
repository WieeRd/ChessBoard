#!/usr/bin/env python3
import chess
from chess import engine

import asyncio
import numpy as np

import hardware as hw
from enum import Enum
from functools import wraps
from typing import Tuple

# TODO: IntFlag
class Tile(Enum):
    "Tile state (Enum)"
    EMPTY = '.'
    GROUND = 'G'
    MISSING = 'M'
    WRONG = 'W'
    SELECT = 'S'

def event(func):
    """Print occured event (Debugging purpose)"""
    @wraps(func)
    def ret(*args):
        print(f"Event : {func.__name__}{args[1:]}")
        return func(*args)
    return ret

class ChessBoard:
    def __init__(self, goodLED: hw.LEDmatrix, warnLED: hw.LEDmatrix, turnLED: Tuple[hw.LED, hw.LED],
                 engine: engine.UciProtocol=None, timeout: int=1):
        self.goodLED = goodLED
        self.warnLED = warnLED
        self.turnLED = turnLED

        self.engine = engine
        if self.engine!=None:
            self.timeout = timeout
            self.AIselect = (0, 0)

        self.board = chess.Board()
        self.tiles = np.array([
            [Tile.MISSING]*8,
            [Tile.MISSING]*8,
            [Tile.EMPTY]*8,
            [Tile.EMPTY]*8,
            [Tile.EMPTY]*8,
            [Tile.EMPTY]*8,
            [Tile.MISSING]*8,
            [Tile.MISSING]*8,
        ])

        self.turn = None
        self.pending = True
        self.errors = 0

        self.in_air = [set(), set()]
        self.legal_moves = tuple(self.board.legal_moves)
        self.ps_moves = ()
        self.select = None

    def color_at(self, x:int, y:int) -> chess.Color:
        # piece_at could return None, so have fun with AttributeError
        return self.board.piece_at(chess.square(x, y)).color

    @event
    async def switch_turn(self):
        self.turn = not self.turn
        self.turnLED[self.turn].on()
        self.turnLED[not self.turn].off()
        self.legal_moves = tuple(self.board.legal_moves)

        if self.engine!=None:
            if self.turn==chess.BLACK: # AI's turn
                loop = asyncio.get_event_loop()
                loop.create_task(self.run_engine())
            elif self.turn==chess.WHITE:
                self.goodLED.off(*self.AIselect)

    async def run_engine(self):
        self.turn = None
        print("Started thinking")
        think = self.engine.play(self.board, engine.Limit(time=self.timeout))
        move = (await think).move
        print("Finished thinking")
        self.legal_moves = (move, )
        y, x = divmod(move.from_square, 8)
        self.AIselect = (x, y)
        self.goodLED.on(x, y)
        self.turn = chess.BLACK

    @event
    async def on_place(self, x:int, y:int):
        tile = self.tiles[y][x]
        assert tile in (Tile.EMPTY, Tile.MISSING, Tile.SELECT)
        if tile==Tile.EMPTY:
            if (x, y) in self.ps_moves:
                await self.on_move(x, y)
            else:
                await self.on_misplace(x, y)
        else:
            color = self.color_at(x, y)
            self.in_air[color].remove((x, y))
            if tile==Tile.MISSING:
                if (x, y) in self.ps_moves:
                    await self.on_kill(x, y)
                else:
                    await self.on_retrieve(x, y)
            elif tile==Tile.SELECT:
                await self.on_unselect()

    @event
    async def on_lift(self, x:int, y:int):
        tile = self.tiles[y][x]
        assert tile in (Tile.GROUND, Tile.WRONG)
        if tile==Tile.GROUND:
            color = self.color_at(x, y)
            self.in_air[color].add((x, y))
            if self.turn==color and len(self.in_air[color])==1:
                await self.on_select(x, y)
            else:
                await self.on_missing(x, y)
        elif tile==Tile.WRONG:
            await self.on_cleanup(x, y)

    @event
    async def on_select(self, x:int, y:int):
        self.tiles[y][x] = Tile.SELECT
        self.select = (x, y)
        func = lambda m: m.from_square==chess.square(x, y)
        tmp = filter(func, self.legal_moves)
        tmp = (divmod(x.to_square, 8) for x in tmp)
        self.ps_moves = tuple((x, y) for y, x in tmp)
        for x, y in self.ps_moves:
            self.goodLED.on(x, y)

    @event
    async def on_unselect(self):
        assert self.select!=None
        x, y = self.select
        self.tiles[y][x] = Tile.GROUND
        for x, y in self.ps_moves:
            self.goodLED.off(x, y)
        self.select = None
        self.ps_moves = ()

    @event
    async def on_missing(self, x:int, y:int):
        self.tiles[y][x] = Tile.MISSING
        self.errors += 1
        self.warnLED.on(x, y)
        if self.select!=None and self.turn==self.color_at(x, y):
            select = self.select
            await self.on_unselect()
            await self.on_missing(*select)

    @event
    async def on_retrieve(self, x:int, y:int):
        self.tiles[y][x] = Tile.GROUND
        self.errors -= 1
        self.warnLED.off(x, y)
        color = self.color_at(x, y)
        if self.turn==color and len(self.in_air[color])==1:
            new_select = tuple(self.in_air[color])[0]
            self.warnLED.off(*new_select)
            await self.on_select(*new_select)
            self.errors -= 1 # gotcha! Pesky lil bug
        if self.pending and self.errors==0:
            self.pending = False
            await self.switch_turn()

    @event
    async def on_misplace(self, x:int, y:int):
        self.tiles[y][x] = Tile.WRONG
        self.errors += 1
        self.warnLED.on(x, y)

    @event
    async def on_cleanup(self, x:int, y:int):
        self.tiles[y][x] = Tile.EMPTY
        self.errors -= 1
        self.warnLED.off(x, y)
        if self.pending and self.errors==0:
            self.pending = False
            await self.switch_turn()

    @event
    async def on_move(self, to_x:int, to_y:int):
        assert self.select!=None and self.turn!=None
        from_x, from_y = self.select
        move = chess.Move(chess.square(from_x, from_y), chess.square(to_x, to_y))
        piece = self.board.piece_at(chess.square(*self.select))
        print(f"{move.uci()} ({chess.piece_name(piece.piece_type)})")

        self.in_air[self.turn].remove(self.select)
        await self.on_unselect()

        self.tiles[to_y][to_x] = Tile.GROUND
        self.tiles[from_y][from_x] = Tile.EMPTY

        # Special move detection
        if piece.piece_type==chess.PAWN:
            if from_x!=to_x: # En passant
                print("En passant detected")
                if self.tiles[from_y][to_x]==Tile.MISSING:
                    await self.on_place(to_x, from_y)
                await self.on_misplace(to_x, from_y)
                self.pending = True
            elif to_y%7==0: # Promotion
                print("Promotion detected")
                move.promotion = chess.QUEEN
        elif piece.piece_type==chess.KING:
            dx = to_x - from_x
            if abs(dx)>1: # Castling
                print("Castling detected")
                rook_init = 7 if dx>0 else 0, to_y
                rook_after = to_x - dx//2, to_y
                self.in_air[self.turn].add(rook_after)
                await self.on_misplace(*rook_init)
                await self.on_missing(*rook_after)
                self.pending = True

        self.board.push(move)
        if self.pending: print("Pending")
        else: await self.switch_turn()

    @event
    async def on_kill(self, to_x:int, to_y:int):
        assert self.select!=None and self.turn!=None
        from_x, from_y = self.select
        move = chess.Move(chess.square(from_x, from_y), chess.square(to_x, to_y))
        print(move.uci())

        self.errors -= 1 # Missing -> Killed
        self.warnLED.off(to_x, to_y)
        self.tiles[to_y][to_x] = Tile.GROUND

        await self.on_unselect()
        self.in_air[self.turn].remove((from_x, from_y))
        self.tiles[from_y][from_x] = Tile.EMPTY

        self.board.push(move)
        await self.switch_turn()


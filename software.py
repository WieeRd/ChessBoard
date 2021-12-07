import chess
import chess.engine
import asyncio
import logging
import functools
import numpy as np
import gpiozero as gp
import hardware as hw

from enum import IntFlag
from typing import List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


def event(func):
    @functools.wraps(func)
    def ret(*args):
        logger.debug(f"Event: {func.__name__}{args[1:]}")
        return func(*args)

    return ret


class State(IntFlag):
    NONE = 0
    DETECTED = 1
    ERROR = 2
    CHOSEN = 4


# 0, 1, 2, 3, 4
EMPTY = State.NONE
GROUND = State.DETECTED
MISSING = State.ERROR
MISPLACE = State.DETECTED | State.ERROR
SELECT = State.CHOSEN


class GameOverError(Exception):
    def __init__(self, reason: chess.Outcome):
        super().__init__(f"Game Over! {reason.result()} ({reason.termination.name})")
        self.reason = reason


class ChessBoard:
    """
    Controls LED chessboard based on occured events.
    Only on_place(), on_lift(), toggle() should be called
    manually unless you fully understand what you're doing
    I don't know what I'm doing tbh
    """

    def __init__(
        self,
        goodLED: hw.LEDmatrix,
        warnLED: hw.LEDmatrix,
        turnLED: Tuple[gp.LED, gp.LED],
        engine: chess.engine.UciProtocol = None,
        timeout: float = 1.0,
    ):
        self.board = chess.Board()
        self.states = np.array(
            [
                [MISSING] * 8,
                [MISSING] * 8,
                [EMPTY] * 8,
                [EMPTY] * 8,
                [EMPTY] * 8,
                [EMPTY] * 8,
                [MISSING] * 8,
                [MISSING] * 8,
            ],
            dtype=np.uint8,
        )

        self.goodLED = goodLED
        self.warnLED = warnLED
        self.turnLED = turnLED

        self.engine = engine
        self.timeout = timeout

        Pos = Tuple[int, int]

        # turn is occasionally set to None to block on_select()
        self.turn: Optional[chess.Color] = None
        # position of lifted(not detected) pieces
        self.lifted: Tuple[Set[Pos], Set[Pos]] = set(), set()
        # error count (missing + misplace)
        self.errors: int = 0
        # when a move requires more than 2 actions,
        # 'pending' state is set instead of switch_turn().
        # when all errors are resolved (errors == 0),
        # switch_turn() is called and pending is unset
        self.pending: bool = True

        # position of currently selected piece
        self.select: Optional[Pos] = None
        # position of piece selected by engine
        self.AIselect: Optional[Pos] = None
        # all possible legal moves on the board
        self.legal_moves: List[chess.Move] = []
        # positions currently selected piece can go to
        self.candidates: List[Pos] = []

    def color_at(self, x: int, y: int) -> chess.Color:
        """
        Return color of piece at (x, y)
        Raise ValueError if no piece is at (x, y)
        """
        square = chess.square(x, y)
        piece = self.board.piece_at(square)
        if not piece:
            raise ValueError(f"No piece at {(x, y)}")
        return piece.color

    async def run_engine(self):
        """
        1. Block on_select on both side
        2. When finished thinking, highlight from_square of result
        3. Limit legal_moves to single move (engine result)
        """
        logger.debug("Running uci engine")
        assert self.engine != None
        self.turn = None  # Block selection untill engine returns

        limit = chess.engine.Limit(time=self.timeout)
        result = await self.engine.play(self.board, limit=limit)
        if not result.move:
            # engine gave up for some reason?
            reason = chess.Outcome(chess.Termination.VARIANT_WIN, chess.WHITE)
            raise GameOverError(reason)

        square = result.move.from_square
        x, y = square % 8, square // 8
        self.legal_moves = [result.move]
        self.AIselect = (x, y)
        self.goodLED.on(x, y)

        self.turn = chess.BLACK
        logger.debug(f"Engine returned {result.move.uci()}")

    @event
    async def switch_turn(self):
        """
        1. Update turnLED state
        2. Check if the game is over & raise GameOverError(Outcome)
        3. If engine is given & AI's turn, run_engine is called
        """
        self.turn = not self.turn
        self.turnLED[self.turn].on()
        self.turnLED[not self.turn].off()
        self.legal_moves = list(self.board.legal_moves)

        outcome = self.board.outcome()
        if outcome != None:
            raise GameOverError(outcome)

        if self.engine != None:
            if self.turn == chess.BLACK:  # AI's turn
                asyncio.create_task(self.run_engine())
            elif self.turn == chess.WHITE and self.AIselect:
                self.goodLED.off(*self.AIselect)

    @event
    async def on_select(self, x: int, y: int):
        """
        When piece of current turn's color is picked up
        and it's the only piece of that color that is picked up

        Highlight possible moves with goodLED
        """
        self.states[y][x] = SELECT
        self.select = (x, y)

        selected = chess.square(x, y)
        self.candidates = [
            (m.to_square % 8, m.to_square // 8)  # chess.Square to (int, int)
            for m in filter(lambda m: m.from_square == selected, self.legal_moves)
        ]

        self.goodLED.on(x, y)
        for x, y in self.candidates:
            self.goodLED.on(x, y)

    @event
    async def on_unselect(self):
        """
        When selected piece is retrieved,
        or another piece with same color is lifted

        Turn off goodLED at highlighted square
        """
        assert self.select != None

        x, y = self.select
        self.states[y][x] = GROUND
        self.select = None

        if not self.AIselect:
            self.goodLED.off(x, y)
        for x, y in self.candidates:
            self.goodLED.off(x, y)
        self.candidates = []

    @event
    async def on_missing(self, x: int, y: int):
        """
        When a piece that shouldn't move is lifted

        Turn on warnLED at lifted square
        If other piece of same color was selected,
        cancel that selection and mark it as missing
        """
        self.states[y][x] = MISSING
        self.errors += 1
        self.warnLED.on(x, y)

        if self.select != None and self.turn == self.color_at(x, y):
            logger.debug("2+ pieces are missing; Canceling selection")
            x, y = self.select
            await self.on_unselect()
            await self.on_missing(x, y)

    @event
    async def on_retrieve(self, x: int, y: int):
        """
        When a missing piece returns to the board

        Turn off warnLED of retrieved square
        If only 1 piece of current turn's color
        remains missing, mark it as select
        """
        self.states[y][x] = GROUND
        self.errors -= 1
        self.warnLED.off(x, y)

        color = self.color_at(x, y)
        if self.turn == color and len(self.lifted[color]) == 1:
            logger.debug("Only 1 piece remains missing; Enabling selection")
            new_select = next(iter(self.lifted[color]))  # get single element from set
            self.errors -= 1
            self.warnLED.off(*new_select)
            await self.on_select(*new_select)

        if self.pending and self.errors == 0:
            logger.debug("All errors resolved. No longer pending.")
            self.pending = False
            await self.switch_turn()

    @event
    async def on_misplace(self, x: int, y: int):
        """
        When unexpected detection occurs
        (Usually by attempting illegal move)

        Turn on warnLED at detected square
        """
        self.states[y][x] = MISPLACE
        self.errors += 1
        self.warnLED.on(x, y)

    @event
    async def on_cleanup(self, x: int, y: int):
        """
        When misplace detection is removed

        Turn off warnLED by on_misplace
        """
        self.states[y][x] = EMPTY
        self.errors -= 1
        self.warnLED.off(x, y)

        if self.pending and self.errors == 0:
            logger.debug("All errors resolved. No longer pending.")
            self.pending = False
            await self.switch_turn()

    @event
    async def on_move(self, x: int, y: int):
        """
        When selected piece is placed at empty square

        Pawn is promoted to Queen when it reaches last square
        When castling, King always has to be moved first
        """
        assert self.select != None and self.turn != None
        piece = self.board.piece_at(chess.square(*self.select))
        assert piece != None

        to_x, to_y = x, y
        from_x, from_y = self.select
        move = chess.Move(chess.square(from_x, from_y), chess.square(to_x, to_y))
        logger.debug(f"Move: {move.uci()} ({piece})")

        self.lifted[self.turn].remove(self.select)
        await self.on_unselect()

        self.states[to_y][to_x] = GROUND
        self.states[from_y][from_x] = EMPTY

        # Special moves
        if piece.piece_type == chess.PAWN:
            # En passant: Pawn moved in X axis without capturing anything
            if from_x != to_x:
                logger.debug("Special move: En passant")
                # (from_y, to_x): Enemey piece to capture

                # # legacy code (past myself wrote something I don't understand)
                # if self.states[from_y][to_x] == MISSING:
                #     await self.on_place(to_x, from_y)
                # await self.on_misplace(to_x, from_y)
                # self.pending = True

                # TODO: not tested
                if self.states[from_y][to_x] == GROUND:
                    # enemy pawn has to be removed
                    await self.on_misplace(to_x, from_y)
                    self.pending = True

                elif self.states[from_y][to_x] == MISSING:
                    # already removed, cancel missing state
                    await self.on_place(to_x, from_y)
                    self.states[from_y][to_x] = EMPTY

            # Promotion: Reached last square (Y==0 or Y==7)
            elif to_y % 7 == 0:
                logger.debug("Special move: Promotion")
                move.promotion = chess.QUEEN

        elif piece.piece_type == chess.KING:
            dx = to_x - from_x
            if abs(dx) > 1:  # Castling: King moved 2+ squares in X axis
                logger.debug(
                    f"Special move: {'King' if dx>0 else 'Queen'}side castling"
                )
                rook_init = (7 if dx > 0 else 0), to_y
                rook_after = (to_x - dx // 2), to_y
                self.lifted[self.turn].add(rook_after)
                await self.on_misplace(*rook_init)
                await self.on_missing(*rook_after)
                self.pending = True

        # Normally switch_turn() is called after moving,
        # but moves that manipulate 2 pieces set 'pending' state instead
        self.board.push(move)
        if self.pending:
            logger.debug("Move requires 2+ actions. 'pending' state set")
        else:
            await self.switch_turn()

    @event
    async def on_capture(self, x: int, y: int):
        """
        When selected piece is placed on MISSING square

        Remove victim piece and the rest is same as on_move
        """
        assert self.select != None and self.turn != None
        to_x, to_y = x, y
        from_x, from_y = self.select
        move = chess.Move(chess.square(from_x, from_y), chess.square(to_x, to_y))
        killer = self.board.piece_at(chess.square(from_x, from_y))
        victim = self.board.piece_at(chess.square(to_x, to_y))
        logger.debug(f"Capture: {move.uci()} ({killer} -> {victim})")

        self.errors -= 1  # Missing -> Killed
        self.warnLED.off(to_x, to_y)
        self.states[to_y][to_x] = GROUND

        await self.on_unselect()
        self.lifted[self.turn].remove((from_x, from_y))
        self.states[from_y][from_x] = EMPTY

        self.board.push(move)
        await self.switch_turn()

    @event
    async def on_lift(self, x: int, y: int):
        """
        When object is no longer detected by the sensor

        Raise GameOverError if the event ended the game
        """
        state = self.states[y][x]
        assert state & State.DETECTED
        if state == GROUND:
            color = self.color_at(x, y)
            self.lifted[color].add((x, y))
            if self.turn == color and len(self.lifted[color]) == 1:
                await self.on_select(x, y)
            else:
                await self.on_missing(x, y)
        elif state == MISPLACE:
            await self.on_cleanup(x, y)

    @event
    async def on_place(self, x: int, y: int):
        """
        When new object is detected by the sensor

        Raise GameOverError if the event ended the game
        """
        state = self.states[y][x]
        assert not (state & State.DETECTED)
        if state == EMPTY:
            if (x, y) in self.candidates:
                await self.on_move(x, y)
            else:
                await self.on_misplace(x, y)
        else:  # can know the owner of the piece
            color = self.color_at(x, y)
            self.lifted[color].remove((x, y))
            if state == MISSING:
                if (x, y) in self.candidates:
                    await self.on_capture(x, y)
                else:
                    await self.on_retrieve(x, y)
            elif state == SELECT:
                await self.on_unselect()

    async def toggle(self, x: int, y: int):
        """
        Invoke on_place or on_lift at (x, y)
        based on State.DETECTED of that tile
        """
        if self.states[y][x] & State.DETECTED:
            await self.on_lift(x, y)
        else:
            await self.on_place(x, y)

    def game_info(self) -> str:
        """
        Brief information of what's going on.
        ex) T:Black | P:False | E:3 | L(B):1, L(W):2
        """
        if self.turn != None:
            T = ("Black", "White")[self.turn]
        else:
            T = "None "
        P = str(self.pending)
        E = str(self.errors)
        LB, LW = len(self.lifted[0]), len(self.lifted[1])
        return f"T:{T} | P:{P} | E:{E} | L(B):{LB}, L(W):{LW}"

    def led_info(self) -> str:
        """
        String representation of LED matricies.
        good: Blue / warn: Red / both: Purple
        """
        char = ".BRP"
        data = self.goodLED.data + self.warnLED.data * 2

        ret = []
        for row in reversed(data):  # because A1 is at bottom left
            ret.append(" ".join(char[col] for col in row))
        return "\n".join(ret)

    def state_info(self) -> str:
        """
        String representation of tile states.
        EMPTY, GROUND, MISSING, MISPLACE, SELECT states
        are shown as ['.', 'G', '?', '!', 'S'], respectively
        """
        char = ".G?!S"

        ret = []
        for row in reversed(self.states):  # because A1 is at bottom left
            ret.append(" ".join(char[col] for col in row))
        return "\n".join(ret)

    def info(self, scanner: hw.Scanner) -> str:
        ...  # copy main.py's game_status

    async def play(self, scanner: hw.Scanner):
        ...  # TODO

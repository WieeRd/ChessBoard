import chess
import chess.engine
import asyncio
import logging
import functools
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


# fmt: off
class State(IntFlag):
    NONE   = 0
    GROUND = 1
    ERROR  = 2
    SELECT = 4


EMPTY    = State.NONE     | State.NONE   # 0
GROUND   = State.GROUND   | State.NONE   # 1
MISSING  = State.NONE     | State.ERROR  # 2
MISPLACE = State.GROUND   | State.ERROR  # 3
SELECT   = State.SELECT                  # 4
# fmt: on


# TODO: rewrite docstring
class ChessBoard:
    """
    Controls LED chessboard based on occured events.
    Only on_place(), on_lift(), toggle() should be called
    manually unless you fully understand what you're doing
    I don't understand what I'm doing to be honest
    """

    def __init__(
        self,
        goodLED: hw.LEDmatrix,
        warnLED: hw.LEDmatrix,
        turnLED: Tuple[gp.LED, gp.LED],
        scanner: hw.Scanner,
        engine: chess.engine.UciProtocol = None,
        timeout: float = 1.0,
    ):
        self.board = chess.Board()
        self.states = [
            [GROUND] * 8,
            [GROUND] * 8,
            [EMPTY] * 8,
            [EMPTY] * 8,
            [EMPTY] * 8,
            [EMPTY] * 8,
            [GROUND] * 8,
            [GROUND] * 8,
        ]

        self.goodLED = goodLED
        self.warnLED = warnLED
        self.turnLED = turnLED
        self.scanner = scanner

        self.engine = engine
        self.timeout = timeout

        Pos = Tuple[int, int]

        # turn is occasionally set to None to block on_select()
        self.turn: Optional[chess.Color] = None
        # position of lifted(not detected) pieces
        self.lifted: Tuple[Set[Pos], Set[Pos]] = (set(), set())
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
        # updated each time switch_turn() is called
        self.outcome: Optional[chess.Outcome] = None

    def _led_str(self) -> List[str]:
        """
        String representation of LED matricies.
        good: Blue / warn: Red / both: Purple
        """
        char = ".BRP"

        good = self.goodLED.data
        warn = self.warnLED.data

        ret = []
        for y in range(7, -1, -1): # because A1 is at bottom left
            row = []
            for x in range(8):
                data = good[y][x] + warn[y][x] * 2
                row.append(char[data])
            ret.append(" ".join(row))

        return ret

    def _state_str(self) -> List[str]:
        """
        String representation of tile states.
        EMPTY, GROUND, MISSING, MISPLACE, SELECT states
        are shown as ['.', 'G', '?', '!', 'S'], respectively
        """
        char = ".G?!S"

        ret = []
        for row in reversed(self.states):  # because A1 is at bottom left
            ret.append(" ".join(char[col] for col in row))
        return ret

    def _info_str(self) -> str:
        """
        Brief information of what's going on.
        e.g. T:Black | P:False | E:3 | L(B):1, L(W):2
        """
        if self.turn != None:
            T = ("Black", "White")[self.turn]
        else:
            T = "None "
        P = str(self.pending)
        E = str(self.errors)
        LB, LW = len(self.lifted[0]), len(self.lifted[1])
        return f"T:{T} | P:{P} | E:{E} | L(B):{LB}, L(W):{LW}"

    def __str__(self) -> str:
        """
        Full information of what's going on.
        (board, led, state, scan, variables)
        """
        game = str(self.board).split(sep="\n")
        led = self._led_str()
        state = self._state_str()
        scan = self.scanner.status("@", ".").split(sep="\n")
        info = self._info_str()

        ret = []
        for i in range(8):
            ret.append(f"{8 - i} {game[i]}  {led[i]}  {state[i]}  {scan[7-i]}")
        ret.append(f"  a b c d e f g h  {info}")
        return "\n".join(ret)

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
        1. Run UCI engine & get the result
        2. Highlight from_square of the result
        3. Limit legal_moves to single move (engine result)
        """
        logger.debug("Running uci engine")
        assert self.engine != None

        limit = chess.engine.Limit(time=self.timeout)
        result = await self.engine.play(self.board, limit=limit)

        if not result.move:
            # engine gave up for some reason?
            logger.debug(f"Engine result: {repr(result)}")
            raise RuntimeError("Engine result doesn't contain any move")

        square = result.move.from_square
        x, y = square % 8, square // 8
        self.legal_moves = [result.move]
        self.AIselect = (x, y)
        self.goodLED.on(x, y)

        self.turn = chess.BLACK  # unblock selection
        logger.debug(f"Engine returned {result.move.uci()}")

    @event
    def switch_turn(self):
        """
        1. Update game outcome
        2. Update turnLED state
        3. If engine is given & AI's turn, run_engine is called
        """
        self.outcome = self.board.outcome()
        if self.outcome != None:
            self.legal_moves = []
            return

        self.turn = not self.turn
        self.turnLED[self.turn].on()
        self.turnLED[not self.turn].off()
        self.legal_moves = list(self.board.legal_moves)

        if self.engine != None:
            if self.turn == chess.BLACK:  # AI's turn
                self.turn = None  # Block selection untill engine returns
                asyncio.create_task(self.run_engine())
            elif self.turn == chess.WHITE and self.AIselect:
                self.goodLED.off(*self.AIselect)
                self.AIselect = None

    @event
    def on_select(self, x: int, y: int):
        """
        When piece of current turn's color is picked up
        and it's the only piece of that color that is picked up

        Highlight possible moves with goodLED
        """
        if self.AIselect and (x, y) != self.AIselect:
            logger.debug("(x, y) != AIselect. Regarded as missing.")
            self.on_missing(x, y)
            return

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
    def on_unselect(self):
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
    def on_missing(self, x: int, y: int):
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
            self.on_unselect()
            self.on_missing(x, y)

    @event
    def on_retrieve(self, x: int, y: int):
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
            self.on_select(*new_select)

        if self.pending and self.errors == 0:
            logger.debug("All errors resolved. No longer pending.")
            self.pending = False
            self.switch_turn()

    @event
    def on_misplace(self, x: int, y: int):
        """
        When unexpected detection occurs
        (Usually by attempting illegal move)

        Turn on warnLED at detected square
        """
        self.states[y][x] = MISPLACE
        self.errors += 1
        self.warnLED.on(x, y)

    @event
    def on_cleanup(self, x: int, y: int):
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
            self.switch_turn()

    @event
    def on_move(self, x: int, y: int):
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
        self.on_unselect()

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
                    self.on_misplace(to_x, from_y)
                    self.pending = True

                elif self.states[from_y][to_x] == MISSING:
                    # already removed, cancel missing state
                    self.on_place(to_x, from_y)
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
                self.on_misplace(*rook_init)
                self.on_missing(*rook_after)
                self.pending = True

        # Normally switch_turn() is called after moving,
        # but moves that manipulate 2 pieces set 'pending' state instead
        self.board.push(move)
        if self.pending:
            logger.debug("Move requires 2+ actions. 'pending' state set")
        else:
            self.switch_turn()

    @event
    def on_capture(self, x: int, y: int):
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

        self.on_unselect()
        self.lifted[self.turn].remove((from_x, from_y))
        self.states[from_y][from_x] = EMPTY

        self.board.push(move)
        self.switch_turn()

    @event
    def on_lift(self, x: int, y: int):
        """
        When object is no longer detected by the sensor

        Raise GameOverError if the event ended the game
        """
        state = self.states[y][x]
        assert state & State.GROUND
        if state == GROUND:
            color = self.color_at(x, y)
            self.lifted[color].add((x, y))
            if self.turn == color and len(self.lifted[color]) == 1:
                self.on_select(x, y)
            else:
                self.on_missing(x, y)
        elif state == MISPLACE:
            self.on_cleanup(x, y)

    @event
    def on_place(self, x: int, y: int):
        """
        When new object is detected by the sensor

        Raise GameOverError if the event ended the game
        """
        state = self.states[y][x]
        assert not (state & State.GROUND)
        if state == EMPTY:
            if (x, y) in self.candidates:
                self.on_move(x, y)
            else:
                self.on_misplace(x, y)
        else:  # can know the owner of the piece
            color = self.color_at(x, y)
            self.lifted[color].remove((x, y))
            if state == MISSING:
                if (x, y) in self.candidates:
                    self.on_capture(x, y)
                else:
                    self.on_retrieve(x, y)
            elif state == SELECT:
                self.on_unselect()

    def toggle(self, x: int, y: int):
        """
        Invoke on_place or on_lift at (x, y)
        based on State.DETECTED of that tile
        """
        if self.states[y][x] & State.GROUND:
            self.on_lift(x, y)
        else:
            self.on_place(x, y)

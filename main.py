#!/usr/bin/env python3
import chess
import chess.engine
import asyncio
import logging
import numpy as np
import gpiozero as gp

import hardware as hw
import software as sw

from itertools import product
from aioconsole import ainput
from typing import Callable, Any, List, Optional

logging.getLogger("chess.engine").setLevel(logging.INFO)
logging.basicConfig(
    level=logging.DEBUG,
    format="[%(levelname)s] (%(name)s) %(message)s"
)

StateChar = {
    sw.EMPTY: ".",
    sw.MISSING: "!",
    sw.GROUND: "+",
    sw.MISPLACE: "?",
    sw.SELECT: "S",
}


def gen_status_str(data: np.ndarray, what: Callable[[Any], str]) -> str:
    ret = []
    for row in data:
        ret.append(' '.join(what(col) for col in row))
    return '\n'.join(ret)

def game_status(game: sw.ChessBoard, scan_data: np.ndarray) -> str:
    color = ['.', 'B', 'R', 'P']
    ledData = np.empty((8,8), dtype=np.int8) # TODO: inefficient
    for y, x in product(range(8), range(8)):
        ledData[y][x] = game.goodLED.data[y][x] + game.warnLED.data[y][x]*2

    tile = gen_status_str(game.states, lambda x: StateChar[x]).split(sep='\n')
    board = str(game.board).split(sep='\n')
    scan = gen_status_str(scan_data, lambda x: '@' if x else '.').split(sep='\n')
    led = gen_status_str(ledData, lambda x: color[x]).split(sep='\n')

    ret = ""
    for i in range(8):
        ret += str(8-i) + ' '
        ret += '  '.join((board[i], led[7-i], scan[7-i], tile[7-i]))
        ret += '\n'
    team = {0: 'Black', 1: 'White', None:'Preparing'}
    ret += "  a b c d e f g h  "
    ret += "T:{} | P:{} | E:{} | aW:{}, aB:{}".format(
        team[game.turn], game.pending, game.errors, len(game.lifted[1]), len(game.lifted[0])
    )

    return ret

async def test():
    red = hw.LEDmatrix()
    blue = hw.LEDmatrix()
    turn = ( hw.DummyLED(), hw.DummyLED() )
    _, engine = await chess.engine.popen_uci("./stockfish")
    # engine = None

    game = sw.ChessBoard(blue, red, turn, engine, 4)
    game.states = np.array([
        [sw.GROUND]*8,
        [sw.GROUND]*8,
        [sw.EMPTY]*8,
        [sw.EMPTY]*8,
        [sw.EMPTY]*8,
        [sw.EMPTY]*8,
        [sw.GROUND]*8,
        [sw.GROUND]*8,
    ])
    scan = np.array([
        [True]*8,
        [True]*8,
        [False]*8,
        [False]*8,
        [False]*8,
        [False]*8,
        [True]*8,
        [True]*8,
    ])

    log: List[str] = []
    while True:
        print(game_status(game, scan))
        try:
            cmd = await ainput(";) ")
            square = chess.parse_square(cmd)
            y, x = divmod(square, 8)
            scan[y][x] = not scan[y][x]
            await game.toggle(x, y)
            log.append(chess.square_name(square))
        except ValueError as e:
            print(f"{type(e).__name__}: {e}")
            print("Invalid command")
            continue
        except (KeyboardInterrupt, EOFError) as e:
            break

    if engine:
        await engine.quit()
    print('\n'.join(log))

# async def main():
#     if not hw.LUMA:
#         print("Library 'luma' is missing")
#         exit(-1)

#     serial = hw.spi(spi=0, device=0, loop=hw.noop())
#     matrix_chain = hw.MatrixChain(serial, chained=2)

#     goodLED = hw.SingleMatrix(matrix_chain, offset=0)
#     warnLED = hw.SingleMatrix(matrix_chain, offset=1)
#     turnLED = ( hw.LED(10), hw.LED(11) )
#     # _, engine = await chess.engine.popen_uci("./stockfish")

#     detector = hw.Electrode()
#     game = sw.ChessBoard(goodLED, warnLED, turnLED)

#     winner: Optional[chess.Color]
#     prev = np.full((8,8), False)
#     while True:
#         curr = detector.scan()
#         for y, x in product(range(8), range(8)):
#             if prev[y][x]!=curr[y][x]:
#                 prev[y][x] = curr[y][x]
#                 try: await game.toggle(x, y)
#                 except sw.GameOverError as e:
#                     winner = e.reason.winner
#                     break

#     # TODO: Ending event

if __name__=="__main__":
    asyncio.set_event_loop_policy(chess.engine.EventLoopPolicy())
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test())

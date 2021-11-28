#!/usr/bin/env python3
import chess
import chess.engine
import asyncio
import logging
import numpy as np
import gpiozero as gp

import hardware as hw
import software as sw

from aioconsole import ainput

# TODO: Dummy Electrode
# TODO: Seperate test.py

logging.getLogger("chess.engine").setLevel(logging.INFO)
logging.basicConfig(
    level=logging.DEBUG, format="[%(levelname)s] (%(name)s) %(message)s"
)


def game_status(game: sw.ChessBoard, scanner: hw.MatrixBase) -> str:
    board = str(game.board).split(sep="\n")
    led = game.led_info().split(sep="\n")
    scan = scanner.status("@", ".").split(sep="\n")
    tile = game.state_info().split(sep="\n")
    info = game.game_info()

    ret = []
    for i in range(8):
        ret.append(f"{str(8-i)} {board[i]}  {led[i]}  {tile[i]}  {scan[7-i]}")
    ret.append(f"  a b c d e f g h  {info}")
    return "\n".join(ret)


async def test():
    red = hw.LEDmatrix()
    blue = hw.LEDmatrix()
    turn = (hw.DummyLED(), hw.DummyLED())
    _, engine = await chess.engine.popen_uci("./stockfish")
    # engine = None

    game = sw.ChessBoard(blue, red, turn, engine, 4)
    game.states = np.array(
        [
            [sw.GROUND] * 8,
            [sw.GROUND] * 8,
            [sw.EMPTY] * 8,
            [sw.EMPTY] * 8,
            [sw.EMPTY] * 8,
            [sw.EMPTY] * 8,
            [sw.GROUND] * 8,
            [sw.GROUND] * 8,
        ]
    )
    scanner = hw.MatrixBase()
    scanner.data = np.array(
        [
            [True] * 8,
            [True] * 8,
            [False] * 8,
            [False] * 8,
            [False] * 8,
            [False] * 8,
            [True] * 8,
            [True] * 8,
        ]
    )

    log = []
    while True:
        print(game_status(game, scanner))
        print()
        try:
            cmd = await ainput(";) ")
            square = chess.parse_square(cmd)
            y, x = divmod(square, 8)
            scanner.data[y][x] = not scanner.data[y][x]
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
    print("\n".join(log))


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

if __name__ == "__main__":
    asyncio.set_event_loop_policy(chess.engine.EventLoopPolicy())
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test())

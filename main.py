#!/usr/bin/env python3
import chess
import chess.engine
import asyncio
import aioconsole
import numpy as np
import itertools as it

import hardware as hw
import software as sw

from typing import Callable, Any, List

def gen_status_str(data: np.ndarray, what: Callable[[Any], str]) -> str:
    ret = []
    for row in data:
        ret.append(' '.join(what(col) for col in row))
    return '\n'.join(ret)

def game_status(game: sw.ChessBoard, scan_data: np.ndarray) -> str:
    ledData = np.empty((8,8), dtype=np.int8) # TODO: inefficient
    color = ['.', 'B', 'R', 'P']
    for y, x in it.product(range(8), range(8)):
        ledData[y][x] = game.goodLED.data[y][x] + game.warnLED.data[y][x]

    board = str(game.board).split(sep='\n')
    scan = gen_status_str(scan_data, lambda x: '@' if x else '.').split(sep='\n')
    led = gen_status_str(ledData, lambda x: color[x]).split(sep='\n')
    tile = gen_status_str(game.tiles, lambda x: x.value).split(sep='\n')

    ret = ""
    for i in range(8):
        ret += str(8-i) + ' '
        ret += '  '.join((board[i], led[7-i], scan[7-i], tile[7-i]))
        ret += '\n'
    team = {0: 'Black', 1: 'White', None:'Preparing'}
    ret += "  a b c d e f g h  "
    ret += "T:{} | P:{} | E:{} | aW:{}, aB:{}".format(
        team[game.turn], game.pending, game.errors, len(game.in_air[1]), len(game.in_air[0])
    )

    return ret

async def test():
    red = hw.DummyMatrix()
    blue = hw.DummyMatrix()
    turn = ( hw.dummyLED(), hw.dummyLED() )
    _, engine = await chess.engine.popen_uci("./stockfish")

    game = sw.ChessBoard(blue, red, turn, engine, 4)
    game.tiles = np.array([
        [sw.Tile.GROUND]*8,
        [sw.Tile.GROUND]*8,
        [sw.Tile.EMPTY]*8,
        [sw.Tile.EMPTY]*8,
        [sw.Tile.EMPTY]*8,
        [sw.Tile.EMPTY]*8,
        [sw.Tile.GROUND]*8,
        [sw.Tile.GROUND]*8,
    ])

    log: List[str] = []
    data = np.array([
        [True]*8,
        [True]*8,
        [False]*8,
        [False]*8,
        [False]*8,
        [False]*8,
        [True]*8,
        [True]*8,
    ])

    while True:
        print(game_status(game, data))
        try:
            cmd = await aioconsole.ainput(";) ")
            square = chess.parse_square(cmd)
            y, x = divmod(square, 8)
            data[y][x] = not data[y][x]
            if data[y][x]:
                await game.on_place(x, y)
            else:
                await game.on_lift(x, y)
            log.append(chess.square_name(square))
        except ValueError as e:
            print(f"{type(e).__name__}: {e}")
            print("Invalid command")
            continue
        except (KeyboardInterrupt, EOFError) as e:
            break
    return log

if __name__=="__main__":
    asyncio.set_event_loop_policy(chess.engine.EventLoopPolicy())
    loop = asyncio.get_event_loop()
    log = loop.run_until_complete(test())
    print('\n'.join(log))

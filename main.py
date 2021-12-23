#!/usr/bin/env python3
import chess
import chess.engine
import asyncio
import logging

import gpiozero as gp
import hardware as hw
import software as sw


logging.getLogger("chess.engine").setLevel(logging.INFO)
logging.basicConfig(
    level=logging.DEBUG, format="[%(levelname)s] (%(name)s) %(message)s"
)


async def main():
    if not hw.LUMA:
        logging.error("Library 'luma' is missing")
        raise ImportError("Library 'luma' is missing")

    chain = hw.MatrixChain(port=0, device=0, cascaded=2)
    red, blue = chain[0], chain[1]
    turn = gp.LED(1), gp.LED(2)
    scanner = hw.Electrode([3, 4, 5], [6, 7, 8])
    _, engine = await chess.engine.popen_uci("./stockfish")

    game = sw.ChessBoard(blue, red, turn, scanner, engine, 1)
    print(game, end="\n\n")

    while game.outcome == None:
        for x, y in await scanner.scan():
            game.toggle(x, y)
            print(game, end="\n\n")

    await engine.quit()


asyncio.set_event_loop_policy(chess.engine.EventLoopPolicy())
loop = asyncio.get_event_loop()
loop.run_until_complete(main())

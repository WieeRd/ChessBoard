import chess
import chess.engine
import asyncio
import logging

import hardware as hw
import software as sw

logging.getLogger("chess.engine").setLevel(logging.INFO)
logging.basicConfig(
    level=logging.DEBUG, format="[%(levelname)s] (%(name)s) %(message)s"
)


# TODO: only on_place & on_lift have to be async
# TODO: rewrite docstring

async def test():
    red = hw.LEDmatrix()
    blue = hw.LEDmatrix()
    turn = hw.VirtualLED(), hw.VirtualLED()
    scanner = hw.ConsoleInput(";) ")
    _, engine = await chess.engine.popen_uci("./stockfish")

    game = sw.ChessBoard(blue, red, turn, scanner, engine)

    while True:
        for x, y in await scanner.scan():
            game.toggle(x, y)
            print(game, end="\n\n")


asyncio.set_event_loop_policy(chess.engine.EventLoopPolicy())
loop = asyncio.get_event_loop()
loop.run_until_complete(test())

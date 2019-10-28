import asyncio
import gui
import time
import datetime
import argparse
import os
import aiofiles
from dotenv import load_dotenv

load_dotenv()


def get_parser_args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        '--host',
        help='Specify hostname. Default is minechat.dvmn.org',
        default=os.getenv('HOST')
    )
    parser.add_argument(
        '--port',
        help='Specify remote port to read data. Default is 5000',
        default=os.getenv('PORT')
    )
    parser.add_argument(
        '--history',
        help='Specify file to save history. Default is history.txt',
        default=os.getenv('HISTORY_FILE')
    )
    parser.add_argument(
        '--debug',
        help='Enable debug',
        default=False,
        )
    return parser.parse_args()


#async def generate_msgs(queue):
#    while True:
#        queue.put_nowait(f'Ping {time.time()}')
#        await asyncio.sleep(1)


async def save_messages(history, queue):
    now = datetime.datetime.now()
    async with aiofiles.open(history, 'a') as file:
        await file.write(f'[{now.strftime("%d.%m.%y %H:%M")}] {queue}')


async def load_history_to_chat(history, queue):
    async with aiofiles.open(history, 'r') as file:
        queue.put_nowait(await file.read())


async def read_msgs(host, port, history, queue):
    while True:
        try:
            reader, writer = await asyncio.open_connection(host, port)
            data = await asyncio.wait_for(reader.readline(), timeout=5)
            queue.put_nowait(data.decode())
            await save_messages(history, data.decode())
        finally:
            writer.close()


async def main():
    args = get_parser_args()
    print(args.host, args.port)
    messages_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_updates_queue = asyncio.Queue()

    await asyncio.gather(
        gui.draw(messages_queue, sending_queue, status_updates_queue),
        load_history_to_chat(args.history, messages_queue),
        read_msgs(args.host, args.port, args.history, messages_queue)
    )


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

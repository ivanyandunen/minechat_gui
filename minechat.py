import asyncio
import gui
# import time
import datetime
import argparse
import os
import logging
import aiofiles
import json
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
        '--iport',
        help='Specify remote port to read data. Default is 5000',
        default=os.getenv('READER_PORT')
    )
    parser.add_argument(
        '--oport',
        help='Specify remote port to read data. Default is 5050',
        default=os.getenv('WRITER_PORT')
    )
    parser.add_argument(
        '--history',
        help='Specify file to save history. Default is history.txt',
        default=os.getenv('HISTORY_FILE')
    )
    parser.add_argument(
        '--token',
        help='Token for registered user',
        default=os.getenv('TOKEN')
    )
    parser.add_argument(
        '--debug',
        help='Enable debug',
        default=False,
        action='store_true'
        )
    return parser.parse_args()


# async def generate_msgs(queue):
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


async def authorize(reader, writer, token):
    writer.write(f'{token}\n'.encode())
    await writer.drain()
    data = await reader.readline()
    account_info = json.loads(data.decode())
    logging.debug(f'Выполнена авторизация. Пользователь {account_info["nickname"]}.')


async def send_msgs(writer, queue):
    message = await queue.get()
    logging.debug(f'Пользователь написал: {message}')
    message = message.replace('\n', ' ')
    writer.write(f'{message}\n\n'.encode())
    await writer.drain()


async def open_writer(host, port, token, queue):
    try:
        reader, writer = await asyncio.open_connection(host, port)
        if await reader.readline():
            if token:
                await authorize(reader, writer, token)
            await send_msgs(writer, queue)
    finally:
        writer.close()


async def main():
    args = get_parser_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    messages_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_updates_queue = asyncio.Queue()

    await asyncio.gather(
        gui.draw(messages_queue, sending_queue, status_updates_queue),
        load_history_to_chat(args.history, messages_queue),
        read_msgs(args.host, args.iport, args.history, messages_queue),
        open_writer(args.host, args.oport, args.token, sending_queue)
    )


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

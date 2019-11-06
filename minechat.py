import asyncio
import gui
import datetime
import argparse
import os
import logging
import aiofiles
import json
import socket
from dotenv import load_dotenv
from tkinter import messagebox


load_dotenv()


class InvalidToken(Exception):
    pass


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


async def save_messages(history, queue):
    now = datetime.datetime.now()
    async with aiofiles.open(history, 'a') as file:
        await file.write(f'[{now.strftime("%d.%m.%y %H:%M")}] {queue}')


async def load_history_to_chat(history, queue):
    async with aiofiles.open(history, 'r') as file:
        queue.put_nowait(await file.read())


async def count_reconnection_delay(connection_attempts):
    if connection_attempts < 5:
        return 3
    elif connection_attempts >= 5 and connection_attempts < 10:
        return 10
    elif connection_attempts >= 10:
        return 20


async def wait_before_reconnection(delay, history, queue):
    if delay:
        queue.put_nowait(f'No connection. Trying to connect in {delay} secs...\n')
        save_messages(
            history,
            f'No connection. Trying to connect in {delay} secs...\n'
            )
        await asyncio.sleep(delay)


async def read_msgs(host, port, history, messages_queue, status_updates_queue):
    connection_attempts = 0

    while True:
        try:
            reader, writer = await asyncio.open_connection(host, port)
            status_updates_queue.put_nowait(
                gui.ReadConnectionStateChanged.ESTABLISHED
                )
            data = await asyncio.wait_for(reader.readline(), timeout=5)
            messages_queue.put_nowait(data.decode())
            await save_messages(history, data.decode())
        except (asyncio.TimeoutError, ConnectionRefusedError, socket.gaierror):
            logging.debug('No connection')
            status_updates_queue.put_nowait(
                gui.ReadConnectionStateChanged.INITIATED
                )
            delay = await count_reconnection_delay(connection_attempts)
            await wait_before_reconnection(delay, history, messages_queue)
            connection_attempts += 1
            continue
        finally:
            writer.close()
            gui.ReadConnectionStateChanged.CLOSED


async def authorize(reader, writer, token):
    writer.write(f'{token}\n'.encode())
    await writer.drain()
    data = await reader.readline()
    if data.decode() == 'null\n':
        logging.debug('Token is invalid')
        raise InvalidToken()
    account_info = json.loads(data.decode())
    logging.debug(f'Выполнена авторизация. Пользователь {account_info["nickname"]}.')
    return account_info


async def send_msgs(writer, queue):
    message = await queue.get()
    logging.debug(f'Пользователь написал: {message}')
    message = message.replace('\n', ' ')
    writer.write(f'{message}\n\n'.encode())
    await writer.drain()


async def open_writer(host, port, token, sending_queue, status_updates_queue):
    while True:
        try:
            reader, writer = await asyncio.open_connection(host, port)
            status_updates_queue.put_nowait(
                gui.SendingConnectionStateChanged.ESTABLISHED
                )
            if await reader.readline():
                if token:
                    account_info = await authorize(reader, writer, token)
                    status_updates_queue.put_nowait(
                        gui.NicknameReceived(account_info['nickname'])
                        )
                await send_msgs(writer, sending_queue)
        except (asyncio.TimeoutError, ConnectionRefusedError, socket.gaierror):
            status_updates_queue.put_nowait(
                gui.SendingConnectionStateChanged.INITIATED
                )
            continue
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
        read_msgs(
            args.host,
            args.iport,
            args.history,
            messages_queue,
            status_updates_queue
            ),
        open_writer(
            args.host,
            args.oport,
            args.token,
            sending_queue,
            status_updates_queue
            )
    )


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except (KeyboardInterrupt, gui.TkAppClosed):
        logging.debug('\n Closed by user')
    except InvalidToken:
        messagebox.showerror('Invalid Token', 'Authorization failed. Check your token')

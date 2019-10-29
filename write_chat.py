import asyncio
import json
import logging
import argparse
import os
from dotenv import load_dotenv

load_dotenv()


def get_writer_args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        '--host',
        help='Specify hostname. Default is minechat.dvmn.org',
        default=os.getenv('HOST')
    )
    parser.add_argument(
        '--port',
        help='Specify remote port to send data. Default is 5050',
        default=os.getenv('WRITER_PORT')
    )
    parser.add_argument(
        '--message',
        help='Message to chat',
        type=str
    )
    parser.add_argument(
        '--token',
        help='Token for registered user',
        default=os.getenv('TOKEN'),
        type=str
    )
    parser.add_argument(
        '--debug',
        help='Enable debug',
        default=False,
        )
    return parser.parse_args()


async def autorize(writer, reader, token):
    writer.write(f'{token}\n'.encode())
    await writer.drain()
    data = await reader.readline()
    if data.decode() == 'null\n':
        logging.debug('Token is invalid')
        await register(writer, reader)
    else:
        account_info = json.loads(data.decode())
        logging.debug(account_info)
    return account_info


async def register(writer, reader):
    nickname = input('Enter preffered nickname: ').replace('\n', ' ')
    writer.write(f'{nickname}\n'.encode())
    await writer.drain()
    data = await reader.readline()
    logging.debug(data.decode())
    return json.loads(data.decode())


async def submit_message(writer, nickname, message):
    message = message.replace('\n', ' ')
    writer.write(f'{message}\n\n'.encode())
    await writer.drain()


async def main():
    args = get_writer_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    try:
        reader, writer = await asyncio.open_connection(args.host, args.port)
        if await reader.readline():
            if args.token:
                account_info = await autorize(writer, reader, args.token)
            else:
                writer.write('\n'.encode())
                await reader.readline()
                account_info = await register(writer, reader)
            await submit_message(
                writer,
                account_info['nickname'],
                args.message
                )
    finally:
        writer.close()


if __name__ == '__main__':
    asyncio.run(main())

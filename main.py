import discord
from discord.ext import commands
import requests
import asyncio
import threading
import json
import time
import os
from flask import Flask, Response
from typing import Any



CHANNEL_ID: int = int(os.environ.get("CHANNEL_ID", 0))
TOKEN: str = os.environ.get("DISCORD_TOKEN", "")
SERVER_URL: str = os.environ.get("SERVER_URL", "")
LISTENER_INTERVAL: float = float(os.environ.get("LISTENER_INTERVAL", 15))

warning_queue = []

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


async def send_warning() -> None:
    warning_msg = warning_queue.pop(0)
    channel = bot.get_channel(CHANNEL_ID)

    if not hasattr(channel, "send"):
        return
    
    await channel.send(warning_msg) # type: ignore


async def send_warning_loop() -> None:
    while True:
        if len(warning_queue) > 0:
            await send_warning()

        await asyncio.sleep(1)


@bot.event
async def on_ready() -> None:
    print(f"{bot.user} is online!")
    asyncio.create_task(send_warning_loop())



def attack_listener() -> None:
    index = 10 ** 10
    while True:
        time.sleep(LISTENER_INTERVAL)
        try:
            response = requests.get(
                url=f"{SERVER_URL}/search",
                params={"index": index, "format": "%xt%gam"},
                timeout=10
            )
        except Exception as e:
            print(e)
            continue

        try:
            index = response.json()[1]
        except Exception as e:
            print(e)
            continue

        for message in response.json()[0]:
            try:
                info_list = _decode_message(message)
            except IndexError:
                continue
            except Exception as e:
                print(e)
                continue
            
            if info_list is None:
                continue
            
            for info in info_list:
                warning_msg = _format_warning(info)
                warning_queue.append(warning_msg)


def _decode_message(message: str) -> None | list[tuple[Any, ...]]:
    start = message.find("{")
    if start == -1:
        return
    
    data = json.loads(message[start:-1])

    info_list = []
    attack_count = len(data["M"])
    for i in range(attack_count):
        try:
            info = _unpack_data(data["M"][i])
        except:
            continue

        if info is not None:
            info_list.append(info)

    return info_list


def _unpack_data(data: dict) -> None | tuple[Any, ...]:
    if data["M"]["T"] != 0:
        return
    
    if "GS" not in data:
        return
    
    remaining_time = data["M"]["TT"] - data["M"]["PT"]

    target_x = data["M"]["TA"][1]
    target_y = data["M"]["TA"][2]
    target_name = data["M"]["TA"][10]

    attacker_x = data["M"]["SA"][1]
    attacker_y = data["M"]["SA"][2]
    attacker_name = data["M"]["SA"][10]

    info = (
        remaining_time,
        target_x,
        target_y,
        attacker_x,
        attacker_y,
        target_name,
        attacker_name
    )
    return info


def _format_warning(info: tuple[Any, ...]) -> str:
    message = " ".join([
        "@everyone",
        f"incoming attack in approx.",
        _seconds2compound(info[0]),
        f"at \"{info[5]}\" ({info[1]}:{info[2]})",
        f"from \"{info[6]}\" ({info[3]}:{info[4]})"
    ])
    return message


def _seconds2compound(seconds: float) -> str:
    h = seconds // 3600
    m = seconds // 60 % 60
    s = seconds // 1 % 60
    if h != 0:
        return f"{h}h {m}m {s}s"
    elif m != 0:
        return f"{m}m {s}s"
    else:
        return f"{s}s"
    

def start_attack_listener() -> None:
    listener = threading.Thread(target=attack_listener, daemon=True)
    listener.start()


def start_flask_server() -> None:
    port = os.environ.get("PORT", 10000)
    app = Flask(__name__)
    
    app.add_url_rule(
        "/", 
        endpoint="respond", 
        view_func=lambda: Response(status=200)
    )

    flask_thread = threading.Thread(
        target=app.run,
        kwargs={"host": "0.0.0.0", "port": port}
    )
    flask_thread.start()


if __name__ == "__main__":
    start_flask_server()
    start_attack_listener()
    bot.run(token=TOKEN)
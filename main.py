# MIT license; Copyright (c) 2025 Walksky Su (walksky@gmail.com)

import asyncio
from coze_chat import chat_client
from config import WIFI_SSID, WIFI_PASSWORD


def do_connect():
    import network
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        print('connecting to network...')
        sta_if.active(True)
        sta_if.connect(WIFI_SSID, WIFI_PASSWORD)
        while not sta_if.isconnected():
            pass
    print('network config:', sta_if.ifconfig())


do_connect()
print("Init Chat !!")

try:
    asyncio.run(chat_client())
except Exception as e:
    print(f"发生错误: {e}")

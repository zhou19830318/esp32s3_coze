# MIT license; Copyright (c) 2025 Walksky Su (walksky@gmail.com)

WIFI_SSID = "WIFI_SSID"               # 替换为你的 Wi-Fi 名称
WIFI_PASSWORD = "WIFI_PASS"         # 替换为你的 Wi-Fi 密码

# 音频配置参数
CHUNK = 1024      # 数据块大小
RATE = 16000      # 采样率
CHANNELS = 1      # 通道数
BIT_DEPTH = 16    # 位深度

# MIC I2S配置
MIC_SCK_PIN = 5       # I2S SCK引脚
MIC_WS_PIN = 4       # I2S WS引脚
MIC_SD_PIN = 6       # I2S SD引脚

# Speak I2S配置
SPK_SCK_PIN = 15       # I2S SCK引脚
SPK_WS_PIN = 16      # I2S WS引脚
SPK_SD_PIN = 7       # I2S SD引脚

VOICE_ID = "7426720361733046281" #替换为你想要的音色

# 替换为你的 Coze Token
ACCESS_TOKEN = "pat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
BOT_ID = "xxxxxxxxxxxx"        # 替换为你的 Bot ID
WS_URL = f"wss://ws.coze.cn/v1/chat?bot_id={BOT_ID}"
HEADERS = {
    "Authorization": "Bearer " + ACCESS_TOKEN
}

# MIT license; Copyright (c) 2025 Walksky Su (walksky@gmail.com)

import os
import json
import asyncio
import time
import random
import ubinascii
import _thread
import sys
from collections import deque
from machine import I2S, Pin
from aiohttp import ClientSession, WSMsgType
from config import WS_URL, HEADERS
from config import MIC_SCK_PIN, MIC_WS_PIN, MIC_SD_PIN
from config import SPK_SCK_PIN, SPK_WS_PIN, SPK_SD_PIN
from config import RATE, CHANNELS, BIT_DEPTH, CHUNK, VOICE_ID

# 导入OLED显示相关变量
from oled_display import oled, listen_fb, talk_fb
# 使用collections.deque和线程锁实现线程安全的队列

# 全局变量
audio_recording = False
audio_playing = False
audio_ws = None   # WebSocket连接对象
audio_in = None   # I2S输入对象（麦克风）
audio_out = None  # I2S输出对象（扬声器）
message_queue = None  # 消息队列，将在chat_client中初始化
message_queue_lock = None  # 消息队列锁，用于线程安全
audio_buffer_queue = None  # 音频缓冲队列，用于缓存音频数据
audio_buffer_lock = None  # 音频缓冲队列锁，用于线程安全


def get_event_id():
    """生成唯一的事件ID，使用时间戳和随机数代替uuid"""
    timestamp = int(time.time() * 1000)  # 毫秒级时间戳
    random_part = random.randint(1000, 9999)  # 4位随机数
    return f"{timestamp}-{random_part}"


def init_i2s_mic():
    """初始化I2S接口用于音频录制"""
    try:
        # 配置I2S为接收模式（录音）
        audio_in = I2S(
            0,                      # I2S ID
            sck=Pin(MIC_SCK_PIN),       # 串行时钟
            ws=Pin(MIC_WS_PIN),         # 字选择
            sd=Pin(MIC_SD_PIN),         # 串行数据
            mode=I2S.RX,            # 接收模式
            bits=BIT_DEPTH,         # 位深度
            format=I2S.MONO,        # 单声道
            rate=RATE,              # 采样率
            ibuf=CHUNK * 4          # 输入缓冲区大小
        )
        print("✅ 麦克风I2S初始化成功")
        return audio_in
    except Exception as e:
        print(f"❌ 麦克风I2S初始化失败: {e}")
        return None


def init_i2s_speaker():
    """初始化I2S接口用于音频播放"""
    try:
        # 配置I2S为发送模式（播放）
        audio_out = I2S(
            1,                      # I2S ID
            sck=Pin(SPK_SCK_PIN),       # 串行时钟
            ws=Pin(SPK_WS_PIN),         # 字选择
            sd=Pin(SPK_SD_PIN),         # 串行数据
            mode=I2S.TX,            # 发送模式
            bits=BIT_DEPTH,         # 位深度
            format=I2S.MONO,        # 单声道
            rate=RATE,              # 采样率
            ibuf=CHUNK * 32          # 输出缓冲区大小
        )
        print("✅ 扬声器I2S初始化成功")
        return audio_out
    except Exception as e:
        print(f"❌ 扬声器I2S初始化失败: {e}")
        return None


def add_to_message_queue(message):
    """将消息添加到队列中，使用线程锁保证线程安全"""
    global message_queue, message_queue_lock
    with message_queue_lock:
        message_queue.append(message)
    # print(f"已添加消息到队列: {message['event_type']}")


async def process_message_queue(ws):
    """处理消息队列中的消息并发送到WebSocket"""
    global message_queue, message_queue_lock
    while True:
        try:
            # 检查队列是否有消息
            message = None
            with message_queue_lock:
                if len(message_queue) > 0:
                    message = message_queue.popleft()

            if message:
                # 发送消息到WebSocket
                try:
                    # print(f"从队列发送消息: {message['event_type']}")
                    await ws.send_json(message)
                except Exception as e:
                    print(f"发送消息时出错: {e}")
                    # 如果发送失败，可以选择将消息放回队列
                    with message_queue_lock:
                        message_queue.appendleft(message)
            else:
                # 队列为空，短暂休眠
                await asyncio.sleep(0.01)
        except Exception as e:
            print(f"处理消息队列时出错: {e}")
            await asyncio.sleep(0.01)


def audio_recording_thread(ws_obj):
    """音频录制线程，持续采集音频并发送到服务器，包含静音检测功能"""
    global audio_recording, audio_in

    try:
        # 初始化I2S麦克风
        audio_in = init_i2s_mic()
        if not audio_in:
            print("无法启动录音线程，麦克风I2S初始化失败")
            return

        # 显示录音状态
        oled.fill(0)  # 清空屏幕
        oled.blit(listen_fb, 16, 8)  # 显示"耹听中.."
        oled.show()

        # 分配音频缓冲区
        audio_buffer = bytearray(CHUNK)  # 修改缓冲区大小

        # 静音检测相关变量
        SILENCE_THRESHOLD = 100  # 静音阈值，根据实际环境调整
        silence_duration = 0     # 当前连续静音时长
        last_sound_time = time.time()  # 上次检测到声音的时间
        had_voice = False        # 是否已经检测到过人声

        print("开始录音并发送音频流...")
        while True:  # 修改为无限循环，通过audio_recording变量控制是否录音
            # 检查是否应该录音
            if not audio_recording:
                # 如果不需要录音，短暂休眠后继续检查
                time.sleep(0.1)
                continue

            # 读取音频数据
            try:
                bytes_read = audio_in.readinto(audio_buffer)
                if bytes_read > 0:
                    # 计算当前音频块的音量
                    volume = 0
                    for i in range(0, bytes_read, 2):  # 16位采样，每个采样2字节
                        if i + 1 < bytes_read:
                            # 将两个字节组合成一个16位整数
                            sample = (audio_buffer[i+1] << 8) | audio_buffer[i]
                            # 如果最高位为1，则为负数，需要转换
                            if sample & 0x8000:
                                sample = -((~sample & 0xFFFF) + 1)
                            volume += abs(sample)

                    # 计算平均音量
                    avg_volume = volume / \
                        (bytes_read // 2) if bytes_read > 0 else 0

                    # 对音频数据进行Base64编码
                    audio_b64 = ubinascii.b2a_base64(
                        audio_buffer[:bytes_read]).decode('utf-8').strip()

                    # 构造音频数据消息
                    audio_msg = {
                        "id": get_event_id(),
                        "event_type": "input_audio_buffer.append",
                        "data": {
                            "delta": audio_b64
                        }
                    }

                    # 将消息添加到队列，而不是直接发送
                    # 现在使用非异步函数，直接调用
                    add_to_message_queue(audio_msg)

                    # 静音检测逻辑
                    current_time = time.time()
                    # print(avg_volume)
                    if avg_volume > SILENCE_THRESHOLD:
                        # 检测到声音
                        had_voice = True
                        last_sound_time = current_time
                        silence_duration = 0
                    else:
                        # 检测到静音
                        if had_voice:  # 只有在之前检测到过声音后才开始计算静音时长
                            silence_duration = current_time - last_sound_time

                            # 如果静音持续超过1.5秒，发送完成事件
                            if silence_duration >= 1.5:
                                # 发送音频完成事件
                                complete_msg = {
                                    "id": get_event_id(),
                                    "event_type": "input_audio_buffer.complete"
                                }
                                print(
                                    f"添加完成事件到队列: {complete_msg['event_type']}")
                                add_to_message_queue(complete_msg)
                                print("检测到静音1.5秒，已添加完成事件到队列")

                                # 重置状态，准备下一轮录音
                                had_voice = False
                                silence_duration = 0
            except Exception as e:
                print(f"录音过程中发生错误: {e}")
                time.sleep(0.1)  # 错误后短暂暂停

            # 检查是否应该退出线程
            if not audio_recording and audio_playing:
                # 如果不需要录音且正在播放音频，则暂停录音但不退出线程
                time.sleep(0.1)

        # 注意：此处代码不会执行，因为使用了无限循环
        # 停止I2S的逻辑移到了chat_client函数中

    except Exception as e:
        print(f"录音线程发生错误: {e}")
        # 关闭I2S设备
        if audio_in:
            try:
                audio_in.deinit()
                audio_in = None
            except:
                pass


def play_audio_data(audio_data_base64):
    """解码并播放base64编码的音频数据"""
    global audio_out, audio_playing

    try:
        # 如果I2S输出未初始化，则初始化
        if audio_out is None:
            audio_out = init_i2s_speaker()
            if audio_out is None:
                print("❌ 无法播放音频，扬声器I2S初始化失败")
                return False

        # 解码base64音频数据
        try:
            audio_bytes = ubinascii.a2b_base64(audio_data_base64)
            # 写入音频数据到I2S
            bytes_written = audio_out.write(audio_bytes)
            return bytes_written > 0
        except Exception as e:
            print(f"❌ 音频解码或播放失败: {e}")
            return False
    except Exception as e:
        print(f"❌ 播放音频时发生错误: {e}")
        return False


async def handle_message(ws, data):
    """处理接收到的消息并发送适当的响应"""
    global audio_recording, audio_ws, audio_playing

    event_type = data['event_type']
    if event_type == 'conversation.audio.delta':
        # 处理音频数据并播放
        try:
            audio_content = data['data']['content']
            # 在播放音频前暂停录音
            audio_recording = False
            # print("暂停录音，开始播放音频")
            play_result = play_audio_data(audio_content)
            if play_result:
                audio_playing = True
                # 显示播放状态
                oled.fill(0)  # 清空屏幕
                oled.blit(talk_fb, 16, 8)  # 显示"说话中.."
                oled.show()
            # 简化日志输出，避免过多打印
            if not audio_playing:
                print("Received audio delta and playing")
        except Exception as e:
            print(f"❌ 处理音频数据失败: {e}")
    elif event_type == 'conversation.audio.completed':
        # 音频播放完成，恢复录音
        audio_playing = False
        audio_recording = True
        print("音频播放完成，恢复录音")
        # 显示录音状态
        oled.fill(0)  # 清空屏幕
        oled.blit(listen_fb, 16, 8)  # 显示"耹听中.."
        oled.show()
        # 如果录音线程已经停止，重新启动
        if audio_ws and not audio_in:
            _thread.start_new_thread(audio_recording_thread, (audio_ws,))
    else:
        pass
        # print("Received event:", json.dumps(data))

    # 处理chat.created事件
    if event_type == 'chat.created':
        # 发送音频配置信息
        audio_config = {
            "id": get_event_id(),
            "event_type": "chat.update",
            "data": {
                "input_audio": {
                    "format": "pcm",
                    "codec": "pcm",
                    "sample_rate": RATE,
                    "channel": CHANNELS,
                    "bit_depth": BIT_DEPTH
                },
                "output_audio": {
                    "codec": "pcm",
                    "pcm_config": {
                        "sample_rate": RATE
                    },
                    "speech_rate": 0,
                    "voice_id": VOICE_ID  # 👈 替换为你的音色 ID
                }
            }
        }

        await ws.send_json(audio_config)
        print("✅ 已发送音频配置")

    # 处理chat.updated事件，启动录音线程
    elif event_type == 'chat.updated':
        # 启动录音线程
        audio_recording = True
        audio_ws = ws
        # 显示录音状态
        oled.fill(0)  # 清空屏幕
        oled.blit(listen_fb, 16, 8)  # 显示"耹听中.."
        oled.show()
        _thread.start_new_thread(audio_recording_thread, (ws,))
        print("✅ 已启动录音线程")

    # 处理chat.completed事件，停止录音
    elif event_type == 'chat.completed':
        audio_recording = False
        # 清空OLED显示
        oled.fill(0)
        oled.show()
        print("✅ 已停止录音")

    # 默认继续保持连接
    return True


async def chat_client():
    # 创建会话并连接到WebSocket服务器
    global audio_recording, audio_playing, message_queue, audio_in, audio_out

    # 初始化消息队列和队列锁
    global message_queue_lock
    message_queue = deque([], 1024)
    message_queue_lock = _thread.allocate_lock()

    # 初始化音频状态
    audio_recording = False
    audio_playing = False
    audio_in = None
    audio_out = None

    # 初始化OLED显示
    oled.fill(0)  # 清空屏幕
    oled.show()

    try:
        async with ClientSession(headers=HEADERS) as session:
            # 认证信息已在创建ClientSession时传递，无需在ws_connect中重复传递
            async with session.ws_connect(WS_URL) as ws:
                print("Connected to server.")

                # 启动消息队列处理任务
                queue_task = asyncio.create_task(process_message_queue(ws))

                # 消息接收循环
                keep_running = True
                while keep_running:
                    try:
                        # 等待接收消息，直接使用receive_json获取JSON内容
                        data = await asyncio.wait_for(ws.receive_json(), timeout=60)

                        # 处理消息并决定是否继续运行
                        keep_running = await handle_message(ws, data)

                    except Exception as e:
                        print(f"发生错误: {e}")
                        sys.print_exception(e)
                        break

                # 取消消息队列处理任务
                queue_task.cancel()
                try:
                    await queue_task
                except asyncio.CancelledError:
                    pass

                # 确保录音和播放停止
                audio_recording = False
                audio_playing = False
                # 关闭I2S设备
                if audio_in:
                    try:
                        audio_in.deinit()
                    except:
                        pass
                if audio_out:
                    try:
                        audio_out.deinit()
                    except:
                        pass
                print("WebSocket客户端已退出")
    except Exception as e:
        # 确保录音和播放停止
        audio_recording = False
        audio_playing = False
        # 关闭I2S设备
        if audio_in:
            try:
                audio_in.deinit()
            except:
                pass
        if audio_out:
            try:
                audio_out.deinit()
            except:
                pass
        print(f"WebSocket连接发生错误: {e}")
        sys.print_exception(e)
        raise

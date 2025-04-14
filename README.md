# ESP32 S3 智能语音助手

基于ESP32 S3芯片和Coze平台语音流式API打造的智能硬件设备。

## 项目概述

本项目利用ESP32 S3芯片连接Coze平台的语音流式API，实现智能语音交互功能。设备可以录制用户语音，发送至Coze平台进行处理，并通过扬声器播放AI回复，同时在OLED屏幕上显示状态信息。

## 硬件准备

### 核心组件

- **主控芯片**：ESP32 S3（高性价比处理器）
- **麦克风**：用于录制用户语音
- **功放芯片 + 喇叭**：用于播放AI回复声音
- **OLED显示屏**：显示设备状态和提示信息

### 接线说明

详细接线方式请参考项目根目录下的`layout.jpg`文件。

## 软件准备

在开始开发前，请完成以下软件准备工作：

### 1. 刷入MicroPython系统

将MicroPython固件刷入ESP32 S3芯片中。推荐使用[Thonny IDE](https://thonny.org/)，它不仅能刷写固件，还能上传文件、查看调试信息，简单好用。

### 2. 配置Coze平台智能体

本项目使用字节Coze平台提供的大模型服务，它支持双向语音流式API，并提供丰富的语音音色。在开发前，请在Coze平台上完成以下步骤：

1. 创建一个智能体
2. 升级账号至专业版，获取语音API调用权限
3. 创建个人访问令牌（Personal Access Token），用于API调用

> Coze平台API文档：https://www.coze.cn/open/docs/developer_guides/streaming_chat_event

## 项目配置与部署

### 1. 配置项目参数

编辑`config.py`文件，填入正确的配置信息：
- Wi-Fi连接信息
- 音频参数配置
- I2S接口引脚定义
- Coze平台访问令牌和Bot ID

### 2. 部署到ESP32 S3

使用Thonny IDE或其他MicroPython开发工具，将以下文件上传至ESP32 S3：
- `main.py`：主程序入口
- `config.py`：配置文件
- `coze_chat.py`：Coze平台通信模块
- `easydisplay.py`：OLED显示控制
- `st7735.py`：OLED驱动
- `aiohttp`目录：WebSocket通信库

## 许可证

MIT License; Copyright (c) 2025 Walksky Su (walksky@gmail.com)

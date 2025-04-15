import time
from machine import SPI, Pin
import st7735_buf
from easydisplay import EasyDisplay

class ScreenManager:
    def __init__(self, width=160, height=80, line_height=16, 
                 spi_num=1, baudrate=20000000, sck_pin=5, mosi_pin=4,
                 cs_pin=6, dc_pin=3, res_pin=2, bl_pin=1, rotate=3,
                 font="text_lite_16px_2312.v3.bmf", color=0xFFFF):
        """
        初始化屏幕管理器
        
        参数:
            width: 屏幕宽度(像素)
            height: 屏幕高度(像素)
            line_height: 行高(像素)
            spi_num: SPI编号
            baudrate: SPI波特率
            sck_pin: SCK引脚
            mosi_pin: MOSI引脚
            cs_pin: CS引脚
            dc_pin: DC引脚
            res_pin: RESET引脚
            bl_pin: 背光引脚
            rotate: 屏幕旋转方向 (0-6)
            font: 字体文件路径
            color: 文本颜色(RGB565格式，默认白色 0xFFFF)
        """
        # 初始化 SPI
        self.spi = SPI(spi_num, baudrate=baudrate, polarity=0, phase=0, 
                       sck=Pin(sck_pin), mosi=Pin(mosi_pin))
        
        # 初始化 ST7735 显示驱动
        self.dp = st7735_buf.ST7735(width=width, height=height, spi=self.spi, 
                                    cs=Pin(cs_pin), dc=Pin(dc_pin), res=Pin(res_pin), 
                                    rotate=rotate, bl=Pin(bl_pin), 
                                    invert=False, rgb=False)
        
        # 初始化 EasyDisplay
        self.ed = EasyDisplay(self.dp, "RGB565", 
                              font=font, 
                              show=True, color=color, clear=False)
        
        # 显示参数
        self.width = width
        self.height = height
        self.line_height = line_height
        self.max_lines = height // line_height
        self.current_x = 0
        self.current_y = 0
        self.lines = []  # 存储每行文本内容
        self.color = color

    @staticmethod
    def is_chinese_char(char):
        """判断字符是否为中文字符"""
        unicode_val = ord(char)
        return (0x4E00 <= unicode_val <= 0x9FFF or 
                0x3400 <= unicode_val <= 0x4DBF or 
                0x20000 <= unicode_val <= 0x2A6DF)

    @staticmethod
    def is_english_char(char):
        """判断字符是否为英文字符"""
        unicode_val = ord(char)
        return 0x0000 <= unicode_val <= 0x007F

    def get_char_width(self, char):
        """获取字符宽度（中文16像素，英文8像素）"""
        if self.is_chinese_char(char):
            return 16
        elif self.is_english_char(char):
            return 8
        return 8  # 默认宽度

    def add_text(self, text, char_delay=0.01, line_delay=0):
        """
        添加文本到屏幕，支持换行和滚动
        
        参数:
            text: 要显示的文本
            char_delay: 字符显示间隔时间(秒)，设为0禁用延迟
            line_delay: 行显示间隔时间(秒)，设为0禁用延迟
        """
        line_buffer = []  # 当前行缓冲区
        line_width = 0    # 当前行宽度
        
        for char in text:
            if char == '\n':  # 换行符
                self._flush_line_buffer(line_buffer)
                self._new_line()
                line_buffer = []
                line_width = 0
                if line_delay > 0:
                    time.sleep(line_delay)
                continue
                
            char_width = self.get_char_width(char)
            
            # 检查是否需要换行
            if line_width + char_width > self.width:
                self._flush_line_buffer(line_buffer)
                self._new_line()
                line_buffer = []
                line_width = 0
                if line_delay > 0:
                    time.sleep(line_delay)
            
            # 添加到行缓冲区
            line_buffer.append((char, line_width))
            line_width += char_width
            
            # 显示当前字符（如果启用延迟）
            if char_delay > 0:
                self.ed.text(char, line_width - char_width, self.current_y, self.color)
                self.ed.show()
                time.sleep(char_delay)
        
        # 刷新剩余内容
        if line_buffer:
            self._flush_line_buffer(line_buffer)

    def _flush_line_buffer(self, line_buffer):
        """将行缓冲区内容一次性显示到屏幕"""
        if not line_buffer:
            return
            
        # 检查是否需要滚动
        if self.current_y >= self.height:
            self._scroll_up()
            self.current_y = self.height - self.line_height
        
        # 一次性显示整行
        for char, x in line_buffer:
            self.ed.text(char, x, self.current_y, self.color)
            self.lines.append((char, x, self.current_y))
        
        self.ed.show()

    def _new_line(self):
        """处理换行"""
        self.current_x = 0
        self.current_y += self.line_height

    def _scroll_up(self):
        """向上滚动一行"""
        if hasattr(self.dp, 'scroll'):
            self.dp.scroll(0, -self.line_height)
            self.ed.fill_rect(0, self.height - self.line_height, 
                             self.width, self.line_height, 0)
        else:
            self.ed.fill(0)
            new_lines = []
            for char, x, y in self.lines:
                new_y = y - self.line_height
                if new_y >= 0:
                    self.ed.text(char, x, new_y, self.color)
                    new_lines.append((char, x, new_y))
            self.lines = new_lines
        self.ed.show()

    def display_image(self, file, x, y, key=None, show=True, clear=False, invert=False, color=None, bg_color=None):
        """
        显示图片（支持PBM/PPM格式）
        
        参数:
            file: 图片文件路径或BytesIO对象
            x: X坐标
            y: Y坐标
            key: 透明色
            show: 是否立即显示
            clear: 是否清屏
            invert: 是否反转颜色
            color: 主体颜色
            bg_color: 背景颜色
        """
        self.ed.pbm(file, x, y, key=key, show=show, clear=clear, invert=invert, color=color, bg_color=bg_color)

    def clear(self):
        """清空屏幕"""
        self.ed.clear()
        self.lines = []
        self.current_x = 0
        self.current_y = 0
        self.ed.show()

    def display_text(self, text, char_delay=0.005, line_delay=0.01, clear=True):
        """
        显示文本并自动滚动（便捷方法）
        
        参数:
            text: 要显示的文本
            char_delay: 字符显示间隔时间(秒)
            line_delay: 行显示间隔时间(秒)
            clear: 是否清屏
        """
        if clear:
            self.clear()
        self.add_text(text, char_delay=char_delay, line_delay=line_delay)

    def set_color(self, color):
        """设置文本颜色"""
        self.color = color

    def set_font(self, font_path):
        """设置字体"""
        self.ed.load_font(font_path)
'''
# 示例用法
if __name__ == "__main__":
    # 创建屏幕管理器实例
    screen = ScreenManager(width=160, height=80, line_height=16)
    
    # 显示文本
    sample_text = """这是一个示例文本，用于测试显示屏的文本显示和滚动功能。
This is a sample text for testing display scrolling.
混合中英文显示效果 Mixed Chinese and English display.
1234567890!@#$%^&*() 数字和符号显示测试。
"""
    screen.display_text(sample_text, char_delay=0.002, line_delay=0.05)
    
    # 添加更多文本
    time.sleep(1)
    screen.add_text("\n更多内容...", char_delay=0.01)
    
    # 改变颜色
    screen.set_color(0xF800)  # 红色
    screen.add_text("\n红色文本")
    
    # 显示图片（假设有一个PBM文件）
    #screen.display_image("nezha.pbm", 0, 0)
    
    # 清屏
    time.sleep(2)
    screen.clear()
'''
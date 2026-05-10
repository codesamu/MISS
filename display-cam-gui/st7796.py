import time
import spidev
import logging
import numpy as np
from gpiozero import *


SPI_Freq = 40000000     # SPI 时钟频率
SPI_Mode = 0            # 模式0
BL_Freq  = 1000         # PWM 频率（背光）
RST_PIN  = 27
DC_PIN   = 25
BL_PIN   = 18



class st7796():
    def __init__(self):
        self.np=np
        self.width  = 320
        self.height = 480 
        
        import RPi.GPIO as RPIO
        self.RPIO = RPIO
        self.RPIO.setmode(self.RPIO.BCM)
        self.RPIO.setwarnings(False)
        
        print(f"DEBUG: Initializing ST7796 pins: RST={RST_PIN}, DC={DC_PIN}, BL={BL_PIN}")
        self.RPIO.setup(RST_PIN, self.RPIO.OUT, initial=self.RPIO.HIGH)
        print("DEBUG: RST OK")
        self.RPIO.setup(DC_PIN, self.RPIO.OUT, initial=self.RPIO.HIGH)
        print("DEBUG: DC OK")
        self.RPIO.setup(BL_PIN, self.RPIO.OUT)
        time.sleep(0.1) # Small delay to ensure allocation
        self.BL_PWM = self.RPIO.PWM(BL_PIN, BL_Freq)
        self.BL_PWM.start(100)
        print("DEBUG: BL OK")
        #Initialize SPI
        self.SPI = spidev.SpiDev(0,0)
        self.SPI.max_speed_hz = SPI_Freq  
        self.SPI.mode = 0b00   
        
        self.lcd_init()
    
    def bl_DutyCycle(self, duty):                   # 设置 PWM 占空比
        self.BL_PWM.ChangeDutyCycle(duty)

    
    
    def digital_write(self, Pin_Num, value):
        if value:
            self.RPIO.output(Pin_Num, self.RPIO.HIGH)
        else:
            self.RPIO.output(Pin_Num, self.RPIO.LOW)
            
    def spi_writebyte(self, data):
        if self.SPI!=None :
            self.SPI.writebytes(data)
    
    def command(self, cmd):
        self.digital_write(DC_PIN, False)
        self.spi_writebyte([cmd])   
        
    def data(self, val):
        self.digital_write(DC_PIN, True)
        self.spi_writebyte([val])  
        
    def reset(self):
        """Reset the display"""
        self.digital_write(RST_PIN,True)
        time.sleep(0.01)
        self.digital_write(RST_PIN,False)
        time.sleep(0.01)
        self.digital_write(RST_PIN,True)
        time.sleep(0.01)
    
    def dre_rectangle(self, Xstart, Ystart, Xend, Yend, color):
        color_high = (color >> 8) & 0xFF
        color_low = color & 0xFF
            
        self.set_windows( Xstart, Ystart, Xend, Yend) 
        for a in range (Xstart, Xend+1):
            for b in range (Ystart , Yend + 1):
                self.data(color_high)
                self.data(color_low)
    
    def lcd_init(self):
        self.reset()
        self.command(0x11)      
        time.sleep(0.12)

        self.command(0x36)      # Memory Data Access Control MY,MX~~
        self.data(0x48)         # Ändert von 0x08 zu 0x48 um Spiegelung zu beheben    

        self.command(0x3A)      
        self.data(0x05)    # self.data(0x66) 

        self.command(0xF0)      # Command Set Control
        self.data(0xC3)    

        self.command(0xF0)      
        self.data(0x96)    

        self.command(0xB4)      
        self.data(0x01)    

        self.command(0xB7)      
        self.data(0xC6)    

        self.command(0xC0)      
        self.data(0x80)    
        self.data(0x45)    

        self.command(0xC1)      
        self.data(0x13)    # 18  #00

        self.command(0xC2)      
        self.data(0xA7)    

        self.command(0xC5)      
        self.data(0x0A)    

        self.command(0xE8)      
        self.data(0x40) 
        self.data(0x8A) 
        self.data(0x00) 
        self.data(0x00) 
        self.data(0x29) 
        self.data(0x19) 
        self.data(0xA5) 
        self.data(0x33) 

        self.command(0xE0) 
        self.data(0xD0) 
        self.data(0x08) 
        self.data(0x0F) 
        self.data(0x06) 
        self.data(0x06) 
        self.data(0x33) 
        self.data(0x30) 
        self.data(0x33) 
        self.data(0x47) 
        self.data(0x17) 
        self.data(0x13) 
        self.data(0x13) 
        self.data(0x2B) 
        self.data(0x31) 

        self.command(0xE1) 
        self.data(0xD0) 
        self.data(0x0A) 
        self.data(0x11) 
        self.data(0x0B) 
        self.data(0x09) 
        self.data(0x07) 
        self.data(0x2F) 
        self.data(0x33) 
        self.data(0x47) 
        self.data(0x38) 
        self.data(0x15) 
        self.data(0x16) 
        self.data(0x2C) 
        self.data(0x32) 
    
        self.command(0xF0)      
        self.data(0x3C)    

        self.command(0xF0)      
        self.data(0x69)    
        
        
        self.command(0x21)

        self.command(0x11)

        time.sleep(0.1)

        self.command(0x29)
        
    def set_windows(self, Xstart, Ystart, Xend, Yend, horizontal = 0):
        if horizontal:  
            #set the X coordinates
            self.command(0x2A)
            self.data(Xstart>>8)         #Set the horizontal starting point to the high octet
            self.data(Xstart & 0xff)     #Set the horizontal starting point to the low octet
            self.data(Xend>>8)         #Set the horizontal end to the high octet
            self.data((Xend) & 0xff)   #Set the horizontal end to the low octet 
            #set the Y coordinates
            self.command(0x2B)
            self.data(Ystart>>8)
            self.data((Ystart & 0xff))
            self.data(Yend>>8)
            self.data((Yend) & 0xff)
            self.command(0x2C)
        else:
            #set the X coordinates
            self.command(0x2A)
            self.data(Xstart>>8)        #Set the horizontal starting point to the high octet
            self.data(Xstart & 0xff)    #Set the horizontal starting point to the low octet
            self.data(Xend>>8)        #Set the horizontal end to the high octet
            self.data((Xend) & 0xff)  #Set the horizontal end to the low octet 
            #set the Y coordinates
            self.command(0x2B)
            self.data(Ystart>>8)
            self.data((Ystart & 0xff))
            self.data(Yend>>8)
            self.data((Yend) & 0xff)
            self.command(0x2C)     
    
    
    def show_image_windows(self, Xstart, Ystart, Xend, Yend, Image):

        # """Set buffer to value of Python Imaging Library image."""
        # """Write display buffer to physical display"""
        imwidth, imheight = Image.size
        if imwidth != self.width or imheight != self.height:
            raise ValueError('Image must be same dimensions as display \
                ({0}x{1}).' .format(self.width, self.height))
        img = self.np.asarray(Image)
        pix = self.np.zeros((imheight,imwidth , 2), dtype = self.np.uint8)
        #RGB888 >> RGB565
        pix[...,[0]] = self.np.add(self.np.bitwise_and(img[...,[0]],0xF8),self.np.right_shift(img[...,[1]],5))
        pix[...,[1]] = self.np.add(self.np.bitwise_and(self.np.left_shift(img[...,[1]],3),0xE0), self.np.right_shift(img[...,[2]],3))
        pix = pix.flatten().tolist()
            
        if Xstart > Xend:
            data = Xstart
            Xstart = Xend
            Xend = data
            
        if Ystart > Yend:        
            data = Ystart
            Ystart = Yend
            Yend = data
        
        if Xend < self.width - 1:
            Xend = Xend + 1
        if Yend < self.width - 1:
            Yend = Yend + 1
            
        self.set_windows( Xstart, Ystart, Xend, Yend)
        self.digital_write(DC_PIN,True)
        
        for i in range (Ystart,Yend):             
            Addr = ((Xstart) + (i * 240)) * 2        
            self.spi_writebyte(pix[Addr : Addr+((Xend-Xstart+1)*2)])

    def show_image(self, Image):
        """Set buffer to value of Python Imaging Library image."""
        """Write display buffer to physical display"""
        imwidth, imheight = Image.size
        if imwidth == self.height and imheight ==  self.width:
            # print("Landscape screen")
            img = self.np.asarray(Image)
            pix = self.np.zeros((self.width, self.height,2), dtype = self.np.uint8)
            #RGB888 >> RGB565
            pix[...,[0]] = self.np.add(self.np.bitwise_and(img[...,[0]],0xF8),self.np.right_shift(img[...,[1]],5))
            pix[...,[1]] = self.np.add(self.np.bitwise_and(self.np.left_shift(img[...,[1]],3),0xE0), self.np.right_shift(img[...,[2]],3))
            pix = pix.flatten().tolist()
            
            self.command(0x36)
            self.data(0xE8)   # MY=1, MX=1, MV=1, BGR=1 – Querformat korrekt
            self.set_windows(0, 0, self.height,self.width, 1)
            self.digital_write(DC_PIN,True)
            for i in range(0,len(pix),4096):
                self.spi_writebyte(pix[i:i+4096])
        else :
            # print("Portrait screen")
            img = self.np.asarray(Image)
            pix = self.np.zeros((imheight,imwidth , 2), dtype = self.np.uint8)
            
            pix[...,[0]] = self.np.add(self.np.bitwise_and(img[...,[0]],0xF8),self.np.right_shift(img[...,[1]],5))
            pix[...,[1]] = self.np.add(self.np.bitwise_and(self.np.left_shift(img[...,[1]],3),0xE0), self.np.right_shift(img[...,[2]],3))
            pix = pix.flatten().tolist()
            
            self.command(0x36)
            self.data(0x48)         # Ändert von 0x08 zu 0x48
            self.set_windows(0, 0, self.width, self.height, 0)
            self.digital_write(DC_PIN,True)
        for i in range(0, len(pix), 4096):
            self.spi_writebyte(pix[i: i+4096])

    
    def clear(self):
        """Clear contents of image buffer"""
        _buffer = [0xff] * (self.width*self.height*2)
        self.set_windows(0, 0, self.width, self.height)
        self.digital_write(DC_PIN,True)
        for i in range(0, len(_buffer), 4096):
            self.spi_writebyte(_buffer[i: i+4096])

    def close(self):
        """Release GPIO and SPI resources"""
        print("DEBUG: Closing st7796 hardware...")
        try:
            if hasattr(self, 'BL_PWM') and self.BL_PWM is not None:
                try:
                    self.BL_PWM.stop()
                except:
                    pass
                self.BL_PWM = None
            if hasattr(self, 'RPIO'):
                # Nuclear cleanup: reset all pins used by this process
                self.RPIO.cleanup()
            if self.SPI:
                self.SPI.close()
            print("DEBUG: st7796 hardware closed successfully.")
        except Exception as e:
            print(f"DEBUG: Error closing st7796: {e}")
    
    

from threading import Event, Thread, Lock
from Queue import Queue
import time
import os
from struct import pack, unpack
from util import *
from cmd_485 import *
import random
import traceback
from serial import *

class Serial485Rx(Thread):
    def __init__(self, serial, rxq, stop, master=True, tx_task=None):
        Thread.__init__(self)
        self.rxq = rxq
        self.serial = serial
        self.stop = stop
        self.master = master
        self.esc = False
        self.buffer = ''
        self.buffer_size = 0
        self.tx_task = tx_task

    def add_byte(self, c):
        b = ord(c)
        logging.debug('[%s] %02X' % (get_func_name(),b))

        if self.buffer_size == 0 and b == FRAME_FLAG:
            return False

        if not self.esc and b == FRAME_ESC:
            self.esc = True
            return False

        if not self.esc and b == FRAME_FLAG:
            return True

        if self.buffer_size >= FRAME_MAX_CMD_SIZE:
            self.buffer_size = 0
            self.esc = False
            return False

        self.buffer += c
        self.buffer_size += 1

        if self.esc:
            self.esc = False

        return False

    def run(self):
        logging.debug('Serial485Rx started (master=%s)' % (str(self.master)))
        while not self.stop.is_set():
            try:
                b = self.serial.read(1)
            except Exception as e:
                print(repr(traceback.format_stack()))
                logging.debug('[%s] %s' % (get_func_name(), repr(e)))
                time.sleep(0.25)
                continue

            if b:
                logging.debug('[%s] %02X byte RX (master=%s)' % (get_func_name(),ord(b),self.master))

            if not b:
                time.sleep(0.25)
                continue

            if self.add_byte(b):
                #logging.debug('[%s] new RX frame. Trying to decode (master=%s)' % (get_func_name(),self.master))
                cmd = Cmd()
                try:
                    if self.master:
                        decoded = cmd.decode_ans(self.buffer)
                    else:
                        decoded = cmd.decode_req(self.buffer)
                except Exception as e:
                    logging.debug('[%s] %s' % (get_func_name(),repr(e)))
                    decoded = False

                if decoded:
                    if not self.master:
                        logging.debug('M->S: ' + str(cmd))
                    else:
                        logging.debug('S->M: ' + str(cmd))
                    
                    #logging.debug('[%s] new RX frame. Decode, adding to queue (master=%s)' % (get_func_name(),self.master))
                    self.rxq.put(cmd)
                    
                if ENABLE_WIRESHARK and self.tx_task.master:
                    self.tx_task.write_wireshark(self.buffer,False)

                self.buffer_size = 0
                self.buffer = ''
                self.esc = 0

        logging.debug('Serial485Rx stopped')


class Serial485(Thread):
    def __init__(self, serial, rxq, txq, stop, is_master):
        Thread.__init__(self)
        self.txq = txq
        self.rxq = rxq
        self.stop = stop
        self.master = is_master
        self.serial = serial
        self.rx_task = Serial485Rx(self.serial, self.rxq, self.stop, self.master, self)
        
        if ENABLE_WIRESHARK and self.master:
            from tuntap import TunTap
            self.tun = TunTap()
            self.tun.open()
            
        self.rx_task.start()

    def write_wireshark(self,buffer,to_device=False):
        #print buffer
        # flags (2) and proto (2)
        hdr_tun = [0,0,0,0]
                            
        hdr_ip_udp = [
            ###### IP ######
            0x45,        # version and header len
            0x00,        # service type
            0x00, 0x00,  # total len
            0x00, 0x00,  # ID 
            0x40, 0x00,  # flags, fragment offset
            0x40,        # TTL
            0x11,        # protocol (UDP)
            0x00, 0x00,  # checksum
            0x00, 0x00, 0x00, 0x00, # Source IP
            0x00, 0x00, 0x00, 0x00, # Dest IP
            ###### UDP ######
            0x00, 0x00,  # Source port
            0x00, 0x00,  # Dest port
            0x00, 0x00,  # len (header + data)
            0x00, 0x00   # checksum
            ]
                
        # set total len
        hdr_ip_udp[2] = (len(hdr_ip_udp) + len(buffer)) >> 8
        hdr_ip_udp[3] = (len(hdr_ip_udp) + len(buffer)) & 0x00ff

        # fake IPs (use device node address)
        dst = ord(buffer[0])
        src = ord(buffer[1])
        #print dst,src
        hdr_ip_udp[12:16] = [src]*4
        hdr_ip_udp[16:20] = [dst]*4

        # custom ports
        if to_device:
            hdr_ip_udp[20] = 0xde
            hdr_ip_udp[21] = 0xad
            hdr_ip_udp[22] = 0xbe
            hdr_ip_udp[23] = 0xef
        else:
            hdr_ip_udp[20] = 0xbe
            hdr_ip_udp[21] = 0xef
            hdr_ip_udp[22] = 0xde
            hdr_ip_udp[23] = 0xad
            
        # UDP len (udp header + packet len)
        hdr_ip_udp[24] = (8 + len(buffer)) >> 8
        hdr_ip_udp[25] = (8 + len(buffer)) & 0x00ff
        
        pad = ''
        #lb = len(hdr_tun) + len(hdr_ip_udp) + len(buffer)  
        #if lb % 4 != 0:
        #    pad = ''*(4 - lb)

        msg = ''.join([ chr(x) for x in hdr_tun + hdr_ip_udp ]) + buffer + pad
        
        #print(len(msg))
        
        self.tun.write(msg)         
        
    def tx(self, buf):
        
        if ENABLE_WIRESHARK and self.master:
            self.write_wireshark(buf,True)
            
        n = 0
        buf = buf.replace(chr(FRAME_ESC), chr(FRAME_ESC)+chr(FRAME_ESC))
        buf = buf.replace(chr(FRAME_FLAG), chr(FRAME_ESC)+chr(FRAME_FLAG))
        buf = chr(FRAME_FLAG) + buf + chr(FRAME_FLAG)

        while True:
            try:
                n += self.serial.write(buf[n:])
            except Exception as e:
                logging.debug('[%s] %s' % (get_func_name(),repr(e)))
                raise Exception('serial TX error')

            if n >= len(buf):
                break

        #logging.debug('[%s] sent %d bytes TX (master=%s)' % (get_func_name(),n,self.master))
        return n

    def run(self):
        logging.debug('Serial485 started')
        while not self.stop.is_set():
            try:
                cmd = self.txq.get(True, 1)
            except Exception as e:
                continue

            try:
                if self.master:
                    cmd.encode_req()
                else:
                    cmd.encode_ans()
            except Exception as e:
                #print repr(traceback.format_stack())
                logging.debug('[%s] %s' % (get_func_name(),repr(e)))
                continue

            if self.master:
                logging.debug('M->S: ' + str(cmd))
            else:
                logging.debug('S->M: ' + str(cmd))
            self.tx(cmd.get())

        self.serial.close()
        logging.debug('Serial485 stopped')


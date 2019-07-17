from threading import Lock, Thread, Event
import logging
import random
import serial
import time
from random import randint

from constants_485 import *
from cmd_485 import *
from serial_485 import *
if EMULATION:
    from serial_pipe import *

# cmd, dst, src, size, crc, point
# version
# manuf, model, id, points, rev
# name, type, unit, rights
# value 

class Device(Thread):
    
    ADDR = [0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F]
    VER = 1
    MANUF = 'UFU'
    MODEL = 'FHDI'
    REV = 0
    ID = 0xC0FFEE00
    POINTS = 5
    POINTS_DESC = [['TEMP',POINT_TYPE_FLOAT,32,POINT_RW,27.5],\
                   ['UMID',POINT_TYPE_FLOAT,57,POINT_RO,80],\
                   ['COOLER',POINT_TYPE_UINT8,251,POINT_RW,0],\
                   ['TAG',POINT_TYPE_ARRAY,250,POINT_RW,"TT302-AI"],\
                   ['EXAUST',POINT_TYPE_UINT8,251,POINT_RW,0]]  
    
    def __init__(self, stop, rxqs, txqs):
        Thread.__init__(self)
        self.stop = stop
        self.rxqs = rxqs
        self.txqs = txqs
        random.seed()

    def tx(self,cmd):
        self.txqs.put(cmd)

    def run(self):
        logging.debug('Starting RX for device addr %s' % str(Device.ADDR))
        cmd = None
        while not self.stop.is_set():
            try:
                cmd = self.rxqs.get(True, 1)
            except:
                continue

            if cmd.dst not in Device.ADDR:
                logging.debug('Not for me %d not in %s' % (cmd.dst,str(Device.ADDR)))
                continue
            
            addr = cmd.dst
            logging.debug('Request : %s' % cmd)
            
            ans = None
            if cmd.cmd == SENS_ITF_VER_CMD:
                ans = Cmd(cmd=SENS_ITF_VER_CMD,\
                          dst=cmd.src,\
                          src=addr,\
                          version=Device.VER)
            elif cmd.cmd == SENS_IDENT_CMD:
                ans = Cmd(cmd=SENS_IDENT_CMD,\
                          dst=cmd.src,\
                          src=addr,\
                          manuf=Device.MANUF,\
                          model=Device.MODEL,\
                          id=Device.ID+addr,\
                          rev=Device.REV,\
                          points=Device.POINTS)
            elif cmd.cmd >= SENS_POINT_DESC_BASE_CMD and cmd.cmd < (SENS_POINT_DESC_BASE_CMD + Device.POINTS):
                p = cmd.cmd - SENS_POINT_DESC_BASE_CMD
                ans = Cmd(cmd=cmd.cmd,\
                          dst=cmd.src,\
                          src=addr,\
                          name=Device.POINTS_DESC[p][0],\
                          type=Device.POINTS_DESC[p][1],\
                          unit=Device.POINTS_DESC[p][2],\
                          rights=Device.POINTS_DESC[p][3])
            elif cmd.cmd >= SENS_POINT_READ_BASE_CMD and cmd.cmd < (SENS_POINT_READ_BASE_CMD + Device.POINTS):
                p = cmd.cmd - SENS_POINT_READ_BASE_CMD
                if Device.POINTS_DESC[p][3] == POINT_RO or Device.POINTS_DESC[p][3] == POINT_RW:
                    ans = Cmd(cmd=cmd.cmd,\
                            dst=cmd.src,\
                            src=addr,\
                            type=Device.POINTS_DESC[p][1],\
                            value=Device.POINTS_DESC[p][4])
                else:
                    logging.debug('Invalid access rights')
            elif cmd.cmd >= SENS_POINT_WRITE_BASE_CMD and cmd.cmd < (SENS_POINT_WRITE_BASE_CMD + Device.POINTS):
                p = cmd.cmd - SENS_POINT_WRITE_BASE_CMD
                if Device.POINTS_DESC[p][3] == POINT_WO or Device.POINTS_DESC[p][3] == POINT_RW:
                    Device.POINTS_DESC[p][4] = cmd.value
                    ans = Cmd(cmd=cmd.cmd,\
                            dst=cmd.src,\
                            src=addr)
                else:
                    logging.debug('Invalid access rights')
            else:
                logging.debug('Invalid command')
                
            if ans:
                #time.sleep(randint(0,300)/1000.0)
                ans.encode_ans()
                logging.debug('Response: %s' % ans)
                self.tx(ans)
                            
        logging.debug('Stopping for device addr %s' % str(Device.ADDR))
        
if __name__ == '__main__':
    
    logging.basicConfig(filename='device.log',
                        level=logging.DEBUG,
                        format='%(asctime)s %(message)s',
                        datefmt='%I:%M:%S')

    console = logging.StreamHandler()
    logging.getLogger('').addHandler(console)

    try:
        if EMULATION:
            ser_dev = SerialPipe(False)
        else:
            ser_dev = serial.Serial(port=SERIAL_DEVICE, baudrate=SERIAL_BAUD, timeout=SERIAL_TIMEOUT)
    except Exception as e:
        logging.info(str(e))
    
    rxq = Queue()
    txq = Queue()
    stop = Event()
    is_master = False    
    
    try:
        ser_task = Serial485(ser_dev, rxq, txq, stop, is_master)
        ser_task.start()
    except Exception as e:
        logging.info(str(e))

    try:
        dev_task = Device(stop, rxq, txq)
        dev_task.start()
    except Exception as e:
        logging.info(str(e))

    while True:
        try:
            v = raw_input('')
        except KeyboardInterrupt as e:
            stop.set()
            break
            
    ser_task.join()
    dev_task.join()
    
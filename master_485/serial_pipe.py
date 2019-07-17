import os
from constants_485 import *

class SerialPipe(object):
    def __init__(self, master, **kwargs):
        
        for f in [PIPE_TX, PIPE_RX]:
            if not os.path.exists(f):
                os.mkfifo(f)
                
        self.master = master
        
        if self.master:
            self.tx = os.open(PIPE_TX,os.O_WRONLY)
            self.rx = os.open(PIPE_RX,os.O_RDONLY)
        else:        
            self.rx = os.open(PIPE_TX,os.O_RDONLY)
            self.tx = os.open(PIPE_RX,os.O_WRONLY)
            
    def write(self, buf):
        return os.write(self.tx,buf)

    def flush(self):
        os.flush(self.tx)
        
    def read(self, nb):
        return os.read(self.rx,nb)

    def open(self, **kwargs):
        pass
        
    def close(self):
        pass
        #if self.master:
        #    os.close(self.tx)
        #    os.close(self.rx)
        #else:
        #    os.close(self.rx)
        #    os.close(self.tx)
              
                
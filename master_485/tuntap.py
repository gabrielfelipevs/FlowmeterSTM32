from constants_485 import *
from pytun import TunTapDevice
from threading import Lock

# sudo apt-get install python-pip
# sudo pip install --upgrade pip
# sudo apt-get install python-dev
# sudo pip install python-pytun
# https://github.com/montag451/pytun
# 
# depois rode o master.py como super usuario
# e habilite o wireshark
# 
# No about do wireshark descubra onde colocar o 
# plugin feito em lua (~/.wireshark/plugins)

class TunTap(object):
    def __init__(self):
        self.tun = TunTapDevice(name="fhdi")
        self.cs = Lock()        
    def open(self):
        self.tun.addr = '172.16.0.1'
        self.tun.netmask = '255.255.255.0'
        self.tun.mtu = 1500
        self.tun.up()

    def close(self):
        self.tun.close()
        
    def write(self,buf):
        self.cs.acquire()
        self.tun.write(buf)
        self.cs.release()
        
if __name__ == "__main__":
    tun = TunTap()
    tun.open()

    while True:
        try:
            v = raw_input('')
        except KeyboardInterrupt as e:
            break                                
        
        tun.write(v)

    tun.close()
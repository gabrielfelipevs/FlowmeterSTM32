import logging
from struct import pack, unpack
from util import *
from constants_485 import *

# cmd, dst, src, size, crc, point
# point, type, value, version, manuf, model  
# unit, rights, name, id, points, rev
class Cmd(object):

    FS = ('>B','>b','>H','>h','>L','>l','>Q','>q','>f','>d', '>%ds')
    TS = (1,1,2,2,4,4,8,8,4,8,0)
    
    def __init__(self, **kwargs):
        self.buffer = ''
        self.cmd = NO_CMD
        self.dst = 0
        self.src = 0
        self.size = 0
        self.payload = {}
        self.crc = 0
        self.retries = 0

        if 'buffer' in kwargs:
            self.buffer = kwargs['buffer']
        else:
            self.buffer = ''
            for k in [ 'cmd', 'dst', 'src', 'size', 'crc']:
                if k in kwargs:
                    setattr(self, k, kwargs[k])
                    del kwargs[k]
            self.payload = kwargs
            if 'type' in self.payload:
                t = self.payload['type']
                if t < 0 and t > POINT_TYPE_ARRAY:
                    logging.error('[%s] Invalid CMD %d' % (get_func_name(), self.cmd))
                    raise Exception('Invalid type')
                
    def get(self):
        return self.buffer

    def __fill_str(self,v,size):
        s = ' '*size
        s = (v + s)[:size]
        return s
    
    def __decode_val(self,f,t,sz=0):
        if t == POINT_TYPE_ARRAY:
            v = unpack((Cmd.FS[t] % sz),f)[0]
        else:
            v = unpack(Cmd.FS[t],f)[0]
        return v
        
    def __encode_val(self,v,t,sz=0):
        if t == POINT_TYPE_ARRAY:
            s = pack((Cmd.FS[t] % sz),v)
        else:
            s = pack(Cmd.FS[t],v)
        return s
        
    def __encode_payload_req(self):
        if self.cmd == SENS_ITF_VER_CMD or \
           self.cmd == SENS_IDENT_CMD or \
           (self.cmd >= SENS_POINT_DESC_BASE_CMD and \
            self.cmd < (SENS_POINT_DESC_BASE_CMD + SENS_MAX_POINTS)) or \
           (self.cmd >= SENS_POINT_READ_BASE_CMD and \
            self.cmd < (SENS_POINT_READ_BASE_CMD + SENS_MAX_POINTS)):
            self.size = 0
            payload_buffer = ''
        elif self.cmd >= SENS_POINT_WRITE_BASE_CMD and \
             self.cmd < (SENS_POINT_WRITE_BASE_CMD + SENS_MAX_POINTS):
            if self.payload['type'] == POINT_TYPE_ARRAY:
                ts = len(self.payload['value'])
            else:
                ts = Cmd.TS[self.payload['type']]
            self.size = 1 + ts
            payload_buffer = pack('>B', self.payload['type']) + \
                                self.__encode_val(self.payload['value'],self.payload['type'],ts)
        else:
            logging.error('[%s] Invalid CMD %d' % (get_func_name(), self.cmd))
            raise Exception('Invalid command')

        return payload_buffer

    def __encode_payload_ans(self):
        if self.cmd == SENS_ITF_VER_CMD:
            self.size = 1
            payload_buffer = pack('>B', self.payload['version'])
        elif self.cmd == SENS_IDENT_CMD:
            self.size = 22
            payload_buffer = pack('>8s8sLBB', \
                                self.__fill_str(self.payload['model'],8), \
                                self.__fill_str(self.payload['manuf'],8), \
                                self.payload['id'], \
                                self.payload['rev'], \
                                self.payload['points'])
        elif self.cmd  >= SENS_POINT_DESC_BASE_CMD and \
             self.cmd  < (SENS_POINT_DESC_BASE_CMD + SENS_MAX_POINTS):
            self.size = 11
            payload_buffer = pack('>8sBBB', \
                                self.__fill_str(self.payload['name'],8), \
                                self.payload['type'], \
                                self.payload['unit'], \
                                self.payload['rights'])
        elif self.cmd >= SENS_POINT_READ_BASE_CMD and \
            self.cmd < (SENS_POINT_READ_BASE_CMD + SENS_MAX_POINTS):
            if self.payload['type'] == POINT_TYPE_ARRAY:
                ts = len(self.payload['value']) 
            else:    
                ts = Cmd.TS[self.payload['type']]
            self.size = 1 + ts
            payload_buffer = pack('>B', self.payload['type']) + \
                                self.__encode_val(self.payload['value'],self.payload['type'],ts)
        elif self.cmd >= SENS_POINT_WRITE_BASE_CMD and \
             self.cmd < (SENS_POINT_WRITE_BASE_CMD + SENS_MAX_POINTS):
            self.size = 0
            payload_buffer = ''
        else:
            logging.error('[%s] Invalid CMD %d' % (get_func_name(), self.cmd))
            raise Exception('Invalid command')

        return payload_buffer

    def __decode_payload_req(self, payload):
        err = True
        if (self.cmd == SENS_ITF_VER_CMD or self.cmd == SENS_IDENT_CMD) and self.size == 0:
            dp = {}
            err = False
        elif (self.cmd >= SENS_POINT_DESC_BASE_CMD and \
              self.cmd < (SENS_POINT_DESC_BASE_CMD + SENS_MAX_POINTS)) or \
             (self.cmd >= SENS_POINT_READ_BASE_CMD and \
              self.cmd < (SENS_POINT_READ_BASE_CMD + SENS_MAX_POINTS)) and self.size == 0:
            dp = {'point': self.cmd}
            err = False
        elif (self.cmd >= SENS_POINT_WRITE_BASE_CMD and \
              self.cmd < (SENS_POINT_WRITE_BASE_CMD + SENS_MAX_POINTS)) and \
              self.size >= 1:
            t = unpack('>B', payload[:1])[0]
            if t >= 0 and t <= POINT_TYPE_ARRAY:
                if t == POINT_TYPE_ARRAY:
                    ts = self.size - 1
                else:
                    ts = Cmd.TS[t]
                if self.size == (1 + ts): 
                    v = self.__decode_val(payload[1:1 + ts],t,ts)
                    dp = { 'type': t, 'value':v, 'point': self.cmd }
                    err = False
        if err:
            logging.error('[%s] Invalid CMD %d with size %d' % (get_func_name(), self.cmd, self.size))
            raise Exception('Invalid payload')

        return dp

    def __decode_payload_ans(self, payload):
        err = True
        if self.cmd == SENS_ITF_VER_CMD and self.size == 1:
            v = unpack('>B',payload[:1])[0]
            dp = { 'version':v }
            err = False
        elif (self.cmd >= SENS_POINT_WRITE_BASE_CMD and \
            self.cmd < (SENS_POINT_WRITE_BASE_CMD + SENS_MAX_POINTS)) and \
            self.size == 0:
            dp = { 'point': self.cmd }
            err = False
        elif self.cmd == SENS_IDENT_CMD and self.size == 22:
            (model,manuf,ident,rev,points) = unpack('>8s8sLBB', payload[:22])
            dp = {'model':model, 'manuf':manuf, 'rev':rev, 'points':points, 'id':ident}
            err = False
        elif (self.cmd >= SENS_POINT_READ_BASE_CMD and \
              self.cmd < (SENS_POINT_READ_BASE_CMD + SENS_MAX_POINTS)) and \
              self.size >= 1:
            t = unpack('>B', payload[:1])[0]
            if t >= 0 and t <= POINT_TYPE_ARRAY:
                if t == POINT_TYPE_ARRAY:
                    ts = self.size - 1
                else:
                    ts = Cmd.TS[t]
                if self.size == (1 + ts):                 
                    v = self.__decode_val(payload[1:1 + ts],t,ts)
                    dp = { 'type': t, 'value':v, 'point': self.cmd }
                    err = False
        elif (self.cmd  >= SENS_POINT_DESC_BASE_CMD and \
              self.cmd < (SENS_POINT_DESC_BASE_CMD + SENS_MAX_POINTS)) and \
              self.size == 11:
            (name,tp,unit,rights) = unpack('>8sBBB',payload[:11])
            dp = {'name':name, 'type':tp, 'unit':unit, 'rights':rights, 'point': self.cmd }
            err = False
        
        if err:
            logging.error('[%s] Invalid CMD %d with size %d' % (get_func_name(), self.cmd, self.size))
            raise Exception('Invalid payload')

        return dp

    def __decode(self, buffer, req):
        if buffer:
            self.buffer = buffer

        if len(self.buffer) < (FRAME_MAX_HDR_SIZE + FRAME_MAX_CRC_SIZE) or \
           len(self.buffer) > FRAME_MAX_CMD_SIZE:
            logging.error('[%s] Invalid buffer size %d < hdr or > max_size' % (get_func_name(), len(self.buffer)))
            return None

        (self.dst, self.src, self.cmd, self.size) = unpack(">BBBB", self.buffer[:FRAME_MAX_HDR_SIZE])

        payload_buffer = self.buffer[FRAME_MAX_HDR_SIZE:-2]
        if len(payload_buffer) != self.size:
            logging.error('[%s] Invalid payload size %d x %d' % (get_func_name(), len(payload_buffer), self.size))
            return None

        self.crc = unpack('>H', self.buffer[-2:])[0]
        crc_calc = crc16([ord(c) for c in self.buffer[:-2]])
        if self.crc != crc_calc:
            logging.error('[%s] Invalid CRC %02X x %02X' % (get_func_name(), self.crc, crc_calc))
            return None

        if req:
            self.payload = self.__decode_payload_req(payload_buffer)
        else:
            self.payload = self.__decode_payload_ans(payload_buffer)

        for k,v in self.payload.iteritems():
            setattr(self, k, v)

        return self

    def __encode(self, req):
        if req:
            payload_buffer = self.__encode_payload_req()
        else:
            payload_buffer = self.__encode_payload_ans()

        hdr = pack('>BBBB', self.dst, self.src, self.cmd, self.size)
        cmd = hdr + payload_buffer
        self.crc = crc16([ord(c) for c in cmd])
        self.buffer = cmd + pack('>H', self.crc)

        return self

    def decode_ans(self, _buffer=''):
        return self.__decode(_buffer, False)

    def decode_req(self, _buffer=''):
        return self.__decode(_buffer, True)

    def encode_ans(self):
        return self.__encode(False)

    def encode_req(self):
        return self.__encode(True)

    def cmd_label(self):
        if self.cmd <= 2:
            label = ['ITF VERSION','SENS IDENT '][self.cmd]
        elif (self.cmd >= SENS_POINT_DESC_BASE_CMD) and (self.cmd < (SENS_POINT_DESC_BASE_CMD + SENS_MAX_POINTS)):
            label = 'POINT DESC '
        elif (self.cmd >= SENS_POINT_READ_BASE_CMD) and (self.cmd < (SENS_POINT_READ_BASE_CMD + SENS_MAX_POINTS)):
            label = 'POINT READ '
        elif (self.cmd >= SENS_POINT_WRITE_BASE_CMD) and (self.cmd < (SENS_POINT_WRITE_BASE_CMD + SENS_MAX_POINTS)):
            label = 'POINT WRITE'
        elif self.cmd == NO_CMD:
            label = 'NO_CMD     '
        else:
            label = 'UNDEF_CMD  '

        return label

    def get_ascii(self):
        s = ''.join(['%02X' % ord(c) for c in self.buffer])
        return s
        
    def __str__(self):
        label = self.cmd_label()
        s = '[' + label + '] '
        s += 'DST %02X SRC %02X REG %02X SIZE %02X CRC %04X PLD %s: ' % (self.dst, self.src, self.cmd, self.size, self.crc, repr(self.payload))
        s += ' ' + self.get_ascii()
        return s

    def beauty(self):
        label = self.cmd_label()
        s = '[' + label + '] '
        s += 'DST %02X SRC %02X REG %02X SIZE %02X CRC %04X:' % (self.dst, self.src, self.cmd, self.size, self.crc)
        s += ' ' + self.get_ascii() + '\n'
        for k,v in self.payload.iteritems():
            s += '%s: %s\n' % (str(k),str(v))
        return s
        
    def __eq__(self, other):
        eq = False
        if self.src == other.src and \
           self.dst == other.dst and \
           self.cmd == other.cmd and \
           self.size == other.size and \
           self.crc == other.crc:
            eq = True
            for k in self.payload:
                if self.payload[k] != other.payload[k]:
                    eq = False
                    break
        return eq

# cmd, dst, src, size, crc, point
# version
# manuf, model, id, points, rev
# name, type, unit, rights
# value 

if __name__ == "__main__":
    #
    # SENS_ITF_VER_CMD
    #
    req_enc = Cmd(cmd=SENS_ITF_VER_CMD,src=0,dst=10).encode_req()
    req_dec = Cmd().decode_req(req_enc.get())
    res_enc = Cmd(cmd=SENS_ITF_VER_CMD,dst=req_dec.src,src=req_dec.dst,version=0x55).encode_ans()
    res_dec = Cmd().decode_ans(res_enc.get())
    
    print(req_enc)
    print(req_dec)
    print(req_enc.get_ascii())
    print(res_enc)
    print(res_dec)
    print(res_enc.get_ascii())

    #
    # SENS_IDENT_CMD
    #
    req_enc = Cmd(cmd=SENS_IDENT_CMD,src=0,dst=10).encode_req()
    req_dec = Cmd().decode_req(req_enc.get())
    res_enc = Cmd(cmd=SENS_IDENT_CMD,dst=req_dec.src,src=req_dec.dst,manuf='UFU/FEELT',model='FHDIC&A',id=0xaabbcc,rev=0x44,points=11).encode_ans()
    res_dec = Cmd().decode_ans(res_enc.get())
    
    print(req_dec)
    print(req_enc.get_ascii())
    print(res_enc)
    print(res_dec)
    print(res_enc.get_ascii())

    #
    # SENS_POINT_DESC_BASE_CMD
    #
    for n in range(0,SENS_MAX_POINTS):
        req_enc = Cmd(cmd=SENS_POINT_DESC_BASE_CMD+n,src=0,dst=10).encode_req()
        req_dec = Cmd().decode_req(req_enc.get())
        name = 'POINT %d' % n
        type = n % (POINT_TYPE_ARRAY + 1)
        unit = n
        rights = n % 4 
        res_enc = Cmd(cmd=SENS_POINT_DESC_BASE_CMD+n,dst=req_dec.src,src=req_dec.dst,name=name,type=type,unit=unit,rights=rights).encode_ans()
        res_dec = Cmd().decode_ans(res_enc.get())
        
        print(req_enc)
        print(req_dec)
        print(req_enc.get_ascii())
        print(res_enc)
        print(res_dec)
        print(res_enc.get_ascii())
    
    #
    # SENS_POINT_READ_BASE_CMD
    #
    for n in range(0,SENS_MAX_POINTS):
        req_enc = Cmd(cmd=SENS_POINT_READ_BASE_CMD+n,src=0,dst=10).encode_req()
        req_dec = Cmd().decode_req(req_enc.get())
        type = n % (POINT_TYPE_ARRAY + 1)
        if type >= POINT_TYPE_FLOAT:
            v = type*3.14
        else:
            v = type + n
        res_enc = Cmd(cmd=SENS_POINT_READ_BASE_CMD+n,dst=req_dec.src,src=req_dec.dst,type=type,value=v).encode_ans()
        res_dec = Cmd().decode_ans(res_enc.get())
        
        print(req_enc)
        print(req_dec)
        print(req_enc.get_ascii())
        print(res_enc)
        print(res_dec)
        print(res_enc.get_ascii())

    # 
    # SENS_POINT_WRITE_BASE_CMD
    #
    for n in range(0,SENS_MAX_POINTS):
        type = n % (POINT_TYPE_ARRAY + 1)
        if type >= POINT_TYPE_FLOAT:
            v = type*3.14
        else:
            v = type + n
        req_enc = Cmd(cmd=SENS_POINT_WRITE_BASE_CMD+n,src=0,dst=10,type=type,value=v).encode_req()
        req_dec = Cmd().decode_req(req_enc.get())
        res_enc = Cmd(cmd=SENS_POINT_WRITE_BASE_CMD+n,dst=req_dec.src,src=req_dec.dst).encode_ans()
        res_dec = Cmd().decode_ans(res_enc.get())
        
        print(req_enc)
        print(req_dec)
        print(req_enc.get_ascii())
        print(res_enc)
        print(res_dec)
        print(res_enc.get_ascii())
    

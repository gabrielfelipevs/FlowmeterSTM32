# -*- coding: latin-1 -*-
import cmd as cmdline
from threading import *
from Queue import Queue, Empty
from serial import *
import time
import logging 
import os
import shelve
import sys
import time
from random import randint
from constants_485 import *
from cmd_485 import *
from serial_485 import *
from serial import *
if EMULATION:
    from serial_pipe import *

logging.basicConfig(filename='master.log',
                    level=logging.DEBUG,
                    format='%(asctime)s %(message)s',
                    datefmt='%I:%M:%S')

cfg_file_path = os.path.dirname(sys.argv[0])
cfg_file_path = os.path.abspath(cfg_file_path)
cfg_file_name = os.path.join(cfg_file_path,'config.db')

try:
    APP_DATA = shelve.open(cfg_file_name, writeback=True)
except Exception as e:
    logging.debug(str(e))
    if os.path.exists(cfg_file_name):
        os.remove(cfg_file_name)
    APP_DATA = shelve.open(cfg_file_name, flag='n', writeback=True)

def clear_queue(q):
    while not q.empty():
        try:
            q.get(False)
        except Empty:
            break
            
class MasterCmd(cmdline.Cmd):
    
    MASTER_ADDR = 0x00
    TMR_OUT = 1.0
    CYC_TMR_OUT = 0.5

    def __init__(self):
        cmdline.Cmd.__init__(self)

        self.prompt = '>> '
        self.stop = Event()
        self.txq = Queue()
        self.rxq = Queue()
        self.spv = Queue()
        self.spv_enabled = False

        try:
            if EMULATION:
                self.serial = SerialPipe(True)
            else:
                self.serial = Serial(SERIAL_MASTER,baudrate=SERIAL_BAUD,timeout=SERIAL_TIMEOUT)
        except Exception as e:
            logging.debug(str(e))
            sys.exit(1)

        self.ser485 = Serial485(self.serial,self.rxq, self.txq, self.stop, True)
        self.ser485.start()

        self.recv = Thread(target=self.recv_data)
        self.recv.start()

    def __conv_hex_int(self,s):
        if s.find('x') >= 0 or s.find('X') >= 0:
            n = int(s,16)
        else:
            n = int(s)
            
        return n
             
    def recv_data(self):
        while not self.stop.is_set():
            try:
                cmd = self.rxq.get(True, 1)
            except Exception as e:
                #logging.info(str(e))
                time.sleep(0.5)
                continue

            self.save_data(cmd)
            
            if self.spv_enabled:
                self.spv.put(cmd)
            else:            
                print(cmd.beauty()[:-1])
                sys.stdout.flush()
              
            self.lastcmd = ''
        
    def save_data(self, cmd):
        dev = str(cmd.src)
        c = cmd.cmd
        
        if dev not in APP_DATA:
            APP_DATA[dev] = {}

        if 'version' not in APP_DATA[dev].keys():
            APP_DATA[dev]['version'] = 0
        
        if 'ident' not in APP_DATA[dev].keys():
            APP_DATA[dev]['ident'] = {}

        if 'desc' not in APP_DATA[dev].keys():
            APP_DATA[dev]['desc'] = {}
        
        if c == SENS_ITF_VER_CMD:
            APP_DATA[dev]['version'] = cmd.version
        elif c == SENS_IDENT_CMD:
            for k,v in cmd.payload.iteritems():
                APP_DATA[dev]['ident'][k] = v
        elif c >= SENS_POINT_DESC_BASE_CMD and c < (SENS_POINT_DESC_BASE_CMD + SENS_MAX_POINTS):
            p = c - SENS_POINT_DESC_BASE_CMD        
            APP_DATA[dev]['desc'][p] = {}
            for k,v in cmd.payload.iteritems():
                APP_DATA[dev]['desc'][p][k] = v

        APP_DATA.sync()
    
    def do_devices(self,buf):
        'List known devices.\nSyntax: devices'
        line = '-'*(3+1+8+1+8+1+8+1+3+1+2+1)
        print(line)
        print('%-3s %-8s %-8s %-8s %-3s %-s' % ('DEV','MANUF','MODEL','ID','REV','PTS'))
        print(line)
        keys = APP_DATA.keys()
        keys.sort()
        for dev in keys:
            if APP_DATA[dev].has_key('ident'):
                manuf  = APP_DATA[dev]['ident']['manuf']
                model  = APP_DATA[dev]['ident']['model']
                id     = APP_DATA[dev]['ident']['id']
                rev    = APP_DATA[dev]['ident']['rev']
                points = APP_DATA[dev]['ident']['points']
                print('%02X  %-8s %-8s %08X %02X  %02X ' % (int(dev),manuf,model,id,rev,points))
            else:
                print('%02X  %-8s %-8s %08X %02X  %02X ' % (int(dev),'-'*8,'-'*8,0,0,0))
        print(line)

    def do_points(self,buf):
        'List known points for specific device.\nSyntax: points dev'
        try:
            dev = self.__conv_hex_int(buf)
        except:
            print("Wrong arguments")
            return  
       
        dev = str(dev)
        if dev in APP_DATA.keys():
            if APP_DATA[dev].has_key('desc'):
                line = '-'*(3+1+8+1+4+1+4+1+6)
                print(line)
                print('%-3s %-8s %-4s %-4s %-6s' % ('NUM','NAME','TYPE','UNIT','RIGHTS'))
                print(line)
                keys = APP_DATA[dev]['desc'].keys()
                keys.sort()
                for p in keys:
                    name  = APP_DATA[dev]['desc'][p]['name']
                    type  = APP_DATA[dev]['desc'][p]['type']
                    unit  = APP_DATA[dev]['desc'][p]['unit']
                    try:
                        rights = APP_DATA[dev]['desc'][p]['rights']
                    except:
                        rights = '??'
                    rights = POINT_RIGHTS[rights]
                    print("%02X  %-8s %02X   %02X   %-2s" % (p,name,type,unit,rights))
                print(line)
            else:
                print('Description not available')
        else:
            print('Device not available')          
                    
    def do_quit(self,buf):
        'Quit program.\nSyntax: quit'
        self.stop.set()
        time.sleep(1)
        if not EMULATION:
            self.serial.close()
        sys.exit(0)

    def do_version(self,buf):
        'Read device interface version.\nSyntax: version dev'
        try:
            dev = self.__conv_hex_int(buf)
        except:
            print("Wrong arguments")
            return        
        c = Cmd(cmd=SENS_ITF_VER_CMD,dst=dev,src=MasterCmd.MASTER_ADDR)
        #logging.debug(c)
        self.txq.put(c)

    def do_ident(self,buf):
        'Read device identification.\nSyntax: ident dev'
        try:
            dev = self.__conv_hex_int(buf)
        except:
            print("Wrong arguments")
            return        
        c = Cmd(cmd=SENS_IDENT_CMD,dst=dev,src=MasterCmd.MASTER_ADDR)
        #logging.debug(c)
        self.txq.put(c)

    def do_clear(self,buf):
        'Clear database.\nSyntax: clear'
        for k in APP_DATA.keys():
            del APP_DATA[k]
        APP_DATA.sync()
        print("Database erased.")

    def do_desc(self,buf):
        'Read point description.\nSyntax: desc dev point'
        try:
            (dev,point) = buf.split()
            dev = self.__conv_hex_int(dev)
            point = self.__conv_hex_int(point)
        except:
            print("Wrong arguments")
            return        
        c = Cmd(cmd=SENS_POINT_DESC_BASE_CMD+point,dst=dev,src=MasterCmd.MASTER_ADDR)
        #logging.debug(c)
        self.txq.put(c)
        
    def __conv_value(self,value,type):
        if type <= POINT_TYPE_INT64:
            value = self.__conv_hex_int(value)
        else:
            value = float(value)
        
        return value
        
    def do_write(self,buf):
        'Write point value.\nSyntax: write dev point value'
        try:
            params = buf.split()
            (dev,point,value) = (params[0],params[1],' '.join(params[2:]))
            dev = self.__conv_hex_int(dev)
            point = self.__conv_hex_int(point)
        except:
            print("Wrong arguments")
            return        
            
        dev = str(dev)
        
        if dev not in APP_DATA.keys():
            print('Device missing')
            return
            
        if not APP_DATA[dev].has_key('desc'):
            print( 'Description missing')
            return
            
        if point not in APP_DATA[dev]['desc']:
            print( 'Point description missing')
            return
        
        unit  = APP_DATA[dev]['desc'][point]['unit']
        type  = APP_DATA[dev]['desc'][point]['type']
        
        if type != POINT_TYPE_ARRAY:
            try:
                value = self.__conv_value(value,type)
            except:
                print( 'Invalid value for type %d' % type)
                return
            
        c = Cmd(cmd=SENS_POINT_WRITE_BASE_CMD+point,dst=int(dev),src=MasterCmd.MASTER_ADDR,value=value,type=type)
        #logging.debug(c)
        self.txq.put(c)        
        
    def do_erase(self,buf):
        'Erase database\nSyntax: erase [dev]'
        if buf:
            try:
                dev = self.__conv_hex_int(buf)
            except:
                print( "Wrong arguments")
                return        
        else:
            dev = 0
        
        if dev == 0:
            for k,v in APP_DATA.iteritems():
                print( 'Erasing %s ...' % k)
                del APP_DATA[k]
        else:
            if APP_DATA.has_key(str(dev)):
                print( 'Erasing %s ...' % dev)
                del APP_DATA[str(dev)]
            else:
                print( 'Invalid device %s.' % dev)
                print( 'Devices available are %s.' % repr(APP_DATA.keys()))
            
        return
        
    def do_read(self,buf):
        'Read point value.\nSyntax: read dev point'
        try:
            (dev,point) = buf.split()
            dev = self.__conv_hex_int(dev)
            point = self.__conv_hex_int(point)
        except:
            print( "Wrong arguments")
            return  
                    
        c = Cmd(cmd=SENS_POINT_READ_BASE_CMD+point,dst=int(dev),src=MasterCmd.MASTER_ADDR)
        #logging.debug(c)
        self.txq.put(c) 
        
    def do_profile(self,buf):
        'Read equipment profile\nSyntax profile dev'
        try:
            dev = self.__conv_hex_int(buf)
        except:
            print( "Wrong arguments")
            return        

        points = 0
        
        self.do_erase(str(dev))
        clear_queue(self.spv)
        self.spv_enabled = True
                                    
        print( '==> Verificando a versão suportada ...')
        self.do_version(str(dev))

        try:
            cmd = self.spv.get(True,MasterCmd.TMR_OUT)
        except Empty:
            print( '==> Xi, a versão falhou ! Melhor começar a debugar ... ')
            return

        if cmd.cmd != SENS_ITF_VER_CMD:
            print( '==> Conversa de surdo e mudo ? Não foi isso que perguntei !')
            return

        if cmd.src != dev or cmd.dst != MasterCmd.MASTER_ADDR:
            print( '==> Endereçamento errado !')
            return
    
        if cmd.payload['version'] != 1:
            print( '==> Versão errada, bye bye !!!')
            return
        
        points += 5
        print( '==> Ok, versão lida. Vai levar 5 pontos por ter conseguido reproduzir')
        print( '==> o comando de versão, compilar, colocar no dispositivo, etc.')
        print( '==> A sua avaliação, de verdade, começa agora !!!')
        time.sleep(1)
        print( "==> Iiiiiiiiiiit's tiiiiiiime !!!" )
        time.sleep(2)
        print( "==> Are you ready ???" )
        time.sleep(3)

        clear_queue(self.spv)
        print( '==> Iniciando a identificação ...')
        self.do_ident(str(dev))
        try:
            cmd = self.spv.get(True,MasterCmd.TMR_OUT)
        except Empty:
            print( '==> Xi, a identificação falhou ! Melhor começar a debugar ... ')
            return
        if cmd.cmd != SENS_IDENT_CMD:
            print( '==> Conversa de surdo e mudo ? Não foi isso que perguntei !')
            return
        if cmd.src != dev or cmd.dst != MasterCmd.MASTER_ADDR:
            print( '==> Endereçamento errado !')
            return

        print("==> Ok, você é o '%s' (id=%d, fabricante='%s', revisão%d)" % \
                    (cmd.payload['model'],cmd.payload['id'],cmd.payload['manuf'],cmd.payload['rev']))
        time.sleep(1)
        np = cmd.payload['points']
        
        if np < 0 or np > 32:
            print( '==> Esse número de pontos não é válido ! Tá de sacanagem comigo ?')
            return 
        points += 10
        print( '==> Vamos investigar agora seus %d ponto(s).' % np)
        print( '==> E, por falar em pontos, você já ganhou %d pontinhos.' % points)
        
        clear_queue(self.spv)
        pd = []
        for p in range(np):
            print( '==> Obtendo descrição para o ponto %d ...' % p)
            self.do_desc('%d %d' % (dev,p))
            try:
                cmd = self.spv.get(True,MasterCmd.TMR_OUT)
            except Empty:
                print( '==> Sem resposta ! Tá meio lerdo, nhein ?')
                return
            if cmd.cmd != SENS_POINT_DESC_BASE_CMD + p:
                print( '==> Conversa de surdo e mudo ? Não foi isso que perguntei !')
                return
            if cmd.src != dev or cmd.dst != MasterCmd.MASTER_ADDR:
                print( '==> Endereçamento errado !')
                return
            if cmd.payload['rights'] < 0 or cmd.payload['rights'] > 2:
                print( '==> Este tipo de direito (%d) não existe, meu jovem !' % cmd.payload['rights'])
                return
            if not cmd.payload['name'].strip():
                print( '==> Nome vazio não vale, meu jovem !')
                return
            if cmd.payload['type'] < 0 or cmd.payload['type'] > 9:
                print( '==> Este tipo (%d) não existe, meu jovem !' % cmd.payload['type'])
                return                               
            print("    Ponto %d (nome '%s',tipo %d, unidade %d, direitos '%s') " % \
                  (p,cmd.payload['name'],cmd.payload['type'],cmd.payload['unit'],POINT_RIGHTS[cmd.payload['rights']]))
            pd.append({'index':p,
                       'name':cmd.payload['name'],
                       'type':cmd.payload['type'],
                       'unit':cmd.payload['unit'],
                       'rights':cmd.payload['rights']})
            time.sleep(2)
        
        points += 10
        print( '==> So far, so good ! Muito bom, já tem %d pontos !' % points)

        print( '==> Afim de faturar mais uns pontinhos ?')
        time.sleep(1)
        print( '==> Vamos fazer um teste de leitura/escrita agora em cada ponto !')
        print( '==> Vai ser bem lento, não se preocupe. Mas repetiremos 5 vezes.')
        time.sleep(1)
        nread = 0
        nwrite = 0
        ntry = 0
        clear_queue(self.spv)
        for n in range(5):
            for p in range(np):
                if pd[p]['rights'] == 1:
                    print( '==> Por favor, habilite a leitura no ponto %s' % pd[p]['name'])
                    return
                
                time.sleep(1)
                print( '==> Lendo valor do ponto %s' % pd[p]['name'])
                self.do_read('%d %d' % (dev,p))
                ntry += 1
                try:
                    cmd = self.spv.get(True,MasterCmd.TMR_OUT)
                except Empty:
                    print( '==> Sem resposta ! Tá meio lerdo, nhein ?')
                    return
                if cmd.cmd != SENS_POINT_READ_BASE_CMD + p:
                    print( '==> Conversa de surdo e mudo ? Não foi isso que perguntei !')
                    return
                if cmd.src != dev or cmd.dst != MasterCmd.MASTER_ADDR:
                    print( '==> Endereçamento errado !')
                    return
                print( '    Valor lido = %s' % (str(cmd.payload['value'])))
                nread += 1
                
                if pd[p]['rights'] == 1 or pd[p]['rights'] == 2:
                    v = randint(0,100)
                    ntry += 1
                    time.sleep(1) 
                    print( '==> Escrevendo no ponto %s o valor %d' % (pd[p]['name'],v))
                    self.do_write('%d %d %d' % (dev,p,v))
                    try:
                        cmd = self.spv.get(True,MasterCmd.TMR_OUT)
                    except Empty:
                        print( '==> Sem resposta ! Tá meio lerdo, nhein ?')
                        return
                    if cmd.cmd != SENS_POINT_WRITE_BASE_CMD + p:
                        print( '==> Conversa de surdo e mudo ? Não foi isso que perguntei !')
                        return
                    if cmd.src != dev or cmd.dst != MasterCmd.MASTER_ADDR:
                        print( '==> Endereçamento errado !')
                        return
                    print( '==> Verificando o valor escrito agora...')
                    time.sleep(1)
                    self.do_read('%d %d' % (dev,p))
                    try:
                        cmd = self.spv.get(True,MasterCmd.TMR_OUT)
                    except Empty:
                        print( '==> Sem resposta ! Tá meio lerdo, nhein ?')
                        return
                    if cmd.cmd != SENS_POINT_READ_BASE_CMD + p:
                        print( '==> Conversa de surdo e mudo ? Não foi isso que perguntei !')
                        return
                    if cmd.src != dev or cmd.dst != MasterCmd.MASTER_ADDR:
                        print( '==> Endereçamento errado !')
                        return
                    print( '    Valor lido = %s' % (str(cmd.payload['value'])))
                    if abs(v - cmd.payload['value']) < 0.001:
                        print( '==> Well done !')
                    else:
                        print( '==> Tem algo de podre no reino da Dinamarca. Valor errado.')
                        return
                        
                    nwrite += 1

                time.sleep(2)
        if nwrite == 0:
            print( '==> Pelo menos um ponto precisa ser de escrita, espertinho !')
            return

        clear_queue(self.spv)
        pa = (100.0*(nread+nwrite))/(ntry)
        print( '==> Seu percentual de acerto foi %2.2f%%' % pa)
        v = round(10*float(nread+nwrite)/(ntry))
        points += v
        print( '==> Mais %d pontos para sua conta, ou seja, %d pontos' % (v,points))

        print( '==> Vamos ver como se sai num teste de leitura cíclica.')
        time.sleep(2)

        nread = 0
        nsupv = 50
        tmrout = MasterCmd.TMR_OUT
        for cr in range(nsupv):
            print( '==> Timeout usado: %d ms' % (tmrout*1000))
            for p in range(np):
                print( '==> Lendo valor do ponto %s' % pd[p]['name'])
                self.do_read('%d %d' % (dev,p))
                try:
                    cmd = self.spv.get(True,tmrout)
                except Empty:
                    print( '==> Sem resposta ! Tá meio lerdo, nhein ?')
                    time.sleep(MasterCmd.TMR_OUT*2)
                    clear_queue(self.spv)
                    continue
                if cmd.cmd != SENS_POINT_READ_BASE_CMD + p:
                    print( '==> Conversa de surdo e mudo ? Não foi isso que perguntei !')
                    time.sleep(MasterCmd.TMR_OUT*2)
                    clear_queue(self.spv)
                    continue
                if cmd.src != dev or cmd.dst != MasterCmd.MASTER_ADDR:
                    print( '==> Endereçamento errado !')
                    time.sleep(MasterCmd.TMR_OUT*2)
                    clear_queue(self.spv)
                    continue
                print( '    Valor lido = %s' % (str(cmd.payload['value'])))
                nread += 1
            tmrout = tmrout - 0.015
        pa = (100.0*nread)/(nsupv*np)
        print( '==> Seu percentual de acerto foi %2.2f%%' % pa)
        v = round(10*float(nread)/(nsupv*np))
        points += v
        print( '==> Mais %d pontos para sua conta, ou seja, %d pontos' % (v,points))
        print( '==> Vamos ver como se sai num teste de escrita cíclica.')
        time.sleep(3)

        clear_queue(self.spv)
        nread = 0
        ntry = 0
        nsupv = 50
        tmrout = MasterCmd.TMR_OUT
        for cr in range(nsupv):
            print( '==> Timeout usado: %d ms' % (tmrout*1000))
            for p in range(np):
                if pd[p]['rights'] == 1 or pd[p]['rights'] == 2:
                    ntry += 1
                    v = randint(0,100) 
                    print( '==> Escrevendo no ponto %s o valor %d' % (pd[p]['name'],v))
                    self.do_write('%d %d %d' % (dev,p,v))
                    try:
                        cmd = self.spv.get(True,tmrout)
                    except Empty:
                        print( '==> Sem resposta ! Tá meio lerdo, nhein ?')
                        time.sleep(MasterCmd.TMR_OUT*2)
                        clear_queue(self.spv)
                        continue
                    if cmd.cmd != SENS_POINT_WRITE_BASE_CMD + p:
                        print( '==> Conversa de surdo e mudo ? Não foi isso que perguntei !')
                        time.sleep(MasterCmd.TMR_OUT*2)
                        clear_queue(self.spv)
                        continue
                    if cmd.src != dev or cmd.dst != MasterCmd.MASTER_ADDR:
                        print( '==> Endereçamento errado !')
                        time.sleep(MasterCmd.TMR_OUT*2)
                        clear_queue(self.spv)
                        continue
                    print( '==> Verificando o valor escrito agora...')

                    self.do_read('%d %d' % (dev,p))
                    try:
                        cmd = self.spv.get(True,tmrout)
                    except Empty:
                        print( '==> Sem resposta ! Tá meio lerdo, nhein ?')
                        time.sleep(MasterCmd.TMR_OUT*2)
                        clear_queue(self.spv)
                        continue
                    if cmd.cmd != SENS_POINT_READ_BASE_CMD + p:
                        print( '==> Conversa de surdo e mudo ? Não foi isso que perguntei !')
                        time.sleep(MasterCmd.TMR_OUT*2)
                        clear_queue(self.spv)
                        continue
                    if cmd.src != dev or cmd.dst != MasterCmd.MASTER_ADDR:
                        print( '==> Endereçamento errado !')
                        time.sleep(MasterCmd.TMR_OUT*2)
                        clear_queue(self.spv)
                        continue
                    print( '    Valor lido = %s' % (str(cmd.payload['value'])))
                    if abs(v - cmd.payload['value']) < 0.001:
                        nread += 1
                    else:
                        print( '==> Tem algo de podre no reino da Dinamarca. Valor errado.')
                        time.sleep(MasterCmd.TMR_OUT*2)
                        clear_queue(self.spv)
                        continue
            tmrout = tmrout - 0.015
        pa = (100.0*nread)/(ntry)
        print( '==> Seu percentual de acerto foi %2.2f%%' % pa)
        v = round(10*float(nread)/(ntry))
        points += v
        print( '==> Mais %d pontos para sua conta, ou seja, %d pontos' % (v,points))
        print( '==> RESULTADO FINAL: %d/55 (%2.2f%%)' % (points,100.0*points/55.0))

        self.spv_enabled = False
        
loop = MasterCmd()
loop.cmdloop()


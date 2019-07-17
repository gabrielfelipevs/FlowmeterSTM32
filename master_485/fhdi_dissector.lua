-- https://wiki.wireshark.org/LuaAPI
-- Entre em "Help->About->Folder" no wireshark para descobrir
-- onde o plugin deve ser copiado.
-- Funciona apenas no Linux (até o momento)

data_types = { "UINT8", "INT8", "UINT16", "INT16", "UINT32", "INT32", "UINT64", "INT64", "FLOAT", "DOUBLE" }
data_size = { 1,1,2,2,4,4,8,8,4,8 }
data_rw = { "RO", "WO", "RW" }

fhdi_proto = Proto("fhdi","FHDI Protocol V1.0")

msg_src    = ProtoField.uint8("fhdi.source","source",base.DEC)
msg_dst    = ProtoField.uint8("fhdi.destination","destination",base.DEC)
msg_reg    = ProtoField.uint8("fhdi.register","register",base.DEC)
msg_size   = ProtoField.uint8("fhdi.size","size",base.DEC)
msg_crc    = ProtoField.uint16("fhdi.crc","crc",base.DEC)
msg_pay    = ProtoField.string("fhdi.payload","payload")
msg_type   = ProtoField.string("fhdi.type","type","Text")
msg_unit   = ProtoField.uint8("fhdi.unit","unit",base.DEC)
msg_rw     = ProtoField.string("fhdi.rights","rights","Text")
msg_err    = ProtoField.string("fhdi.error","error","Text")
msg_name   = ProtoField.string("fhdi.name","name","Text")
msg_model  = ProtoField.string("fhdi.model","model","Text")
msg_manuf  = ProtoField.string("fhdi.manufactor","manufactor","Text")
msg_str    = ProtoField.string("fhdi.value","value","Text")
msg_id     = ProtoField.uint32("fhdi.id","id",base.DEC)
msg_hwrev  = ProtoField.uint8("fhdi.hwrev","hwrev",base.DEC)
msg_points = ProtoField.uint8("fhdi.points","points",base.DEC)
msg_ver    = ProtoField.uint8("fhdi.version","version",base.DEC)

fhdi_proto.fields = {msg_src, msg_dst, msg_reg, msg_size, msg_crc, msg_pay, 
                     msg_type, msg_str, msg_err, msg_name, msg_unit, msg_rw,
                     msg_model, msg_manuf, msg_hwrev, msg_points, msg_id,
                     msg_ver}

function conv_val(buffer,pos,type,size)
    if type == 0 or type == 2 or type == 4 or type == 6 then
        v = buffer(pos,size):uint()
    elseif type == 1 or type == 3 or type == 5 or type == 7 then
        v = buffer(pos,size):int()
    elseif type == 8 or type == 9 then
        v = buffer(pos,size):float()
    end
    
    return v 
end

function cmd_label(reg)
    if reg == 0 then
        label = "ITF VERSION"
    elseif reg == 1 then
        label = "SENS IDENT "
    elseif (reg >= 0x10) and (reg < 0x30) then
        label = "POINT DESC "
    elseif (reg >= 0x30) and (reg < 0x50) then
        label = "POINT READ "
    elseif (reg >= 0x50) and (reg < 0x70) then
        label = "POINT WRITE"
    else
        label = "UNDEF_CMD  "
    end
    
    return label
end

function fhdi_proto.dissector(buffer,pinfo,tree)
    pinfo.cols.protocol = fhdi_proto.name
    
    local n = buffer:len()
    local req
    
    if tonumber(pinfo.src_port) == 0xdead then
        req = true
        req_txt = ' (Req)'
    else
        req = false
        req_txt = ' (Res)'
    end
    
    local subtree = tree:add(fhdi_proto,buffer(),fhdi_proto.description .. req_txt)
    
    if n < 6 then
        subtree:add(msg_str,buffer(),"Frame is too short")
        return
    elseif n > (256+2+4) then
        subtree:add(msg_str,buffer(),"Frame is too big")
    end
    
    subtree:add(msg_dst,buffer(0,1))    
    subtree:add(msg_src,buffer(1,1))
    subtree:add(msg_reg,buffer(2,1))
    subtree:add(msg_size,buffer(3,1))
   
    local dst = buffer(0,1):uint()
    local src = buffer(1,1):uint()    
    local reg = buffer(2,1):uint()    
    local size = buffer(3,1):uint()    
        
    pinfo.cols.info = cmd_label(reg) .. " (" .. src .. " -> " .. dst .. ")" 
   
    -- point desc res
    if (req == false) and (reg >= 0x10 and reg < 0x30) then
        if n >= 17 then
            local name = buffer(4,8):string()
            local dt = buffer(12,1):uint()
            local du = buffer(13,1):uint()
            local rw = buffer(14,1):uint()
            if dt < 10 then
                if rw < 3 then
                    subtree:add(msg_name,buffer(4,8),name)
                    subtree:add(msg_type,buffer(12,1),data_types[dt+1] .. " (" .. dt .. ")")
                    subtree:add(msg_unit,buffer(13,1),du)
                    subtree:add(msg_rw,buffer(14,1),data_rw[rw+1] .. " (" .. rw .. ")")
                else
                    subtree:add(msg_str,buffer(14,1),"Invalid access rights")
                end     
            else
                subtree:add(msg_str,buffer(12,1),"Invalid data type")
            end
        else
            subtree:add(msg_str,buffer(4,n-4),"Frame is too short")
        end
    end


    -- version
    if (req == false and reg == 0) then
        if n >= 7 then
            local ver = buffer(4,1):uint()
            subtree:add(msg_ver,buffer(4,1),ver)
        else
            subtree:add(msg_str,buffer(4,n-6),"Frame is too short")
        end
    end
    
    -- ident
    if (req == false and reg == 1) then
        if n >= 28 then
            local model = buffer(4,8):string()
            local manuf = buffer(12,8):string()
            local id = buffer(20,4):uint()
            local hwrev = buffer(24,1):uint()
            local points = buffer(25,1):uint()

            subtree:add(msg_model,buffer(4,8),model)
            subtree:add(msg_manuf,buffer(12,8),manuf)
            subtree:add(msg_id,buffer(20,4),id)
            subtree:add(msg_hwrev,buffer(24,1),hwrev)
            subtree:add(msg_points,buffer(25,1),points)
        else
            subtree:add(msg_str,buffer(4,n-6),"Frame is too short")
        end
    end
    
    -- write req or read res 
    if (req == true and (reg >= 0x50 and reg < 0x60)) or 
       (req == false and (reg >= 0x30 and reg < 0x50)) then
       if n >= 7 then 
            local dt = buffer(4,1):uint()
            -- check data type before using
            if dt <= 10 then
                local ds = data_size[dt+1]
                if n >= (7+ds) then
                    if dt < 10 then
                        subtree:add(msg_type,buffer(4,1),data_types[dt+1] .. " (" .. dt .. ")")
                        v = conv_val(buffer,5,dt,ds)
                        subtree:add(msg_str,buffer(5,ds),v)
                    else
                        subtree:add(msg_str,buffer(4,1),"Invalid data type")
                    end
                else
                    subtree:add(msg_str,buffer(4,n-6),"Frame is too short")
                end        
            else
                subtree:add(msg_str,buffer(4,n-6),"Invalid data type")
            end        
        else
            subtree:add(msg_str,buffer(4,n-6),"Frame is too short")
        end        
    end
        
    subtree:add(msg_crc,buffer(n-2,2))
end

DissectorTable.get("udp.port"):add(0xdead,fhdi_proto)

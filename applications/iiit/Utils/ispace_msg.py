# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2020, Sam Babu, Godithi.
# All rights reserved.
#
#
# IIIT Hyderabad

#}}}

#Sam

import datetime
import dateutil
from enum import IntEnum
import logging
from random import randint
import json

from volttron.platform.agent import utils
from volttron.platform import jsonrpc

from ispace_utils import mround

utils.setup_logging()
_log = logging.getLogger(__name__)


ROUNDOFF_PRICE_POINT = 0.01
ROUNDOFF_BUDGET = 0.0001
ROUNDOFF_ACTIVE_POWER = 0.0001
ROUNDOFF_ENERGY = 0.0001

class MessageType(IntEnum):
    price_point = 0
    budget = 1
    active_power = 2
    energy = 3
    pass


ISPACE_MSG_ATTRIB_LIST = [ 'msg_type', 'one_to_one'
                            , 'value', 'value_data_type', 'units'
                            , 'price_id', 'isoptimal'
                            , 'src_ip', 'src_device_id'
                            , 'dst_ip', 'dst_device_id'
                            , 'duration', 'ttl', 'ts', 'tz'
                            ]


class ISPACE_Msg:
    ''' iSPACE Message base class
    '''
    #TODO: enchancement - need to add a msg uuid, also convert price_id to use uuid instead for radint
    msg_type = None
    one_to_one = None
    value = None
    value_data_type = None
    units = None
    price_id = None
    isoptimal = None
    #msg_from_remote_device = True if src_ip == local_ip else False
    src_ip = None
    src_device_id = None
    dst_ip = None
    dst_device_id = None
    duration = None
    #TODO: currelty ttl is in seconds, maybe changed to milliseconds for better performance
    ttl = None
    ts = None
    tz  = None
    
    def __init__(self, msg_type = None
                    , one_to_one = None
                    , isoptimal = None
                    , value = None
                    , value_data_type = None
                    , units = None
                    , price_id = None
                    , src_ip = None
                    , src_device_id = None
                    , dst_ip = None
                    , dst_device_id = None
                    , duration = None
                    , ttl = None
                    , ts = None
                    , tz = None
                    ):
        self.msg_type = msg_type
        self.one_to_one = one_to_one
        self.value = value
        self.value_data_type = value_data_type
        self.units = units
        self.price_id = price_id
        self.isoptimal = isoptimal
        self.src_ip = src_ip
        self.src_device_id = src_device_id
        self.dst_ip = dst_ip
        self.dst_device_id = dst_device_id
        self.duration = duration
        self.ttl = ttl
        self.ts = ts
        self.tz = tz
        return
        
    #str overload to return class attributes as str dict
    def __str__(self):
        #_log.debug('__str__()')
        params = self._get_params_dict()
        return str(params)
                
    def _get_params_dict(self):
        params = {}
        params['msg_type'] = self.msg_type
        params['one_to_one'] = self.one_to_one
        params['value'] = self.value
        params['value_data_type'] = self.value_data_type
        params['units'] = self.units
        params['price_id'] = self.price_id
        params['isoptimal'] = self.isoptimal
        params['src_ip'] = self.src_ip
        params['src_device_id'] = self.src_device_id
        params['dst_ip'] = self.dst_ip
        params['dst_device_id'] = self.dst_device_id
        params['duration'] = self.duration
        params['ttl'] = self.ttl
        params['ts'] = self.ts
        params['tz'] = self.tz
        #_log.debug('params: {}'.format(params))
        return params

    def ttl_timeout(self):
        #live for ever
        if self.ttl < 0:
            _log.warning('ttl: {} < 0, do nothing!!!'.format(self.ttl))
            return False
            
        if self.tz == 'UTC':
            ts  = dateutil.parser.parse(self.ts)
            now = dateutil.parser.parse(datetime.datetime.utcnow().isoformat(' ') + 'Z')
            check = True if (now - ts).total_seconds() > self.ttl else False
            return check
        else:
            _log.warning('ttl_timeout(), unknown tz: {}'.format(self.tz))
            return False
            
    def decrement_ttl(self):
        #live for ever
        if self.ttl <= 0:
            _log.warning('ttl: {} < 0, do nothing!!!'.format(self.ttl))
            return False
            
        if self.tz == 'UTC':
            ts  = dateutil.parser.parse(self.ts)
            now = dateutil.parser.parse(datetime.datetime.utcnow().isoformat(' ') + 'Z')
            self.ttl = int((self.ttl - mround((now - ts).total_seconds(), 1)) / 2)
            return True
        else:
            _log.warning('decrement_ttl(), unknown tz: {}'.format(self.tz))
            return False
            
    #check for mandatory fields in the message
    def valid_msg(self, mandatory_fields = []):
        for attrib in mandatory_fields:
            if attrib == 'msg_type' and self.msg_type is None:
                return False
            elif attrib == 'one_to_one' and self.one_to_one is None:
                return False
            elif attrib == 'value' and self.value is None:
                return False
            elif attrib == 'value_data_type' and self.value_data_type is None:
                return False
            elif attrib == 'units' and self.units is None:
                return False
            elif attrib == 'price_id' and self.price_id is None:
                return False
            elif attrib == 'isoptimal' and self.isoptimal is None:
                return False
            elif attrib == 'src_ip' and self.src_ip is None:
                return False
            elif attrib == 'src_device_id' and self.src_device_id is None:
                return False
            elif attrib == 'dst_ip' and self.dst_ip is None:
                return False
            elif attrib == 'dst_device_id' and self.dst_device_id is None:
                return False
            elif attrib == 'duration' and self.duration is None:
                return False
            elif attrib == 'ttl' and self.ttl is None:
                return False
            elif attrib == 'ts' and self.ts is None:
                return False
            elif attrib == 'tz' and self.tz is None:
                return False
        return True
    
    #validate various sanity measure like, valid fields, valid pp ids, ttl expire, etc.,
    def sanity_check_ok(self, hint = None, mandatory_fields = [], valid_price_ids = []):
        if not self.valid_msg(mandatory_fields):
            _log.warning('rcvd a invalid msg, message: {}, do nothing!!!'.format(message))
            return False
            
        #print only if a valid msg
        _log.info('{} Msg: {}'.format(hint, self))
        
        #process msg only if price_id corresponds to these ids
        if valid_price_ids != [] and self.price_id not in valid_price_ids:
            _log.debug('pp_id: {}'.format(self.price_id)
                        + ' not in valid_price_ids: {}, do nothing!!!'.format(valid_price_ids))
            return False
            
        #process msg only if msg is alive (didnot timeout)
        if self.ttl_timeout():
            _log.warning('msg ttl expired, do nothing!!!')
            return False
            
        return True
        
    def check_dst_addr(self, device_id, ip_addr):
        return (False if self.one_to_one and 
                            (device_id != self.dst_device_id or ip_addr != self.dst_ip)
                            else True)
                            
    #return class attributes as json params that can be passed to do_rpc()
    def get_json_params(self, id='123456789'):
        json_package = {
            'jsonrpc': '2.0',
            'id': id,
            'method':'bus_topic',
        }
        json_package['params'] = self._get_params_dict()
        data = json.dumps(json_package)
        return data
        
    #getters
    def get_msg_type(self):
        return self.msg_type
        
    def get_one_to_one(self):
        return self.one_to_one
        
    def get_value(self):
        return self.value
        
    def get_value_data_type(self):
        return self.value_data_type
        
    def get_units(self):
        return self.units
        
    def get_price_id(self):
        return self.price_id
        
    def get_isoptimal(self):
        return self.isoptimal
        
    def get_src_ip(self):
        return self.src_ip
        
    def get_src_device_id(self):
        return self.src_device_id
        
    def get_dst_ip(self):
        return self.dst_ip
        
    def get_dst_device_id(self):
        return self.dst_device_id
        
    def get_duration(self):
        return self.duration
        
    def get_ttl(self):
        return self.ttl
        
    def get_ts(self):
        return self.ts
        
    def get_tz(self):
        return self.tz
        
    #setters
    def set_msg_type(self, msg_type):
        #_log.debug('set_msg_type()')
        self.msg_type = msg_type
        
    def set_one_to_one(self, one_to_one):
        self.one_to_one = one_to_one
        
    def set_value(self, value):
        #_log.debug('set_value()')
        #_log.debug('self.msg_type: {}, MessageType.price_point: {}'.format(self.msg_type, MessageType.price_point))
        if self.msg_type == MessageType.price_point:
            tmp_value = mround(value, ROUNDOFF_PRICE_POINT)
            self.value = 0 if tmp_value <= 0 else 1 if tmp_value >= 1 else tmp_value
        elif self.msg_type == MessageType.budget:
            self.value = mround(value, ROUNDOFF_BUDGET)
        elif self.msg_type == MessageType.active_power:
            self.value = mround(value, ROUNDOFF_ACTIVE_POWER)
        elif self.msg_type == MessageType.energy:
            self.value = mround(value, ROUNDOFF_ENERGY)
        else:
            _log.debug('else')
            self.value = value
        
    def set_value_data_type(self, value_data_type):
        self.value_data_type = value_data_type
        
    def set_units(self, units):
        self.units = units
        
    def set_price_id(self, price_id):
        self.price_id = price_id
        
    def set_isoptimal(self, isoptimal):
        self.isoptimal = isoptimal
        
    def set_src_ip(self, src_ip):
        self.src_ip = src_ip
        
    def set_src_device_id(self, src_device_id):
        self.src_device_id = src_device_id
        
    def set_dst_ip(self, dst_ip):
        self.dst_ip = dst_ip
        
    def set_dst_device_id(self, dst_device_id):
        self.dst_device_id = dst_device_id
        
    def set_duration(self, duration):
        self.duration = duration
        
    def set_ttl(self, ttl):
        self.ttl = ttl
        
    def set_ts(self, ts):
        self.ts = ts
        
    def set_tz(self, tz):
        self.tz = tz
        
    pass
    
    
#create a MessageType.energy ISPACE_Msg and publishs the message to local bus
def ted_helper(self, agent_id, ted, pp_msg, pub_topic, new_ttl=10):
    msg_type = MessageType.energy
    one_to_one = pp_msg.get_one_to_one()
    isoptimal = pp_msg.get_isoptimal()
    value = ted
    value_data_type = 'float'
    units = 'kWh'
    price_id = pp_msg.get_price_id()
    src_ip = pp_msg.get_dst_ip()
    src_device_id = pp_msg.get_dst_device_id()
    dst_ip = pp_msg.get_src_ip()
    dst_device_id = pp_msg.get_src_device_id()
    duration = pp_msg.get_duration()
    ttl = new_ttl
    ts = datetime.datetime.utcnow().isoformat(' ') + 'Z'
    tz = 'UTC'
    
    tap_msg = ISPACE_Msg(msg_type, one_to_one
                        , isoptimal, value, value_data_type, units, price_id
                        , src_ip, src_device_id, dst_ip, dst_device_id
                        , duration, ttl, ts, tz)
                        
    pub_msg = tap_msg.get_json_params(agent_id)
    _log.debug('publishing to local bus topic: {}'.format(pub_topic))
    _log.debug('Msg: {}'.format(pub_msg))
    publish_to_bus(self, pub_topic, pub_msg)
    return
    
#create a MessageType.active_power ISPACE_Msg and publishs the message to local bus
def tap_helper(self, agent_id, tap, pp_msg, pub_topic, new_ttl=10):
    msg_type = MessageType.active_power
    one_to_one = pp_msg.get_one_to_one()
    isoptimal = pp_msg.get_isoptimal()
    value = tap
    value_data_type = 'float'
    units = 'Wh'
    price_id = pp_msg.get_price_id()
    src_ip = pp_msg.get_dst_ip()
    src_device_id = pp_msg.get_dst_device_id()
    dst_ip = pp_msg.get_src_ip()
    dst_device_id = pp_msg.get_src_device_id()
    duration = pp_msg.get_duration()
    ttl = new_ttl
    ts = datetime.datetime.utcnow().isoformat(' ') + 'Z'
    tz = 'UTC'
    
    tap_msg = ISPACE_Msg(msg_type, one_to_one
                        , isoptimal, value, value_data_type, units, price_id
                        , src_ip, src_device_id, dst_ip, dst_device_id
                        , duration, ttl, ts, tz)
                        
    pub_msg = tap_msg.get_json_params(agent_id)
    _log.debug('publishing to local bus topic: {}'.format(pub_topic))
    _log.debug('Msg: {}'.format(pub_msg))
    publish_to_bus(self, pub_topic, pub_msg)
    return
    
def check_for_msg_type(message, msg_type):
    data = jsonrpc.JsonRpcData.parse(message).params
    try:
        if data['msg_type'] == msg_type:
            return True
    except Exception:
        _log.warning('key attrib: "msg_type", not available in the message.')
        pass
    return False
    
#converts bus message into an ispace_msg
def parse_bustopic_msg(message, mandatory_fields = []):
    #data = json.loads(message)
    data = jsonrpc.JsonRpcData.parse(message).params
    return _parse_data(data, mandatory_fields)
    
#converts jsonrpc_msg into an ispace_msg
def parse_jsonrpc_msg(message, mandatory_fields = []):
    data = jsonrpc.JsonRpcData.parse(message).params
    return _parse_data(data, mandatory_fields)
    
def _update_value(new_msg, attrib, new_value):
    if attrib == 'msg_type':
        new_msg.set_msg_type(new_value)
    elif attrib == 'one_to_one':
        new_msg.set_one_to_one(new_value if new_value is not None else False)
    elif attrib == 'value':
        new_msg.set_value(new_value)
    elif attrib == 'value_data_type':
        new_msg.set_value_data_type(new_value)
    elif attrib == 'units':
        new_msg.set_units(new_value)
    elif attrib == 'price_id':
        new_msg.set_price_id(new_value if new_value is not None else randint(0, 99999999))
    elif attrib == 'isoptimal':
        new_msg.set_isoptimal(new_value)
    elif attrib == 'src_ip':
        new_msg.set_src_ip(new_value)
    elif attrib == 'src_device_id':
        new_msg.set_src_device_id(new_value)
    elif attrib == 'dst_ip':
        new_msg.set_dst_ip(new_value)
    elif attrib == 'dst_device_id':
        new_msg.set_dst_device_id(new_value)
    elif attrib == 'duration':
        new_msg.set_duration(new_value if new_value is not None else 3600)
    elif attrib == 'ttl':
        new_msg.set_ttl(new_value if new_value is not None else -1)
    elif attrib == 'ts':
        new_msg.set_ts(new_value if new_value is not None
                                else datetime.datetime.utcnow().isoformat(' ') + 'Z')
    elif attrib == 'tz':
        new_msg.set_tz(new_value if new_value is not None else 'UTC')
    return
    
def _parse_data(data, mandatory_fields = []):
    #_log.debug('_parse_data()')
    #_log.debug('data: [{}]'.format(data))
    #_log.debug('datatype: {}'.format(type(data)))
    
    #ensure msg_type attrib is set first
    try:
        msg_type =  data['msg_type']
    except KeyError:
        _log.warning('key attrib: "msg_type", not available in the data.'
                        + ' Setting to default({})'.format(MessageType.price_point))
        msg_type = MessageType.price_point
        pass
        
    #TODO: select class msg_type based on msg_type, instead of base class
    new_msg = ISPACE_Msg()
    _update_value(new_msg, 'msg_type', msg_type)
    
    #if list is empty, parse all attributes
    if mandatory_fields == []:
        #if the attrib is not found in the data, throws a keyerror exception
        _log.warning('mandatory_fields to check against is empty!!!')
        for attrib in ISPACE_MSG_ATTRIB_LIST:
            _update_value(new_msg, attrib, data[attrib])
    else:
        #if the madatory field is not found in the data, throws a keyerror exception
        for attrib in mandatory_fields:
            _update_value(new_msg, attrib, data[attrib])
            
        #do a second pass to also get attribs not in the mandatory_fields
        #if attrib not found, catch the exception(pass) and continue with next attrib
        for attrib in ISPACE_MSG_ATTRIB_LIST:
            if attrib not in mandatory_fields:
                try:
                    _update_value(new_msg, attrib, data[attrib])
                except KeyError:
                    _log.warning('key: {}, not available in the data'.format(attrib))
                    pass
                
    return new_msg
        
        
class ISPACE_Msg_OptPricePoint(ISPACE_Msg):
    def __init__(self):
        super().__init__(self, MessageType.price_point, True)
        return
    pass
    
    
class ISPACE_Msg_BidPricePoint(ISPACE_Msg):
    def __init__(self):
        super().__init__(self, MessageType.price_point, False)
        return
    pass
    
    
class ISPACE_Msg_ActivePower(ISPACE_Msg):
    def __init__(self):
        super().__init__(self, MessageType.active_power, True)
        return
    pass
    
    
class ISPACE_Msg_Energy(ISPACE_Msg):
    def __init__(self):
        super().__init__(self, MessageType.energy, False)
        return
    pass
    
    
class ISPACE_Msg_Budget(ISPACE_Msg):
    def __init__(self):
        super().__init__(self, MessageType.budget)
        return
    pass
    
    
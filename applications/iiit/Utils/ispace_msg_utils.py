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
from ispace_msg import ISPACE_Msg, MessageType

utils.setup_logging()
_log = logging.getLogger(__name__)


ROUNDOFF_PRICE_POINT = 0.01
ROUNDOFF_BUDGET = 0.0001
ROUNDOFF_ACTIVE_POWER = 0.0001
ROUNDOFF_ENERGY = 0.0001


#create a MessageType.energy ISPACE_Msg
def ted_helper(pp_msg, device_id, discovery_address, ted, new_ttl=10):
    msg_type = MessageType.energy
    one_to_one = pp_msg.get_one_to_one()
    isoptimal = pp_msg.get_isoptimal()
    value = ted
    value_data_type = 'float'
    units = 'kWh'
    price_id = pp_msg.get_price_id()
    src_ip = discovery_address
    src_device_id = device_id
    dst_ip = pp_msg.get_src_ip()
    dst_device_id = pp_msg.get_src_device_id()
    duration = pp_msg.get_duration()
    ttl = new_ttl
    ts = datetime.datetime.utcnow().isoformat(' ') + 'Z'
    tz = 'UTC'
    return ISPACE_Msg(msg_type, one_to_one
                        , isoptimal, value, value_data_type, units, price_id
                        , src_ip, src_device_id, dst_ip, dst_device_id
                        , duration, ttl, ts, tz)
                        
#create a MessageType.active_power ISPACE_Msg
def tap_helper(pp_msg, device_id, discovery_address, tap, new_ttl=10):
    msg_type = MessageType.active_power
    one_to_one = pp_msg.get_one_to_one()
    isoptimal = pp_msg.get_isoptimal()
    value = tap
    value_data_type = 'float'
    units = 'Wh'
    price_id = pp_msg.get_price_id()
    src_ip = discovery_address
    src_device_id = device_id
    dst_ip = pp_msg.get_src_ip()
    dst_device_id = pp_msg.get_src_device_id()
    duration = pp_msg.get_duration()
    ttl = new_ttl
    ts = datetime.datetime.utcnow().isoformat(' ') + 'Z'
    tz = 'UTC'
    return ISPACE_Msg(msg_type, one_to_one
                        , isoptimal, value, value_data_type, units, price_id
                        , src_ip, src_device_id, dst_ip, dst_device_id
                        , duration, ttl, ts, tz)
                        
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
        
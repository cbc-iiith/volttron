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
import logging
import sys
import uuid
from random import random, randint

from volttron.platform.vip.agent import Agent, Core, PubSub, compat, RPC
from volttron.platform.agent import utils
from volttron.platform.messaging import topics, headers as headers_mod
from volttron.platform.agent.known_identities import (
    MASTER_WEB, VOLTTRON_CENTRAL, VOLTTRON_CENTRAL_PLATFORM)
from volttron.platform import jsonrpc
from volttron.platform.jsonrpc import (
        INVALID_REQUEST, METHOD_NOT_FOUND,
        UNHANDLED_EXCEPTION, UNAUTHORIZED,
        UNABLE_TO_REGISTER_INSTANCE, DISCOVERY_ERROR,
        UNABLE_TO_UNREGISTER_INSTANCE, UNAVAILABLE_PLATFORM, INVALID_PARAMS,
        UNAVAILABLE_AGENT)

import time
import gevent
import gevent.event

from ispace_utils import publish_to_bus, retrive_details_from_vb
from ispace_msg import ISPACE_Msg, MessageType
from ispace_msg_utils import parse_bustopic_msg, check_for_msg_type

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.4'


def pricecontroller(config_path, **kwargs):
    config = utils.load_config(config_path)
    vip_identity = config.get('vip_identity', 'iiit.pricecontroller')
    # This agent needs to be named iiit.pricecontroller. Pop the uuid id off the kwargs
    kwargs.pop('identity', None)
    
    Agent.__name__ = 'PriceController_Agent'
    return PriceController(config_path, identity=vip_identity, **kwargs)
    
    
class PriceController(Agent):
    '''Price Controller
    '''
    _period_read_data = None
    _period_process_pp = None
    _period_process_loop = None
    
    _vb_vip_identity = None
    _topic_price_point_us = None
    _topic_price_point = None
    _topic_energy_demand_ds = None
    _topic_energy_demand = None
    
    _agent_disabled = False
    _pp_optimize_option = None
    _topic_extrn_pp = None
    _pca_mode = None
    
    _device_id = None
    _discovery_address = None
    
    def __init__(self, config_path, **kwargs):
        super(PriceController, self).__init__(**kwargs)
        _log.debug("vip_identity: " + self.core.identity)
        
        self.config = utils.load_config(config_path)
        return
        
    @Core.receiver('onsetup')
    def setup(self, sender, **kwargs):
        _log.info(self.config['message'])
        self._agent_id = self.config['agentid']
        
        self._period_read_data = self.config.get('period_read_data', 30)
        self._period_process_pp = self.config.get('period_process_pp', 10)
        self._period_process_loop = self.config.get('period_process_loop', 2)
        
        #local device_ids
        self._local_device_ids = []
        self._local_opt_ap = []
        self._local_bid_ed = []
        
        #ds device ids, opt_ap --> act_pwr@opt_pp, bid_ed --> bid_energy_demand@bid_pp
        self._ds_device_ids = []
        self._ds_opt_ap = []
        self._ds_bid_ed = []

        self._device_id = None
        self._ip_addr = None
        self._discovery_address = None
        
        self._vb_vip_identity = self.config.get('vb_vip_identity', 'iiit.volttronbridge')
        self._topic_price_point_us = self.config.get('pricePoint_topic_us', 'us/pricepoint')
        self._topic_price_point = self.config.get('pricePoint_topic', 'building/pricepoint')
        self._topic_energy_demand_ds = self.config.get('energyDemand_topic_ds', 'ds/energydemand')
        self._topic_energy_demand = self.config.get('energyDemand_topic', 'building/energydemand')
        
        self._agent_disabled = False
        self._pca_mode = self.config.get('pca_mode', 'ONLINE')
        self._pp_optimize_option = self.config.get('pp_optimize_option', 'PASS_ON_PP')
        self._topic_extrn_pp = self.config.get('extrn_optimize_pp_topic', 'pca/pricepoint')
        return
        
    @Core.receiver('onstart')
    def startup(self, sender, **kwargs):
        _log.debug('startup()')
        
        self._us_senders_list = ['iiit.volttronbridge', 'iiit.pricepoint']
        self._ds_senders_list = ['iiit.volttronbridge']
        _local_senders_list = []
        
        _log.debug('registering rpc routes')
        self.vip.rpc.call(MASTER_WEB, 'register_agent_route'
                            ,r'^/PriceController'
                            , "rpc_from_net"
                            ).get(timeout=30)
                            
        self.tmp_pp_msg = None
        
        self.us_opt_pp_msg = None
        self.us_bid_pp_msg = None
        self.act_opt_pp_msg = None
        self.act_bid_pp_msg = None
        self.local_opt_pp_msg = None
        self.local_bid_pp_msg = None
        
        self.external_vip_identity = None
        
        #subscribing to _topic_price_point_us
        self.vip.pubsub.subscribe("pubsub", self._topic_price_point_us, self.on_new_us_pp)
        
        #subscribing to ds energy demand, vb publishes ed from registered ds to this topic
        self.vip.pubsub.subscribe("pubsub", self._topic_energy_demand_ds, self.on_ds_ed)

        #at regular interval publish total active power. does not wait to receive from all ds
        self.core.periodic(self._period_read_data, self.publish_opt_tap, wait=None)
        #at regular interval check if all ds ted received, if so publish and stop
        self.core.periodic(self._period_process_loop, self.publish_bid_ted, wait=None)
        
        #subscribing to topic_price_point_extr
        self.vip.pubsub.subscribe("pubsub", self._topic_extrn_pp, self.on_new_extrn_pp)
        
        self.core.periodic(self._period_process_loop, self.process_loop, wait=None)
        
        retrive_details_from_vb(self)
        return
        
    @Core.receiver('onstop')
    def onstop(self, sender, **kwargs):
        _log.debug('onstop()')
        _log.debug('un registering rpc routes')
        
        del self._local_device_ids[:]
        del self._local_opt_ap[:]
        del self._local_bid_ed[:]
        del self._ds_device_ids[:]
        del self._ds_opt_ap[:]
        del self._ds_bid_ed[:]

        self.vip.rpc.call(MASTER_WEB, 'unregister_all_agent_routes').get(timeout=10)
        return
        
    @Core.receiver('onfinish')
    def onfinish(self, sender, **kwargs):
        _log.debug('onfinish()')
        return
        
    @RPC.export
    def rpc_from_net(self, header, message):
        _log.debug('rpc_from_net()')
        result = False
        try:
            rpcdata = jsonrpc.JsonRpcData.parse(message)
            _log.debug('rpc method: {}'.format(rpcdata.method))
            _log.debug('rpc params: {}'.format(rpcdata.params))
            if rpcdata.method == "rpc_disable_agent":
                result = self._disable_agent(message)
            elif rpcdata.method == "rpc_set_pp_optimize_option":
                result = self._set_pp_optimize_option(message)
            elif rpcdata.method == "rpc_register_opt_agent":
                result = self._register_external_opt_agent(message)
            elif rpcdata.method == "rpc_ping":
                result = True
            else:
                return jsonrpc.json_error(rpcdata.id, METHOD_NOT_FOUND,
                                            'Invalid method {}'.format(rpcdata.method))
            return jsonrpc.json_result(rpcdata.id, result)
        except KeyError as ke:
            print(ke)
            return jsonrpc.json_error(rpcdata.id, INVALID_PARAMS,
                                        'Invalid params {}'.format(rpcdata.params))
        except Exception as e:
            print(e)
            return jsonrpc.json_error(rpcdata.id, UNHANDLED_EXCEPTION, e)
            
    def _disable_agent(self, message):
        disable_agent = jsonrpc.JsonRpcData.parse(message).params['disable_agent']
        if disable_agent in [True, False]:
            self._agent_disabled = disable_agent
            result = True
        else:
            result = 'Invalid option'
        return result
        
    def _set_pp_optimize_option(self, message):
        option = jsonrpc.JsonRpcData.parse(message).params['option']
        if option in ['PASS_ON_PP'
                        , 'DEFAULT_OPT'
                        , 'EXTERN_OPT'
                        ]:
            self._pp_optimize_option = option
            result = True
        else:
            result = 'Invalid option'
        return result
        
    def _register_opt_agent(self, message):
        external_vip_identity = jsonrpc.JsonRpcData.parse(message).params['vip_identity']
        if external_vip_identity is not None:
            self.external_vip_identity = external_vip_identity
            result = True
        else:
            result = 'Invalid option'
        return result
    
    #subscribe to local/ed (i.e., ted) from the controller (building/zone/smarthub controller)
    def on_new_ed(self, peer, sender, bus,  topic, headers, message):
        # parse message & validate
        # (_ed, _is_opt, _ed_pp_id) = get_data(message)
        
        #if _ed_pp_id = us_opt_pp_id:
        #   #ed for global opt, do nothing
        #   #vb moves this ed to next level
        #   return
        
        #if pass_on and _ed_pp_id in us_pp_ids[]
        #   #do nothing
        #   #vb moves this ed to next level
        #   return
        
        #if extrn_opt and _ed_pp_id in extrn_pp_ids[]
        #   publish_ed(extrn/ed, _ed, _ed_pp_id)
        #   return
        
        # if default_opt and _ed_pp_id in local_pp_ids[]
        #       (new_pp, new_pp_isopt) = _compute_new_price()
        #       if new_pp_isopt
        #           #local optimal reached
        #           publish_ed(local/ed, _ed, us_bid_pp_id)
        #           #if next level accepts this bid, the new target is this ed
        #       based on opt conditon _computeNewPrice can publish new bid_pp or 
        # and save data to self._ds_bid_ed
        
        return
        
    def on_new_extrn_pp(self, peer, sender, bus,  topic, headers, message):
        self.tmp_bustopic_msg = None
        valid_senders_list = [self.external_vip_identity]
        if not self._validate_pp_msg(sender, valid_senders_list, message):
            #cleanup and return
            self.tmp_bustopic_msg = None
            return
        pp_msg = self.tmp_bustopic_msg
        self.tmp_bustopic_msg = None      #release self.tmp_bustopic_msg
        
        self.act_pp_msg = pp_msg
        
        if pp_msg.get_isoptimal():
            self.local_opt_pp_msg = pp_msg
        else:
            self.local_bid_pp_msg = pp_msg
        
        if self._pp_optimize_option == "EXTERN_OPT":
            pub_topic =  self._topic_price_point
            pub_msg = pp_msg.get_json_params(self._agent_id)
            _log.debug('publishing to local bus topic: {}'.format(pub_topic))
            _log.debug('Msg: {}'.format(pub_msg))
            publish_to_bus(self, pub_topic, pub_msg)
            return True
            
        return
        
    def on_new_us_pp(self, peer, sender, bus,  topic, headers, message):
        self.tmp_bustopic_msg = None
        
        #check message type before parsing
        success = check_for_msg_type(message, MessageType.price_point)
        if not success:
            return False
            
        valid_senders_list = self._us_senders_list
        minimum_fields = ['msg_type', 'value', 'value_data_type', 'units', 'price_id']
        validate_fields = ['value', 'value_data_type', 'units', 'price_id', 'isoptimal', 'duration', 'ttl']
        valid_price_ids = []
        if not self._valid_bustopic_msg(sender, valid_senders_list
                                                , minimum_fields
                                                , validate_fields
                                                , valid_price_ids
                                                , message):
            #cleanup and return
            self.tmp_bustopic_msg = None
            return
            
        pp_msg = self.tmp_bustopic_msg
        self.tmp_bustopic_msg = None      #release self.tmp_bustopic_msg
        
        # at times we operate on two pp_msg from us 
        # example: opt_pp --> currently in progess and bid_pp --> new bidding has been initiated)
        # The latest pp_msg is considered as active pp_msg
        # However, responses from to old opt_pp/bid_pp 
        self.act_pp_msg = pp_msg
        
        #keep a track of us pp_msg
        if sender == self._vb_vip_identity:
            if pp_msg.get_isoptimal():
                self.us_opt_pp_msg = pp_msg
            else:
                self.us_bid_pp_msg = pp_msg
        #keep a track of local pp_msg
        elif sender == 'iiit.pricepoint':
            if pp_msg.get_isoptimal():
                self.local_opt_pp_msg = pp_msg
            else:
                self.local_bid_pp_msg = pp_msg
                
        if self._pp_optimize_option == "PASS_ON_PP":
            pub_topic =  self._topic_price_point
            pub_msg = pp_msg.get_json_params(self._agent_id)
            _log.debug('publishing to local bus topic: {}'.format(pub_topic))
            _log.debug('Msg: {}'.format(pub_msg))
            publish_to_bus(self, pub_topic, pub_msg)
            return True
            
        if self._pp_optimize_option == "EXTERN_OPT":
            pub_topic =  self.topic_extrn_pp
            pub_msg = pp_msg.get_json_params(self._agent_id)
            _log.debug('publishing to local bus topic: {}'.format(pub_topic))
            _log.debug('Msg: {}'.format(pub_msg))
            publish_to_bus(self, pub_topic, pub_msg)
            return True

        if pp_msg.get_isoptimal() or self._pp_optimize_option == "EXTERN_OPT":
            pub_topic =  (self.topic_extrn_pp
                            if self._pp_optimize_option == "EXTERN_OPT"
                            else self._topic_price_point )
            pub_msg = pp_msg.get_json_params(self._agent_id)
            _log.debug('publishing to local bus topic: {}'.format(pub_topic))
            _log.debug('Msg: {}'.format(pub_msg))
            publish_to_bus(self, pub_topic, pub_msg)
            return True
            
        if self._pp_optimize_option == "DEFAULT_OPT":
            #list for pp_msg
            new_pp_msg = self._computeNewPrice()
            self.local_bid_pp_msg = new_pp_msg
            _log.info('new bid pp_msg: {}'.format(new_pp_msg))
            
            pub_topic =  self._topic_price_point
            pub_msg = new_pp_msg.get_json_params(self._agent_id)
            _log.debug('publishing to local bus topic: {}'.format(pub_topic))
            _log.debug('Msg: {}'.format(pub_msg))
            publish_to_bus(self, pub_topic, pub_msg)
            return True
            
    #validate incomming bus topic message and convert to self.tmp_bustopic_msg if check pass
    def _valid_bustopic_msg(self, sender, valid_senders_list, minimum_fields
                                    , validate_fields, valid_price_ids, message):
        _log.debug('_validate_bustopic_msg()')
        pp_msg = None
        
        #check if this agent is not diabled
        if self._agent_disabled:
            _log.info("self.agent_disabled: " + str(self._agent_disabled) + ", do nothing!!!")
            return False
            
        if sender not in valid_senders_list:
            _log.debug('sender: {}'.format(sender)
                        + ' not in sender list: {}, do nothing!!!'.format(valid_senders_list))
            return False
            
            
        try:
            _log.debug('message: {}'.format(message))
            minimum_fields = ['value', 'value_data_type', 'units', 'price_id']
            pp_msg = parse_bustopic_msg(message, minimum_fields)
            #_log.info('self.pp_msg: {}'.format(self.pp_msg))
        except KeyError as ke:
            _log.exception(ke)
            _log.exception(jsonrpc.json_error('NA', INVALID_PARAMS,
                    'Invalid params {}'.format(rpcdata.params)))
            return False
        except Exception as e:
            _log.exception(e)
            _log.exception(jsonrpc.json_error('NA', UNHANDLED_EXCEPTION, e))
            return False
            
        hint = ('New Price Point' if check_for_msg_type(message, MessageType.price_point)
               else 'New Active Power' if check_for_msg_type(message, MessageType.active_power)
               else 'New Energy Demand' if check_for_msg_type(message, MessageType.energy_demand)
               else 'Unknown Msg Type')

        validate_fields = ['value', 'value_data_type', 'units', 'price_id', 'isoptimal', 'duration', 'ttl']
        valid_price_ids = []
        #validate various sanity measure like, valid fields, valid pp ids, ttl expiry, etc.,
        if not self.pp_msg.sanity_check_ok(hint, validate_fields, valid_price_ids):
            _log.warning('Msg sanity checks failed!!!')
            return False
        self.tmp_bustopic_msg = pp_msg
        return True
    
    #compute new bid price point for every local device and ds devices
    #return list for pp_msg
    def _compute_new_price(self):
        _log.debug('_computeNewPrice()')
        #TODO: implement the algorithm to compute the new price
        #      based on walras algorithm.
        #       config.get (optimization cost function)
        #       based on some initial condition like ed, us_new_pp, etc, compute new_pp
        #       publish to bus
        
        #optimization algo
        #   ed_target = r% x ed_optimal
        #   EPSILON = 10       #deadband
        #   gamma = stepsize
        #   max_iter = 20        (assuming each iter is 30sec and max time spent is 10 min)
        #   
        #   count_iter = 0
        #   pp_old = pp_opt
        #   pp_new = pp_old
        #   do while (ed_target - ed_current > EPSILON)
        #       if (count_iter < max_iter)
        #            pp_new = pp_old + gamma(ed_current - ed_previous)
        #            pp_old = pp_new
        #    
        #   pp_opt = pp_new
        #
        #       iterate till optimization condition satistifed
        #       when new pp is published, the new ed for all devices is accumulated by on_new_ed()
        #       once all the eds are received call this function again
        #       publish the new optimal pp
        
        #price id of the new pp
        #set one_to_one = false if the pp is same for all the devices,
        #                 true if the pp pp is different for every device
        #             However, use the SAME price id for all pp_msg
        #
        msg_type = MessageType.price_point
        one_to_one = True
        value_data_type = 'float'
        units = 'cents'
        price_id = randint(0, 99999999)
        src_ip = None
        src_device_id = None
        duration = self.act_pp_msg.get_duration()
        ttl = 10
        ts = datetime.datetime.utcnow().isoformat(' ') + 'Z'
        tz = 'UTC'
        
        device_list = []
        dst_ip = []
        dst_device_id = []
        
        old_pricepoint = []
        old_ted = []
        target = 0
        
        self._target_acheived = False
        new_pricepoint = self._some_cost_fn(old_pricepoint, old_ted, target)
        isoptimal = True if self._target_acheived else False

        pp_messages = []
        for device_idx in device_list:
            pp_msg = ISPACE_Msg(msg_type, one_to_one
                    , isoptimal, new_pricepoint[device_idx], value_data_type, units, price_id
                    , src_ip, src_device_id, dst_ip[device_idx], dst_device_id[device_idx]
                    , duration, ttl, ts, tz)
            pp_messages.insert(pp_msg)
        return pp_messages
        
    def _some_cost_fn(self, old_pricepoint, old_ted, target):
        new_pricepoints = []
        return new_pricepoints
        
    #perodically run this function to check if ted from all ds received or ted_timed_out
    def process_loop(self):
        #may be some devices may have disconnected
        #      i.e., devices_count >= len(vb_devices_count)
        #       reconcile the device ids and match ds_ted[] with device_ids[]
        vb_local_devices = self.vip.rpc.call(self.vb_vip_identity
                                                , 'get_local_devices'
                                                ).get(timeout=10)
        vb_ds_devices = self.vip.rpc.call(self.vb_vip_identity
                                                , 'get_ds_devices'
                                                ).get(timeout=10)
        
        rcvd_all_local_bid_ed = self._rcvd_all_local_bid_ed(vb_local_devices)
        rcvd_all_ds_bid_ed = self._rcvd_all_ds_bid_ed(vb_ds_devices)
        us_bid_pp_timeout = self._us_bid_pp_timeout()
        
        if ( (not (rcvd_all_ds_bid_ed and rcvd_all_local_bid_ed) ) 
                and not us_bid_pp_timeout()
                ):
            _log.debug('not all bids received and not yet timeout!!!.' 
                        + ' rcvd_all_ds_bid_ed: {}'.format(rcvd_all_ds_bid_ed)
                        + ' and rcvd_all_local_bid_ed: {}'.format(rcvd_all_local_bid_ed)
                        + ' or us_bid_pp_timeout: {}'.format(us_bid_pp_timeout)
                        + ', will try again in ' + str(self._period_process_loop))
            return
                
        if self._pca_mode == 'ONLINE' and self._pp_optimize_option == 'PASS_ON_PP':
            publish_bid_ted()
            return
            '''
            elif self._pca_mode == 'ONLINE' and self._pp_optimize_option == 'DEFAULT_OPT':
                pp_messages = self._compute_new_price()
                self._ds_bid_ed[:] = []
                #publish these pp_messages
                return
            elif self._pca_mode == 'ONLINE' and self._pp_optimize_option == 'EXTERN_OPT':
                return
            elif self._pca_mode == 'STANDALONE' and self._pp_optimize_option == 'PASS_ON_PP':
                return
            elif self._pca_mode == 'STANDALONE' and self._pp_optimize_option == 'DEFAULT_OPT':
                return
            elif self._pca_mode == 'STANDALONE' and self._pp_optimize_option == 'EXTERN_OPT':
                return
            '''
        else:
            #not implemented
            _log.warning('publish_bid_ted() not implemented'
                            + 'pca_mode: {}'.format(self._pca_mode)
                            + 'optimize option: {}'.format(self._pp_optimize_option)
                            )
            pass
        return
        
    def _us_bid_pp_timeout(self):
        #TODO: need to return much before actual timeout, can't wait till actual timeout
        ts  = dateutil.parser.parse(self._bid_pp_ts)
        now = dateutil.parser.parse(datetime.datetime.utcnow().isoformat(' ') + 'Z')
        return (True if (now - ts).total_seconds() > self._bid_pp_ttl else False)
        
    def _rcvd_all_local_bid_ed(self, vb_local_devics):
        vb_local_devices_count = len(vb_local_devics)
        local_devices_count = len(list(set(vb_local_devics) & set(self._local_bid_ed)))
        return (True if local_devices_count == vb_local_devices_count else False)
        
    def _rcvd_all_ds_bid_ed(self, vb_ds_devices):
        vb_ds_devices_count = len(vb_ds_devices)
        ds_devices_count = len(list(set(vb_ds_devices)&set(self._ds_bid_ed)))
        return (True if ds_devices_count == vb_ds_devices_count else False)
        
    def on_ds_ed(self, peer, sender, bus,  topic, headers, message):
        # 1. validate message
        # 2. check againt valid pp ids
        # 3. if (src_id_add == self._ip_addr) and opt_pp:
        # 5.         local_opt_tap      #local opt active power
        # 6. elif (src_id_add == self._ip_addr) and not opt_pp:
        # 7.         local_bid_ted      #local bid energy demand
        # 8. elif opt_pp:
        #             ds_opt_tap
        #    else
        #               ds_bid_ted
        # 9.      if opt_pp
        #post ed to us only if pp_id corresponds to these ids 
        #      (i.e., ed for either us opt_pp_id or bid_pp_id)
        
        self.tmp_bustopic_msg = None
        
        #handle only ap or ed type messages
        success_ap = check_for_msg_type(message, MessageType.active_power)
        if not success_ap:
            success_ed = check_for_msg_type(message, MessageType.energy_demand)
            if not success_ed:
                return
                
        #unique senders list
        #valid_senders_list = list(set(self._ds_senders_list + self._local_senders_list))
        valid_senders_list = self._ds_senders_list + self._local_senders_list
        minimum_fields = ['msg_type', 'value', 'value_data_type', 'units', 'price_id']
        validate_fields = ['value', 'value_data_type', 'units', 'price_id', 'isoptimal', 'duration', 'ttl']
        valid_price_ids = self._get_valid_price_ids()
        if not self._valid_bustopic_msg(sender, valid_senders_list
                                                , minimum_fields
                                                , validate_fields
                                                , valid_price_ids
                                                , message):
            #cleanup and return
            self.tmp_bustopic_msg = None
            return
            
        pp_msg = self.tmp_bustopic_msg
        self.tmp_bustopic_msg = None      #release self.tmp_bustopic_msg

        if self._pp_optimize_option == "PASS_ON_PP":
            price_id = pp_msg.get_price_id()
            device_id = pp_msg.get_src_device_id()
            
            #MessageType.active_power
            if (success_ap and  price_id == self.us_opt_pp_msg.get_price_id()):
                #put data to local_tap bucket
                if device_id in get_vb_local_device_ids():
                    idx = self._get_local_device_idx(device_id)
                    self._local_opt_ap[idx] = pp_msg.get_value()
                    return
                #put data to ds_tap bucket
                elif device_id in get_vb_ds_device_ids():
                    idx = self._get_ds_device_idx(device_id)
                    self._ds_opt_ap[idx] = pp_msg.get_value()
                    return
            #MessageType.energy_demand
            elif (success_ed and price_id == self.us_bid_pp_msg.get_price_id()):
                #put data to ds_tap bucket
                if device_id in get_vb_local_device_ids():
                    idx = self._get_local_device_idx(device_id)
                    self._local_bid_ed[idx] = pp_msg.get_value()
                    return
                #put data to ds_tap bucket
                elif device_id in get_vb_ds_device_ids():
                    idx = self._get_ds_device_idx(device_id)
                    self._ds_bid_ed[idx] = pp_msg.get_value()
                    return
        return
        
    def _get_local_device_idx(device_id):
        if device_id not in self._local_device_ids:
            self._local_device_ids.append(device_id)
            idx = self._ds_device_ids.index(device_id)
            self._local_opt_ap.insert(idx, 0.0)
            self._local_bid_ed.insert(idx, 0.0)
        return self._local_device_ids.index(device_id)
        
    def _get_ds_device_idx(device_id):
        if device_id not in self._ds_device_ids:
            self._ds_device_ids.append(device_id)
            idx = self._ds_device_ids.index(device_id)
            self._ds_opt_ap.insert(idx, 0.0)
            self._ds_bid_ed.insert(idx, 0.0)
        return self._ds_device_ids.index(device_id)
        
    def _get_valid_price_ids(self):
        price_ids = []
        if self._pp_optimize_option == "PASS_ON_PP":
            price_ids = [self.us_opt_pp_msg.get_price_id()
                            , self.us_bid_pp_msg.get_price_id()
                            ]
        return price_ids
        
    def publish_opt_tap(self):
        #_log.debug('publish_opt_tap()')
        #since time period much larger (default 30s, i.e, 2 reading per min)
        #need not wait to receive active power from all devices
        #any ways this is used for monitoring purpose and the readings are averaged over a period
        if self._pca_mode == 'ONLINE' and self._pp_optimize_option == 'PASS_ON_PP':
            pp_msg = self.us_opt_pp_msg
        else:
            #not implemented
            _log.warning('publish_opt_tap() not implemented'
                            + 'pca_mode: {}'.format(self._pca_mode)
                            + 'optimize option: {}'.format(self._pp_optimize_option)
                            )
            return
            
        #create a MessageType.active_power ISPACE_Msg
        tap_msg = tap_helper(pp_msg
                            , self._device_id
                            , self._discovery_address
                            , self._calc_total_act_pwr()
                            , self._period_read_data
                            )
                            
        #publish the new price point to the local message bus
        pub_topic = self._topic_energy_demand + "/" + self._device_id
        pub_msg = tap_msg.get_json_params(self._agent_id)
        _log.debug('publishing to local bus topic: {}'.format(pub_topic))
        _log.debug('Msg: {}'.format(pub_msg))
        publish_to_bus(self, pub_topic, pub_msg)
        return
        
    def _calc_total_act_pwr(self):
        #compute total active power (tap)
        tap = 0
        for ap in self._local_opt_ap: tap += ap
        for ap in self._ds_opt_ap: tap += ap
        return tap
        
    def publish_bid_ted(self):
        #_log.debug('publish_bid_ted()')
        #already checked if all bids are received or timeout
        #create a MessageType.energy ISPACE_Msg
        if self._pca_mode == 'ONLINE' and self._pp_optimize_option == 'PASS_ON_PP':
            pp_msg = self.us_bid_pp_msg
        else:
            #not implemented
            _log.warning('publish_bid_ted() not implemented'
                            + 'pca_mode: {}'.format(self._pca_mode)
                            + 'optimize option: {}'.format(self._pp_optimize_option)
                            )
            return
        
        ted_msg = ted_helper(self.us_bid_pp_msg
                            , self._device_id
                            , self._discovery_address
                            , self._calc_total_energy_demand()
                            , self._period_read_data
                            )
                            
        #publish the new price point to the local message bus
        pub_topic = self._topic_energy_demand
        pub_msg = ted_msg.get_json_params(self._agent_id)
        _log.debug('publishing to local bus topic: {}'.format(pub_topic))
        _log.debug('Msg: {}'.format(pub_msg))
        publish_to_bus(self, pub_topic, pub_msg)
        return
        
    def _calc_total_energy_demand(self):
        #compute total energy demand (ted)
        ted = 0
        for ed in self._local_bid_ed: ted += ed
        for ed in self._ds_opt_ed: ted += ed
        return ted
        
        
def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(pricecontroller)
    except Exception as e:
        print (e)
        _log.exception('unhandled exception')
        
        
if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        pass
        
        
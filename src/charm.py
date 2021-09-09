#!/usr/bin/env python3
# Copyright 2021 Ubuntu
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

import ipaddress
import logging
import os
import interface_openstack_loadbalancer.loadbalancer as ops_lb_interface
import interface_hacluster.ops_ha_interface as ops_ha_interface
import subprocess
from pathlib import Path

import charmhelpers.core.host as ch_host
import charmhelpers.core.templating as ch_templating

import ops_openstack.adapters
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus

import ops_openstack.core
logger = logging.getLogger(__name__)


def reload_service(service_name) -> None:
    """Reload service.

    :param service_name: Name of service to reload
    :type service_name: str
    """
    subprocess.check_call(['systemctl', 'reload', service_name])


class LoadbalancerAdapter(
        ops_openstack.adapters.OpenStackOperRelationAdapter):
    """Adapter for Loadbalanceer interface."""

    @property
    def endpoints(self):
        """List of registered endpoints.

        :returns: List of endpoint dicts
        :rtype: str
        """
        endpoint_data = self.relation.get_loadbalancer_requests()['endpoints']
        _endpoints = {
            service.replace("-", "_"): config
            for service, config in endpoint_data.items()}
        return _endpoints


class OpenstackLoadbalancerAdapters(
        ops_openstack.adapters.OpenStackRelationAdapters):
    """Collection of relation adapters."""

    relation_adapters = {
        'loadbalancer': LoadbalancerAdapter,
    }


class OpenstackLoadbalancerCharm(ops_openstack.core.OSBaseCharm):
    """Charm the service."""

    PACKAGES = ['haproxy']
    HAPROXY_CONF = Path('/etc/haproxy/haproxy.cfg')
    HAPROXY_SERVICE = 'haproxy'
    RESTART_MAP = {
        str(HAPROXY_CONF): [HAPROXY_SERVICE]}
    RFUNCS = {
        HAPROXY_SERVICE: reload_service}

    _stored = StoredState()

    def __init__(self, *args):
        """Setup interfaces and observers"""
        super().__init__(*args)
        self.api_eps = ops_lb_interface.OSLoadbalancerProvides(
            self,
            'loadbalancer')
        self.adapters = OpenstackLoadbalancerAdapters((self.api_eps,), self)
        self.ha = ops_ha_interface.HAServiceRequires(self, 'ha')
        self.framework.observe(
            self.api_eps.on.lb_requested,
            self._process_lb_requests)
        self.framework.observe(self.ha.on.ha_ready, self._configure_hacluster)
        self.unit.status = ActiveStatus()
        self._stored.is_started = True

    def _get_binding_subnet_map(self):
        bindings = {}
        for binding_name in self.meta.extra_bindings.keys():
            network = self.model.get_binding(binding_name).network
            bindings[binding_name] = [i.subnet for i in network.interfaces]
        return bindings

    @property
    def vips(self):
        return self.config.get('vip').split()

    def _get_space_vip_mapping(self):
        bindings = {}
        for binding_name, subnets in self._get_binding_subnet_map().items():
            bindings[binding_name] = [
                vip
                for subnet in subnets
                for vip in self.vips
                if ipaddress.ip_address(vip) in subnet]
        return bindings

    def _send_loadbalancer_response(self):
        # May do tls termination in future
        protocol = 'http'
        for binding, vips in self._get_space_vip_mapping().items():
            eps = self.api_eps.get_loadbalancer_requests()['endpoints']
            for name, data in eps.items():
                self.api_eps.loadbalancer_ready(
                    name,
                    binding,
                    vips,
                    data['frontend_port'],  # Requested port is honoured atm
                    protocol)
        self.api_eps.advertise_loadbalancers()

    def _configure_hacluster(self, _):
        vip_config = self.config.get('vip')
        if not vip_config:
            logging.warn("Cannot setup vips, vip config missing")
            return
        for vip in vip_config.split():
            self.ha.add_vip(self.model.app.name, vip)
        self.ha.add_init_service(self.model.app.name, 'haproxy')
        self.ha.bind_resources()

    def _configure_haproxy(self):
        @ch_host.restart_on_change(self.RESTART_MAP,
                                   restart_functions=self.RFUNCS)
        def _render_configs():
            for config_file in self.RESTART_MAP.keys():
                ch_templating.render(
                    os.path.basename(config_file),
                    config_file,
                    self.adapters)
        logging.info("Rendering config")
        _render_configs()

    def _process_lb_requests(self, event):
        self._configure_haproxy()
        self._send_loadbalancer_response()

if __name__ == "__main__":
    main(OpenstackLoadbalancerCharm)

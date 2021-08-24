#!/usr/bin/env python3
# Copyright 2021 Ubuntu
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following post for a quick-start guide that will help you
develop a new k8s charm using the Operator Framework:

    https://discourse.charmhub.io/t/4208
"""
import collections
import jinja2
import json
import logging
import interface_api_endpoints
import interface_hacluster.ops_ha_interface as ops_ha_interface
import subprocess

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus

import ops_openstack.core
logger = logging.getLogger(__name__)

# defaults
#   log global
#   option log-health-checks
#   timeout connect 5s
#   timeout client 50s
#   timeout server 450s

# frontend dashboard_front
#   mode http
#   bind *:80
#   option httplog
#   redirect scheme https code 301 if !{ ssl_fc }

# frontend dashboard_front_ssl
#   mode tcp
#   bind *:443
#   option tcplog
#   default_backend dashboard_back_ssl

# backend dashboard_back_ssl
#   mode tcp
#   option httpchk GET /
#   http-check expect status 200
#   server x <HOST>:<PORT> check-ssl check verify none
#   server y <HOST>:<PORT> check-ssl check verify none
#   server z <HOST>:<PORT> check-ssl check verify none

HAPROXY_TEMPLATE = """
defaults
  log global
  option log-health-checks
  timeout connect 5s
  timeout client 50s
  timeout server 450s

{% for service, service_config in endpoints.items() %}
frontend {{service}}_front
  mode tcp
  bind *:{{service_config.frontend_port}}
  option tcplog
  default_backend {{service}}_back

backend {{service}}_back
  mode tcp
  option httpchk GET /
  http-check expect status 200
{% for unit in service_config.members %}
  server {{ unit.unit_name }} {{ unit.backend_ip }}:{{ unit.backend_port }} check-ssl check verify none
{% endfor %}
{% endfor %}
"""

class OpenstackLoadbalancerCharm(ops_openstack.core.OSBaseCharm):
    """Charm the service."""

    PACKAGES = ['haproxy']
    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.api_eps = interface_api_endpoints.APIEndpointsProvides(self)
        self.ha = ops_ha_interface.HAServiceRequires(self, 'ha')
        self.framework.observe(self.api_eps.on.ep_ready, self._configure_haproxy)
        self.framework.observe(self.ha.on.ha_ready, self._configure_hacluster)
        self.unit.status = ActiveStatus()

    def _get_config_from_relation(self):
        app_config_keys = ['check-type', 'frontend-port']
        unit_config_keys = ['backend-ip', 'backend-port']
        app_data = {
            'endpoints': {}} 
        for relation in self.model.relations['loadbalancer']:
            unit = list(relation.units)[0]
            for ep in json.loads(relation.data[unit].get('endpoints', '[]')):
                service_type = ep['service-type'].replace('-', '_')
                app_data['endpoints'][service_type] = {
                    'members': []}
                for config in app_config_keys:
                    app_data['endpoints'][service_type][config.replace('-', '_')] = ep[config]
        unit_data = {}
        for relation in self.model.relations['loadbalancer']:
            for unit in relation.units:
                eps = json.loads(relation.data[unit].get('endpoints', '[]'))
                for service in app_data['endpoints'].keys():
                    unit_config = {}
                    for ep in eps:
                        if ep['service-type'].replace('-', '_') == service:
                            unit_config = ep
                    unit_config['unit_name'] = unit.name.replace('/', '_')
                    unit_config = {k.replace('-', '_'):v for k,v in unit_config.items()}
                    app_data['endpoints'][service]['members'].append(unit_config)
        return app_data

    def _get_haproxy_config(self):
        """Generate squid.conf contents."""
        jinja_env = jinja2.Environment(loader=jinja2.BaseLoader())
        jinja_template = jinja_env.from_string(HAPROXY_TEMPLATE)
        ctxt = {}
        ctxt.update(self._get_config_from_relation())
        ctxt = {k.replace('-', '_'): v for k, v in ctxt.items()}
        return jinja_template.render(**ctxt)

    def _configure_hacluster(self, event):
        for vip in self.config.get('vip').split():
            self.ha.add_vip(self.model.app.name, vip)
        self.ha.add_init_service(self.model.app.name, 'haproxy')
        self.ha.bind_resources()

    def _configure_haproxy(self, event):
        with open('/etc/haproxy/haproxy.cfg', 'w') as f:
            contents = self._get_haproxy_config()
            f.write(contents)
        self._stored.is_started =  True
        subprocess.check_call(['systemctl', 'restart', 'haproxy'])

if __name__ == "__main__":
    main(OpenstackLoadbalancerCharm)

#!/usr/bin/env python3

# Copyright 2021 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import collections
import functools
import json
import logging

from ops.charm import CharmBase, RelationEvent
from ops.framework import (
    StoredState,
    EventBase,
    ObjectEvents,
    EventSource,
    Object)


UNIT_DATA_KEYS = ['backend-port', 'backend-ip']
APP_DATA_KEYS = ['frontend-port', 'check-type']
SERVICE_NAME_KEY = 'service-name'
PUBLIC_SPACE = "public"
ADMIN_SPACE = "admin"
INTERNAL_SPACE = "internal"


class EndpointRelationReadyEvent(EventBase):
    pass


class EndpointRequestsEvent(EventBase):
    pass


class EndpointConfiguredEvent(EventBase):
    pass


class APIEndpointsEvents(ObjectEvents):
    ep_relation_ready = EventSource(EndpointRelationReadyEvent)
    ep_requested = EventSource(EndpointRequestsEvent)
    ep_configured = EventSource(EndpointConfiguredEvent)


class APIEndpointsRequires(Object):

    on = APIEndpointsEvents()
    _stored = StoredState()

    def __init__(self, charm: CharmBase, relation_name: str) -> None:
        """Initialise class

        :param charm: The charm using this interface.
        :param relation_name: Model alias map to store
        """
        super().__init__(charm, relation_name)
        self.charm = charm
        self.relation_name = relation_name
        self.framework.observe(
            charm.on[self.relation_name].relation_changed,
            self._on_relation_changed)
        self.framework.observe(
            charm.on[self.relation_name].relation_joined,
            self._on_relation_joined)

    def _on_relation_joined(self, event: RelationEvent) -> None:
        """Handle relation joined event

        :param event: Event triggering action
        """
        self.on.ep_relation_ready.emit()

    def _on_relation_changed(self, event: RelationEvent) -> None:
        """Handle relation changed event

        :param event: Event triggering action
        """
        self._process_response()

    def _update_relation_data(self, relation_data: dict,
                              service: dict) -> dict:
        """Update or add service to requests

        The endpoints are a list of dicts for both app data and unit data. This
        method updates an entry in the list if it already exists or adds a new
        one it it does not.

        :param relation_data: Relation data dict.
        :param service: Service data
        """
        endpoints = [e
                     for e in json.loads(relation_data.get('endpoints', '[]'))
                     if e['service-name'] != service['service-name']]
        endpoints.append(service)
        return endpoints

    def request_loadbalancer(self, service_name: str, lb_port: int,
                             backend_port: int, backend_ip: str,
                             lb_check_type: str = 'http') -> None:
        """Send request for loadbalancer.

        :param service_name: Name of service
        :param lb_port: Port the loadbalancer should bind to.
        :param backend_port: Port backend is bound to.
        :param backend_ip: IP address backend is listening on.
        :param lb_check_type: NEEDS UPDATING
        """
        unit_data = {
            'service-name': service_name,
            'backend-port': backend_port,
            'backend-ip': backend_ip}
        app_data = {
            'service-name': service_name,
            'frontend-port': lb_port,
            'check-type': lb_check_type}
        for relation in self.model.relations[self.relation_name]:
            if self.model.unit.is_leader():
                relation.data[self.model.app]['endpoints'] = json.dumps(
                    self._update_relation_data(
                        relation.data[self.model.app],
                        app_data),
                    sort_keys=True)
            relation.data[self.model.unit]['endpoints'] = json.dumps(
                self._update_relation_data(
                    relation.data[self.model.unit],
                    unit_data),
                sort_keys=True)

    def get_frontend_data(self) -> dict:
        """Get the details of the loadbalancers that have been created.

        Construct a dictionary of created listeners.
        """
        if not self.model.relations[self.relation_name]:
            return
        data = None
        for relation in self.model.relations[self.relation_name]:
            data = relation.data[relation.app].get('frontends')
            if data:
                data = json.loads(data)
        return data

    def _process_response(self) -> None:
        """Check for a complete response from loadbalancer"""
        if self.get_frontend_data():
            self.on.ep_configured.emit()

    def get_lb_endpoint(self, service_name: str, binding: str):
        """Return the loadbalancer details on a given binding.

        :param service_name: Name of service
        :param binding: Port the loadbalancer should bind to.
        """
        endpoint = None
        lb_endpoints = self.get_frontend_data()
        if lb_endpoints:
            endpoint = lb_endpoints.get(service_name, {}).get(binding)
        return endpoint

    get_lb_public_endpoint = functools.partialmethod(
        get_lb_endpoint,
        binding=PUBLIC_SPACE)
    get_lb_internal_endpoint = functools.partialmethod(
        get_lb_endpoint,
        binding=INTERNAL_SPACE)
    get_lb_admin_endpoint = functools.partialmethod(
        get_lb_endpoint,
        binding=ADMIN_SPACE)


class APIEndpointsProvides(Object):

    on = APIEndpointsEvents()
    _stored = StoredState()

    def __init__(self, charm: str,
                 relation_name: str = 'loadbalancer') -> None:
        """Initialise class

        :param charm: The charm using this interface.
        :param relation_name: Model alias map to store
        """
        super().__init__(charm, relation_name)
        self.relation_name = relation_name
        self.framework.observe(
            charm.on["loadbalancer"].relation_changed,
            self._on_relation_changed)
        self.charm = charm
        self.service_listeners = collections.defaultdict(dict)

    def _on_relation_changed(self, event: RelationEvent) -> None:
        """Handle relation changed event

        :param event: Event triggering action
        """
        self.on.ep_requested.emit()

    def _get_frontends(self) -> dict:
        """Get a dict of requested loadbalancers.

        Examine the application data bag across all relations to construct
        a dictionary of all requested loadbalancers and their settings.
        """
        ep_data = collections.defaultdict(dict)
        for relation in self.model.relations[self.relation_name]:
            endpoints = json.loads(
                relation.data[relation.app].get('endpoints', '[]'))
            for ep in endpoints:
                for config in APP_DATA_KEYS:
                    _config_key = config.replace('-', '_')
                    ep_data[ep[SERVICE_NAME_KEY]][_config_key] = ep[config]
        return {'endpoints': ep_data}

    def _get_backends(self) -> dict:
        """Get a dict of registered backends.

        Examine the unit data bag across all relations to construct
        a dictionary of all registered backends for a service.
        """
        members = collections.defaultdict(list)
        for relation in self.model.relations['loadbalancer']:
            units = sorted(
                [u for u in relation.units],
                key=lambda unit: unit.name)
            for unit in units:
                unit_name = unit.name.replace('/', '_')
                eps = json.loads(relation.data[unit].get('endpoints', '[]'))
                for ep in eps:
                    member_data = {
                        'unit_name': unit_name}
                    for config in UNIT_DATA_KEYS:
                        _config_key = config.replace('-', '_')
                        member_data[_config_key] = ep[config]
                    members[ep['service-name']].append(member_data)
        return members

    def get_loadbalancer_requests(self) -> dict:
        """Return dict of loadbalancer requests.

        Match loadbalancer requests with advertised backends.
        """
        ep_data = self._get_frontends()
        for ep, members in self._get_backends().items():
            if ep_data['endpoints'].get(ep):
                ep_data['endpoints'][ep]['members'] = members
        return ep_data

    def _get_requested_service_names(self, relation) -> list:
        """A list of loadbalancer service name requests for a relation"""
        requests = json.loads(
            relation.data[relation.app].get('endpoints', '[]'))
        return [e['service-name'] for e in requests]

    def loadbalancer_ready(self, service_name: str, space: str, ips: list,
                           port: int, protocol: str) -> None:
        """Register a loadbalancer as ready."""
        self.service_listeners[service_name][space] = {
            'ip': ips,
            'port': port,
            'protocol': protocol}

    def advertise_loadbalancers(self) -> None:
        """Advertise a loadbalancers as ready down the requesting relation

        Tell requesters whether their requested  loadbalacers are ready.
        """
        if not self.model.unit.is_leader():
            logging.info("Not sending response, not leader")
            return
        for relation in self.model.relations[self.relation_name]:
            _listeners = {}
            for service_name in self._get_requested_service_names(relation):
                _listeners[service_name] = self.service_listeners.get(
                    service_name)
            relation.data[self.model.app]['frontends'] = json.dumps(
                _listeners,
                sort_keys=True)

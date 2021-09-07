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

import copy
import json
import unittest
import sys
sys.path.append('lib')  # noqa
sys.path.append('src')  # noqa
from ops.testing import Harness
from ops.charm import CharmBase
import interface_api_endpoints
from unit_tests.manage_test_relations import (
    add_loadbalancer_relation,
    add_loadbalancer_response,
    add_requesting_dash_relation,
    add_requesting_glance_relation,
    loadbalancer_data,
)


class TestAPIEndpointsRequires(unittest.TestCase):

    class MyCharm(CharmBase):

        def __init__(self, *args):
            super().__init__(*args)
            self.seen_events = []
            self.ingress = interface_api_endpoints.APIEndpointsRequires(
                self,
                'loadbalancer')
            self.framework.observe(
                self.ingress.on.ep_requested,
                self._log_event)
            self.framework.observe(
                self.ingress.on.ep_configured,
                self._log_event)
            self.framework.observe(
                self.ingress.on.ep_relation_ready,
                self._register_ep)

        def _log_event(self, event):
            self.seen_events.append(type(event).__name__)

        def _register_ep(self, event):
            self._log_event(event)
            self.seen_events.append(type(event).__name__)
            self.ingress.request_loadbalancer(
                'ceph-dashboard',
                8443,
                8443,
                '10.0.0.10',
                lb_check_type='https')

    def setUp(self):
        super().setUp()
        self.harness = Harness(
            self.MyCharm,
            meta='''
name: my-charm
requires:
  loadbalancer:
    interface: api-endpoints
'''
        )
        self.eps = [{
            'service-name': 'ceph-dashboard',
            'frontend-port': 8443,
            'backend-port': 8443,
            'backend-ip': '10.0.0.10',
            'check-type': 'https'}]
#        self.loadbalancer_data = {
#            'ceph-dashboard': {
#                'admin': {
#                    'ip': ['10.20.0.101'],
#                    'port': 8443,
#                    'protocol': 'http'},
#                'internal': {
#                    'ip': ['10.30.0.101'],
#                    'port': 8443,
#                    'protocol': 'http'},
#                'public': {
#                    'ip': ['10.10.0.101'],
#                    'port': 8443,
#                    'protocol': 'http'}}}
#
#    def add_loadbalancer_relation(self):
#        rel_id = self.harness.add_relation(
#            'loadbalancer',
#            'service-loadbalancer')
#        self.harness.add_relation_unit(
#            rel_id,
#            'service-loadbalancer/0')
#        self.harness.update_relation_data(
#            rel_id,
#            'service-loadbalancer/0',
#            {'ingress-address': '10.0.0.3'})
#        return rel_id
#
#    def add_loadbalancer_response(self, rel_id):
#        self.harness.update_relation_data(
#            rel_id,
#            'service-loadbalancer',
#            {
#                'frontends': json.dumps(
#                    self.loadbalancer_data)})

    def test_init(self):
        self.harness.begin()
        self.assertEqual(
            self.harness.charm.ingress.relation_name,
            'loadbalancer')

    def test__on_relation_changed(self):
        self.harness.begin()
        self.harness.set_leader()
        rel_id = add_loadbalancer_relation(self.harness)
        unit_rel_data = self.harness.get_relation_data(
            rel_id,
            'my-charm/0')
        app_rel_data = self.harness.get_relation_data(
            rel_id,
            'my-charm')
        self.assertEqual(
            json.loads(unit_rel_data['endpoints']),
            [{
                'service-name': 'ceph-dashboard',
                'backend-port': 8443,
                'backend-ip': '10.0.0.10'}])
        self.assertEqual(
            json.loads(app_rel_data['endpoints']),
            [{
                'service-name': 'ceph-dashboard',
                'frontend-port': 8443,
                'check-type': 'https'}])

    def test_register_second_ep(self):
        self.harness.begin()
        self.harness.set_leader()
        rel_id = add_loadbalancer_relation(self.harness)
        new_eps = copy.deepcopy(self.eps)
        new_eps.append({
            'service-name': 'ceph-api',
            'frontend-port': 9443,
            'backend-port': 9443,
            'backend-ip': '10.0.0.10',
            'check-type': 'https'})
        self.harness.charm.ingress.request_loadbalancer(
            'ceph-api',
            9443,
            9443,
            '10.0.0.10',
            lb_check_type='https')
        unit_rel_data = self.harness.get_relation_data(
            rel_id,
            'my-charm/0')
        app_rel_data = self.harness.get_relation_data(
            rel_id,
            'my-charm')
        self.assertEqual(
            json.loads(unit_rel_data['endpoints']),
            [
                {
                    'service-name': 'ceph-dashboard',
                    'backend-port': 8443,
                    'backend-ip': '10.0.0.10'},
                {
                    'service-name': 'ceph-api',
                    'backend-port': 9443,
                    'backend-ip': '10.0.0.10'}])
        self.assertEqual(
            json.loads(app_rel_data['endpoints']),
            [
                {
                    'service-name': 'ceph-dashboard',
                    'frontend-port': 8443,
                    'check-type': 'https'},
                {
                    'service-name': 'ceph-api',
                    'frontend-port': 9443,
                    'check-type': 'https'}])

    def test_update_existing_request(self):
        self.harness.begin()
        self.harness.set_leader()
        rel_id = add_loadbalancer_relation(self.harness)
        self.harness.charm.ingress.request_loadbalancer(
            'ceph-dashboard',
            9443,
            9443,
            '10.0.0.20',
            lb_check_type='http')
        unit_rel_data = self.harness.get_relation_data(
            rel_id,
            'my-charm/0')
        app_rel_data = self.harness.get_relation_data(
            rel_id,
            'my-charm')
        self.assertEqual(
            json.loads(unit_rel_data['endpoints']),
            [
                {
                    'service-name': 'ceph-dashboard',
                    'backend-port': 9443,
                    'backend-ip': '10.0.0.20'}])
        self.assertEqual(
            json.loads(app_rel_data['endpoints']),
            [
                {
                    'service-name': 'ceph-dashboard',
                    'frontend-port': 9443,
                    'check-type': 'http'}])

    def test_get_frontend_data(self):
        self.harness.begin()
        self.harness.set_leader()
        rel_id = add_loadbalancer_relation(self.harness)
        add_loadbalancer_response(self.harness, rel_id)
        self.assertEqual(
            self.harness.charm.ingress.get_frontend_data(),
            loadbalancer_data)

    def test__process_response(self):
        self.harness.begin()
        self.harness.set_leader()
        rel_id = add_loadbalancer_relation(self.harness)
        self.assertNotIn(
            'EndpointConfiguredEvent',
            self.harness.charm.seen_events)
        add_loadbalancer_response(self.harness, rel_id)
        self.assertIn(
            'EndpointConfiguredEvent',
            self.harness.charm.seen_events)

    def test_retrieving_endpoints(self):
        self.harness.begin()
        self.harness.set_leader()
        rel_id = add_loadbalancer_relation(self.harness)
        self.assertIsNone(
            self.harness.charm.ingress.get_lb_endpoint(
                'ceph-dashboard',
                'public'))
        add_loadbalancer_response(self.harness, rel_id)
        self.assertEqual(
            self.harness.charm.ingress.get_lb_endpoint(
                'ceph-dashboard',
                'public'),
            {
                'ip': ['10.10.0.101'],
                'port': 8443,
                'protocol': 'http'})
        self.assertEqual(
            self.harness.charm.ingress.get_lb_public_endpoint(
                'ceph-dashboard'),
            {
                'ip': ['10.10.0.101'],
                'port': 8443,
                'protocol': 'http'})
        self.assertEqual(
            self.harness.charm.ingress.get_lb_internal_endpoint(
                'ceph-dashboard'),
            {
                'ip': ['10.30.0.101'],
                'port': 8443,
                'protocol': 'http'})
        self.assertEqual(
            self.harness.charm.ingress.get_lb_admin_endpoint(
                'ceph-dashboard'),
            {
                'ip': ['10.20.0.101'],
                'port': 8443,
                'protocol': 'http'})


class TestAPIEndpointsProvides(unittest.TestCase):

    class MyCharm(CharmBase):

        def __init__(self, *args):
            super().__init__(*args)
            self.seen_events = []
            self.api_eps = interface_api_endpoints.APIEndpointsProvides(self)
            self.framework.observe(
                self.api_eps.on.ep_requested,
                self._log_event)
            self.framework.observe(
                self.api_eps.on.ep_configured,
                self._log_event)

        def _log_event(self, event):
            self.seen_events.append(type(event).__name__)

    def setUp(self):
        super().setUp()
        self.harness = Harness(
            self.MyCharm,
            meta='''
name: my-charm
provides:
  loadbalancer:
    interface: api-endpoints
'''
        )

    def test_on_changed(self):
        self.harness.begin()
        # No EndpointDataEvent as relation is absent
        self.assertEqual(
            self.harness.charm.seen_events,
            [])
        rel_id = self.harness.add_relation('loadbalancer', 'ceph-dashboard')
        self.harness.add_relation_unit(
            rel_id,
            'ceph-dashboard/0')
        self.harness.update_relation_data(
            rel_id,
            'ceph-dashboard/0',
            {'ingress-address': '10.0.0.3'})
        self.assertIn(
            'EndpointRequestsEvent',
            self.harness.charm.seen_events)

#    def add_requesting_dash_relation(self.harness)(self):
#        rel_id = self.harness.add_relation('loadbalancer', 'ceph-dashboard')
#        self.harness.add_relation_unit(
#            rel_id,
#            'ceph-dashboard/0')
#        self.harness.add_relation_unit(
#            rel_id,
#            'ceph-dashboard/1')
#        self.harness.update_relation_data(
#            rel_id,
#            'ceph-dashboard/0',
#            {
#                'endpoints': json.dumps([
#                    {
#                        'service-name': 'ceph-dashboard',
#                        'backend-port': 8443,
#                        'backend-ip': '10.0.0.10'},
#                    {
#                        'service-name': 'ceph-api',
#                        'backend-port': 9443,
#                        'backend-ip': '10.0.0.10'}])})
#        self.harness.update_relation_data(
#            rel_id,
#            'ceph-dashboard/1',
#            {
#                'endpoints': json.dumps([
#                    {
#                        'service-name': 'ceph-dashboard',
#                        'backend-port': 8443,
#                        'backend-ip': '10.0.0.11'},
#                    {
#                        'service-name': 'ceph-api',
#                        'backend-port': 9443,
#                        'backend-ip': '10.0.0.11'}])})
#        self.harness.update_relation_data(
#            rel_id,
#            'ceph-dashboard',
#            {
#                'endpoints': json.dumps([
#                    {
#                        'service-name': 'ceph-dashboard',
#                        'frontend-port': 8443,
#                        'check-type': 'https'},
#                    {
#                        'service-name': 'ceph-api',
#                        'frontend-port': 9443,
#                        'check-type': 'https'}])})
#
#        return rel_id
#
#    def add_requesting_glance_relation(self.harness)(self):
#        rel_id = self.harness.add_relation('loadbalancer', 'glance')
#        self.harness.add_relation_unit(
#            rel_id,
#            'glance/0')
#        self.harness.update_relation_data(
#            rel_id,
#            'glance/0',
#            {
#                'endpoints': json.dumps([
#                    {
#                        'service-name': 'glance-api',
#                        'backend-port': 9292,
#                        'backend-ip': '10.0.0.50'}])})
#        self.harness.update_relation_data(
#            rel_id,
#            'glance',
#            {
#                'endpoints': json.dumps([
#                    {
#                        'service-name': 'glance-api',
#                        'frontend-port': 9292,
#                        'check-type': 'http'}])})
#        return rel_id

    def test__get_frontends(self):
        self.harness.begin()
        add_requesting_dash_relation(self.harness)
        add_requesting_glance_relation(self.harness)
        self.assertEqual(
            self.harness.charm.api_eps._get_frontends(),
            {
                'endpoints': {
                    'ceph-dashboard': {
                        'check_type': 'https',
                        'frontend_port': 8443},
                    'ceph-api': {
                        'check_type': 'https',
                        'frontend_port': 9443},
                    'glance-api': {
                        'check_type': 'http',
                        'frontend_port': 9292}}})

    def test__get_backends(self):
        self.harness.begin()
        add_requesting_dash_relation(self.harness)
        add_requesting_glance_relation(self.harness)
        self.assertEqual(
            self.harness.charm.api_eps._get_backends(),
            {
                'ceph-dashboard': [
                    {
                        'unit_name': 'ceph-dashboard_0',
                        'backend_ip': '10.0.0.10',
                        'backend_port': 8443},
                    {
                        'unit_name': 'ceph-dashboard_1',
                        'backend_ip': '10.0.0.11',
                        'backend_port': 8443}],
                'ceph-api': [
                    {
                        'unit_name': 'ceph-dashboard_0',
                        'backend_ip': '10.0.0.10',
                        'backend_port': 9443},
                    {
                        'unit_name': 'ceph-dashboard_1',
                        'backend_ip': '10.0.0.11',
                        'backend_port': 9443}],
                'glance-api': [
                    {
                        'unit_name': 'glance_0',
                        'backend_ip': '10.0.0.50',
                        'backend_port': 9292}]})

    def test_get_loadbalancer_requests(self):
        self.harness.begin()
        add_requesting_dash_relation(self.harness)
        add_requesting_glance_relation(self.harness)
        self.assertEqual(
            self.harness.charm.api_eps.get_loadbalancer_requests(),
            {
                'endpoints': {
                    'ceph-dashboard': {
                        'check_type': 'https',
                        'frontend_port': 8443,
                        'members': [
                            {
                                'backend_ip': '10.0.0.10',
                                'backend_port': 8443,
                                'unit_name': 'ceph-dashboard_0'},
                            {
                                'backend_ip': '10.0.0.11',
                                'backend_port': 8443,
                                'unit_name': 'ceph-dashboard_1'}]},
                    'ceph-api': {
                        'check_type': 'https',
                        'frontend_port': 9443,
                        'members': [
                            {
                                'backend_ip': '10.0.0.10',
                                'backend_port': 9443,
                                'unit_name': 'ceph-dashboard_0'},
                            {
                                'backend_ip': '10.0.0.11',
                                'backend_port': 9443,
                                'unit_name': 'ceph-dashboard_1'}]},
                    'glance-api': {
                        'check_type': 'http',
                        'frontend_port': 9292,
                        'members': [
                            {
                                'backend_ip': '10.0.0.50',
                                'backend_port': 9292,
                                'unit_name': 'glance_0'}]}}})

    def test_send_loadbalancer_response(self):
        self.harness.begin()
        self.harness.set_leader()
        dash_rel_id = add_requesting_dash_relation(self.harness)
        glance_rel_id = add_requesting_glance_relation(self.harness)
        self.harness.charm.api_eps.loadbalancer_ready(
            'ceph-dashboard',
            'admin',
            ['10.20.0.101'],
            8443,
            'http')
        self.harness.charm.api_eps.loadbalancer_ready(
            'ceph-dashboard',
            'internal',
            ['10.30.0.101'],
            8443,
            'http')
        self.harness.charm.api_eps.loadbalancer_ready(
            'ceph-dashboard',
            'public',
            ['10.10.0.101'],
            8443,
            'http')
        self.harness.charm.api_eps.loadbalancer_ready(
            'ceph-api',
            'admin',
            ['10.20.0.101'],
            9443,
            'http')
        self.harness.charm.api_eps.loadbalancer_ready(
            'ceph-api',
            'internal',
            ['10.30.0.101'],
            9443,
            'http')
        self.harness.charm.api_eps.loadbalancer_ready(
            'ceph-api',
            'public',
            ['10.10.0.101'],
            9443,
            'http')
        self.harness.charm.api_eps.loadbalancer_ready(
            'glance-api',
            'admin',
            ['10.20.0.101'],
            9292,
            'http')
        self.harness.charm.api_eps.loadbalancer_ready(
            'glance-api',
            'internal',
            ['10.30.0.101'],
            9292,
            'http')
        self.harness.charm.api_eps.loadbalancer_ready(
            'glance-api',
            'public',
            ['10.10.0.101'],
            9292,
            'http')
        self.harness.charm.api_eps.advertise_loadbalancers()
        dash_rel_data = self.harness.get_relation_data(
            dash_rel_id,
            'my-charm')
        self.assertEqual(
            json.loads(dash_rel_data['frontends']),
            {
                'ceph-dashboard': {
                    'admin': {
                        'ip': ['10.20.0.101'],
                        'port': 8443,
                        'protocol': 'http'},
                    'internal': {
                        'ip': ['10.30.0.101'],
                        'port': 8443,
                        'protocol': 'http'},
                    'public': {
                        'ip': ['10.10.0.101'],
                        'port': 8443,
                        'protocol': 'http'}},
                'ceph-api': {
                    'admin': {
                        'ip': ['10.20.0.101'],
                        'port': 9443,
                        'protocol': 'http'},
                    'internal': {
                        'ip': ['10.30.0.101'],
                        'port': 9443,
                        'protocol': 'http'},
                    'public': {
                        'ip': ['10.10.0.101'],
                        'port': 9443,
                        'protocol': 'http'}}})
        glance_rel_data = self.harness.get_relation_data(
            glance_rel_id,
            'my-charm')
        self.assertEqual(
            json.loads(glance_rel_data['frontends']),
            {
                'glance-api': {
                    'admin': {
                        'ip': ['10.20.0.101'],
                        'port': 9292,
                        'protocol': 'http'},
                    'internal': {
                        'ip': ['10.30.0.101'],
                        'port': 9292,
                        'protocol': 'http'},
                    'public': {
                        'ip': ['10.10.0.101'],
                        'port': 9292,
                        'protocol': 'http'}}})

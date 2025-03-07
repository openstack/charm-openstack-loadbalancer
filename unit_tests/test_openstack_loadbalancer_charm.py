#!/USr/bin/env python3

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

import ipaddress
import json
import os
import re
import sys
import unittest

sys.path.append('lib')  # noqa
sys.path.append('src')  # noqa

from mock import patch

from ops._private.harness import _TestingModelBackend
from ops.jujucontext import _JujuContext
from ops.testing import Harness
from ops import framework, model
import charm
from unit_tests.manage_test_relations import (
    add_requesting_dash_relation,
    add_requesting_glance_relation,
)


class CharmTestCase(unittest.TestCase):

    def setUp(self, obj, patches):
        super().setUp()
        self.patches = patches
        self.obj = obj
        self.patch_all()

    def patch(self, method):
        _m = patch.object(self.obj, method)
        mock = _m.start()
        self.addCleanup(_m.stop)
        return mock

    def patch_all(self):
        for method in self.patches:
            setattr(self, method, self.patch(method))


class _OpenstackLoadbalancerCharm(charm.OpenstackLoadbalancerCharm):

    def _get_bind_ip(self):
        return '10.0.0.10'


class TestOpenstackLoadbalancerCharmBase(CharmTestCase):

    PATCHES = [
        'ch_host',
        'subprocess',
    ]

    def setUp(self):
        super().setUp(charm, self.PATCHES)
        self.harness = self.get_harness()

    def get_harness(self):
        initial_config = {}
        # dummy juju version
        os.environ["JUJU_VERSION"] = "0.0.0"
        _harness = Harness(
            _OpenstackLoadbalancerCharm,
            meta='''
name: my-charm
extra-bindings:
  public:
  admin:
  internal:
provides:
  loadbalancer:
    interface: api-endpoints
requires:
  ha:
    interface: hacluster
    scope: container
'''
        )

        # BEGIN: Workaround until network_get is implemented
        class _TestingOPSModelBackend(_TestingModelBackend):

            def network_get(self, endpoint_name, relation_id=None):
                network_data = {
                    'admin': {
                        'bind-addresses': [{
                            'interface-name': 'eth1',
                            'addresses': [{
                                'cidr': '10.10.0.0/24',
                                'value': '10.10.0.10'}]}],
                        'ingress-addresses': ['10.10.0.10'],
                        'egress-subnets': ['10.10.0.0/24']},
                    'public': {
                        'bind-addresses': [{
                            'interface-name': 'eth2',
                            'addresses': [{
                                'cidr': '10.20.0.0/24',
                                'value': '10.20.0.10'}]}],
                        'ingress-addresses': ['10.20.0.10'],
                        'egress-subnets': ['10.20.0.0/24']},
                    'internal': {
                        'bind-addresses': [{
                            'interface-name': 'eth3',
                            'addresses': [{
                                'cidr': '10.30.0.0/24',
                                'value': '10.30.0.10'}]}],
                        'ingress-addresses': ['10.30.0.10'],
                        'egress-subnets': ['10.30.0.0/24']}}
                return network_data[endpoint_name]

        _harness._backend = _TestingOPSModelBackend(
            _harness._unit_name,
            _harness._meta,
            _harness._get_config(None),
            _JujuContext.from_dict(os.environ),)
        _harness._model = model.Model(
            _harness._meta,
            _harness._backend)
        _harness._framework = framework.Framework(
            ":memory:",
            _harness._charm_dir,
            _harness._meta,
            _harness._model)
        # END Workaround
        _harness.update_config(initial_config)
        return _harness

    def test_init(self):
        self.harness.begin()
        self.assertTrue(self.harness.charm._stored.is_started)

    def test__get_binding_subnet_map(self):
        self.harness.begin()
        self.assertEqual(
            self.harness.charm._get_binding_subnet_map(),
            {
                'admin': [ipaddress.IPv4Network('10.10.0.0/24')],
                'internal': [ipaddress.IPv4Network('10.30.0.0/24')],
                'public': [ipaddress.IPv4Network('10.20.0.0/24')]})

    def test_vips(self):
        self.harness.begin()
        self.harness.update_config({
            'vip': '10.10.0.100 10.20.0.100 10.30.0.100'})
        self.assertEqual(
            self.harness.charm.vips,
            ['10.10.0.100', '10.20.0.100', '10.30.0.100'])

    def test__get_space_vip_mapping(self):
        self.harness.begin()
        self.harness.update_config({
            'vip': '10.10.0.100 10.20.0.100 10.30.0.100'})
        self.assertEqual(
            self.harness.charm._get_space_vip_mapping(),
            {
                'admin': ['10.10.0.100'],
                'internal': ['10.30.0.100'],
                'public': ['10.20.0.100']})

    def test__send_loadbalancer_response(self):
        self.harness.begin()
        self.harness.set_leader()
        self.harness.update_config({
            'vip': '10.10.0.100 10.20.0.100 10.30.0.100'})
        dash_rel_id = add_requesting_dash_relation(self.harness)
        glance_rel_id = add_requesting_glance_relation(self.harness)
        self.harness.charm._send_loadbalancer_response()
        glance_rel_data = self.harness.get_relation_data(
            glance_rel_id,
            'my-charm')
        dash_rel_data = self.harness.get_relation_data(
            dash_rel_id,
            'my-charm')
        self.assertEqual(
            json.loads(glance_rel_data['frontends']),
            {
                'glance-api': {
                    'admin': {
                        'ip': ['10.10.0.100'],
                        'port': 9292,
                        'protocol': 'http'},
                    'internal': {
                        'ip': ['10.30.0.100'],
                        'port': 9292,
                        'protocol': 'http'},
                    'public': {
                        'ip': ['10.20.0.100'],
                        'port': 9292,
                        'protocol': 'http'}}})
        self.assertEqual(
            json.loads(dash_rel_data['frontends']),
            {
                'ceph-dashboard': {
                    'admin': {
                        'ip': ['10.10.0.100'],
                        'port': 8443,
                        'protocol': 'http'},
                    'internal': {
                        'ip': ['10.30.0.100'],
                        'port': 8443,
                        'protocol': 'http'},
                    'public': {
                        'ip': ['10.20.0.100'],
                        'port': 8443,
                        'protocol': 'http'}},
                'ceph-api': {
                    'admin': {
                        'ip': ['10.10.0.100'],
                        'port': 9443,
                        'protocol': 'http'},
                    'internal': {
                        'ip': ['10.30.0.100'],
                        'port': 9443,
                        'protocol': 'http'},
                    'public': {
                        'ip': ['10.20.0.100'],
                        'port': 9443,
                        'protocol': 'http'}}})

    def test__configure_hacluster(self):
        self.harness.begin()
        self.harness.set_leader()
        self.harness.update_config({
            'vip': '10.10.0.100 10.20.0.100 10.30.0.100'})
        rel_id = self.harness.add_relation(
            'ha',
            'hacluster')
        self.harness.add_relation_unit(
            rel_id,
            'hacluster/0')
        self.harness.charm._configure_hacluster(None)
        rel_data = self.harness.get_relation_data(
            rel_id,
            'my-charm/0')
        self.assertEqual(
            json.loads(rel_data['json_clones']),
            {'cl_res_my_charm_haproxy': 'res_my_charm_haproxy'})
        self.assertEqual(
            json.loads(rel_data['json_init_services']),
            ['haproxy'])
        self.assertEqual(
            json.loads(rel_data['json_resources'])['res_my_charm_haproxy'],
            'lsb:haproxy')
        vip_resources = {
            k: v
            for k, v in json.loads(rel_data['json_resources']).items()
            if re.match('res_my-charm_.*vip$', k)}
        self.assertEqual(len(vip_resources), 3)
        self.assertTrue(all(
            [v == 'ocf:heartbeat:IPaddr2' for v in vip_resources.values()]))

    def test_LoadbalancerAdapter(self):
        self.harness.begin()
        self.harness.set_leader()
        self.harness.update_config({
            'vip': '10.10.0.100 10.20.0.100 10.30.0.100'})
        add_requesting_dash_relation(self.harness)
        add_requesting_glance_relation(self.harness)
        self.assertEqual(
            self.harness.charm.adapters.loadbalancer.endpoints,
            {
                'ceph_dashboard': {
                    'frontend_port': 8443,
                    'check_type': 'https',
                    'members': [
                        {
                            'unit_name': 'ceph-dashboard_0',
                            'backend_port': 8443,
                            'backend_ip': '10.0.0.10'},
                        {
                            'unit_name': 'ceph-dashboard_1',
                            'backend_port': 8443,
                            'backend_ip': '10.0.0.11'}]},
                'ceph_api': {
                    'frontend_port': 9443,
                    'check_type': 'https',
                    'members': [
                        {
                            'unit_name': 'ceph-dashboard_0',
                            'backend_port': 9443,
                            'backend_ip': '10.0.0.10'},
                        {
                            'unit_name': 'ceph-dashboard_1',
                            'backend_port': 9443,
                            'backend_ip': '10.0.0.11'}]},
                'glance_api': {
                    'frontend_port': 9292,
                    'check_type': 'http',
                    'members': [
                        {
                            'unit_name': 'glance_0',
                            'backend_port': 9292,
                            'backend_ip': '10.0.0.50'}]}})

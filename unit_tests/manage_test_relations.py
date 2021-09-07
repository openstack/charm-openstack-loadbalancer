import json

loadbalancer_data = {
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
            'protocol': 'http'}}}


def add_loadbalancer_relation(harness):
    rel_id = harness.add_relation(
        'loadbalancer',
        'service-loadbalancer')
    harness.add_relation_unit(
        rel_id,
        'service-loadbalancer/0')
    harness.update_relation_data(
        rel_id,
        'service-loadbalancer/0',
        {'ingress-address': '10.0.0.3'})
    return rel_id


def add_loadbalancer_response(harness, rel_id):
    harness.update_relation_data(
        rel_id,
        'service-loadbalancer',
        {
            'frontends': json.dumps(
                loadbalancer_data)})


def add_requesting_dash_relation(harness):
    rel_id = harness.add_relation('loadbalancer', 'ceph-dashboard')
    harness.add_relation_unit(
        rel_id,
        'ceph-dashboard/0')
    harness.add_relation_unit(
        rel_id,
        'ceph-dashboard/1')
    harness.update_relation_data(
        rel_id,
        'ceph-dashboard/0',
        {
            'endpoints': json.dumps([
                {
                    'service-name': 'ceph-dashboard',
                    'backend-port': 8443,
                    'backend-ip': '10.0.0.10'},
                {
                    'service-name': 'ceph-api',
                    'backend-port': 9443,
                    'backend-ip': '10.0.0.10'}])})
    harness.update_relation_data(
        rel_id,
        'ceph-dashboard/1',
        {
            'endpoints': json.dumps([
                {
                    'service-name': 'ceph-dashboard',
                    'backend-port': 8443,
                    'backend-ip': '10.0.0.11'},
                {
                    'service-name': 'ceph-api',
                    'backend-port': 9443,
                    'backend-ip': '10.0.0.11'}])})
    harness.update_relation_data(
        rel_id,
        'ceph-dashboard',
        {
            'endpoints': json.dumps([
                {
                    'service-name': 'ceph-dashboard',
                    'frontend-port': 8443,
                    'check-type': 'https'},
                {
                    'service-name': 'ceph-api',
                    'frontend-port': 9443,
                    'check-type': 'https'}])})

    return rel_id


def add_requesting_glance_relation(harness):
    rel_id = harness.add_relation('loadbalancer', 'glance')
    harness.add_relation_unit(
        rel_id,
        'glance/0')
    harness.update_relation_data(
        rel_id,
        'glance/0',
        {
            'endpoints': json.dumps([
                {
                    'service-name': 'glance-api',
                    'backend-port': 9292,
                    'backend-ip': '10.0.0.50'}])})
    harness.update_relation_data(
        rel_id,
        'glance',
        {
            'endpoints': json.dumps([
                {
                    'service-name': 'glance-api',
                    'frontend-port': 9292,
                    'check-type': 'http'}])})
    return rel_id

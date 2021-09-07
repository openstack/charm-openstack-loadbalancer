# Overview

The openstack-loadbalancer charm deploys a loadbalancer that can load balance
traffic over a number of units of a service. The charm supports using vips
accross the loadbalancer units to provide HA.

# Usage

## Configuration

See file `config.yaml` for the full list of options, along with their
descriptions and default values.

## Deployment

Use the vip charm config option to specify the vips to be used by the
loadbalancer, normally one vip per network space that the charm is bound to.

    juju deploy -n 3 openstack-loadbalancer
    juju config openstack-loadbalancer vip="10.0.0.100 10.10.0.100 10.20.0.100"
    juju deploy hacluster
    juju relate openstack-loadbalancer:ha hacluster:ha

Then relate the charm to a service that requires a loadbalancer

    juju add-relation openstack-loadbalancer:loadbalancer ceph-dashboard:loadbalancer

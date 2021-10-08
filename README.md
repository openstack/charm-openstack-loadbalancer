# Overview

The openstack-loadbalancer charm deploys a loadbalancer that can load balance
traffic over a number of units of a service. The charm supports using vips
accross the loadbalancer units to provide HA.

# Usage

## Configuration

This section covers common and/or important configuration options. See file
`config.yaml` for the full list of options, along with their descriptions and
default values. See the [Juju documentation][juju-docs-config-apps] for details
on configuring applications.

#### `vips`

Sets the VIPs to use on the openstack-loadbalancer units to provide fault tolerant
access to a servce. The value should be a space seperated list of IPs.

## Deployment

The charm has `public`, `admin` and `internal` space bindings. These are the
spaces that the charm will create listeners on for ingress traffic. The charm
`vips` option should be used to provice an IP on each one of these network
spaces.

This charm needs to be related to the hacluster charm to manage vips and the
haproxy service.

    juju deploy -n 3 openstack-loadbalancer
    juju config openstack-loadbalancer vip="10.0.0.100 10.10.0.100 10.20.0.100"
    juju deploy hacluster openstack-loadbalancer-hacluster
    juju relate openstack-loadbalancer:ha openstack-loadbalancer-hacluster:ha

To provide a load balancer relate the charm to a service that supports the loadbalancer
interface.

    juju add-relation openstack-loadbalancer:loadbalancer ceph-dashboard:loadbalancer

# Documentation

The OpenStack Charms project maintains two documentation guides:

* [OpenStack Charm Guide][cg]: for project information, including development
  and support notes
* [OpenStack Charms Deployment Guide][cdg]: for charm usage information

# Bugs

Please report bugs on [Launchpad][lp-bugs-charm-openstack-loadbalancer].

<!-- LINKS -->

[juju-docs-actions]: https://juju.is/docs/working-with-actions
[juju-docs-config-apps]: https://juju.is/docs/configuring-applications
[cg]: https://docs.openstack.org/charm-guide
[cdg]: https://docs.openstack.org/project-deploy-guide/charm-deployment-guide
[lp-bugs-charm-openstack-loadbalancer]: https://bugs.launchpad.net/charm-openstack-loadbalancer

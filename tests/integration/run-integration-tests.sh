#!/bin/bash

set +e  # Don't quit on error

DEVICE=${1:-"srlinux"}

function can_ping() {
 local host=$1
 local ip=$2
 docker exec -it clab-${host} ping -W1 -c2 $ip
 if [ $? != 0 ]; then
  echo "Error: ${host} should be able to ping ${ip}"
  exit 1
 fi
}

function cant_ping() {
 local host=$1
 local ip=$2

 docker exec -it clab-${host} ping -W1 -c2 $ip
 if [ $? != 1 ]; then
  echo "Error: ${host} should not be able to ping ${ip}"
  exit 1
 fi
}


# Runs a bunch of integration test cases, and performs ping checks to validate the setup
function vlan-bridge-native() {
 netlab up -d "${DEVICE}" -p clab "vlan/vlan-bridge-native.yml"

 can_ping  "vlan-h1" "172.16.0.2"
 can_ping  "vlan-h3" "172.16.1.4"
 cant_ping "vlan-h1" "172.16.1.3"

 netlab down
}

function evpn-asymmetric-irb() {
 # netlab up -d "${DEVICE}" -p clab "evpn/vxlan-asymmetric-irb.yml"

 # TODO full-mesh ping automated
 can_ping  "evpn-h1" "172.16.0.2" # h2
 can_ping  "evpn-h1" "172.16.1.3" # h3
 can_ping  "evpn-h1" "172.16.2.4" # h4
 can_ping  "evpn-h2" "172.16.1.3" # h3
 can_ping  "evpn-h2" "172.16.2.4" # h4
 can_ping  "evpn-h3" "172.16.2.4" # h4
 
 netlab down
}

# vlan-bridge-native
evpn-asymmetric-irb


exit $?
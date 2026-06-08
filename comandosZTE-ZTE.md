ZXAN#configure terminal
Enter configuration commands, one per line.  End with CTRL/Z.
ZXAN(config)#pon-onu-mng
%Error 140305: Incomplete command.
ZXAN(config)#pon-onu-mng 
ZXAN(config)#pon-onu-mng g
ZXAN(config)#pon-onu-mng gpon_onu-1/2/16:26
ZXAN(config-gpon-onu-mng)#service 1 gemport 1 vlan 150
ZXAN(config-gpon-onu-mng)#wan-ip 1 ping-response enable traceroute-response enable 
wan-ip 1 ping-response enable traceroute-response enable 
         ^
%Error 140303: Invalid input detected at '^' marker.
ZXAN(config-gpon-onu-mng)#wan-ip 1 ?                                              
  ipv4  IPv4 mode
  ipv6  IPv6 mode
ZXAN(config-gpon-onu-mng)#wan-ip 1 ipv4 ?
  mode           IP address configure mode
  ping-response  Ping response
ZXAN(config-gpon-onu-mng)#wan-ip 1 ipv4 pi
ZXAN(config-gpon-onu-mng)#wan-ip 1 ipv4 ping-response ?
  disable  Disable
  enable   Enable
ZXAN(config-gpon-onu-mng)#wan-ip 1 ipv4 ping-response enable ?
  traceroute-response  Traceroute response
ZXAN(config-gpon-onu-mng)#wan-ip 1 ipv4 ping-response enable tra
ZXAN(config-gpon-onu-mng)#wan-ip 1 ipv4 ping-response enable traceroute-response ?
  disable  Disable
  enable   Enable
ZXAN(config-gpon-onu-mng)#wan-ip 1 ipv4 ping-response enable traceroute-response enable
ZXAN(config-gpon-onu-mng)#secur
ZXAN(config-gpon-onu-mng)#security-m   
ZXAN(config-gpon-onu-mng)#security-mgmt ?
  <1-255>  Service control rule index
ZXAN(config-gpon-onu-mng)#security-mgmt 1 ?
  ingress-type  Ingress type
  mode          Service control mode
  protocol      Service protocol
  start-src-ip  Start of filter source IP address
  state         Service control state
  <cr>
ZXAN(config-gpon-onu-mng)#security-mgmt 1 in
ZXAN(config-gpon-onu-mng)#security-mgmt 1 ingress-type ?
  iphost  IP host
  lan     LAN
  wan     WAN, the default type
ZXAN(config-gpon-onu-mng)#security-mgmt 1 state ?      
  disable        Disable
  enable         Enable
  enable-action  This action only effects when ONU working.
ZXAN(config-gpon-onu-mng)#security-mgmt 1 state enable ?
  ingress-type  Ingress type
  mode          Service control mode
  protocol      Service protocol
  start-src-ip  Start of filter source IP address
  <cr>
ZXAN(config-gpon-onu-mng)#security-mgmt 1 state enable mode ?
  discard  The default operation
  forward  Forwarding
ZXAN(config-gpon-onu-mng)#security-mgmt 1 state enable mode forw
ZXAN(config-gpon-onu-mng)#security-mgmt 1 state enable mode forward ?
  ingress-type  Ingress type
  protocol      Service protocol
  start-src-ip  Start of filter source IP address
  <cr>
ZXAN(config-gpon-onu-mng)#security-mgmt 1 state enable mode forward ingress-type iphost 1 protocol web
ZXAN(config-gpon-onu-mng)#end
ZXAN#



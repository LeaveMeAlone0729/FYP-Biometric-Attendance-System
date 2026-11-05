"""Canonical policy input; callers never supply the source address."""
import ipaddress

def parse_cidr(value):
    if not isinstance(value,str) or '/' not in value or '%' in value:
        raise ValueError('Enter an IPv4 or IPv6 CIDR network with a prefix length.')
    network=ipaddress.ip_network(value,strict=True)
    if isinstance(network,ipaddress.IPv6Network) and network.network_address.ipv4_mapped is not None:
        raise ValueError('Use an IPv4 CIDR for IPv4-mapped connection addresses.')
    return network

def canonical_cidr(value):
    return str(parse_cidr(value))

def connection_ip(scope):
    peer=scope.get('client')
    if peer is None:return None,'SOURCE_IP_MISSING'
    if not isinstance(peer,(tuple,list)) or len(peer)<2 or not isinstance(peer[0],str):
        return None,'SOURCE_IP_INVALID'
    host=peer[0]
    if '%' in host:return None,'SOURCE_IP_INVALID'
    try:address=ipaddress.ip_address(host)
    except ValueError:return None,'SOURCE_IP_INVALID'
    if isinstance(address,ipaddress.IPv6Address) and address.ipv4_mapped is not None:address=address.ipv4_mapped
    if address.is_loopback:return address,'LOOPBACK_SOURCE_NOT_AUTHORIZED'
    if address.is_unspecified or address.is_multicast:return address,'SOURCE_IP_NOT_UNICAST'
    return address,None

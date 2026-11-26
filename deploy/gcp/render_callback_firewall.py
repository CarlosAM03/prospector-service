"""Print the additive nftables configuration for the Service callback bridge."""

import argparse
import ipaddress


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("callback_ipv4", type=ipaddress.IPv4Address)
    args = parser.parse_args()
    address = args.callback_ipv4
    if not address.is_global or address.is_multicast or address.is_reserved:
        parser.error("callback must use a verified unicast public IPv4 address")
    print(f"""table inet prospector_egress {{
  chain block_host_access {{
    type filter hook input priority -10; policy accept;
    iifname "prsvc-egress0" counter drop
  }}
  chain allow_callback_only {{
    type filter hook forward priority -10; policy accept;
    iifname "prsvc-egress0" ip daddr {address} tcp dport 443 counter accept
    iifname "prsvc-egress0" counter drop
  }}
}}""")


if __name__ == "__main__":
    main()

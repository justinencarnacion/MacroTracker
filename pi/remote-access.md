# Remote Access to the Pi: Using what I learned from CSEN 146

This document records how SSH access to the MacroTracker Raspberry Pi was
extended from "home Wi-Fi only" to "any network", without a third-party
overlay service such as Tailscale. It was built by hand to apply concepts
from a Computer Networks course: IP addressing, DHCP, DNS, NAT, port
forwarding, TCP, and SSH security.

All addresses, names, and ports below are **placeholders**. Public IPs use
the documentation ranges reserved by RFC 5737 (`203.0.113.0/24`,
`198.51.100.0/24`); none of them are real.

| Placeholder | Meaning |
| --- | --- |
| `<pi-lan-ip>` | The Pi's private address on the home network, e.g. `192.168.1.50` |
| `<home-public-ip>` | The home's public IPv4 address, e.g. `203.0.113.10` |
| `<name>.duckdns.org` | The Dynamic DNS hostname |
| `<ext-port>` | The high, non-standard TCP port forwarded to the Pi |
| `<pi-user>` | The Pi's login user |

## Summary

| Step | What was done | Course concepts |
| --- | --- | --- |
| 0. CGNAT check | Compared the router's WAN IP with the address an external server sees (`curl ifconfig.me`); ran `traceroute` | Public vs private (RFC 1918) addressing, NAT, CGNAT (`100.64.0.0/10`), double NAT |
| 1. DHCP reservation | Bound the Pi's MAC address to a fixed private IP on the router | DHCP (DORA), MAC addresses and OUIs, Layer 2 vs Layer 3 |
| 2. SSH hardening + fail2ban | Key-only login, root login disabled, one allowed user, sshd on two ports, automatic banning of repeat offenders | Sockets and the `LISTEN` state, the TCP 4-tuple, ephemeral ports, public-key authentication, host-key verification, defence in depth |
| 3. Dynamic DNS | A cron job sends an HTTPS update to DuckDNS every 5 minutes; checked with `dig` | DNS A records, resolver hierarchy, TTL, NAT rewriting the source address |
| 4. Port forwarding | A static rule sending one external TCP port to the Pi | Inbound vs outbound NAT, the NAT translation table, destination NAT, why ICMP (`ping`) can't be forwarded |
| 5. Test from outside | `nc -vz`, then `ssh`, from a phone hotspot | The TCP three-way handshake, timeout vs RST, NAT loopback (hairpinning) |

Each step is explained in detail in [section 4](#4-step-by-step-with-the-concepts-behind-each-step).

---

## 1. The problem

The bot runs 24/7 on a Raspberry Pi at home. From inside the home network,
`ssh macrotracker` worked because the Pi was reachable at a private address.
From any other network it failed, for two separate reasons:

1. **Naming:** `macrotracker.local` is resolved by **mDNS** (multicast DNS),
   which only works on the local network segment. The outside world has no
   way to resolve it.
2. **Reachability:** the Pi has a **private IP** behind the home router's
   **NAT**. Even with the right public address, the router drops unsolicited
   inbound connections because it has no rule saying which internal host
   should receive them.

The bot itself never had this problem, and that turned out to be a useful
lesson (section 7).

## 2. Final architecture

```
   Laptop on another network (phone hotspot, campus Wi-Fi, ...)
     │
     │ 1. DNS query: <name>.duckdns.org ?  ──►  DuckDNS answers: <home-public-ip>
     │
     │ 2. TCP SYN to <home-public-ip>:<ext-port>
     ▼
 ┌──────────────────────────── Internet ────────────────────────────┐
 └───────────────────────────────┬───────────────────────────────────┘
                                 │
                        ISP modem (bridge, no NAT)
                                 │
              ┌──────────────────┴──────────────────┐
              │  Home router (NETGEAR Orbi)         │  WAN side: <home-public-ip>
              │  NAT + port-forward rule:           │  LAN side: 192.168.1.1/24
              │  TCP <ext-port> → <pi-lan-ip>:<ext-port>
              │  DHCP reservation: Pi MAC → <pi-lan-ip>
              └──────────────────┬──────────────────┘
                                 │  private network (192.168.1.0/24)
                                 ▼
              ┌─────────────────────────────────────┐
              │  Raspberry Pi (<pi-lan-ip>)          │
              │  sshd listening on TCP 22 and <ext-port>
              │  key-only auth, fail2ban            │
              │  cron: every 5 min → DuckDNS update │
              │  Docker: MacroTracker bot (outbound only)
              └─────────────────────────────────────┘
```

## 3. Mapping the work to the network stack

| Layer (TCP/IP model) | What was configured | Concepts applied |
| --- | --- | --- |
| **Application** | SSH server hardening; Dynamic DNS updates over HTTPS; DNS lookups with `dig` | Client/server model, DNS records, authentication |
| **Transport** | sshd listening on two TCP ports; testing with `nc -vz`; reading sockets with `ss -tln` | TCP ports, sockets, the three-way handshake |
| **Network** | Public vs private IPv4; NAT and port forwarding; CGNAT check; `traceroute` | RFC 1918 addressing, NAPT, routing hops |
| **Link** | DHCP reservation bound to the Pi's MAC address | DHCP, MAC addresses, the local broadcast domain |

---

## 4. Step by step, with the concepts behind each step

### Step 0: Is there a public IP at all? (Network layer)

Port forwarding only works if the router's WAN interface holds a real public
IPv4 address. Many ISPs use **Carrier-Grade NAT (CGNAT, RFC 6598,
`100.64.0.0/10`)**, where several customers share one public address. Behind
CGNAT, no home router configuration can accept inbound connections, because
the ISP's own NAT drops them first.

**Test:** compare the router's reported WAN IP with what an external server
sees as the source address of a request:

```bash
curl -4 ifconfig.me        # the address the internet sees
```

They matched, so the home has a real public IP. A `traceroute` confirmed the
topology: hop 1 was the home router, and hop 2 was already inside the ISP's
network. That ruled out "double NAT" (an ISP gateway doing NAT in front of
the home router), because the ISP modem was acting as a simple bridge.

> **Concept:** NAT exists because IPv4 has only about 4.3 billion addresses.
> A home gets **one** public address, and every device inside uses a
> **private** address from RFC 1918 (`10/8`, `172.16/12`, `192.168/16`).
> Private addresses are not routable on the public internet.

### Step 1: A stable private address (Link layer: DHCP)

Devices on the home network get their IPs from the router's **DHCP server**
through the DORA exchange (Discover, Offer, Request, Acknowledge). Leases can
change, and a port-forward rule that points at a stale IP is useless.

**Done:** in the router's **LAN Setup → Address Reservation**, the Pi's
**MAC address** was bound to `<pi-lan-ip>`. Every DHCP request from that MAC
now receives the same IP.

> **Concept:** a MAC address is a Layer 2 identifier burned into the network
> interface. The first three bytes (the OUI) identify the manufacturer, and
> the Pi's MAC starts with the Raspberry Pi vendor prefix. DHCP uses the MAC
> to recognise returning clients. The Pi's IPv6 link-local address
> (`fe80::...`) is also derived from that MAC (EUI-64), which is how the same
> device could be recognised across both protocols.

### Step 2: Prepare the server before exposing it (Application + Transport)

Before opening anything to the internet, the SSH server was hardened with a
drop-in file `/etc/ssh/sshd_config.d/10-hardening.conf`:

```
Port 22                    # home network
Port <ext-port>            # forwarded from the internet
PasswordAuthentication no  # keys only
KbdInteractiveAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
AllowUsers <pi-user>
MaxAuthTries 3
LoginGraceTime 20
X11Forwarding no
```

The config was validated with `sudo sshd -t` before restarting, while a
second SSH session stayed open as a recovery path in case of a mistake.

**Verifying the listening sockets:**

```bash
ss -tln | grep -E ':(22|<ext-port>) '
# LISTEN 0 128   0.0.0.0:<ext-port>   0.0.0.0:*
# LISTEN 0 128   0.0.0.0:22           0.0.0.0:*
# LISTEN 0 128      [::]:<ext-port>      [::]:*
# LISTEN 0 128      [::]:22              [::]:*
```

> **Concept: sockets and ports.** A server process binds a **socket** to an
> (IP, port) pair and waits in the `LISTEN` state. `0.0.0.0` means "every
> IPv4 interface" and `[::]` means "every IPv6 interface". A single process
> (sshd) can listen on several ports at once. A TCP connection is uniquely
> identified by the 4-tuple (source IP, source port, destination IP,
> destination port). The client's source port is a random **ephemeral port**,
> which is how one server port handles many simultaneous clients.

> **Concept: public-key authentication.** The laptop holds a **private key**;
> the Pi stores only the matching **public key** in `authorized_keys`. During
> login, the server sends a challenge that only the private-key holder can
> sign. The secret never crosses the network, so there is nothing to guess or
> steal in transit. A related idea is **host-key verification**: the first
> connection displays the Pi's host-key fingerprint and saves it in
> `known_hosts` (trust on first use). Later connections refuse to proceed if
> the host key changes, which protects against man-in-the-middle attacks.

**fail2ban** was then added. It reads sshd's entries in the systemd journal
and, after 5 failures within 10 minutes from one source IP, inserts a
firewall rule that drops that IP for an hour. The home subnet is exempt so
the owner can never lock themselves out.

> **Concept: defence in depth.** No single control is relied upon. Key-only
> authentication makes guessing impossible; `AllowUsers` and
> `PermitRootLogin no` shrink the attack surface; fail2ban stops repeat
> offenders at the IP layer; and the non-standard port reduces automated scan
> noise. The port number on its own is **not** security ("security through
> obscurity"), but it is a cheap way to keep logs readable.

### Step 3: A name that follows a changing address (Application layer: DNS)

Residential public IPs are **dynamic**: the ISP can reassign them after a
modem reboot or maintenance. Instead of paying for a static IP,
**Dynamic DNS** gives a fixed hostname whose record is updated automatically.

**Done:**

1. Registered `<name>.duckdns.org`.
2. Wrote `~/duckdns/duck.sh` on the Pi, which makes one HTTPS request:
   ```
   GET https://www.duckdns.org/update?domains=<name>&token=<secret>&ip=
   ```
   The empty `ip=` tells DuckDNS to use the **source IP of the request**, which
   is the home's public address after the router's NAT translates it.
3. Scheduled it with **cron** every 5 minutes:
   ```
   */5 * * * * ~/duckdns/duck.sh >/dev/null 2>&1
   ```
4. Verified resolution from the laptop:
   ```bash
   dig +short <name>.duckdns.org   # returns <home-public-ip>
   ```

> **Concept: DNS.** DNS maps names to addresses using resource records. Here
> it is an **A record** (name → IPv4 address). `dig` sends a query to a
> resolver, which walks the hierarchy (root → `.org` → `duckdns.org`
> authoritative servers) and caches the answer for the record's **TTL**.
> Dynamic DNS providers use short TTLs so that changes propagate quickly. The
> update token is a shared secret, which is why the script is `chmod 700`.

> **Concept: NAT rewrites source addresses.** The Pi sends the update from
> `<pi-lan-ip>`, but DuckDNS sees `<home-public-ip>`. On the way out, the
> router rewrote the packet's source IP and port and recorded the mapping in
> its **NAT translation table** so that the reply could find its way back.
> That is how every outbound connection from the home network works.

### Step 4: Allow one inbound connection (Network layer: port forwarding)

Outbound connections create NAT table entries automatically. **Inbound**
connections do not: when a TCP SYN arrives at `<home-public-ip>:<ext-port>`,
the router has no entry telling it which internal host should receive it, so
it drops the packet. A **port-forward** rule is a static NAT entry
(destination NAT):

| Service | Protocol | External port | Internal IP | Internal port |
| --- | --- | --- | --- | --- |
| ssh-macrotracker | TCP | `<ext-port>` | `<pi-lan-ip>` | `<ext-port>` |

The router now rewrites the **destination** of matching packets to
`<pi-lan-ip>:<ext-port>` and forwards them. Port 22 is deliberately **not**
forwarded; it stays reachable only from inside the home.

> **Why sshd listens on `<ext-port>` too:** some consumer gateways cannot map
> an external port to a *different* internal port. Having sshd listen on the
> same high port keeps the rule a simple 1:1 mapping that works on any
> router.

> **Why you can't "ping the Pi" from outside:** ping uses **ICMP**, which is
> a Network-layer protocol with **no port numbers**. Port forwarding matches
> on (protocol, port), so there is nothing to forward. Pinging
> `<home-public-ip>` reaches the router itself, not the Pi. Reachability is
> tested at the Transport layer instead (next step).

### Step 5: Test from outside (Transport layer: TCP handshake)

The laptop was moved to a phone hotspot so that traffic genuinely entered
from the internet. Three tests were run, from lowest layer to highest:

```bash
curl -4 ifconfig.me                          # 1. confirm we're outside (different public IP)
nc -vz -G 5 <name>.duckdns.org <ext-port>    # 2. TCP handshake only
ssh macrotracker-remote                      # 3. full SSH login
```

- **Test 1** proved the laptop's public IP differed from the home's.
- **Test 2**, `nc -vz`, opens a TCP connection and closes it immediately.
  Success means the **three-way handshake** (SYN → SYN-ACK → ACK) completed:
  DNS resolved, the router forwarded the SYN, the Pi's socket was listening,
  and the SYN-ACK made it back. A timeout would point at forwarding or
  firewalling; a "connection refused" (RST) would mean the packet reached
  the host but nothing was listening on that port.
- **Test 3** layered SSH's key exchange and public-key authentication on top
  of that TCP connection.

> **Why testing from home can fail: NAT loopback (hairpinning).** From inside
> the LAN, connecting to the home's *own* public IP requires the router to
> receive the packet on its LAN interface, apply the WAN-side port-forward,
> and send it back into the LAN. Many consumer routers don't support this,
> so the test can fail at home even when everything is configured correctly.
> At home, the LAN path (`ssh macrotracker`, port 22) is used instead.

The client side was made convenient with two entries in `~/.ssh/config`:

```
Host macrotracker            # at home: mDNS name, port 22
    HostName macrotracker.local
    User <pi-user>
    IdentityFile ~/.ssh/macrotracker-pi

Host macrotracker-remote     # anywhere: Dynamic DNS name, forwarded port
    HostName <name>.duckdns.org
    Port <ext-port>
    User <pi-user>
    IdentityFile ~/.ssh/macrotracker-pi
```

The deploy script reuses the remote path with
`DEPLOY_HOST=macrotracker-remote ./deploy/deploy.sh`.

---

## 5. A connection, packet by packet

What happens when `ssh macrotracker-remote` runs from a coffee-shop network:

1. **DNS:** the laptop resolves `<name>.duckdns.org` → `<home-public-ip>`.
2. **TCP SYN:** the laptop sends a SYN from `198.51.100.7:51234` (its own
   public IP after *its* network's NAT, plus an ephemeral port) to
   `<home-public-ip>:<ext-port>`.
3. **Destination NAT:** the Orbi matches the port-forward rule and rewrites
   the destination to `<pi-lan-ip>:<ext-port>`.
4. **Handshake:** the Pi's listening socket replies with a SYN-ACK. The router
   reverses the translation on the way out, and the laptop sends the final
   ACK. The connection is now `ESTABLISHED`.
5. **SSH:** protocol versions are exchanged, a session key is agreed (key
   exchange), the host key is checked against `known_hosts`, and the client
   proves possession of its private key.
6. **Session:** every subsequent byte travels inside that TCP connection,
   encrypted with the session key.

## 6. Verification and monitoring commands

| Command (on the Pi unless noted) | Shows | Layer |
| --- | --- | --- |
| `ss -tln` | Listening TCP sockets | Transport |
| `ss -tn state established '( sport = :<ext-port> )'` | Active remote SSH connections | Transport |
| `sudo fail2ban-client status sshd` | Failed attempts and banned IPs | Application/Network |
| `journalctl -u ssh --since today` | Every SSH connection attempt | Application |
| `crontab -l`, `cat ~/duckdns/duck.log` | DDNS schedule and last result (`OK`) | Application |
| `dig +short <name>.duckdns.org` (laptop) | Current DNS answer | Application |
| `nc -vz <name>.duckdns.org <ext-port>` (laptop, outside) | TCP reachability | Transport |
| `traceroute -n 8.8.8.8` (laptop) | Routing hops; confirms no double NAT | Network |

## 7. Why the bot never needed any of this

The Discord bot connects **outbound** to Discord's gateway (a WebSocket over
TLS on TCP 443), Google Sheets, and Gemini. Because the Pi initiates every
connection, the router's NAT creates the translation entries automatically
and replies flow back in. **No inbound port is needed for the bot.** Only
*administrative* access (SSH) required an inbound rule, which is why the
attack surface is a single forwarded port. Docker publishes no ports at all.

## 8. Problems hit along the way, and what they taught

| Symptom | Root cause | Lesson |
| --- | --- | --- |
| `Permission denied (publickey)` on first login | The image used a different username than expected | Authentication failure ≠ network failure; `ssh -v` shows which key and user were tried |
| `Could not resolve hostname macrotracker.local` away from home | mDNS only works on the local link | Name resolution is scoped; public names need public DNS |
| `fail2ban-client`: "Failed to access socket" | The status command ran one second before the server finished starting | Check the service log (`journalctl -u`) before assuming misconfiguration |
| Duplicate lines in crontab and `~/.ssh/config` | Append commands (`>>`, `crontab -` with `-l`) were run twice | Appends are not idempotent; inspect the file before re-running |
| Cloud VM unavailable (out of capacity) | Free-tier cloud capacity in a single-availability-domain region | Self-hosting at home trades cloud convenience for network configuration |

## 9. Alternatives considered

| Approach | How it reaches the Pi | Trade-off |
| --- | --- | --- |
| **Port forwarding + DDNS (chosen)** | Static DNAT rule on the home router | Full control and the most to learn; one port exposed to the internet |
| WireGuard VPN on the Pi | Forward only a UDP VPN port; SSH stays internal | More secure (the port is silent without a valid key), more setup |
| Overlay networks (e.g. Tailscale) | NAT traversal plus a coordination server; no open ports | Easiest and safest, but relies on a third party and hides the networking details |
| Static public IP from the ISP | Same as the chosen design, without DDNS | Costs money; DDNS gives the same result for free |

## 10. Turning it off

Delete the port-forward rule on the router. The Pi immediately becomes
unreachable from the internet again, while LAN access and the bot are
unaffected.

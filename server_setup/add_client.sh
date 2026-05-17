#!/usr/bin/env bash
# =====================================================================
#  AuroraVPN - Ajout d'un client a un serveur deja installe
# =====================================================================
#  Usage :
#    sudo ./add_client.sh <nom-du-client>
#
#  Equivalent a `install_wireguard.sh <nom>` quand le serveur est deja
#  installe. Plus rapide, ne reinstalle pas les paquets.
# =====================================================================

set -euo pipefail

CLIENT_NAME="${1:-}"
[ -n "$CLIENT_NAME" ] || { echo "Usage : sudo $0 <nom-du-client>"; exit 1; }

WG_DIR="/etc/wireguard"
WG_INTERFACE="${WG_INTERFACE:-wg0}"
WG_PORT="${WG_PORT:-51820}"
WG_DNS="${WG_DNS:-1.1.1.1, 9.9.9.9}"

[ "$EUID" -eq 0 ] || { echo "Doit etre lance en root."; exit 1; }
[ -f "$WG_DIR/${WG_INTERFACE}.conf" ] || { echo "Serveur non installe. Lancer install_wireguard.sh d'abord."; exit 1; }

next_client_ip() {
    local last_octet
    last_octet=$(grep -oP "10\.66\.66\.\K[0-9]+" "$WG_DIR/${WG_INTERFACE}.conf" \
                 | sort -n | tail -1)
    [ -z "$last_octet" ] && last_octet=1
    echo "10.66.66.$((last_octet + 1))"
}

client_dir="$WG_DIR/clients/$CLIENT_NAME"
mkdir -p "$client_dir"
chmod 700 "$client_dir"

if [ ! -f "$client_dir/private.key" ]; then
    umask 077
    wg genkey > "$client_dir/private.key"
    wg pubkey < "$client_dir/private.key" > "$client_dir/public.key"
    wg genpsk > "$client_dir/preshared.key"
fi

priv=$(cat "$client_dir/private.key")
pub=$(cat "$client_dir/public.key")
psk=$(cat "$client_dir/preshared.key")
server_pub=$(cat "$WG_DIR/server_public.key")
endpoint=$(curl -s --max-time 5 https://api.ipify.org || echo "REMPLACER_PAR_IP")
ip=$(next_client_ip)

wg set "${WG_INTERFACE}" peer "${pub}" \
    preshared-key "$client_dir/preshared.key" \
    allowed-ips "${ip}/32"
wg-quick save "${WG_INTERFACE}" >/dev/null

cat > "$client_dir/${CLIENT_NAME}.conf" <<EOF
[Interface]
PrivateKey = ${priv}
Address    = ${ip}/32
DNS        = ${WG_DNS}
MTU        = 1420

[Peer]
PublicKey           = ${server_pub}
PresharedKey        = ${psk}
Endpoint            = ${endpoint}:${WG_PORT}
AllowedIPs          = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
EOF
chmod 600 "$client_dir/${CLIENT_NAME}.conf"

echo ""
echo "=== Client ${CLIENT_NAME} ajoute ==="
echo "Configuration : $client_dir/${CLIENT_NAME}.conf"
echo ""
qrencode -t ansiutf8 < "$client_dir/${CLIENT_NAME}.conf" 2>/dev/null || true
echo ""
wg show "${WG_INTERFACE}"

#!/usr/bin/env bash
# =====================================================================
#  AuroraVPN - Provisioning serveur WireGuard
# =====================================================================
#  Cible : Ubuntu 22.04+ / Debian 12+ / fresh VPS root
#  Hebergeurs testes : Hetzner Cloud, OVH VPS, DigitalOcean,
#                      Vultr, Linode, Scaleway
#
#  Usage :
#    ssh root@<server-ip>
#    curl -fsSL https://raw.githubusercontent.com/<vous>/AuroraVPN/main/server_setup/install_wireguard.sh -o install_wireguard.sh
#    chmod +x install_wireguard.sh
#    ./install_wireguard.sh                  # creation serveur + 1er client
#    ./install_wireguard.sh client2          # creation d'un client supplementaire (apres install)
#
#  En sortie :
#    - serveur WG actif sur UDP 51820
#    - fichier client : /etc/wireguard/clients/<nom>/<nom>.conf
#    - QR code affiche dans le terminal (pour mobile)
# =====================================================================

set -euo pipefail

# ----- Configuration (peut etre surchargee par variables d'env) ------

WG_INTERFACE="${WG_INTERFACE:-wg0}"
WG_PORT="${WG_PORT:-51820}"
WG_SUBNET="${WG_SUBNET:-10.66.66.0/24}"
WG_SERVER_IP="${WG_SERVER_IP:-10.66.66.1}"
WG_DNS="${WG_DNS:-1.1.1.1, 9.9.9.9}"
WG_DIR="/etc/wireguard"
CLIENT_NAME="${1:-aurora-client}"

C_GREEN="\033[1;32m"
C_CYAN="\033[1;36m"
C_AMBER="\033[1;33m"
C_RED="\033[1;31m"
C_RESET="\033[0m"

step()  { echo -e "${C_CYAN}==> $*${C_RESET}"; }
ok()    { echo -e "${C_GREEN}    OK${C_RESET}"; }
warn()  { echo -e "${C_AMBER}    !  $*${C_RESET}"; }
fatal() { echo -e "${C_RED}!! $*${C_RESET}"; exit 1; }

# ----- Verifications --------------------------------------------------

require_root() {
    [ "$EUID" -eq 0 ] || fatal "Doit etre lance en root (utiliser sudo)."
}

detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_ID="${ID,,}"
        OS_VER="${VERSION_ID:-}"
    else
        fatal "Impossible de detecter l'OS."
    fi
    case "$OS_ID" in
        ubuntu|debian) ;;
        *) warn "OS non teste ($OS_ID). Le script pourrait fonctionner si apt est present." ;;
    esac
}

# ----- Etapes ---------------------------------------------------------

install_packages() {
    step "Installation de WireGuard et des dependances..."
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        wireguard wireguard-tools iptables qrencode curl ca-certificates
    ok
}

detect_public_interface() {
    step "Detection de l'interface reseau publique..."
    PUB_IFACE=$(ip route get 8.8.8.8 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="dev") {print $(i+1); exit}}')
    [ -n "$PUB_IFACE" ] || fatal "Interface publique introuvable."
    echo "    -> $PUB_IFACE"
    ok
}

generate_server_keys() {
    step "Generation des cles serveur..."
    umask 077
    mkdir -p "$WG_DIR"
    cd "$WG_DIR"
    if [ ! -f server_private.key ]; then
        wg genkey > server_private.key
        wg pubkey < server_private.key > server_public.key
        ok
    else
        warn "Cles deja existantes, on garde les anciennes."
    fi
}

write_server_config() {
    step "Ecriture de la configuration serveur..."
    local server_priv
    server_priv=$(cat "$WG_DIR/server_private.key")
    cat > "$WG_DIR/${WG_INTERFACE}.conf" <<EOF
[Interface]
Address    = ${WG_SERVER_IP}/24
ListenPort = ${WG_PORT}
PrivateKey = ${server_priv}
SaveConfig = true

PostUp   = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o ${PUB_IFACE} -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o ${PUB_IFACE} -j MASQUERADE
EOF
    chmod 600 "$WG_DIR/${WG_INTERFACE}.conf"
    ok
}

enable_ip_forwarding() {
    step "Activation du IP forwarding..."
    if grep -qE "^#?net\.ipv4\.ip_forward" /etc/sysctl.conf; then
        sed -i 's|^#\?net\.ipv4\.ip_forward.*|net.ipv4.ip_forward=1|' /etc/sysctl.conf
    else
        echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
    fi
    sysctl -p > /dev/null
    ok
}

detect_oracle_cloud() {
    # Oracle Cloud Always Free a un /etc/oci-hostname.conf, et son image
    # Ubuntu par defaut contient une regle iptables REJECT qui bloque tout
    # le trafic entrant (a part SSH). Il faut INSERER nos regles AVANT
    # cette regle REJECT (sinon elles sont ignorees).
    if [ -f /etc/oci-hostname.conf ] || \
       grep -qi "oracle" /sys/class/dmi/id/sys_vendor 2>/dev/null || \
       grep -qi "OracleCloud" /sys/class/dmi/id/chassis_asset_tag 2>/dev/null; then
        IS_ORACLE_CLOUD=1
        echo "    -> Oracle Cloud detecte"
    else
        IS_ORACLE_CLOUD=0
    fi
}

open_firewall_port() {
    step "Ouverture du port UDP ${WG_PORT}..."
    detect_oracle_cloud

    if command -v ufw >/dev/null 2>&1; then
        ufw allow "${WG_PORT}/udp" >/dev/null 2>&1 || true
        echo "    -> ufw : autorise"
    fi
    if command -v firewall-cmd >/dev/null 2>&1; then
        firewall-cmd --permanent --add-port="${WG_PORT}/udp" >/dev/null 2>&1 || true
        firewall-cmd --reload >/dev/null 2>&1 || true
        echo "    -> firewalld : autorise"
    fi

    if [ "${IS_ORACLE_CLOUD:-0}" -eq 1 ]; then
        # Oracle Cloud : on INSERE en tete (-I 1) pour passer avant le REJECT.
        iptables -I INPUT  1 -p udp --dport "${WG_PORT}" -j ACCEPT 2>/dev/null || true
        iptables -I INPUT  2 -i  "${WG_INTERFACE}" -j ACCEPT 2>/dev/null || true
        iptables -I FORWARD 1 -i "${WG_INTERFACE}" -j ACCEPT 2>/dev/null || true
        iptables -I FORWARD 2 -o "${WG_INTERFACE}" -j ACCEPT 2>/dev/null || true
        # Sauvegarde persistante (Oracle utilise iptables-persistent ou netfilter-persistent)
        if command -v netfilter-persistent >/dev/null 2>&1; then
            netfilter-persistent save >/dev/null 2>&1 || true
        elif command -v iptables-save >/dev/null 2>&1; then
            mkdir -p /etc/iptables
            iptables-save  > /etc/iptables/rules.v4 2>/dev/null || true
            ip6tables-save > /etc/iptables/rules.v6 2>/dev/null || true
        fi
        echo "    -> Oracle : regles inserees AVANT le REJECT par defaut"
        echo ""
        echo "    !! N'OUBLIE PAS d'ouvrir aussi UDP ${WG_PORT} dans la"
        echo "       Security List de ta Virtual Cloud Network (console"
        echo "       Oracle Cloud > Networking > VCN > Security Lists)."
    else
        iptables -I INPUT -p udp --dport "${WG_PORT}" -j ACCEPT 2>/dev/null || true
    fi
    ok
}

start_wireguard() {
    step "Demarrage du service WireGuard..."
    systemctl enable "wg-quick@${WG_INTERFACE}" >/dev/null 2>&1 || true
    systemctl restart "wg-quick@${WG_INTERFACE}"
    sleep 1
    if systemctl is-active --quiet "wg-quick@${WG_INTERFACE}"; then
        ok
    else
        fatal "Service WireGuard inactif. Voir : journalctl -xeu wg-quick@${WG_INTERFACE}"
    fi
}

# ----- Gestion des clients --------------------------------------------

next_client_ip() {
    # Recupere la derniere IP attribuee dans la conf et incremente.
    local last_octet
    last_octet=$(grep -oP "10\.66\.66\.\K[0-9]+" "$WG_DIR/${WG_INTERFACE}.conf" 2>/dev/null \
                 | sort -n | tail -1)
    if [ -z "$last_octet" ] || [ "$last_octet" -lt 1 ]; then
        last_octet=1
    fi
    echo "10.66.66.$((last_octet + 1))"
}

create_client() {
    local name="$1"
    step "Creation du client : ${name}..."
    local client_dir="$WG_DIR/clients/$name"
    mkdir -p "$client_dir"
    chmod 700 "$client_dir"

    # Cles client (idempotent)
    if [ ! -f "$client_dir/private.key" ]; then
        wg genkey > "$client_dir/private.key"
        wg pubkey < "$client_dir/private.key" > "$client_dir/public.key"
        wg genpsk > "$client_dir/preshared.key"
        chmod 600 "$client_dir"/*.key
    fi

    local client_priv client_pub client_psk server_pub server_endpoint client_ip
    client_priv=$(cat "$client_dir/private.key")
    client_pub=$(cat "$client_dir/public.key")
    client_psk=$(cat "$client_dir/preshared.key")
    server_pub=$(cat "$WG_DIR/server_public.key")
    server_endpoint=$(curl -s --max-time 5 https://api.ipify.org || echo "REMPLACER_PAR_IP_PUBLIQUE")
    client_ip=$(next_client_ip)

    # Ajout du peer cote serveur (live + persistant)
    wg set "${WG_INTERFACE}" peer "${client_pub}" \
        preshared-key "$client_dir/preshared.key" \
        allowed-ips "${client_ip}/32"
    wg-quick save "${WG_INTERFACE}" >/dev/null 2>&1

    # Generation du fichier client .conf
    cat > "$client_dir/${name}.conf" <<EOF
# === AuroraVPN client : ${name} ===
[Interface]
PrivateKey = ${client_priv}
Address    = ${client_ip}/32
DNS        = ${WG_DNS}
MTU        = 1420

[Peer]
PublicKey           = ${server_pub}
PresharedKey        = ${client_psk}
Endpoint            = ${server_endpoint}:${WG_PORT}
AllowedIPs          = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
EOF
    chmod 600 "$client_dir/${name}.conf"

    echo ""
    echo -e "${C_GREEN}=== Client ${name} cree ===${C_RESET}"
    echo "Fichier de configuration :"
    echo "    $client_dir/${name}.conf"
    echo ""
    echo "Recopiez-le sur votre Windows dans :"
    echo "    C:\\ProgramData\\AuroraVPN\\aurora.conf"
    echo "puis lancez AuroraVPN avec real_subprocess=True."
    echo ""
    echo "Ou scannez le QR ci-dessous depuis l'app WireGuard mobile :"
    echo ""
    qrencode -t ansiutf8 < "$client_dir/${name}.conf" || warn "qrencode indispo"
    echo ""
}

# ----- Modes d'execution ----------------------------------------------

main() {
    require_root
    detect_os

    if [ -f "$WG_DIR/${WG_INTERFACE}.conf" ] && [ -n "${1:-}" ]; then
        # Serveur deja installe + nom client passe -> ajout client uniquement
        echo -e "${C_CYAN}Serveur WireGuard deja installe.${C_RESET}"
        echo "Ajout d'un nouveau client : $CLIENT_NAME"
        detect_public_interface  # n'est utilise que pour le NAT, deja fait
        create_client "$CLIENT_NAME"
        exit 0
    fi

    install_packages
    detect_public_interface
    generate_server_keys
    write_server_config
    enable_ip_forwarding
    open_firewall_port
    start_wireguard
    echo ""
    create_client "$CLIENT_NAME"

    echo -e "${C_GREEN}=== Tout est pret. ===${C_RESET}"
    echo "Pour ajouter un autre client plus tard :"
    echo "    $0 nom-du-client"
    echo ""
    echo "Verification du statut :"
    wg show
}

main "$@"

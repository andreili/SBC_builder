EAPI=8

DESCRIPTION=""
SLOT="0"
KEYWORDS="~alpha amd64 arm arm64 hppa ~ia64 ~loong ~m68k ~mips ppc ppc64 ~riscv ~s390 sparc x86"
IUSE="+curl +imagemagick mysql postgres sqlite"
REQUIRED_USE="|| ( mysql postgres sqlite )"

RDEPEND="
        dev-lang/php[curl?,filter,gd,hash(+),intl,json(+),mysql?,pdo,posix,postgres?,session,simplexml,truetype,xmlreader,xmlwriter,zip,sqlite?]
        imagemagick? ( dev-php/pecl-imagick )
        virtual/httpd-php
        media-libs/vips
        media-libs/exiftool
        dev-php/pdlib
        app-admin/sudo
        net-analyzer/zabbix
        net-dns/unbound
        net-fs/nfs-utils
        net-misc/ntp
        net-misc/networkmanager
        net-p2p/transmission
        net-vpn/openvpn
        sys-fs/dosfstools
        sys-fs/mdadm
        www-apps/gitea
        www-servers/nginx
        dev-db/phpmyadmin
        app-misc/mosquitto
	sys-apps/smartmontools
"

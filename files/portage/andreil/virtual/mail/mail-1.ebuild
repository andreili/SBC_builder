# Copyright 1999-2025 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

DESCRIPTION=""
SLOT="0"
KEYWORDS="~amd64 ~arm ~arm64 ~x86"

#IUSE="+curl +imagemagick mysql postgres +sqlite"
#REQUIRED_USE="|| ( mysql postgres sqlite )"

RDEPEND="net-mail/dovecot
        www-apps/postfixadmin
        mail-client/roundcube
        mail-filter/amavisd-new
        mail-filter/spamassassin
        app-antivirus/clamav
        mail-mta/postfix
"

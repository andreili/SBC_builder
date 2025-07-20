EAPI=8

DESCRIPTION=""
SLOT="0"
KEYWORDS="~alpha amd64 arm arm64 hppa ~ia64 ~loong ~m68k ~mips ppc ppc64 ~riscv ~s390 sparc x86"
IUSE="mainsail"

RDEPEND="
	dev-vcs/git
	dev-python/pip
	media-libs/openjpeg
	dev-db/lmdb
	dev-libs/libsodium
	net-wireless/wireless-tools
	x11-libs/wxGTK
	x11-base/xorg-server
	media-libs/libjpeg-turbo
	sys-apps/systemd[policykit(+)]
	app-admin/sudo
	net-misc/networkmanager
	sys-apps/usbutils
	app-mobilephone/dfu-util
	mainsail? ( www-servers/nginx )
	media-video/ffmpeg[x264(+),x265(+)]
	sci-libs/openblas
	dev-python/matplotlib
	sys-devel/crossdev
	sys-apps/pciutils
	media-libs/libv4l
	net-misc/ntp
"

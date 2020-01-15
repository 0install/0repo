wget https://downloads.sourceforge.net/project/zero-install/0install/2.15/0install-linux-x86_64-2.15.tar.bz2
tar xjf 0install-linux-x86_64-2.15.tar.bz2
cd 0install-linux-x86_64-2.15
./install.sh home
export PATH=$HOME/bin:$PATH
0install add 0test http://0install.net/2008/interfaces/0test.xml --version='0.10..'
0install show 0test
cat > ~/.config/0install.net/injector/trustdb.xml <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<trusted-keys xmlns="http://zero-install.sourceforge.net/2007/injector/trust">
  <key fingerprint="DA9825AECAD089757CDABD8E07133F96CA74D8BA">
    <domain value="0install.net"/>
  </key>
  <key fingerprint="88C8A1F375928691D7365C0259AA3927C24E4E1E">
    <domain value="apps.0install.net"/>
  </key>
</trusted-keys>
EOF

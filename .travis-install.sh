wget https://downloads.sourceforge.net/project/zero-install/0install/2.10/0install-linux-x86_64-2.10.tar.bz2
tar xjf 0install-linux-x86_64-2.10.tar.bz2
cd 0install-linux-x86_64-2.10
./install.sh home
export PATH=$HOME/bin:$PATH
0install add 0test http://0install.net/2008/interfaces/0test.xml
cat > ~/.config/0install.net/injector/trustdb.xml <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<trusted-keys xmlns="http://zero-install.sourceforge.net/2007/injector/trust">
  <key fingerprint="DA9825AECAD089757CDABD8E07133F96CA74D8BA">
    <domain value="0install.net"/>
    <domain value="repo.roscidus.com"/>
  </key>
  <key fingerprint="617794D7C3DFE0FFF572065C0529FDB71FB13910">
    <domain value="repo.roscidus.com"/>
  </key>
  <key fingerprint="AC9B973549D819AE22BCD08D22EA111A7E4242A4">
    <domain value="repo.roscidus.com"/>
  </key>
</trusted-keys>
EOF

wget https://downloads.sourceforge.net/project/zero-install/0install/2.10/0install-linux-x86_64-2.10.tar.bz2
tar xjf 0install-linux-x86_64-2.10.tar.bz2
cd 0install-linux-x86_64-2.10
./install.sh home
export PATH=$HOME/bin:$PATH
0install add 0test http://0install.net/2008/interfaces/0test.xml

0repo
=====

Copyright Thomas Leonard, 2013


WARNING: much of this isn't implemented yet!


Introduction
------------

The 0repo software provides an easy and reliable way to maintain a repository
of 0install software for others to use. It can be run interactively by a single
developer on their laptop to maintain a repository of their own programs, or
installed as a service to allow a group of people to manage a set of programs
together.

Developers place new software releases in an "incoming" directory. 0repo
performs various checks on the new release and, if it's OK, adds it to the
repository. 0repo signs the published feeds with its GPG key.

The generated files may be rsync'd to a plain web host, without the need for
special software on the hosting platform.

Features:

- Can be run automatically as part of a scripted release process (for
  single-developer use).

- Can run as a service to accept contributions from multiple developers.

- Keeps feeds under version control.

- Repositories are always consistent (no missing keys, missing stylesheets,
  invalid URIs, etc).

- Files can be hosted on a standard web host (e.g. Apache).

- Provides a catalogue file listing all published feeds, which can be polled
  automatically by mirror sites (e.g. 0mirror).

- Supports both archives hosted within the repository and archives hosted
  externally.


Setup
-----

Run "0repo create DIR" to create a new repository (directory DIR will be
created to hold the files and will be populated with an initial configuration).

    $ 0repo create ~/repo
    $ cd ~/repo

Within this directory you will find:

- 0repo-config.py - configuration settings
- feeds	        - directory of (unsigned) feeds, initially empty
- feeds/.git	- version control Git repository for the feeds
- public	        - output directory (to be rsync'd to hosting provider)

Edit 0repo-config.py and set the required parameters:

These are required:

- The base URL for the feeds
- The base URL for the archives
- GPG key to use for signing feeds

These are optional:

- Command to upload feeds to web hosting
- Command to upload archives to archive hosting
- GPG keys of trusted contributors


Adding a release
----------------

0repo is designed to be called by other tools, such as 0release, 0template,
0downstream, etc. However, this section explains how the process can be
performed manually instead.

Place the XML of your new release in the "incoming" directory. For testing,
you could add this file as repo/incoming/GNU-Hello-1.3.xml:

    <?xml version="1.0" ?>
    <interface xmlns="http://zero-install.sourceforge.net/2004/injector/interface"
               xmlns:compile="http://zero-install.sourceforge.net/2006/namespaces/0compile">
      <name>GNU Hello</name>
      <summary>produces a familiar, friendly greeting</summary>
      <description>The GNU Hello program produces a familiar, friendly greeting.</description>
      <homepage>http://www.gnu.org/software/hello/</homepage>
    
      <feed-for interface='{REPO_BASE}/GNU-Hello.xml'/>
    
      <group arch="*-src">
        <command name='compile'
	         shell-command='"$SRCDIR/configure" --prefix="$DISTDIR" &amp;&amp; make install'>
          <compile:implementation main="bin/hello"/>
        </command>
        <requires interface="http://repo.roscidus.com/devel/make">
          <environment insert="bin" name="PATH"/>
        </requires>
        <implementation id="sha1=2aae32fd27d194167eac7eb611d7ce0983f83dd7" version="1.3">
          <archive extract="hello-1.3" href="http://ftp.gnu.org/gnu/hello/hello-1.3.tar.gz" size="87942"/>
        </implementation>
      </group>
    </interface>

Replace the `<feed-for>`'s `{REPO_BASE}` with the URL of the directory where
you will publish.

Note that, in this example, the archive is hosted outside of the repository. To
store the release in the repository, use a relative href on the `<archive>`
element and place the archive in the incoming directory too. e.g.

    <archive extract="hello-1.3" href="hello-1.3.tar.gz" size="87942"/>

When you are ready, run 0repo inside the "repo" directory. If your new version
is accepted, a new unsigned feed file be created as repo/feeds/GNU-Hello.xml
and committed to Git. A signed version of this feed will appear as
repo/public/GNU-Hello.xml. If you specified a relative URL for the archive, the
signed version will have an absolute URL and the archive will be copied to your
configured archives directory. On success, the files are deleted from the
incoming directory.

You will also have a public/catalog.xml file listing the new program.

When 0repo generates the signed feeds it will also:

- check that each feed's URI is correct for its location
- add the stylesheet declaration
- for each relative <archive>'s href, check that the archive exists
  locally and make the URL absolute

The results go in a separate 'public' directory, which can then be
transferred to the hosting provider (e.g. using rsync). This directory
also contains a generated `catalog.xml` file, which 0mirror can poll.


Editing feeds
-------------

You can edit the unsigned feeds under repo/feeds whenever you want. Running
0repo again will regenerate the signed feeds in repo/public (if the source feed
has changed). You should commit your changes with `git commit`.

To remove a feed, `git rm repo/feeds/FEED.xml` and run `0repo` again.


Running a shared repository
---------------------------

For a shared repository: the release tool generates the archives and
the XML for the new version, signs the XML with the developer's key,
and uploads to a queue (could be e.g. FTP). 0repo downloads the
contents of the queue to its incoming directory, checks the signature
and merges the new XML into the feed. If there's a problem, it emails
the user.

For other edits (e.g. adding a <package-implementation> or adding a missing
dependency to an already-released version), the contributor sends a Git pull
request. The repository owner merges the pull request and runs
0repo.


Auditing
--------

When 0repo adds a new release, the Git commit message includes the XML,
including the signature, if any. This makes it possible to tell whether a
malicious update was caused by a compromised 0repo (commit is invalid) or by a
compromised contributor (the malicious XML is correctly signed by that
contributor).

Commits made by 0repo are signed with its GPG key. You can check these
signatures using `git log --show-signature` in the `feeds` directory.


Conditions
----------

This library is free software; you can redistribute it and/or
modify it under the terms of the GNU Lesser General Public
License as published by the Free Software Foundation; either
version 2.1 of the License, or (at your option) any later version.

This library is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public
License along with this library; if not, write to the Free Software
Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307  USA

The feed.xsl and feed.css stylesheets have their own license; see
the file headers for details.


Bug Reports
-----------

Please report any bugs to [the 0install mailing list](http://0install.net/support.html).

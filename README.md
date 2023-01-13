0repo
=====

Copyright Thomas Leonard, 2013


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

- Can run as a service to accept contributions from multiple developers (not
  yet implemented).

- Keeps feeds under version control.

- Repositories are always consistent (no missing keys, missing stylesheets,
  invalid URIs, etc).

- Files can be hosted on a standard web host (e.g. Apache).

- Provides a catalogue file listing all published feeds, which can be polled
  automatically by mirror sites (e.g. 0mirror).

- Supports both archives hosted within the repository and archives hosted
  externally.


Installation
------------

To add 0repo:

    0install add 0repo https://apps.0install.net/0install/0repo.xml

Note on upgrading:

Starting from version 0.11, 0repo uses Python 3. Since your configuration file
is in Python syntax, you will need to convert it to use Python 3 syntax. This
can be done automatically by running the [2to3][] tool on it.


Setup
-----

If you're setting up a repository for a single developer then you can use
your existing personal GPG key (if you have one). Otherwise, you should create
a new one:

    $ gpg --gen-key

You can accept the defaults offered. Make sure you specify an email address,
because 0repo uses that as the committer in Git log messages, which require
an email address.

Then run "0repo create DIR KEY" to create the new repository (directory DIR
will be created to hold the files and will be populated with an initial
configuration).

    $ 0repo create ~/repositories/myrepo 'John Smith'
    $ cd ~/repositories/myrepo

Within this directory you will find:

- `0repo-config.py`: configuration settings
- `feeds`: directory of (unsigned) feeds, initially empty
- `feeds/.git`: version control Git repository for the feeds
- `incoming`: queue of incoming files to be processed
- `public`: output directory (to be synced to hosting provider)

Edit `0repo-config.py` and set the required parameters:

These constants and functions must be set:

- `REPOSITORY_BASE_URL`: The base URL for the feeds
- `ARCHIVES_BASE_URL`: The base URL for the archives
- `GPG_SIGNING_KEY`: Should be already set to the key you specified
- `upload_public_dir`: Code to upload feeds to web hosting
- `get_feeds_rel_path`: Part of the feed's URL following `REPOSITORY_BASE_URL`
- `get_public_rel_path`: Path of feed generated (signed) feed placed under `public`

These are optional:

- `SIGN_COMMITS`: Whether 0repo should sign Git commits it makes
- `CONTRIBUTOR_GPG_KEYS`: GPG keys of trusted contributors
- `LOCAL_ARCHIVES_BACKUP_DIR`: Where to keep local copies of uploaded archives
- `get_archive_rel_url`: Layout of your file server (e.g. a single directory or nested)
- `check_new_impl`: Policy checks for new code (e.g. check license is present and acceptable)
- `upload_archives`: Code to upload archives to archive hosting
- `CHECK_DIGESTS`: Recalculate digests specified for local archives in incoming feeds
- `TRACK_TESTING_IMPLS`: Prompt about old implementations that are "testing" too long
- `GPG_PUBLIC_KEY_DIRECTORY`: Path relative to each feed to place the GPG key
- `is_excluded_from_catalog`: Controls whether feed should be excluded from generated catalog
- `check_uploaded_archive`: Check to verify archive has been uploaded correctly
- `check_external_archive`: Check to verify URL of external archive is correct

Finally, register this repository so that other tools can find it (you need to do this after setting `REPOSITORY_BASE_URL`):

    $ 0repo register
    Created new entry in /home/me/.config/0install.net/0repo/repositories.json:
    http://example.com/: {"path": "/home/me/repositories/myrepo", "type": "local"}


Importing pre-existing feeds
----------------------------

If you've been managing a set of feeds without 0repo, you can import them into it using the `add` command:

    cd .../my-old-repository
    0repo add *.xml

The feeds will be added to the `feeds` directory, with any signatures removed (the signature will be stored in the Git commit message). 0repo looks at the `uri` attribute in the XML to decide which of the registered repositories to use.

Note: Any archives referenced in the feeds will not be imported or managed by
0repo. It will simply continue using the existing URL. See "Importing or
reindexing archives" below if you want 0repo to track your existing archives
(this is optional).

If you get it wrong and want to retry, just revert `/feeds` (which is version controlled with Git) to the previous state. e.g.

    $ cd feeds
    $ git tag before-import
    $ 0repo add .../*.xml
    [ Problem ]
    $ git reset --hard before-import
    [ Fix problem ]
    $ 0repo add .../*.xml


Adding a release
----------------

To add a release, create a local XML file containing just the new version, with a `<feed-for>` giving the target feed. For example, you could do this using [0template](http://0install.net/0template.html):

    $ 0template someprog.xml.template version=1.2
    Writing someprog-1.2.xml

Then, ask 0repo to add the new XML to the repository:

    $ 0repo add someprog-1.2.xml

0repo will use the `<feed-for>` to select the correct repository and will add
it there. If the feed doesn't already exist in the repository, 0repo will
create a new one for it.


Archives
--------

If the archives are to be stored outside of the repository (e.g. an existing
3rd-party release), you can just include the full URL in the XML file.

On the other hand, if you wish to store the release archives in the repository,
use a simple name (with no "/" characters) as the href on the `<archive>`
element and place the archive in the same directory as your new XML. e.g.

    <archive extract="someprog-1.2" href="someprog-1.2.tar.gz" size="87942"/>

Then run `0repo add` on the XML to import it into the repository.

0repo will upload the archive to the repository's file hosting (using the command
configured in `0repo-config.py`) and insert the full URL into the generated feed.

0repo keeps track of which files have been uploaded where in the `/archives.db`
file. This is a plain text file which you can edit manually if needed. It
should always correspond to the state of the remote file hosting. Each time you
use 0repo to update the public feeds, it looks up the archive URLs in this file
to generate the full URLs in `/public`.

For example, to migrate all your archives to a new server:

1. Copy all the files from the old server to the new one.
2. Do a search-and-replace in `archives.db` to give the new locations.
3. Run `0repo update` to update the public feeds.


Importing or reindexing archives
--------------------------------

You can update the `archives.db` file from the current state of the `archive-backups`
directory using the `0repo reindex` command.

For each file in `archive-backups`, 0repo will calculate the new URL as
`config.ARCHIVES_BASE_URL` + relative path within the archives directory. It will also
update the SHA1 sum.

It displays a list of changes and additions made to the archive and, for changes, saves
a copy of the old file. It does not automatically update the `public` directory; run
`0repo update` afterwards to do that, if you're happy with the changes.

For example:

    $ 0repo reindex
    test-2.tar.bz2:
      Old URL: http://ftp.example.com/pub/archives/test-2.tar.bz2
      New URL: http://example.com/myrepo/archives/test-2.tar.bz2
    Old database saved as /home/me/repositories/test/archives.db.old
    Updated /home/me/repositories/test/archives.db (changes: 1)
    Run '0repo update' to update public feeds.

TODO:

- Replace matching absolute URLs with short names under `/feeds`.
- Remove missing and unreferenced entries from the database.


The generated files
-------------------

After importing feeds or adding new versions, 0repo will generate a set of signed
feeds in the `public` directory, along with a `catalog.xml` file listing all the
programs in the repository, the repository's public GPG key and various stylesheets.

When 0repo generates the signed feeds it will also:

- check that each feed's URI is correct for its location
- add the stylesheet declaration
- for each relative `<archive>`'s `href`, check that the archive is known
  and make the URL absolute

The `public` directory can then be transferred to the hosting provider (e.g.
using rsync). Edit the `upload_public_dir` function in `0repo-config.py` to
let 0repo upload it automatically.


Editing feeds
-------------

You can edit the unsigned feeds under `repo/feeds` whenever you want. Running
`0repo` again will regenerate the signed feeds in repo/public (if the source feed
has changed). You should commit your changes with `git commit`.

You can also run `0repo modify URI (ID|VERSION) --stability=STABILITY` to modify
the stability rating of one or more implementations in a feed with a specific URI.
This is useful, e.g., for promoting a `testing` release to `stable`.

To remove a feed, `git rm repo/feeds/FEED.xml` and run `0repo` again.


Retracting a release
--------------------

If you make a release and then want to remove it, you have several options. You can
set the stability to `buggy`, e.g.

    0repo modify http://my/feed.yml 1.0 --stability=buggy

The release still exists, but 0install will avoid selecting it by default.

If you've just made a release and want to remove it completely, you can `git revert`
the commit that added it. Use `git log` to see the last log entry for your feed, e.g.

    $ cd feeds
    $ git log -n 1 myfeed.xml
    commit e9dfc086bb19f6fb94dc22c27ac2c0e70fbcd5cf
    Author: ...
    Date:   ...
    
        Added myprog 1.3
    
        <?xml version="1.0"?>
        ...

Use `git revert e9dfc086bb19` (the ID in the "commit" line) to revert it, then `0repo update`
to push the changes.

If you want to remove an older version, `git revert` might not work. In that case, you'll have
to edit the XML to remove the `<implementation>`s manually and then run `0repo update`.

Either way, once you've pushed the updated XML, you can then remove the archive
from the server and from the `archives.db` file.


Running a shared repository
---------------------------

This is not yet implemented.

For a shared repository: the release tool generates the archives and
the XML for the new version, signs the XML with the developer's key,
and uploads to a queue (could be e.g. FTP). 0repo downloads the
contents of the queue to its incoming directory, checks the signature
and merges the new XML into the feed. If there's a problem, it emails
the user.

For other edits (e.g. adding a `<package-implementation>` or adding a missing
dependency to an already-released version), the contributor sends a Git pull
request. The repository owner merges the pull request and runs 0repo.


Running in CI environments
--------------------------

To completely skip GnuPG signatures (e.g., when running a CI build to verify a pull request) set the environment variable `NO_SIGN` to any non-empty value.

To track the 0repo configuration in Git together with the feeds run:

    mv 0repo-config.py feeds/0repo-config.py
    ln -s feeds/0repo-config.py 0repo-config.py


Repository files
----------------

Here are the technical details about what files are in the repository and what
kind of manual editing is safe:

- `/incoming` is just a temporary holding area for new files. It should normally
  be empty, and you can freely delete anything from here.

- `/archives.db` is 0repo's idea of what files are on the remote file hosting server.
  If you move files around on the server, you should update this file to record the
  new information. You must not delete entries from here that are referenced by feeds
  under `/feeds`, otherwise 0repo won't be able to generate the public feeds.
  If necessary, you can regenerate `archives.db` from `archive-backups` using `0repo reindex`.

- `/feeds` is the state of the feeds in your repository. You can edit these freely.
  Changes are tracked under Git, and you'll need to commit any changes you make (0repo
  will refuse to update a feed which has uncommitted changes). You can use `git revert`,
  `git reset`, etc to back out changes.

- `/public` contains the generated files. It can be regenerated if lost. 0repo does not
  resign files if the new file would be otherwise identical to the existing file, and does
  not overwrite style-sheets, etc. However, you may wish to keep important state in here,
  so 0repo will never delete it itself and will restrict itself to updating the feeds.

- `/archive-backups` contains a copy of files uploaded to the file hosting. It
  is not read by 0repo in normal operation, but just provides a local backup
  copy for emergencies.


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

[2to3]: https://docs.python.org/2/library/2to3.html

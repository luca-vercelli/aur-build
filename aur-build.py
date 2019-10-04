#!/usr/bin/env python3
#
# external dependencies:
#   python-sh   (provides module sh)
#   pacman
#   pamac
#   wget
#   gunzip
#
# hacked: /etc/sudoers
#         /usr/share/polkit-1/rules.d/00-aur-build.rules

import argparse
import os
import sys
import time
import datetime
import csv
import pydoc
import glob
import sh
import getpass

VERSION = "0.1"
LOCAL_DB_PATH = "/var/cache/aur-build/"
LOCAL_DB = LOCAL_DB_PATH + "db"
PAMAC_BUILD_FOLDER = "/var/tmp/pamac-build-" + getpass.getuser()
PACMAN_PKG_FOLDER = "/var/cache/pacman/pkg/"

STATUS_NEW = "NEW"
STATUS_DOESNTBUILD = "DOESNTBUILD"
STATUS_BUILDS = "BUILDS"
STATUS_DELETED = "DELETED"
STATUS_OFFICIAL = "OFFICIAL"

SKIP_PACKAGES = None    # mainly for debug. None means no limit.
MAX_PACKAGES = None     # mainly for debug. None means no limit.

db = None
args = None


class Database:
    def __init__(self, path):
        self.path = path
        if not os.path.exists(self.path):
            self.create()

    def create(self):
        """
        Create/recreate database. No backup is done.
        """
        open(self.path, 'w').close()

    def write(self, pkgs_dict):
        """
        Overwrite whole database with new data
        """
        with open(self.path, 'w') as text_file:
            writer = csv.writer(text_file, delimiter=';')

            writer.writerow(['Name',
                             'Status',
                             'Build time (min)',
                             'Built on',
                             'Filename'])
            
            for pkg in sorted(pkgs_dict.values()):
                writer.writerow([pkg.pkgname,
                                 pkg.status,
                                 pkg.buildtime,
                                 pkg.builtwhen,
                                 pkg.filename])

    def load(self):
        """
        Load data from 
        :return: a dict pkgname -> Package object
        """
        pkgs_dict = {}
        with open(self.path, 'r') as text_file:
            csv_reader = csv.reader(text_file, delimiter=';')
            header = True
            for row in csv_reader:
                if header:
                    header = False
                else:
                    if not row or not row[0]:
                        continue
                    pkgname = row[0]
                    pkg = Package(pkgname,
                                  row[1] or STATUS_NEW,
                                  row[2] or None,
                                  row[3] or None,
                                  row[4] or None)
                    pkgs_dict[pkgname] = pkg
        return pkgs_dict

    def show(self):
        """
        This is essentially 
        less /var/cache/aur-build/db
        """
        file = open(self.path, 'r')
        pydoc.pager(file.read())
        file.close()


class Package:
    def __init__(self,
                 pkgname,
                 status=STATUS_NEW,
                 buildtime=None,
                 builtwhen=None,
                 filename=None):
        self.pkgname = pkgname
        self.status = status
        self.filename = filename
        try:
            self.buildtime = int(buildtime)
        except:
            self.buildtime = None
        self.builtwhen = builtwhen

    def __lt__(self, other):
        """
        This allows ordering a list of packages by name
        """
        return self.pkgname < other.pkgname

    def become_official(self):
        """
        Search the package in standard Manjaro repositories
        If found, set self.status = STATUS_OFFICIAL
        """
        try:
            sh.pacman("-Ss", self.pkgname)
            self.status = STATUS_OFFICIAL
            return True
        except sh.ErrorReturnCode_1:
            # if not found, pacman gives rc=1
            return False
        # for all other exceptions, raise

    def build(self):
        """
        Install the package via pamac, then removes it (just to have the .tar.xz)
        Update the object itself
        WARNING: enable wheel in /etc/sudoers, and polkit
        """
        start_time = time.time()  # in seconds from Epoch
        self.filename = None
        self.buildtime = None
        self.builtwhen = get_iso_date()   # es. 2008-11-22
        try:
            sh.pamac("build", "--no-confirm", self.pkgname,
                     _out=sys.stdout,
                     _err=sys.stderr)
            # I don't know package version here. I take the last one built
            file_filter = PACMAN_PKG_FOLDER + self.pkgname + "*.pkg.tar.xz"
            self.filename = sorted(glob.glob(file_filter))[-1]
            self.status = STATUS_BUILDS
        except sh.ErrorReturnCode as e:
            print("Pamac aborted with status %d" % e.exit_code)
            self.status = STATUS_DOESNTBUILD
        # for all other exceptions, raise

        self.buildtime = round((time.time() - start_time) / 60)

        if self.status == STATUS_BUILDS:
            try:
                sh.pamac("remove", "--no-confirm", self.pkgname,
                         _out=sys.stdout,
                         _err=sys.stderr)
                # suggestion: don't use RemoveUnrequiredDeps
            except sh.ErrorReturnCode as e:
                print("Warning! cannot remove package. Pamac aborted with status %d" %
                      e.exit_code)
            # for all other exceptions, raise

        # clean build folder
        # why pamac does not clean it by itself ?!?
        # warning: shutil.rmtree fails because pkg subfolder is not readable
        # shutil.rmtree(PAMAC_BUILD_FOLDER)
        sh.rm("-rf", PAMAC_BUILD_FOLDER)


def program_name():
    """
    Return this file's name, without path
    """
    return os.path.basename(__file__)


def print_version():
    """
    Just print program version
    """
    print("%s v.%s" % (program_name(), VERSION))


def create_arg_parser():
    """
    Create parser for parsing CLI arguments
    """
    parser = argparse.ArgumentParser(
                        description='Build all AUR packages via pamac')
    group_actions = parser.add_argument_group("Actions")
    group_actions.add_argument('--run',
                               dest='run',
                               action='store_true',
                               help='Shorthand for -d -n -e')
    group_actions.add_argument('-i', '--init-db',
                               dest='init_db',
                               action='store_true',
                               help='Initialize/clear database')
    group_actions.add_argument('-d', '--download',
                               dest='download',
                               action='store_true',
                               help='Download packages list and update database')
    group_actions.add_argument('-n', '--build-new-packages',
                               dest='build_new',
                               action='store_true',
                               help='Build all packages in status ' + STATUS_NEW)
    group_actions.add_argument('-e', '--build-packages-with-errors',
                               dest='build_err',
                               action='store_true',
                               help='Build all packages in status ' + STATUS_DOESNTBUILD)
    group_actions.add_argument('-r', '--rebuild-built-packages',
                               dest='rebuild',
                               action='store_true',
                               help='Rebuild all packages in status ' + STATUS_BUILDS)
    group_actions.add_argument('-b', '--build-all',
                               dest='build_all',
                               action='store_true',
                               help='Re/build all packages. Shorthand for -n -e -r')
    group_actions.add_argument('--show-log',
                               dest='show_log',
                               action='store_true',
                               help='Print database content')
    group_actions.add_argument('--stats',
                               dest='stats',
                               action='store_true',
                               help='Print database statistics')
    parser.add_argument('--skip',
                        dest='skip_packages',
                        action='store',
                        type=int,
                        default=SKIP_PACKAGES,
                        help='Skip first n packages in db')
    parser.add_argument('--max',
                        dest='max_packages',
                        action='store',
                        type=int,
                        default=MAX_PACKAGES,
                        help='Analyse at most first n packages in db (after skipped ones)')
    parser.add_argument('-v', '--version',
                        action='version',
                        version='%(prog)s ' + VERSION)
    return parser


def get_aur_package_list():
    """
    Retrieve full list of AUR packages
    currently, 'packages' file is 900Kb with 59K rows 
    :see:
    https://forum.manjaro.org/t/list-all-aur-packages-not-just-installed/39631/2
    :return: unsorted list of strings (package names only)
    """
    REMOTE_FILE = "https://aur.archlinux.org/packages.gz"

    stdout = sh.gunzip(sh.wget("-q", "-O", "-", REMOTE_FILE)).stdout
    # stdout is a 'bytes' object
    pkgnames_v0 = stdout.decode('utf-8').split('\n')
    pkgnames_v1 = [line.strip() for line in pkgnames_v0]
    pkgnames = [line for line in pkgnames_v1 if line and line[0] != '#']
    return pkgnames
    # NO WAY TO GET THE PKG VERSION ????


def get_iso_date():
    """
    es. 2008-11-22
    """
    return str(datetime.date.today())


def get_iso_time():
    """
    es. 2008-11-22 23:59:59
    """
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())   


def build_all(pkgs_dict, build_status=[STATUS_NEW]):
    """
    Build all packages with correct status
    """
    num_packages = len(pkgs_dict)
    num_skipped_packages = 0
    num_analysed_packages = 0
    for pkgname, pkg in pkgs_dict.items():
        print("=== Reading package: %s =========" % pkgname)
        
        if args.skip_packages and num_skipped_packages < args.skip_packages:
            print("Skipping.")
            num_skipped_packages += 1
            continue
        
        num_analysed_packages += 1

        if pkg.status not in build_status:
            must_build = False
            # DELETED and OFFICIAL packages fall here
            # We never build packages DELETED or OFFICIAL
        elif pkg.become_official():
            db.write(pkgs_dict)
            must_build = False
        else:
            must_build = True

        if must_build:
            pkg.build()
            db.write(pkgs_dict)
        else:
            print("Skipping, package has status %s" % pkg.status)

        print("%d packages elaborated out of %d (%d%%)" % (
              num_skipped_packages + num_analysed_packages,
              num_packages,
              (num_skipped_packages + num_analysed_packages) // num_packages))

        if args.max_packages and num_built_packages >= args.max_packages:
            print("====================")
            print("Exiting because we analysed MAX_PACKAGES=%d packages" %
                  num_built_packages)
            return


def update_db():
    """
    Update packages database
    i.e. download packages list, add new packages, mark missing packages as DELETED
    """
    pkgs_dict = db.load()
    new_pkg_names = set(get_aur_package_list())
    for pkgname in pkgs_dict:
        if pkgname not in new_pkg_names:
            pkg = pkgs_dict[pkgname]
            pkg.status = "DELETED"
    for pkgname in new_pkg_names:
        if pkgname not in pkgs_dict:
            pkgs_dict[pkgname] = Package(pkgname)
    db.write(pkgs_dict)


def print_statistics(pkgs_dict):
    """
    Print out statistics on database, grouped by status
    """
    pkgcnt = {
        STATUS_NEW: 0,
        STATUS_DOESNTBUILD: 0,
        STATUS_BUILDS: 0,
        STATUS_DELETED: 0,
        STATUS_OFFICIAL: 0
        }
    buildtime = {
        STATUS_NEW: 0,
        STATUS_DOESNTBUILD: 0,
        STATUS_BUILDS: 0,
        STATUS_DELETED: 0,
        STATUS_OFFICIAL: 0
        }
    fsize = 0
    max_buildtime = 0
    max_fsize = 0

    for pkg in pkgs_dict.values():
        pkgcnt[pkg.status] = pkgcnt[pkg.status] + 1
        tm = pkg.buildtime or 0
        buildtime[pkg.status] = buildtime[pkg.status] + tm
        if tm > max_buildtime:
            max_buildtime = tm
        if pkg.filename is not None:
            sz = os.path.getsize(pkg.filename)              # TODO could be stored on db
            fsize = fsize + sz
            if sz > max_fsize:
                max_fsize = sz

    for status, time in buildtime.items():
        if time < 60:                   # min/hour
            time = str(time) + "'"
        elif time < 288:                # min/day
            time = str(time // 60) + "h" + str(time % 60) + "'"
        else:
            time = str(time // 288) + "d" + str((time % 288) // 60) + "h"
        buildtime[status] = time
        
    print("\t\tPckgs\tBuild time (h)\tSize (Mb)")
    print(("Builds:\t\t%d\t%s\t\t\t%d\n" +
           "Doesn't build:\t%d\t%s\n" +
           "New:\t\t%d\t%s\n" +
           "Deleted:\t%d\t%s\n" +
           "Official:\t%d\t%s\n") %
          (pkgcnt[STATUS_BUILDS],      buildtime[STATUS_BUILDS],        fsize//1048576,
           pkgcnt[STATUS_DOESNTBUILD], buildtime[STATUS_DOESNTBUILD],
           pkgcnt[STATUS_NEW],         buildtime[STATUS_NEW],
           pkgcnt[STATUS_DELETED],     buildtime[STATUS_DELETED],
           pkgcnt[STATUS_OFFICIAL],    buildtime[STATUS_OFFICIAL]))
    print("Max build time for a package is " + str(max_buildtime) + " min. Max file size is " + str(max_fsize) + "Mb.")


def check_if_root():
    if os.geteuid() != 0:
        exit("You need to have root privileges to run this script.")


if __name__ == "__main__":
    parser = create_arg_parser()
    args = parser.parse_args()

    db = Database(LOCAL_DB)

    something_was_done = False
    
    if args.run:
        args.download = True
        args.build_new = True
        args.build_err = True
    
    if args.build_all:
        args.build_new = True
        args.build_err = True
        args.rebuild = True

    if args.init_db:
        print("Cleaning database...")
        db.create()
        print("Done.")
        something_was_done = True

    if args.download:
        print("Updating package database...")
        update_db()
        print("Done.")
        something_was_done = True

    if args.build_new or args.build_err or args.rebuild:
        print("Start building packages at %s ..." % get_iso_time())
        pkgs_dict = db.load()
        
        allowed_status = []
        if args.build_new:
            allowed_status.append(STATUS_NEW)
        if args.build_err:
            allowed_status.append(STATUS_DOESNTBUILD)
        if args.rebuild:
            allowed_status.append(STATUS_BUILDS)
        
        build_all(pkgs_dict, allowed_status)
        print("Done.")
        something_was_done = True

    if args.show_log:
        db.show()
        something_was_done = True

    if args.stats:
        pkgs_dict = db.load()
        print_statistics(pkgs_dict)
        something_was_done = True

    if not something_was_done:
        print("Missing arguments.")
        parser.print_help()
        exit(2)

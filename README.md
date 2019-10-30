# aur-build
Build **all** AUR packages

Many days of execution can be required to build all. I am building all packages in a VirtualBox machine with 2GB RAM, 1GB /tmp space, inside a laptop (Manjaro Linux CLI). I expect at least 200 days of execution (=5 min x 58000 packages), and many packages won't build due to lack of resources.

## Install
You are strongly suggested to install this only on a dedicatd machine, or under chroot.

You have to enable AUR repositories on `pamac`.

Install deplendencies and paths:

    pacman -Syu base-devel python-sh pamac-cli
    
    mkdir -p /var/cache/aur-build
    chmod 777 /var/cache/aur-build


You have to hack `sudo` and `policykit` in order to avoid `pamac` to ask for passwords. For example in this way:

    gpasswd -a %%%myusername%%% wheel

    echo '
    %wheel ALL=(ALL) NOPASSWD: ALL
    ' > /etc/sudoers.d/90-aur-build

    echo '
    // -*- mode: js2 -*-
    polkit.addRule(function(action, subject) {
        if ((action.id === "org.freedesktop.policykit.exec" || 
             action.id === "org.manjaro.pamac.commit")&&
            subject.active === true && subject.local === true &&
            subject.isInGroup("wheel")) {
                return polkit.Result.YES;
        }
    });
    ' > /usr/share/polkit-1/rules.d/20-aur-build.rules

## Usage

Run with

    ./aur-build.py --run

Build results are saved in a database `/var/cache/aur-build/db`.
Show some statistics on this database with

    ./aur-build.py --stats
    
Other options are documented with

    ./aur-build.py --help

## Bad packages to take care of

`acestream-mozilla-plugin` build fails, after 1347 minutes of build (this shouldn't happen with new _timeout_ option)

`acpi_call-ck` asks the user for something, even if `--no-confirm` pacman option has been selected

`active-collab-timer` asks the user for something, even if `--no-confirm` pacman option has been selected

`adwaita-icon-theme-git` this removes `pamac` !!! So following build will fail

`adwaita-qt` hangs up

`alink` asks the user for something, even if `--no-confirm` pacman option has been selected

`amass` builds something as root ?!? then cannot delete it


# aur-build
Build **all** AUR packages via `pamac` (i.e. this is intended for Manjaro Linux)

Many days of execution can be required to build all. I am building all packages in a VirtualBox machine with 2GB RAM, 1GB /tmp space, inside a laptop. I expect at least 40 days of execution (=1 min x 50000 packages), and many packages won't build due to lack of resources.

## Install
You are strongly suggested to install this only on a dedicatd machine, or under chroot.

You have to enable AUR repositories on `pamac`.

Install deplendencies and paths:

    pacman -Syu base-devel python-sh
    
    mkdir -p /var/cache/aur-build
    chmod 777 /var/cache/aur-build


You have to hack `sudo` and `policykit` in order to avoid `pamac` to ask for passwords. For example in this way:

    gpasswd -a %%%myusername%%% wheel

    echo << END > /etc/sudoers.d/90-aur-build
    %wheel ALL=(ALL) NOPASSWD: ALL
    END

    echo << END > /usr/share/polkit-1/rules.d/20-aur-build.rules
    // -*- mode: js2 -*-
    polkit.addRule(function(action, subject) {
        if ((action.id === "org.freedesktop.policykit.exec" || 
             action.id === "org.manjaro.pamac.commit")&&
            subject.active === true && subject.local === true &&
            subject.isInGroup("wheel")) {
                return polkit.Result.YES;
        }
    });
    END

## Usage

Run with

    ./aur-build.py --run

Other options are documented with

    ./aur-build.py --help

## Statistics on build results
Build results are saved in a database `/var/cache/aur-build/db`.
Show some statistics on this database with

    ./aur-build.py --stats





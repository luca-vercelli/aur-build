# aur-build
Build all AUR packages via `pamac` (i.e. this is intended for Manjaro Linux)

## Install
You are strongly suggested to install this only on a dedicatd machine, or on chroot.

You have to hack `sudo` and `policykit` in order to avoid pamac to ask for passwords.

    pacman -Syu base-devel python-sh
    
    mkdir -p /var/cache/aur-build
    chmod 777 /var/cache/aur-build

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

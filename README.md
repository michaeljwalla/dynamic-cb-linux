# dynamic-cb-linux
This is a lightweight clipboard manager for linux systems utilizing the Xorg server protocol.\
It features history, content pinning, disk caching, MIME conversion, file saving, and automatic startup.

## Requirements
- X11 server
- systemd-based distribution
- Internet

## Installation
- clone the repo
- missing dependencies will be listed -- if not using APT, you may need to install them via your own package manager.
- run `install.sh` in your shell to launch and establish the systemd process.

## Recommendations
- most desktop environments include processes to monitor and execute scripts based on keybinds. \
  bind `dynamic-clipboard` to a keybind of your choosing to quickly toggle the menu's visibility.
- pinned items persist across boots; unpinned items do not
- feel free to increase the history limits / item threshold. The default installation is targeted for memory-constrained devices.

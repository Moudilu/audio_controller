# Audio controller

Control audio output devices with their ALSA device and via remote.

## Installation

The recommended way to install and run the project is through [`pipx`](https://python-poetry.org/).
Install pipx with `sudo apt install pipx`.

Install the project with `sudo PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx install git+https://github.com/Moudilu/audio_controller.git`.

Install the required user and service:

```bash
sudo useradd -r audio-controller
sudo wget -O /etc/systemd/system/audio-controller.service https://github.com/Moudilu/audio_controller/raw/refs/heads/main/resources/audio-controller.service
sudo systemctl daemon-reload
sudo systemctl enable --now audio-controller
```

Note: Allocating the user statically is required as `DynamicUser` does not play well with DBus at the time of writing.

To update the project, run `sudo PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx upgrade git+https://github.com/Moudilu/audio_controller.git`.

## Projects used

- [python-evdev](https://python-evdev.readthedocs.io/en/latest/tutorial.html)
- [python3-uhubctl](https://github.com/nbuchwitz/python3-uhubctl)
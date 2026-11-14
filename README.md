# Acer Nitro ANV15-52 Hackintosh

OpenCore EFI and post-install scripts for the Acer Nitro ANV15-52: macOS Tahoe with **the Iris Xe and the RTX 5050 accelerated at the same time**.

> [!WARNING]
> Experimental drivers, tested on one laptop. **The post-install scripts have never run on a clean install,** only on a copy of the system tree. Back up your data first and read [docs/RECOVERY.md](docs/RECOVERY.md).

## Specs

| | |
| --- | --- |
| Laptop | Acer Nitro ANV15-52 |
| CPU | Intel Core i9-13900H |
| GPU | Intel Iris Xe, NVIDIA RTX 5050 Laptop |
| Display | 15.6" 1920×1080, 180 Hz (CSOT MNF601BA3-1) |
| Audio | Realtek ALC245 |
| Wi-Fi, Bluetooth | MediaTek MT7920 |
| Ethernet | Realtek Killer E2600 |
| macOS | Tahoe 26.7.3 (25G342) |
| Bootloader | OpenCore 1.0.9, started from rEFInd |
| SMBIOS | MacBookPro16,2 |

## Status

| Feature | | Notes |
| --- | --- | --- |
| Iris Xe and RTX 5050 acceleration | ✅ | Metal 2 and Metal 3, together |
| Internal panel | ✅ | 180 Hz, brightness |
| HiDPI | ✅ | On the panel, up to "looks like" 1600×900 |
| HDMI | ✅ | Up to 1080p at 144 Hz, and 4K at 60 Hz. A monitor plugged in after a boot without one lights up |
| USB-C video and hot plug | ✅ | One display, on the Iris Xe |
| Three displays | ✅ | Panel, USB-C, HDMI |
| HDR | ✅ | Over USB-C, and HDR10 over HDMI on the RTX: 1080p up to 144 Hz, and 4K at 60 Hz in YCbCr 4:2:2 when RGB at 10 bits is beyond the monitor's HDMI clock |
| Monitor control over DDC/CI | ✅ | A monitor on the RTX's HDMI: its brightness is read. Setting it from an app was not tried |
| Sleep and wake | ✅ | With the RTX on. Tested with the real NVRAM, not yet with the [emulated NVRAM](#nvram) of the `full` profile |
| Video decoding on the RTX | ✅ | H.264, VP9, AV1 in Chrome; H.264, HEVC, VP9 in Safari too, not AV1 ([Safari video](#safari-video-on-the-rtx)) |
| Protected video, Firefox | ✅ | Widevine test streams up to 4K. Netflix not tried yet |
| Protected video, Chrome | ✅ | Widevine, Netflix included, with [NMAppFree](#chrome-and-nmappfree) |
| Protected video, Safari | ❌ | No decoder for protected video |
| CPU turbo | ✅ | With HybridPM: one core reaches 4.64 GHz, for about 10 W more at idle |
| Speakers, headphones, internal microphone | ✅ | |
| HDMI audio | ✅ | Volume and mute from macOS, with `nmhdavol=1` |
| DisplayPort audio over USB-C | ✅ | Also after a short sleep; volume and mute as for HDMI |
| Keyboard, Fn keys, trackpad | ✅ | |
| Webcam, USB | ✅ | |
| Battery, charge limit, fans, sensors | ✅ | NitroSense app, and the RTX's temperatures and load in the SMC, the load taken from NVAccel's own statistics. The menu bar item is redrawn only when its text changes, and the app polls every 10 s while its window and panel are closed: WindowServer's "Invalid window" log lines went from about 45 to under 10 every 30 s |
| Ethernet | ✅ | The driver loads here, no cable test. Reported working on another PC with this chip |
| Wi-Fi and Bluetooth, original MediaTek MT7920 | ✅ | Wi-Fi 6 (802.11ax), with the access point's BSS color |
| Wi-Fi and Bluetooth with an Intel card instead | ✅ | Swap the kexts, see [efi/README.md](efi/README.md#kexts) |
| AirDrop | ✅ | With `-mtkawdl`, on by default. Tested with a Pixel through Quick Share: Pixel to Mac with this build, Mac to Pixel with the build just before it. Not tried with an iPhone |
| Handoff, Continuity | ❔ | Not tested |
| Powering off the RTX | ❌ | About 41 W at idle |
| Thunderbolt, FileVault, battery life | ❔ | Not tested |

## Quick guide

Full guide: [docs/INSTALL.md](docs/INSTALL.md).

1. **BIOS:** VMD off, Secure Boot off.
2. **USB stick,** FAT32, named `OPENCORE`:
   ```bash
   python3 efi/build_efi.py identity
   python3 efi/build_efi.py build --profile install
   python3 efi/build_efi.py deploy --profile install --volume /Volumes/OPENCORE --go
   ```
3. **rEFInd:** add [efi/refind-opencore.conf](efi/refind-opencore.conf) to `refind.conf`. There is no `BOOTx64.efi` here.
4. **macOS:** install it from the entry **OpenCore install**, then update to 26.7.3 (25G342).
5. **Drivers and final EFI,** on the new macOS, with the charger connected. The first `build` also compiles LLVM and clang for NVK: about two hours and 10 GB of disk. Do not restart until `install` says it has finished.
   ```bash
   xcode-select --install
   python3 postinstall/postinstall.py fetch
   python3 postinstall/postinstall.py build
   python3 efi/build_efi.py build --profile full --compiled ~/anv15-52-build/out
   python3 efi/build_efi.py deploy --profile full --volume /Volumes/OPENCORE --go
   sudo python3 postinstall/postinstall.py install --go
   ```
6. **First boot:** shut down, choose **OpenCore** in rEFInd, then at the desktop run `python3 postinstall/postinstall.py verify`.

To go back: `sudo python3 postinstall/postinstall.py rollback --go`.

The scripts build from the latest `acer/current` of each fork, which can be newer than this page. `fetch --tested` takes the commits last tested.

Serial, MLB, UUID and ROM are generated on your machine, in `private/identity.json`. Keep a copy, and do not publish it or an EFI built with it.

## Boot-args you can take out

On by default. Take them out of `boot-args` in your `config.plist` to go back. What each one does on this laptop: [efi/README.md](efi/README.md#boot-args-of-the-full-profile).

| Boot-args | What they do |
| --- | --- |
| `-wex-nv-video` | Safari decodes video on the RTX ([Safari video](#safari-video-on-the-rtx)) |
| `-wex-va-renderer` | Hardware video processing on the Iris Xe, through the Intel video driver corrected for this GPU. Experimental |
| `nvwallpaper=1` | The Aerial wallpaper decodes on the RTX |
| `-mtkawdl` | AirDrop on the MT7920: AWDL on the Wi-Fi, and the Bluetooth LE advertising that makes this Mac visible |
| `nmhdavol=1` | Volume and mute for the audio of the displays: HDMI on the RTX, DisplayPort over USB-C |
| `nvfb10bit=1 nvfbhdr=1` | HDR10 over HDMI on the RTX |
| `nvrmfbddc=1` | DDC/CI for a monitor on the RTX |
| `nvrmaspm=1 nvfbkeepfront=1 nvfbvrr=1` | NullMoth's ASPM, frame kept across mode changes and variable refresh: no effect seen here yet |

Some features now on in the kexts have a boot-arg that turns them off instead: `-wex-no-hdr-modes` for the HDR switch of a monitor on USB-C, `-nohpm` for HybridPM's turbo (one core at 4.64 GHz, about 10 W more at idle), `-mtknohe` for Wi-Fi 6 on the MT7920.

## Chrome and NMAppFree

The AMFI boot-args, which the Metal drivers not signed by Apple need, make the kernel treat every program as part of macOS and apply its strictest Mach IPC rules to all of them. Chrome's Widevine helper breaks one of those rules and is killed. [NMAppFree](https://github.com/Thatisjigen/NMAppFree), a Lilu plugin in the EFI, takes the apps outside the system folders out of that policy when they start, as macOS already does for a plugin host such as Firefox. It re-signs nothing and changes no file.

**Security:** this relaxes the kernel's Mach IPC hardening for every program outside `/System`, `/usr`, `/bin`, `/sbin` and `/Library/Apple`. That is how those apps run on a real Mac, but it is less hardening than the AMFI boot-args give them otherwise. The system binaries keep it.

| Boot-arg | What NMAppFree does |
| --- | --- |
| none | Every app outside the system folders. The mode that was tested |
| `-nmappfreeoff` | Nothing: Chrome goes back to no protected video |
| `-nmappfreedbg` | One log line for each app it exempts |

The other modes are in [its README](https://github.com/Thatisjigen/NMAppFree#modes-boot-args) and were not tested here.

## Safari video on the RTX

With `-wex-nv-video` in the boot-args, Safari's GPU process (`com.apple.WebKit.GPU`) decodes **H.264, HEVC and VP9** on the RTX, through the NVIDIA runtime's video decoders (`libnvencvt`) that a WhateverXe rule lets that process map. A 4K H.264 clip plays at about a fifth of the CPU a software decoder takes. AV1 stays off: 10-bit AV1 decodes wrong on this Blackwell GPU, so it is refused rather than shown wrong. Tested on YouTube up to 2160p.

## NVRAM

The `full` profile keeps NVRAM in memory, with OpenCore's `OpenVariableRuntimeDxe.efi` loaded early, before `OpenRuntime.efi`: nothing reaches the firmware's flash any more. OpenCore itself already wrote nothing there (`WriteFlash` is `false`); now what macOS and the kexts write stays in memory too. The `install` profile keeps the real NVRAM.

What is lost at each restart:

- **Panic reports.** The kernel writes a panic into NVRAM, now in memory, and the restart clears it: no report after the reboot.
- **Variables macOS writes,** such as the volume of the startup sound and any `sudo nvram` change, and NullMoth's boot guard (`nullmoth-nv-starts`, `nullmoth-nv-ok`): failed starts are not counted across restarts, so the guard never turns the NVIDIA driver off. If the RTX stops the boot, use `-nvoff` ([docs/RECOVERY.md](docs/RECOVERY.md)).
- **macOS updates** keep their state across restarts in NVRAM: update with the real NVRAM.

For the real NVRAM, to catch a panic or to update: in `UEFI` › `Drivers` disable `OpenVariableRuntimeDxe.efi` and set `LoadEarly` of `OpenRuntime.efi` back to `false`. Sleep and wake have not been tried yet with the emulated NVRAM.

## Known issues

- **Intel GPU resets:** in about one boot out of three the Intel blitter hangs and resets over and over, and everything slows down for some minutes. Cause unknown.
- **A panic when the Intel GPU stops answering:** seen twice with WhateverXe 0.8.2, under a heavy build and with the Aerial screensaver: the DEBUG build stopped at its check of the command streamer's status buffer. The build pinned here re-arms that buffer instead, at most once a second; it has not been needed yet.
- **Do not sleep with `-nvoff`:** the one try without the RTX ended in a watchdog panic.
- **4K at 60 Hz over HDMI goes out at 59.94 Hz:** the driver takes the first variant of the monitor's mode. At 60 Hz the HiDPI desktop that looks like 1920×1080 uses a 1080p signal; 4K at 60 Hz is shown at its own size.
- **A monitor on HDMI can look too dark:** macOS gives it gamma 1.961. Choose the profile `sRGB IEC61966-2.1` in System Settings › Displays.

## In this repository

- [efi/](efi/README.md): OpenCore configs without identity, ACPI, USB map, kexts, boot-args
- [postinstall/](postinstall/README.md): scripts that compile the drivers and install them, with the list of forks
- [docs/INSTALL.md](docs/INSTALL.md), [docs/RECOVERY.md](docs/RECOVERY.md), [docs/LICENSES.md](docs/LICENSES.md)

## Credits

[b00t0x](https://github.com/b00t0x/WhateverXe) for WhateverXe, [nullmoth](https://github.com/nullmoth/nvidia-macos-driver) for the NVIDIA driver, [acidanthera](https://github.com/acidanthera) for OpenCore, Lilu, VirtualSMC and AppleALC, and [mickys](https://github.com/mickys/nvenc), [ptnzzn](https://github.com/ptnzzn/NitroSense-macOS), [zzzyy678](https://github.com/zzzyy678/SMCNvidiaGPU), [pokipoi](https://github.com/pokipoi/LatSOF-Audio), [JulioNectar](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe) for XE-PM, [kitsuneislife](https://github.com/kitsuneislife), [e5u](https://github.com/e5u/SimpleMtkWlan) and [flxxxxddd](https://github.com/flxxxxddd/SimpleMtkBtFw) for the MediaTek Wi-Fi and Bluetooth, the Linux mt76 driver, HighDelay, retropineaple, Dino-VN, Dat Nguyen and many others.

## License

Scripts and documents: [MIT](LICENSE). The rest keeps its own license, and **NullMoth's NVIDIA drivers are for noncommercial use only**: [docs/LICENSES.md](docs/LICENSES.md). This repository does not contain macOS or any third-party binary.


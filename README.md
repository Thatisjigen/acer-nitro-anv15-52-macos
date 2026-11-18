# Acer Nitro ANV15-52 Hackintosh

OpenCore EFI and post-install scripts for the Acer Nitro ANV15-52: macOS Tahoe with **the Iris Xe and the RTX 5050 accelerated at the same time**, and AMFI on.

> [!WARNING]
> Tested on one laptop, the one below. The post-install scripts have not been run on a clean install yet: back up your data first and keep [docs/RECOVERY.md](docs/RECOVERY.md) at hand.

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
| Iris Xe and RTX 5050 acceleration | ✅ | Together: Metal 2 on the Iris Xe, Metal 3 and Metal 4 on the RTX |
| GPU for each app | ✅ | macOS's own processes on the Iris Xe, apps on the RTX; one app can be changed in NitroSense ([GPU for each app](#gpu-for-each-app)) |
| AMFI | ✅ | On, with [NMLibVal](#amfi) in the EFI |
| Internal panel | ✅ | 180 Hz, brightness, HiDPI |
| HDMI | ✅ | Up to 1080p at 144 Hz and 4K at 60 Hz; a monitor plugged in later lights up |
| USB-C video | ✅ | One display, hot plug |
| Three displays | ✅ | Panel, USB-C, HDMI |
| HDR | ✅ | Over USB-C, and HDR10 over HDMI |
| Monitor control over DDC/CI | ✅ | The brightness of a monitor on HDMI is read; setting it was not tried |
| Sleep and wake | ✅ | In S0 (Deep Idle): the PC stays asleep until the power button wakes it; macOS wakes it for a moment once an hour for its maintenance |
| Video decoding on the RTX | ✅ | H.264, HEVC and VP9 wherever macOS's decoders are asked, AV1 in Chrome ([Video on the RTX](#video-on-the-rtx)) |
| Video decoding on the Iris Xe | ⚠️ | HEVC yes, H.264 no: H.264 decodes on the RTX |
| Video encoding on the RTX | ✅ | H.264 and HEVC |
| Metal Performance Shaders on the Iris Xe | ✅ | Vision's image classification works, with the same results at every run |
| DLSS 4 | ❔ | Installed; not tried in a game yet ([DLSS 4](#dlss-4)) |
| Protected video | ✅ | Chrome, Netflix included, and Firefox. Not in Safari |
| CPU turbo, P-cores and E-cores | ✅ | One core at about 5.0 GHz, 5.1 at its peak, with HybridPM; background work on the E-cores with IntelHybridCores |
| Audio | ✅ | Speakers, headphones, internal microphone; HDMI and USB-C audio with volume and mute |
| Keyboard, Fn keys, trackpad, webcam, USB | ✅ | |
| Battery, charge limit, fans, sensors | ✅ | NitroSense app, the RTX's sensors included |
| Ethernet | ✅ | The driver loads; not tried with a cable |
| Wi-Fi and Bluetooth, MediaTek MT7920 | ✅ | Wi-Fi 6. An Intel card works too, tried with an AC 8265: swap the kexts, see [efi/README.md](efi/README.md#kexts) |
| AirDrop | ✅ | With a Pixel through Quick Share: about 10 MB/s to the phone, 13 MB/s from it. Not tried with an iPhone |
| Powering off the RTX | ⚙️ | Off by default: `nvrtd3=2` turns it on ([RTX power-off](#rtx-power-off)) |
| Handoff, Continuity, Thunderbolt, FileVault, battery life | ❔ | Not tested |

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

On by default. Take them out of `boot-args` in your `config.plist` to go back. All of them, and the switches that turn features of the kexts off: [efi/README.md](efi/README.md#boot-args-of-the-full-profile).

| Boot-args | What they do |
| --- | --- |
| `-wex-nv-video` | Safari decodes video on the RTX |
| `-wex-va-renderer` | Hardware video processing on the Iris Xe. Experimental |
| `hcmode=4` | Background work on the E-cores only, as on Apple Silicon |
| `shda-lang=it` | The language of the names of the audio outputs, Italian here: put your own |
| `-mtkawdl` | AirDrop on the MT7920 |
| `nmhdavol=1` | Volume and mute for the audio of the displays |
| `nvfb10bit=1 nvfbhdr=1` | HDR10 over HDMI on the RTX |
| `nvrmfbddc=1` | DDC/CI for a monitor on the RTX |
| `nvrmaspm=1 nvfbkeepfront=1 nvfbvrr=1` | NullMoth's ASPM, frame kept across mode changes and variable refresh |

**Keep `keepsyms=1`:** SimpleHDA needs it to load Apple's audio driver, and without it there is no sound.

## AMFI

AMFI, the kernel's check of code signatures, stays on. The GPU drivers in `/Library/GPUBundles` are not signed by Apple, so WindowServer and the apps would refuse to load them. **NMLibVal**, a Lilu plugin in the EFI, has AMFI accept those drivers, recognized by their path, and nothing else. At boot the kernel still logs that the NVIDIA drivers are signed ad hoc: that is expected.

NMLibVal is written for this laptop. Its source is not public yet; the compiled kext is in [efi/kexts](efi/kexts/NMLibVal.kext). If a macOS update leaves the desktop without acceleration, see [docs/RECOVERY.md](docs/RECOVERY.md).

## GPU for each app

The Iris Xe drives the panel. As on Apple's Macs with two GPUs, macOS's own processes draw on the Iris Xe, and apps are offered the RTX as the high-performance GPU. In NitroSense, under **Graphics per app**, one app can be set to Automatic, Power saving (the Iris Xe only) or Performance (the RTX as its default GPU); it applies when the app starts again.

The RTX goes to its full clocks only for an app set to Performance and for games. `BOOST=1` in `/Library/GPUBundles/nvmtl/nvrm610.conf` lets every app raise them.

## Video on the RTX

The NVIDIA plugin registers the RTX's video decoders in every process that loads it: H.264, HEVC and VP9 decode on the RTX in macOS's decode service, which works for QuickTime and the other apps, in Chrome, and in Safari with `-wex-nv-video`. AV1 decodes on the RTX in Chrome only. The Aerial wallpaper's movies, 4K at 240 pictures a second, are left to Apple's decoder on the Iris Xe.

## RTX power-off

Off by default. To turn it on, enable `SSDT-PEGP-PINS-ANV.aml` in `ACPI` › `Add` and add `nvrtd3=2` to the boot-args. The NVIDIA driver then cuts the RTX's power when nothing has used it for a minute, through the firmware's own power methods, and brings it back by itself in about a second and a half when something needs it: an app that draws on the RTX, a video in Safari, a monitor plugged into the HDMI port.

- It stays on while a monitor is on the HDMI port, which belongs to the RTX, while an app uses it (Chrome set to the RTX keeps it on), and while more than 256 MB of video memory is in use (`nvrtd3vram=<MB>` changes that).
- About 4.7 W less at an idle desktop, in one measurement on battery: 19.7 W with the card off, 24.4 W on.
- While it is off, NitroSense wakes it about once a minute to read its sensors. HDMI audio after the card has been off was not tried.
- Tried on this laptop with NullMoth 2.9: the card went off and came back four times, and the PC slept once with it off. With 3.0 it was only started switched off.

## DLSS 4

NullMoth's Metal plugin can run NVIDIA's DLSS behind MetalFX's temporal scaler. The last step of `install` downloads about 750 MB of NVIDIA's files (DLSS SDK runtimes, NGX from the Linux driver, nvJitLink), checks each one against its pinned SHA-256 and builds the GPU kernels for the RTX in `/Library/NullMoth/dlss`. **Those files stay under NVIDIA's licences:** do not publish them.

To leave it out: `install --go --skip dlss`. To take it out later: `sudo rm -rf /Library/NullMoth/dlss`.

## NVRAM

The `full` profile keeps NVRAM in memory, with OpenCore's `OpenVariableRuntimeDxe.efi`: nothing reaches the firmware's flash. Panic reports, `sudo nvram` changes and NullMoth's boot guard do not survive a restart, so if the RTX stops the boot use `-nvoff` ([docs/RECOVERY.md](docs/RECOVERY.md)).

**Update macOS with the real NVRAM:** in `UEFI` › `Drivers` disable `OpenVariableRuntimeDxe.efi` and set `LoadEarly` of `OpenRuntime.efi` back to `false`.

## Known issues

- **Hardware H.264 decoding on the Iris Xe does not work:** Apple's decoder refuses the session, so H.264 decodes on the RTX.

## In this repository

- [efi/](efi/README.md): OpenCore configs without identity, ACPI, USB map, kexts, boot-args
- [postinstall/](postinstall/README.md): scripts that compile the drivers and install them, with the list of forks
- [docs/INSTALL.md](docs/INSTALL.md), [docs/RECOVERY.md](docs/RECOVERY.md), [docs/LICENSES.md](docs/LICENSES.md)

## Credits

[b00t0x](https://github.com/b00t0x/WhateverXe) for WhateverXe, [nullmoth](https://github.com/nullmoth/nvidia-macos-driver) for the NVIDIA driver, [acidanthera](https://github.com/acidanthera) for OpenCore, Lilu, VirtualSMC and AppleALC, and [mickys](https://github.com/mickys/nvenc), [ptnzzn](https://github.com/ptnzzn/NitroSense-macOS), [zzzyy678](https://github.com/zzzyy678/SMCNvidiaGPU), [pokipoi](https://github.com/pokipoi/LatSOF-Audio), [rodgod-rr](https://github.com/rodgod-rr/IntelHybridCores) for IntelHybridCores, [JulioNectar](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe) for XE-PM, [kitsuneislife](https://github.com/kitsuneislife), [e5u](https://github.com/e5u/SimpleMtkWlan) and [flxxxxddd](https://github.com/flxxxxddd/SimpleMtkBtFw) for the MediaTek Wi-Fi and Bluetooth, the Linux mt76 driver, HighDelay, retropineaple, Dino-VN, Dat Nguyen, GeekAudio, kevineduardo, Ghltbm, kubus, januory, LSmurfs, Julian Buhagiar, renedis, nickk19, vikenzo196, 91270, SaqibAlMalik, thanhnndev, TrDiTu, myvoow, Axel Gneiting and Mel Henning of Mesa, and many others.

## License

Scripts and documents: [MIT](LICENSE). The rest keeps its own license, and **NullMoth's NVIDIA drivers are for noncommercial use only**: [docs/LICENSES.md](docs/LICENSES.md). This repository does not contain macOS or any third-party binary.

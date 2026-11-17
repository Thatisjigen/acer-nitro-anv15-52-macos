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
| Iris Xe and RTX 5050 acceleration | ✅ | Together: Metal 2 on the Iris Xe, Metal 3 and Metal 4 on the RTX |
| GPU for each app | ✅ | macOS's own processes draw on the Iris Xe, apps are offered the RTX as the high-performance GPU, and one app can be set to power saving or performance ([GPU for each app](#gpu-for-each-app)) |
| Internal panel | ✅ | 180 Hz, brightness |
| HiDPI | ✅ | On the panel, up to "looks like" 1600×900 |
| HDMI | ✅ | Up to 1080p at 144 Hz, and 4K at 60 Hz. A monitor plugged in after a boot without one lights up |
| USB-C video and hot plug | ✅ | One display, on the Iris Xe |
| Three displays | ✅ | Panel, USB-C, HDMI |
| HDR | ✅ | Over USB-C, and HDR10 over HDMI on the RTX, in RGB, with the desktop composed at 10 bits: 1080p at 120 Hz at 10 bits, and at 144 Hz at 8 bits with the PQ curve, as RGB at 10 bits there is beyond the HDMI clock the GPU allows. 4K at 60 Hz, which went out in YCbCr 4:2:2, takes the same 8-bit path now: not tried again |
| Monitor control over DDC/CI | ✅ | A monitor on the RTX's HDMI: its brightness is read. Setting it from an app was not tried |
| Sleep and wake | ✅ | S3, with the RTX on, and short: the PC wakes by itself ([Known issues](#known-issues)). The monitor on the RTX lights up again also when the GPU's wake work comes before the framebuffer's power-on (GeekAudio's fix). Tested with the real NVRAM; with the [emulated NVRAM](#nvram) of the `full` profile, only in EFIs that also had wake or S0 tables this one leaves out |
| DLSS 4 | ❔ | Installed by default, for games that use MetalFX's temporal scaler; not tried in a game yet ([DLSS](#dlss-4)) |
| Video decoding on the RTX | ✅ | H.264, HEVC and VP9 wherever macOS's decoders are asked: its decode service, Chrome, Safari. AV1 in Chrome, not in Safari ([Video on the RTX](#video-on-the-rtx)) |
| Video decoding on the Iris Xe | ❌ | H.264: the hardware decoder refuses the session. HEVC decodes there: the Aerial wallpaper's movies ([Known issues](#known-issues)) |
| Video encoding on the RTX | ✅ | H.264 and HEVC with NullMoth's encoders, in a test program that opens the RTX: 3.1 and 2.3 ms for a 1080p picture. No AV1 encoding on this card, and the Iris Xe's hardware encoder does not open a session |
| Protected video, Firefox | ✅ | Widevine test streams up to 4K. Netflix not tried yet |
| Protected video, Chrome | ✅ | Widevine, Netflix included, with [NMAppFree](#chrome-and-nmappfree) |
| Protected video, Safari | ❌ | No decoder for protected video |
| CPU turbo | ✅ | With HybridPM: one core reaches 4.64 GHz. Its energy-performance preference is now 64: at 96 the cores rose too slowly to compose a 144 Hz display once the desktop left them idle. The idle cost, about 10 W when it was first measured, was not measured again |
| P-cores and E-cores | ✅ | With IntelHybridCores in place of CpuTopologyRebuild: background work runs on the E-cores only (`hcmode=4`), and `hw.perflevel0` and `hw.perflevel1` report 6 cores with 12 threads and 8 cores. System Information says 20 cores, Hyper-Threading off |
| Speakers, headphones, internal microphone | ✅ | |
| HDMI audio | ✅ | Volume and mute from macOS, with `nmhdavol=1` |
| DisplayPort audio over USB-C | ✅ | Also after a short sleep; volume and mute as for HDMI |
| Keyboard, Fn keys, trackpad | ✅ | |
| Webcam, USB | ✅ | |
| Battery, charge limit, fans, sensors | ✅ | NitroSense app, and the RTX's sensors in the SMC: temperature, clock and P-state live from the GPU's shared data page, the load from NVAccel's own statistics. The menu bar item is redrawn only when its text changes, and the app polls every 10 s while its window and panel are closed: WindowServer's "Invalid window" log lines went from about 45 to under 10 every 30 s. With the fans on Max, Custom or a manual duty, the kext puts them back to Auto when the daemon stops answering: 7.7 s after it was suspended, 0.1 s after it was killed |
| Ethernet | ✅ | The driver loads here, no cable test. Reported working on another PC with this chip |
| Wi-Fi and Bluetooth, original MediaTek MT7920 | ✅ | Wi-Fi 6 (802.11ax), with the access point's BSS color. If reception stops while frames still go out, the driver reloads the firmware by itself instead of staying deaf until the next boot: that still happens once after a boot ([Known issues](#known-issues)) |
| Wi-Fi and Bluetooth with an Intel card instead | ✅ | Swap the kexts, see [efi/README.md](efi/README.md#kexts) |
| AirDrop | ✅ | With `-mtkawdl`, on by default. AWDL's radio stays still while nothing uses it: at idle the Wi-Fi raises as many interrupts with `awdl0` up as down. With a Pixel through Quick Share: about 10 MB/s to the phone and 13 MB/s from it. Not tried with an iPhone |
| Handoff, Continuity | ❔ | Not tested |
| Powering off the RTX | ❌ | It stays on. The laptop took about 41 W at idle when that was measured; the CPU package has gone from about 21 W to 7 W at idle since ([GPU for each app](#gpu-for-each-app)), and the whole laptop was not measured again |
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
| `-wex-nv-video` | Safari decodes video on the RTX ([Video on the RTX](#video-on-the-rtx)) |
| `-wex-va-renderer` | Hardware video processing on the Iris Xe, through the Intel video driver corrected for this GPU. Experimental |
| `hcmode=4` | IntelHybridCores: background work on the E-cores only, as on Apple Silicon. Without it the kext's own default, mode 2, only prefers them |
| `shda-lang=it` | SimpleHDA's language for the names of the audio outputs, Italian here: put your own. Without it SimpleHDA reads the language from NVRAM, which the emulated NVRAM does not carry, and on the test machine the names came out in Chinese |
| `nvwallpaper=1` | Nothing any more: the plugin no longer reads it. The Aerial wallpaper's movies are left to Apple's decoder on the Iris Xe ([Video on the RTX](#video-on-the-rtx)). It is still in the config because the tested EFI has it |
| `-mtkawdl` | AirDrop on the MT7920: AWDL on the Wi-Fi, and the Bluetooth LE advertising that makes this Mac visible |
| `nmhdavol=1` | Volume and mute for the audio of the displays: HDMI on the RTX, DisplayPort over USB-C |
| `nvfb10bit=1 nvfbhdr=1` | HDR10 over HDMI on the RTX |
| `nvrmfbddc=1` | DDC/CI for a monitor on the RTX |
| `nvrmaspm=1 nvfbkeepfront=1 nvfbvrr=1` | NullMoth's ASPM, frame kept across mode changes and variable refresh: no effect seen here yet |

Some features now on in the kexts have a boot-arg that turns them off instead: `-wex-no-hdr-modes` for the HDR switch of a monitor on USB-C, `-nohpm` for HybridPM's turbo (one core at 4.64 GHz; `hpmepp=N` sets another energy-performance preference than 64), `-mtknohe` for Wi-Fi 6 on the MT7920, `-hcoff` for IntelHybridCores, `nvfb30=0` for the 30-bit desktop on the RTX.

## Chrome and NMAppFree

The AMFI boot-args, which the Metal drivers not signed by Apple need, make the kernel treat every program as part of macOS and apply its strictest Mach IPC rules to all of them. Chrome's Widevine helper breaks one of those rules and is killed. [NMAppFree](https://github.com/Thatisjigen/NMAppFree), a Lilu plugin in the EFI, takes the apps outside the system folders out of that policy when they start, as macOS already does for a plugin host such as Firefox. It re-signs nothing and changes no file.

**Security:** this relaxes the kernel's Mach IPC hardening for every program outside `/System`, `/usr`, `/bin`, `/sbin` and `/Library/Apple`. That is how those apps run on a real Mac, but it is less hardening than the AMFI boot-args give them otherwise. The system binaries keep it.

| Boot-arg | What NMAppFree does |
| --- | --- |
| none | Every app outside the system folders. The mode that was tested |
| `-nmappfreeoff` | Nothing: Chrome goes back to no protected video |
| `-nmappfreedbg` | One log line for each app it exempts |

The other modes are in [its README](https://github.com/Thatisjigen/NMAppFree#modes-boot-args) and were not tested here.

## GPU for each app

The Iris Xe drives the panel, and the NVIDIA plugin of this fork shares the two GPUs out as Apple's two-GPU Macs do:

- **macOS's own processes** (Finder, the Dock, Spotlight, System Settings and the rest) draw on the Iris Xe alone. Before, each of them held a Vulkan device on the RTX that it never drew with.
- **Apps** are offered the RTX as the high-performance GPU, and so are the system services that work for them: WindowServer, the video decode and encode services, the wallpaper.
- **One app** can be set to Automatic, Power saving (the Iris Xe only) or Performance (the RTX as its default GPU) in NitroSense, under **Graphics per app**. It is macOS's own per-app setting for external GPUs, `GPUSelectionPolicy` in the `com.apple.gpu` preferences, and it applies when the app starts again.

On the test machine Chrome gets the RTX, Finder and macOS's other processes do not, and neither does NitroSense, which sets itself to power saving. Setting an app to Performance was not tried.

The RTX goes to its full clocks only for an app set to Performance and for a game. Before, WindowServer's frames for the HDMI monitor raised it every few seconds on a still desktop, from 4.9 W to 8.5 W, and YouTube in Safari held it at 12 W; what it draws now was not measured. `BOOST=1` in `/Library/GPUBundles/nvmtl/nvrm610.conf` brings that back.

At idle, between the boot before this change and the first one with it: the CPU package went from 21.4 W to 7.3 W, WindowServer from 610 ms to 13 ms of CPU each second, the user's processes with a device on the RTX from 24 to 8, the RTX from 6.5 W to 5.3 W, the CPU from 64 °C to 51 °C. That boot also brought the other driver updates of this round and no longer had NullMoth's NMIntelFB kext, which the test machine had kept and these scripts never installed: the figures are not this change's alone.

## Video on the RTX

The NVIDIA plugin registers the RTX's video decoders (`libnvencvt`, from the nvenc fork) in every process that loads it, so **H.264, HEVC and VP9** decode on the RTX wherever macOS's decoders are asked: in the system's decode service, which works for QuickTime and the other sandboxed apps, in Chrome, and in Safari's GPU process (`com.apple.WebKit.GPU`). That one may map the library only through a WhateverXe rule, which `-wex-nv-video` turns on. The decoded pictures are untiled on the RTX as well: the Iris Xe takes no part.

- **Safari:** a 4K H.264 clip plays at about a fifth of the CPU a software decoder takes. Tested on YouTube up to 2160p. AV1 stays off there: 10-bit AV1 on this GPU family has a new setup that was not checked on this card, and Safari has no other AV1 decoder to fall back on. Outside Safari 10-bit AV1 uses that setup, unchecked here too.
- **Low-priority work:** a decoder that waits on a background thread, as an export does, got about 6 pictures a second of 1080p H.264, because macOS stretched its sleeps. With the wait on a timer that is not stretched it gets about 120, in a test program.
- **The Aerial wallpaper is left to the Iris Xe.** Its movies are 4K HEVC at 240 pictures a second, one for each display. NVDEC gave about 33 pictures a second of one of them, nearly all late, with the RTX and the fans busy; Apple's decoder on the Iris Xe kept one in real time, and three at about 120 pictures a second each with the RTX idle. That is a command-line test with the wallpaper's movie: the wallpaper itself was not checked after the change.

## DLSS 4

NullMoth's Metal plugin can run NVIDIA's DLSS behind MetalFX's temporal scaler: a game that asks MetalFX to upscale its frames gets DLSS on the RTX instead. It needs NVIDIA's own files, which this repository does not carry. The last step of `install`, `dlss`, runs NullMoth's `dlss_fetch.sh`, compiled by `build` from the NVIDIA fork:

- it downloads **about 750 MB** from NVIDIA's public sites: the DLSS SDK 310.9.16 runtimes from GitHub NVIDIA/DLSS, NVIDIA's Linux driver 620.70.06 for its NGX library, and nvJitLink 12.9.86 from PyPI, so `install` needs the network and 2.5 GB free in `/var/tmp`;
- it refuses any file whose SHA-256 is not the one pinned in the script, then builds the GPU kernels for the card it finds (sm_120 for the RTX 5050) in `/Library/NullMoth/dlss`, in a few minutes. It runs as root, from a private copy of the build that `install` checks first;
- **the files stay under NVIDIA's licences** (DLSS SDK, driver, CUDA): they are downloaded on your Mac and must not be published.

On the test machine the files and 259 kernels for sm_120 were installed this way; no game has been tried with them yet. To leave it out: `install --go --skip dlss`. To take it out later: `sudo rm -rf /Library/NullMoth/dlss`; without that folder the plugin works as before. A game reads it when it starts: no reboot.

## NVRAM

The `full` profile keeps NVRAM in memory, with OpenCore's `OpenVariableRuntimeDxe.efi` loaded early, before `OpenRuntime.efi`: nothing reaches the firmware's flash any more. OpenCore itself already wrote nothing there (`WriteFlash` is `false`); now what macOS and the kexts write stays in memory too. The `install` profile keeps the real NVRAM.

What is lost at each restart:

- **Panic reports.** The kernel writes a panic into NVRAM, now in memory, and the restart clears it: no report after the reboot.
- **Variables macOS writes,** such as the volume of the startup sound and any `sudo nvram` change, and NullMoth's boot guard (`nullmoth-nv-starts`, `nullmoth-nv-ok`): failed starts are not counted across restarts, so the guard never turns the NVIDIA driver off. If the RTX stops the boot, use `-nvoff` ([docs/RECOVERY.md](docs/RECOVERY.md)).
- **macOS updates** keep their state across restarts in NVRAM: update with the real NVRAM.

For the real NVRAM, to catch a panic or to update: in `UEFI` › `Drivers` disable `OpenVariableRuntimeDxe.efi` and set `LoadEarly` of `OpenRuntime.efi` back to `false`. With the emulated NVRAM, sleep and wake were tried only in EFIs that also had wake or S0 tables this one leaves out, and were clean there.

## Known issues

- **The Intel GPU can hang under WindowServer:** on the render engine. The desktop freezes for about ten seconds, until the hang check resets the GPU. On the last boot tested it happened four times in an hour and a half, the first two while a video played in a browser, and YouTube stopped twice; in the four boots before it, almost 11 hours, never. After the reset WhateverXe recovers in 3 to 4 ms, with Julian Buhagiar's recovery for this scheduler and the fixes of this fork: the desktop goes on, and the work the reset killed is reported to Metal as failed, so the apps draw again. The cause is not known and is being looked into. WhateverXe also keeps its command streamer's status buffer in step with the hardware, so a reset of the second render ring or an entry written late no longer loses an event.
- **Hardware H.264 decoding on the Iris Xe does not work:** Apple's Intel decoder refuses the session. H.264 decodes on the RTX instead, or in software in a process kept off the RTX's decoders. HEVC does decode on the Iris Xe.
- **Wi-Fi reception can stop once after a boot:** the card stops filling its receive ring while commands and transmission go on, about a minute and a half into the last boot tested. The driver sees it after 30 s, or 6 s during an AirDrop, and reloads the firmware; reception comes back. The cause is not known.
- **Sleep is short, and there is no S0 sleep:** in S3 this board wakes only from the USB controller, and it does so by itself: the sleeps tried here lasted from a few seconds to a minute and a half, and neither the power button nor a keyboard woke the PC, as the DSDT gives them no wake for S3. The firmware's low-power idle (S0) is not set up: its ACPI tables are left out of this EFI, because no S0 sleep was tested.
- **A panic when the Intel GPU cannot be recovered:** when 10 of the last 15 minutes carry a restart request from IOAccel, WhateverXe panics on purpose, so the machine restarts instead of freezing about half an hour later with nothing in any log. `-wex-no-gpu-panic` turns it off. A status-buffer event the native scheduler expects, an element switch within one context, is dispatched instead of ending in a panic: Julian Buhagiar's fix for Alder Lake, kept here. The state is in the registry root as `WEXGPUWatch`, because the log cannot decode a kext OpenCore injects.
- **Do not sleep with `-nvoff`:** the one try without the RTX ended in a watchdog panic.
- **4K at 60 Hz over HDMI goes out at 59.94 Hz:** the driver takes the first variant of the monitor's mode. At 60 Hz the HiDPI desktop that looks like 1920×1080 uses a 1080p signal; 4K at 60 Hz is shown at its own size.
- **A monitor on HDMI can look too dark:** macOS gives it gamma 1.961. Choose the profile `sRGB IEC61966-2.1` in System Settings › Displays.

## In this repository

- [efi/](efi/README.md): OpenCore configs without identity, ACPI, USB map, kexts, boot-args
- [postinstall/](postinstall/README.md): scripts that compile the drivers and install them, with the list of forks
- [docs/INSTALL.md](docs/INSTALL.md), [docs/RECOVERY.md](docs/RECOVERY.md), [docs/LICENSES.md](docs/LICENSES.md)

## Credits

[b00t0x](https://github.com/b00t0x/WhateverXe) for WhateverXe, [nullmoth](https://github.com/nullmoth/nvidia-macos-driver) for the NVIDIA driver, [acidanthera](https://github.com/acidanthera) for OpenCore, Lilu, VirtualSMC and AppleALC, and [mickys](https://github.com/mickys/nvenc), [ptnzzn](https://github.com/ptnzzn/NitroSense-macOS), [zzzyy678](https://github.com/zzzyy678/SMCNvidiaGPU), [pokipoi](https://github.com/pokipoi/LatSOF-Audio), [rodgod-rr](https://github.com/rodgod-rr/IntelHybridCores) for IntelHybridCores, [JulioNectar](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe) for XE-PM, [kitsuneislife](https://github.com/kitsuneislife), [e5u](https://github.com/e5u/SimpleMtkWlan) and [flxxxxddd](https://github.com/flxxxxddd/SimpleMtkBtFw) for the MediaTek Wi-Fi and Bluetooth, the Linux mt76 driver, HighDelay, retropineaple, Dino-VN, Dat Nguyen, GeekAudio, kevineduardo, Ghltbm, kubus, januory, LSmurfs, Julian Buhagiar, renedis, nickk19, vikenzo196, 91270, SaqibAlMalik, thanhnndev, TrDiTu, myvoow, Axel Gneiting and Mel Henning of Mesa, and many others.

## License

Scripts and documents: [MIT](LICENSE). The rest keeps its own license, and **NullMoth's NVIDIA drivers are for noncommercial use only**: [docs/LICENSES.md](docs/LICENSES.md). This repository does not contain macOS or any third-party binary.


# Post-install

Builds the drivers from the latest commit of the `acer/current` branches of the forks and installs them into `/Library`, in order, after a clean install of macOS. The fourteen kexts for the EFI come from the same build.

> [!CAUTION]
> **These scripts have never run on a clean install, and `install --go` has never run on a real system.** That can only be tried by formatting. Below is what was tried and what was not. Back up your data first.

## Commands

From the repository folder, on a freshly installed macOS, with the network and the build tools (`xcode-select --install`). Xcode is not needed.

| Command | What it does | `sudo` |
| --- | --- | --- |
| `python3 postinstall/postinstall.py doctor` | Read only: machine, macOS build, SIP, boot-args, space | No |
| `python3 postinstall/postinstall.py fetch` | Downloads and checks, in `~/anv15-52-build`, and takes the latest commit of each fork. `--tested` takes the commits last tested instead. REFUSES `sudo` | No |
| `python3 postinstall/postinstall.py build` | Compiles, in the same folder. REFUSES `sudo` | No |
| `python3 postinstall/postinstall.py plan` | **Dry run:** what `install` would do, file by file. Writes nothing | No |
| `sudo python3 postinstall/postinstall.py install --go` | Installs. Without `--go` it is the same as `plan` | Yes |
| `python3 postinstall/postinstall.py state` | What is there now, against what was built | No |
| `python3 postinstall/postinstall.py verify` | After the reboot: kexts loaded, Metal, signatures, hashes | No |
| `sudo python3 postinstall/postinstall.py rollback --go` | Everything back. Without `--go` it says what it would do | Yes |

None of them restarts the PC. **The `full` EFI goes on the USB stick before `install --go`:** the Apple Intel driver ends up in `/Library`, and it needs WhateverXe. The guide is [docs/INSTALL.md](../docs/INSTALL.md). `build` must also have compiled the fourteen kexts for the EFI, or `install` stops before touching the system.

`install` stops:

- if the macOS build is not one that was tested (`--any-build` goes on anyway);
- if the PCI IDs `8086:A7A0` and `10DE:2D98` are missing (`--any-machine`);
- if SIP is on or the boot-args are missing: it means you did not start from this EFI;
- if it finds the drivers already in place (`--allow-existing` replaces them, with copies);
- if a compiled file changed after the build, or a download does not have the expected hash;
- if an earlier run installed builds of other commits: see [updating](#updating).

## The steps, in order

| # | Step | What it installs | From |
| --- | --- | --- | --- |
| 1 | `nullmoth` | Kexts, Metal plugin, NVK and GSP firmware in `/Library/Extensions`, `/Library/GPUBundles`, `/Library/NullMoth` | `nullmoth-nvidia-3.0.tar.gz` with its `install.sh`, which also rebuilds the auxiliary collection. The package has no firmware: its installer takes it out of NVIDIA's driver package 620.70.06, about 550 MB, which `fetch` downloaded and checked, so nothing is downloaded as root. DLSS (the `dlss` step does it at the end), the copy of the bundle for Safari and the boost daemon stay off; the shared shader caches go back to root, as on the test machine. It prints a "Done. Reboot now" and an "Undo" of its own: they do not apply here. It also adds its audio driver, `NMXAudio`, and a job that gives the brightness back to an internal panel driven by the NVIDIA GPU: this step removes both, as sound here comes from AppleALC, LatSOF-Audio and NMHDA, and the panel is on the Iris Xe. With WhateverGreen loaded, as under the install EFI, it adds `gfxrst=4` to the NVRAM boot-args; OpenCore writes its own at the next start |
| 2 | `graphics` | The `AppleIntelTGL*` kexts and the Intel bundles. Its Metal driver already has the fix for the memory WindowServer lost at each frame, and its own `impostor.dylib` stays the bridge of that driver | `WhateverXe-Graphics-0.4.4.pkg` by b00t0x, with `installer` |
| 3 | `nvrm-kexts` | NVRM, NVRMFB, NVAccel and NVRMAGDC, compiled, over those of the package | `nvidia-macos-driver` |
| 4 | `plugin` | `NVMTLDriver` and `libnvmtl_translate.dylib`, then a new signature for the bundle | `nvidia-macos-driver` |
| 5 | `decoder` | `libnvencvt` in place of NullMoth's two decoders and under its own name, then a new signature. The plugin registers its decoders in every process that plays video, so `nvrm610.conf` stays as the package wrote it, as on the test machine; the line an earlier install added there for Safari is taken out, because it would now ask for the library's encoders in that process | `nvenc` |
| 6 | `nvk` | NVK, compiled, in place of the package's. If `build` did not make it, `install` stops before touching anything: it never falls back to the package's | `nvk/` of `nvidia-macos-driver` on Mesa 26.3.0-rc3, then four commits of Mesa `main` for NAK on SM120 by Axel Gneiting and Mel Henning ([nvk-mesa/](nvk-mesa/)), the fork's lock around NVK's table of CPU mappings (`nvk/nvk-mappings-lock.patch`), and `drop_flat_weak_binds.py` in this folder: without 2964 useless symbol lookups, apps open Metal sooner |
| 7 | `metal-cache` | Empties the Metal shader caches of WindowServer and of your user, which hold programs compiled for the drivers that were there before and render corrupted on every display until they are rebuilt. They are rebuilt at the next start and are not copied for rollback | |
| 8 | `latsof` | `LatSOFAudio.kext`, internal microphone | `LatSOF-Audio`, with the SOF firmware downloaded from sof-bin |
| 9 | `hidpi-panel` | A display override for the CSOT panel, so that macOS offers HiDPI modes. Ignored by any other panel | [overrides/](overrides/) |
| 10 | `auxkc` | The auxiliary kext collection, from `/Library/Extensions` | `kmutil`. It swaps it only if it holds all eight expected IDs |
| 11 | `nitrosense` | `nitrod`, `nitroctl`, LaunchDaemon, `/Applications/NitroSense.app` | `NitroSense-macOS`. It starts at the reboot, as it needs NitroEC from the EFI |
| 12 | `dlss` | DLSS 4 for games that use MetalFX's temporal scaler: NVIDIA's DLSS, NGX and nvJitLink files and the GPU kernels built from them, in `/Library/NullMoth/dlss`. **The only step that downloads, as root, during `install`:** about 750 MB from NVIDIA's sites, each file checked against the SHA-256 pinned in `dlss_fetch.sh`. The files stay under NVIDIA's licences. `--skip dlss` leaves it out; `sudo rm -rf /Library/NullMoth/dlss` takes it out later | `dlss_fetch.sh`, `dlss_cache` and `nm_unzstd` of `nvidia-macos-driver`, compiled by the `dlss` stage with the fork's `build/build_dlss_cache.sh`, run from a root-owned copy that `install` checks against the build |

Fourteen more compiled kexts go in the EFI, not in `/Library`, all built in release: Lilu, WhateverXe, IntelHybridCores, AppleALC, IDispHDA, NMHDA, SMCNvidiaGPU, HybridPM, NitroEC, AirportMtkWlan, SimpleMtkBtPatcher, SimpleMtkBtFw, BTLEAdvFixup and USBDiskKeeper ([efi/README.md](../efi/README.md)). Lilu is compiled from the fork, file by file as its Xcode project for 1.7.2 lists them, with its release settings, and its `Info.plist` is made from the fork's as Xcode makes it. `fetch` still downloads acidanthera's 1.7.2 DEBUG release, because its SDK is what every Lilu plugin here is compiled against. SimpleMtkBtFw, the Bluetooth firmware loader, is compiled from the same fork as the patcher, with the USB match of this laptop in its `Info.plist`. AirportMtkWlan carries the MT7920 firmware, downloaded with its hash from linux-firmware and built into the kext on your machine: MediaTek's licence keeps it out of this repository, so do not publish that kext. SMCNvidiaGPU has to match NVRM, and `build` compiles it together with the NVRM it just made.

**NVK is compiled as NullMoth compiles it,** because only that toolchain gives their library byte for byte: clang and the libc++ headers 22.1.8, Rust 1.97.1, glslang at one commit of `main`, SPIRV-Tools 2026.4 and SPIRV-LLVM-Translator 22.1.7, meson under Python 3.12. LLVM publishes no x86_64 macOS build of version 22, so the first `build` compiles LLVM and clang: about 1 h 30 with four jobs, out of about two hours for the whole toolchain, and about 530 MB of downloads, each checked by its hash or by rustup, cargo and meson. The toolchain stays in `~/anv15-52-build/deps/nvk.noindex` and in the Rust folder, about 1.5 GB, beside 350 MB of archives; the folder needs about 10 GB at the peak, while LLVM is built. Later builds reuse it, and the `nvk` stage takes about 5 minutes.

**Not installed:** NMIntelFB and its daemon (turned off by `-nmintelfboff`), `NMXAudio`, and `nvutild` and the boot diagnostics, which NullMoth no longer needs.

## The forks

Every change to someone else's project is a commit on a public fork, on the branch `acer/current` (`main` in HybridPM). IntelHybridCores is the `main` of its author, unchanged. USBKeeper is not a fork: it was written for this laptop, and is built from its `main`. NMLibVal, also written for this laptop, is not built here: its compiled kext is in [efi/kexts](../efi/kexts/NMLibVal.kext). The commits last tested are in [manifest.json](manifest.json).

| Fork | Upstream | What it adds |
| --- | --- | --- |
| [WhateverXe](https://github.com/Thatisjigen/WhateverXe/tree/acer/current) | [b00t0x/WhateverXe](https://github.com/b00t0x/WhateverXe) 0.8.3 | Sleep and wake, recovery from GPU hangs, USB-C hot plug, HiDPI, HDR; Safari's GPU process may map the NVIDIA runtime (`-wex-nv-video`), the Intel video driver's image conversion corrected for this GPU (`-wex-va-renderer`), a hung command streamer's status buffer re-armed instead of a panic, the status buffer kept in step after a late entry or a shared reset, a hung GPU's stamps completed again and a panic when it stays hung for 10 of 15 minutes (`-wex-no-gpu-panic`), and Julian Buhagiar's same-context element switch; his recovery from GPU hangs with the scheduler on the host, where the work a reset killed is reported to Metal as failed, the other engine of the render domain is reset with it and the stamp of the notification after the resume is completed; Intel's workaround Wa_18022495364; and, on by default here, fixes by vikenzo196 (the channel notification after a reset, the batches of a channel reset twice in a row), renedis (the display interrupts around a display sleep) and 91270 (the idle status buffer across a wake from S0). Against the hangs of the Iris Xe under WindowServer: Metal compute on the render engine in place of the donor's second engine (`-wex-parallel-compute`), the engine workarounds the donor drops from PCI revision 4 on (`-wex-no-engine-wa`), the render engine's aux table cache invalidated at every context restore (`-wex-no-aux-inv`), and Julian Buhagiar's balance of the GT forcewake a hang report left held. For Metal Performance Shaders: Intel's plug-in in the Metal driver switched off in memory (`-wex-intel-mps-plugin` leaves it on) and the 64 KB class of thread-group memory for compute kernels (`-wex-no-slm-64k`). 0.8.3 itself now admits the panel during the firmware handoff and restores the display interrupts at the wake from a display sleep, so the fork's commit for the first and nickk19's for the second are no longer in it |
| [nvidia-macos-driver](https://github.com/Thatisjigen/nvidia-macos-driver/tree/acer/current) | [nullmoth/nvidia-macos-driver](https://github.com/nullmoth/nvidia-macos-driver) 3.0 | Wake, HDMI audio and zero-copy flips in the kexts, and a flip on one display no longer holds up the cursor and the other displays; the RTX resumes on a thread of its own at wake, so USB does not wait for it; HDR10 and DDC/CI on the RTX's HDMI, and a monitor plugged in after a boot without one; a desktop at 30-bit depth with its 10-bit surfaces flipped directly, HDR10 in RGB with the default colorimetry, at 8 bits where 10 are beyond the HDMI clock (`nvfbhdr422=1` keeps the earlier YCbCr 4:2:2 output), and a head lit again after a flip that never landed; two-GPU fixes, pipeline cache and Photo Booth in the plugin and translator; the RTX offered to apps as the high-performance GPU while macOS's own processes stay on the Iris Xe, NVK's boost only for apps set to performance and for games, the video decoders registered in every process, and in NVK a completion event registered only while something waits on it and a lock around the NVRM back end's table of CPU mappings, which two threads could change at once; the head lit again when the GPU's wake work comes before the framebuffer's power-on; a shader cache tag that survives a new signature of the translator, writable BGR10A2 textures (HDR photos) and the Geekbench 6 fix of NullMoth's PR #587 in the plugin; with patches by Dino-VN, Dat Nguyen, luckiest-luk, xsvm, GeekAudio, kevineduardo, Ghltbm, kubus, januory, LSmurfs and TheFormidable |
| [nvenc](https://github.com/Thatisjigen/nvenc/tree/acer/current) | [mickys/nvenc](https://github.com/mickys/nvenc) | NVDEC decoders for the RTX 5050: H.264, HEVC, VP9, AV1, and 10-bit AV1 with kevineduardo's setup for this GPU family. The decoded frames are untiled on the RTX that decoded them, not on the CPU and not on the Iris Xe, which hung under that load. A decoder that waits on a low-priority thread no longer has its sleeps stretched by macOS. The Aerial wallpaper's movies, 4K HEVC at 240 pictures a second, are left to Apple's decoder (`NVDEC_APPLE`). A decoding session that reads synchronously keeps a decoder of its own |
| [NitroSense-macOS](https://github.com/Thatisjigen/NitroSense-macOS/tree/acer/current) | [ptnzzn/NitroSense-macOS](https://github.com/ptnzzn/NitroSense-macOS) 1.1.1 | The EC of the ANV15-52: fans, modes, charge limit. Only an admin reads the CPU energy counters, and a stuck client cannot stop the fan watchdog of the daemon. The menu bar item is redrawn only when its text changes, and the app polls every 10 s while its window and panel are closed. The kext puts the fans back to Auto when the daemon dies or hangs, an idea from myvoow's nitro-control-anv15-41. **Graphics per app:** Automatic, Power saving or Performance for each app, through macOS's own `GPUSelectionPolicy` |
| [SMCNvidiaGPU](https://github.com/Thatisjigen/SMCNvidiaGPU/tree/acer/current) | [zzzyy678/SMCNvidiaGPU](https://github.com/zzzyy678/SMCNvidiaGPU) | RTX sensors, built together with NVRM. The temperature, the graphics clock and the P-state come from RM's shared data page at every tick, and the load from NVAccel's statistics, so RM is asked less often; an RM call that holds RM's locks over 500 ms stops its calls for the boot |
| [LatSOF-Audio](https://github.com/Thatisjigen/LatSOF-Audio/tree/acer/current) | [pokipoi/LatSOF-Audio](https://github.com/pokipoi/LatSOF-Audio) | Raptor Lake-P, automatic DSP start; the DMA position buffer is kept while the controller points at it, which used to overwrite a freed page at every boot and wake. Firmware not included |
| [AppleALC](https://github.com/Thatisjigen/AppleALC/tree/acer/current) | [acidanthera/AppleALC](https://github.com/acidanthera/AppleALC) 1.9.8 | Layouts 66 and 67 for this ALC245, and IDispHDA, the audio of the Iris Xe over USB-C |
| [SimpleMtkWlan](https://github.com/Thatisjigen/SimpleMtkWlan/tree/acer/current) | [e5u/SimpleMtkWlan](https://github.com/e5u/SimpleMtkWlan) 1.6.0 | The MT7920, `14C3:7920`: detection and firmware as in Linux, Wi-Fi 6 with the access point's BSS color (`-mtknohe` turns it off), a node cache of 512 so 5 GHz networks still appear, and the interface back up after a wake. With `-mtkawdl`, AWDL for AirDrop: the radio as Linux mt76 drives the MT7921 family, the interface from ForbiddenItlwm and thanhnndev. Its debug log holds no kernel pointers or keys, and only `-mtkdbglog` makes it readable by every user. When reception stops while frames still go out, the firmware is reloaded, as mt76 does for a wedged chip: after 6 s for a connected station or while an AWDL peer is sending, 30 s otherwise, and at once, three times in a row at most, when a station that had connected again stops again; the report of a stall is kept until the next boot. AWDL's radio stays still while nothing uses it, also when macOS has just turned AWDL on, and for two minutes after a stall; it waits up to a second for a remain-on-channel grant, as Linux does, lets the radio get home before it closes the reception and leaves the receive filter to the firmware. Association requests to a WPA network carry the Privacy bit, which some access points insist on. PCIe ASPM and the L1 substates are turned off on the card and the port above it, as mt76 does (`-mtkallowaspm` leaves them); A-MSDUs inside A-MPDUs are accepted; a receive descriptor is taken only once the hardware has marked it done. For AirDrop: Block Ack agreements with peers, unicast data at VHT rates in A-MSDUs, and Apple's schedule followed on the station's channel and off it. GPL-2.0; the firmware is generated at build, not in Git |
| [SimpleMtkBtFw](https://github.com/Thatisjigen/SimpleMtkBtFw/tree/acer/current) | [flxxxxddd/SimpleMtkBtFw](https://github.com/flxxxxddd/SimpleMtkBtFw) 1.1.0 | The Bluetooth patcher touches only the transfers of the MediaTek controller, and prepares USB buffers read only: no backtrace for every USB transfer |
| [ForbiddenItlwm](https://github.com/Thatisjigen/ForbiddenItlwm/tree/acer/current) | [retropineaple/ForbiddenItlwm](https://github.com/retropineaple/ForbiddenItlwm) | Only its BTLEAdvFixup is built: Bluetooth LE advertising for AirDrop, in a mode for a MediaTek controller that leaves the HCI to SimpleMtkBtPatcher, on with `-mtkawdl`. GPL-3.0 |
| [HybridPM](https://github.com/Thatisjigen/HybridPM) | XE-PM of [JulioNectar](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe) | A standalone Lilu plugin; on unless `-nohpm`. The cores choose their own clock, as TrDiTu proposed, unless `hpmauto=0`, with an energy-performance preference of 64 (`hpmepp=N` for another): at 96 they rose too slowly to compose a 144 Hz display. Only root reads its sensors |
| [Lilu](https://github.com/Thatisjigen/Lilu/tree/acer/current) | [acidanthera/Lilu](https://github.com/acidanthera/Lilu) 1.7.2 | One commit: 16 KiB for the trampolines of the plugins instead of 4. The kexts of this EFI filled the 4, and a route that finds no room fails without a word: IDispHDA lost three, and with them the DisplayPort audio of the Iris Xe. BSD-3-Clause |
| [IntelHybridCores](https://github.com/Thatisjigen/IntelHybridCores) | [rodgod-rr/IntelHybridCores](https://github.com/rodgod-rr/IntelHybridCores) | Nothing: the fork only keeps the commit that was tested. A Lilu plugin that tells the scheduler and `hw.perflevel` which cores are P and which are E. MIT |
| [USBKeeper](https://github.com/Thatisjigen/USBKeeper) | None, its own project | USBDiskKeeper, a Lilu plugin: the USB stick OpenCore starts from stays attached when its port drops it for a moment at wake, instead of being ejected |

**Do not open pull requests upstream from these branches** without rewriting and understanding the code: parts were written with AI tools, and NullMoth does not accept AI-written contributions. The original authors stay the authors of the commits taken from them.

## Hash checks

- **Downloads:** each archive has its SHA-256 in [manifest.json](manifest.json). If it does not match, the file is deleted and everything stops. The NullMoth package is also checked against its own `SHA256SUMS`, whose hash is in the manifest: a folder unpacked from another version does not pass. The Python packages of NVK's build have their hashes in [nvk-requirements.txt](nvk-requirements.txt); Rust, its crates and NAK's crates are checked by rustup, cargo and Mesa's `.wrap` files.
- **Forks:** `fetch` takes the head of each branch, so there is no hash to compare with beforehand: Git checks that the sources are that commit, and `fetch` says when one is newer than what was last tested. `fetch --tested` takes the commits listed in the manifest.
- **Compiled files:** `build` writes the commits and the hash of each file in `out/manifest.json`, and `install` refuses a file changed afterwards. Then each step reads back what it wrote.
- **Against what was tested:** `build` compares each file with the one tested on the reference machine, and says whether it is the same file, or that its fork is newer than what was tested. A difference is a warning, not a stop: another compiler changes the files.

## Copies and rollback

Before each step, everything the step touches goes to `/Library/ANV15-52/backup-<date>/files`, and `journal.tsv` notes what was there and what was not, only once all the step's copies are made. If a step stops, running `install --go` again goes on from there with the same copies. Ctrl-C does the same, and lets the running command finish its clean-up.

`rollback` reads the journal from the bottom: what was there comes back, what was not is removed. **It is always complete:** half way, the kexts on disk would not match the auxiliary collection. An incomplete line in the journal is not acted on, and is reported. The same can be done from Recovery with `rollback.sh`, which does not need Python: [docs/RECOVERY.md](../docs/RECOVERY.md). After a rollback, `install --go` starts from the beginning.

These do not go back: the NVRAM variables NullMoth clears, the `installer` receipts in `/var/db/receipts`, and the EFI, which is separate.

## Updating

`fetch` and `build` again take the latest commits, and then the EFI and `/Library` get them together. `install` does not go on top of builds of other commits, so it is a rollback followed by an install, before you restart:

```bash
python3 postinstall/postinstall.py fetch
```

```bash
python3 postinstall/postinstall.py build
```

```bash
python3 efi/build_efi.py build --profile full --compiled ~/anv15-52-build/out
```

```bash
python3 efi/build_efi.py deploy --profile full --volume /Volumes/OPENCORE --go
```

```bash
sudo python3 postinstall/postinstall.py rollback --go
```

```bash
sudo python3 postinstall/postinstall.py install --go
```

SMCNvidiaGPU is built together with NVRM, so the two stay together even when only one of them moved. If a fork moves to a new base, such as a newer NullMoth package, `manifest.json` has to change with it: `fetch` does not know that by itself. Like everything else on this page, this path has only been tried on a copy of the system tree.

## What was really tried

On one machine, with macOS 26.7.3 (25G342), Command Line Tools 26.6, clang 21.0.0 and SDK 26.5, at the commits listed in the manifest. **Nothing was installed by these scripts.** The drivers that run on that machine were built from the same sources by other scripts; the table says how the files built here compare with them.

**`build`, at these commits:** in a folder filled beforehand with copies of what `fetch` leaves, all with the hashes of the manifest; `fetch` itself was not run again, as NVIDIA's `.run` and the Graphics package, which only `install` uses, were not on that machine. The SOF archive was replaced by one holding the same firmware file at the same path, and NVK's toolchain was the one that had built the library running there, copied into the build folder. Four parallel jobs. WhateverXe passed the 227 CPU tests that run without Apple's driver binaries and skipped the 67 that need them. Only the stages of the forks that moved were run again: WhateverXe, AirportMtkWlan, NitroSense and NVK. The other files are those of the builds before, compared again with the ones that run.

| File | Result |
| --- | --- |
| NVRM, NVRMFB, NVAccel, NVRMAGDC, NMHDA | **The same file, byte for byte.** NVKMS writes the time of its build into NVRM: the manifest gives the one of the archive that was tested |
| NVK (`libvulkan_nouveau.dylib`) | **The same file, byte for byte**, with the four Mesa commits of [nvk-mesa/](nvk-mesa/) and the fork's lock around the table of CPU mappings, after the `nvk` stage takes out the flat weak binds and signs it. That stage was run with the toolchain already built; building the toolchain from zero was done before, by hand, with the same commands |
| `NVMTLDriver` | Same code and UUID; the running one carries the seal of the bundle it is installed in |
| LatSOFAudio, NitroEC, SMCNvidiaGPU, HybridPM, AppleALC, IDispHDA, SimpleMtkBtPatcher, SimpleMtkBtFw, USBDiskKeeper | **The same file** |
| Lilu | Same code: only the UUID differs, into which the linker of the running one hashed the paths of the folder it was built in. This recipe leaves no path in it, so every build gives the same file |
| IntelHybridCores | Same code. The running one keeps the paths and times of its debug map, and with them another UUID and another signature: without the debug map, the signature and the UUID the two are the same file. Here the debug map holds relative paths and no times, so every build gives the same file |
| `dlss_fetch.sh`, `dlss_cache`, `nm_unzstd`, `assertfail_trap.ptx` | **The same files** as the ones that installed DLSS there. The `dlss` step itself has not run: the same tools were run there by hand, from a root-owned copy, with `dlss_fetch.sh --yes` |
| AirportMtkWlan | Differs only in its version string, which carries the short commit of the branch it is built from: built with the string of the one that ran, it is the same file |
| BTLEAdvFixup | Same code: only the UUID differs, into which the linker of the running one hashed the paths and times of its debug map. Here it gets neither, so every build gives the same file |
| WhateverXe | Same code. The running one has the old names of its diagnostics, its IORegistry keys among them. Built with this recipe from the tree that runs, it is the same file but for the UUID, which changes at every build: the linker hashes the paths and times of the objects into it before the build strips them |
| `nitrod`, `nitroctl`, NitroSense.app | Same code. The running ones still have the date of an EC dump in a help text: with that text the daemon is the same file. The tool and the app that run were built before the code they share with the daemon had its heartbeat for the fan watchdog, which neither of them calls: built with this recipe from those trees, they are the files that run |
| `libnvencvt` | Same code. The running one was built by a script of its own, with another version string and another internal name, before one log line lost a code of the work log: built that way, with that line, it is the same file. That machine still has an older build of it as `libnvdec_h264.dylib`, which `decoder` replaces with this one |
| `libnvmtl_translate` | Same sources. The running one keeps the paths of the folder it was built in; here they read `/build/translator`. `build` always compiles it in `/private/tmp/anv15-52-translator`, because cargo puts that path in the hash of its symbols |

Not compiled, and the same as on that machine: the files of Graphics 0.4.4, which are those of its tag. Different from that machine, and not in the table: the other files of the NVIDIA bundle there are still those of the 2.9 package (the same code as 3.0's, other signatures), and its NVRMAGDC has the `Info.plist` of 2.9, which says 2.6.6.

**NVAccel, something to know:** it is compiled without `NM_TAHOE`, the variant NullMoth uses for macOS 15, while its release for Tahoe uses the other one. On Tahoe this variant takes 19 `IOAccel*` methods from the Intel kext `AppleIntelTGLGraphics` (`kmutil libraries`), so without Graphics the auxiliary collection should not build, though that was not tried: it is one reason why `graphics` comes before `nvrm-kexts`. It has run this way on the test machine, and the scripts stay on what was tested. Whether it has to do with anything still open was not investigated.

**The logic of `install` and `rollback`, on a fake system:** `python3 tests/test_postinstall.py`, 26 tests with stand-in files: refusals, copies, going on after an error or Ctrl-C, rollback with and without Python, broken journal lines, an NVK or DLSS tools that were not built, the old line taken out of `nvrm610.conf`, DLSS left alone on a copy of the system tree, and the Intel Metal driver known with the pages WhateverXe corrects. Run again at these commits.

**Intel's MPS plug-in, on that machine:** WhateverXe switches it off in memory, and the `Info.plist` of the Metal driver is the one Graphics installs, with its switch at 1. An image classification by Vision on the Iris Xe asks for no compilation from source, and the image analysis macOS runs in the background went through its pictures there with no failed compilation. A step of these scripts used to set that switch to 0 in the file: it is gone, and a file it changed keeps working. The kext corrects two pages of the Metal driver in memory, and a read of the file returns them corrected while they are in the file cache: `state` and `verify` know the driver by its hash without those two pages too, and `verify` reads `WEXMPSPluginOffReady` from the registry. Both were run there, read only.

**With NullMoth 2.7.2, before these pins, and not repeated since:** `fetch` and `build` from zero with every download, in an empty folder (about 15 minutes, 2.4 GB); `install --go` with the real files on a copy of the system tree (`--root`, no `sudo`; `kmutil`, `installer` and `launchctl` did not run), whose result matched the running system but for the version in four `Info.plist` files; `doctor`, `plan`, `state` and `verify` on the running system; `deploy` of the EFI on a FAT test image; the commands `rollback.sh` uses, found in the 26.6.2 recovery image; `fetch` going back and forward between two commits of one fork.

## What was not tried

- `install --go` on a real system. In particular: `kmutil` run from here, the `install.sh` of **3.0** (the test machine went through the one of 2.5.5, then the pieces by hand), `installer` and `launchctl`.
- The reboot after all this, on a system where the pieces arrive together. This exact combination has never run.
- The `nvk` stage from an empty folder in one go: LLVM, clang and the other tools were built by hand with the same commands and options, then the stage reused them.
- A real rollback, from the system or from Recovery.
- The `dlss` step through `install`: its downloads and kernel build ran on the test machine from the same tools, by hand.
- Any other ANV15-52.

## If you update something

- A fork moves on: `fetch` takes it by itself. To say it was tested: `python3 tools/update_pins.py --write`, then update `tested_binaries` and the status in the [README](../README.md). Until then the README describes the older commits.
- Before publishing: `bash tools/check_all.sh`.

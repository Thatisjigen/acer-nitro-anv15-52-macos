# EFI

Two profiles, built by `efi/build_efi.py` in `build/EFI/EFI/`:

| Profile | Folder | What for | Compile? |
| --- | --- | --- | --- |
| `install` | `OC-INSTALL` | Install macOS, recovery. The config that installed macOS on the test machine | No, downloads only |
| `full` | `OC` | The system with the drivers | Yes: eleven kexts, from the forks, NMAppFree and USBKeeper |

Neither has `EFI/BOOT/BOOTx64.efi`, and `LauncherOption` is `Disabled`: rEFInd stays the main boot manager and OpenCore is one of its entries ([refind-opencore.conf](refind-opencore.conf)). Linux and Windows start from their own rEFInd entries, without going through OpenCore.

**There are no third-party or Apple binaries here:** the builder downloads them from fixed URLs and checks the hash of each archive, each executable and each `Info.plist` ([sources.lock.json](sources.lock.json)). A difference stops everything.

## Identity: your values

`config.template.plist` and `config.install.template.plist` hold OpenCore's sample values instead of serial, MLB, SystemUUID and ROM. Yours are generated once:

```bash
python3 efi/build_efi.py identity
```

They are in `private/identity.json`, readable only by you and outside Git. The serial comes from OpenCore's `macserial` for MacBookPro16,2, the UUID is random, the ROM is 6 random bytes marked as a local address. **Do not regenerate them at each update:** macOS would see another Mac. Do not publish `private/`, an EFI built with your identity, or OpenCore's logs, which can hold these values. `build/` is outside Git for the same reason.

Want your own values? Write `private/identity.json` with the keys `SystemSerialNumber`, `MLB`, `SystemUUID`, `ROM` (hexadecimal). Apple services were not tested.

## What is specific to this Acer

| What | File | What for |
| --- | --- | --- |
| Processors | `acpi/SSDT-PLUG-ANV` | 20 `Processor` objects with the UIDs read from the MADT of this PC |
| EC and USB | `acpi/SSDT-EC-USBX-ANV` | A fake EC for macOS; the real EC0 stays |
| Clock | `acpi/SSDT-AWAC-ANV` | Legacy RTC, only with Darwin |
| `_OSI` | `acpi/SSDT-XOSI-ANV` and an ACPI patch | The rename is limited to the Acer DSDT of 232164 bytes |
| USB | `acpi/SSDT-USB-Reset`, `kexts/UTBMap-ANV.kext` | A map with the 9 real ports and their type |
| Brightness | `acpi/SSDT-PNLF-ANV` | PNLF with UID 19 for WhateverXe |
| NitroSense EC | `acpi/SSDT-NITRO` | EC window `0xFE708500`, only with Darwin |
| Duplicate table | `ACPI/Delete` in the config | Removes one of the two 101-byte `ACRPRDCT` SSDTs: otherwise `AE_ALREADY_EXISTS` on AEVD |
| Memory | `Booter/MmioWhitelist` | Keeps the MMIO at `0xFF000000`: without it, a page fault at boot |
| Trackpad | `Kernel/Patch` | VoodooI2C waits for VoodooGPIO without a limit instead of 1 s. Valid only for this binary of VoodooI2C |
| CPU | `Kernel/Emulate`, `Kernel/Patch` | Comet Lake CPUID, hyper-threading, `ProvideCurrentCpuInfo` |
| Panel | `DeviceProperties` on `Pci(0x2,0x0)` | EDID of the CSOT MNF601BA3-1 with the 180 Hz mode, stolen memory at 60 MB. WhateverXe also reads the bits from it: keep it, see [below](#if-your-panel-is-different) |
| Audio | `DeviceProperties` on `Pci(0x1F,0x3)` | `layout-id` 67 |
| Model | `PlatformInfo` | MacBookPro16,2: with 16,1 `displaypolicyd` waits for a MUX and USB-C does not light up |

SMBIOS uses `UpdateSMBIOSMode=Custom` with `CustomSMBIOSGuid=true`, to stay within macOS. The SSDTs are injected only from this OpenCore entry. The processors' SSDT creates its objects outside `If (_OSI("Darwin"))`, because macOS did not start otherwise; `_STA` stays conditional.

`SSDT-USB-Reset` comes from the EFI of NullMoth's 1401 app and is 110 bytes: its source here comes from `iasl -d`. The other `.aml` files are the ones that ran, byte for byte, with the source next to them. To recompile them you need `iasl`: the header changes with the version, the content does not. The builder uses the `.aml` files of the repository.

## If your panel is different

The EDID in `DeviceProperties` (`AAPL00,override-no-connect`) is the one of the CSOT panel, with the 180 Hz mode rebuilt. Without the right EDID the panel may stay dark or run at another rate. Another panel needs it removed or redone, and that was never tried.

**That EDID also sets the colour depth.** WhateverXe reads the bits from it before WindowServer asks for the modes. It counts only if it is 128 bytes with the right checksum, EDID 1.4, DisplayPort interface; byte 20 here is `a5`, 8 bits. That keeps the panel at 24 bits, which is what removed the red and burnt colours at wake. If you remove the override, or your EDID says 10 bits or breaks those conditions, the panel can go to 30 bits and those colours can come back. This is deduced from what was seen here, not tested on another panel.

## Kexts

| Group | Kexts |
| --- | --- |
| Base | Lilu, RestrictEvents, CpuTopologyRebuild, HybridPM (on unless `-nohpm`), NVMeFix, NMAppFree (Chrome's Widevine with the AMFI boot-args) |
| Graphics | WhateverXe (DEBUG build, in place of WhateverGreen), BrightnessKeys |
| Audio | AppleALC, SimpleHDA, NMHDA, IDispHDA (the Iris Xe over USB-C) |
| SMC | VirtualSMC, SMCBatteryManager, SMCNvidiaGPU |
| Input | VoodooI2C with its plugins, VoodooI2CHID, VoodooPS2Controller with its keyboard plugin |
| USB | USBToolBox, UTBMap-ANV, XHCI-unsupported, USBDiskKeeper (the USB stick OpenCore starts from stays attached when its port drops it at wake) |
| Network | RealtekRTL8111, AirportMtkWlan, SimpleMtkBtFw, SimpleMtkBtPatcher, BlueToolFixup: the original MediaTek MT7920. SimpleMtkBtFw gets one more USB match, `13D3:3622`, the Bluetooth of this laptop. SimpleMtkBtPatcher is compiled from the fork: it touches only the transfers of the MediaTek controller, and prepares USB buffers read only, without the backtraces the release logs for every USB transfer |
| Laptop | NitroEC |

Present and disabled: UTBDefault, EHD0Off-ANV, USBPorts, WhateverGreen, itlwm, and AirportItlwm, IntelBluetoothFirmware and IntelBTPatcher. **With an Intel card** in place of the MT7920, enable those three and disable AirportMtkWlan, SimpleMtkBtFw and SimpleMtkBtPatcher: that was tested with an AC 8265.

Also present and disabled, because at boot they find nothing on this laptop: SMCLightSensor (no light sensor), SMCProcessor (no processor it supports), SMCSuperIO (no SuperIO chip), VoodooPS2Mouse and VoodooPS2Trackpad (the trackpad is on I2C), and AMFIPass, which has nothing to do once the AMFI boot-args below are set.

## Boot-args of the `full` profile

| Boot-arg | Whose | What for |
| --- | --- | --- |
| `keepsyms=1` | macOS | Symbols in panics |
| `ctrsmt=full` | CpuTopologyRebuild | Core topology |
| `amfi_get_out_of_my_way=0x1 amfi=0x80 ipc_control_port_options=0` | NullMoth, Graphics | WindowServer can load Metal drivers not signed by Apple. Without them the kernel rejects both plugins and the desktop does not arrive. They also put every app under the kernel's strictest Mach IPC rules: NMAppFree takes the user apps back out, see the [README](../README.md#chrome-and-nmappfree) |
| `-allow3d -disablegfxfirmware` | WhateverXe | Intel acceleration |
| `-wex-nv-video` | WhateverXe | Safari's GPU process may map the NVIDIA runtime, so Safari decodes H.264, HEVC and VP9 on the RTX |
| `-wex-va-renderer` | WhateverXe | The Intel video driver's image conversion, corrected for this GPU: hardware video processing on the Iris Xe. Experimental |
| `nvwallpaper=1` | NVIDIA Metal plugin | The Aerial wallpaper and its preview in Settings › Displays decode on the RTX |
| `nvrmaspm=1` | NVRM | Asks for PCIe ASPM L1 on the RTX's link. Nothing changes here: the port above the RTX offers no ASPM |
| `nvrmfbddc=1` | NVRMFB | A DDC/CI bus for each monitor on the RTX, for monitor-control apps. Tested here: the brightness read from the monitor |
| `nvfb10bit=1 nvfbhdr=1` | NVRMFB | HDR10 on the RTX's HDMI, for a monitor whose EDID lists PQ. 10-bit output alone shows no change here |
| `nvfbkeepfront=1` | NVRMFB | The frame stays on screen across a mode change. Not judged yet |
| `nvfbvrr=1` | NVRMFB | Variable refresh, when the monitor offers it. Not testable here: the monitor gives no VRR range over HDMI |

On in the kexts themselves, each with a boot-arg that turns it off: the framebuffer, accelerator and four heads of the RTX; in WhateverXe the recovery from GPU hangs (`-wex-no-reset-recover`), coherent scanout and the larger display buffer that scaled modes need (`-wex-no-scanout-coherent`, `-wex-no-hidpi-dbuf`), the HDR switch for a monitor on USB-C (`-wex-no-hdr-modes`, `-wex-no-hdr-sgx`); HybridPM's turbo (`-nohpm`); Wi-Fi 6 on the MT7920 (`-mtknohe`).

## Differences from the tested EFIs

**`install` profile:** all 71 assembled files are identical to the ones that installed macOS on the test machine. The only difference in `config.plist` is the identity. `Tools/` and `Resources/` are absent, as the `Builtin` picker does not use them. It keeps the MacBookPro16,1 model of that install, with a serial generated for 16,2: on the test machine the move from 16,1 to 16,2 happened on a system already installed.

**`full` profile:** the comparison is in `tools/sanitize_config.py compare`. In `config.plist` only these change:

- the identity;
- 15 keys an editor had dropped, put back with the value OpenCore 1.0.9 uses when they are absent, so that `ocvalidate` passes: same behaviour. Among them `FixupAppleEfiImages`, `false` because that is what its absence meant in the tests. `InitialMode` is `Auto`: an empty one is illegal for `ocvalidate`;
- `-nmappfreedbg`, NMAppFree's log line for each app it exempts, left out;
- the comments.

Among the binaries, everything downloaded matches the test machine byte for byte, except:

| File | Difference |
| --- | --- |
| `AirportItlwm` | Tested: build `738d4c6`. Downloaded: `7204c69`, because the `v2.4.0-alpha` release was published again and the old build is gone. **Not tested** |
| `WhateverXe`, `AppleALC`, `NMHDA`, `SMCNvidiaGPU`, `HybridPM`, `NitroEC`, `IDispHDA`, `AirportMtkWlan`, `SimpleMtkBtPatcher`, `NMAppFree`, `USBDiskKeeper` | Compiled by you, from the latest commit of the forks, of NMAppFree and of USBKeeper: see [postinstall/README.md](../postinstall/README.md). `AirportMtkWlan` holds MediaTek's firmware: do not publish it |
| `SimpleMtkBtFw` | The `Info.plist` gets the USB match of this laptop's Bluetooth, the same as on the test machine |
| `UTBMap-ANV`, `EHD0Off-ANV` | Only comment strings in their `Info.plist` |

## Validate

```bash
python3 efi/build_efi.py validate build/EFI/EFI/OC
```

It runs `ocvalidate` 1.0.9, then checks that each file named in the config exists and that each kext comes after those it depends on. `ocvalidate` says the config is well written, not that the PC boots.

## Write to the USB stick

```bash
python3 efi/build_efi.py deploy --profile full --volume /Volumes/OPENCORE
```

It validates the folder first, as above, and stops if it does not pass. Without `--go` it writes nothing. With `--go` it saves the folder it replaces in `private/efi-backups/`, copies next to it, reads back, compares, and only then swaps the two folders. It does not touch `EFI/BOOT`, other folders, BootOrder, NVRAM or rEFInd, and accepts only a writable FAT volume.

# EFI

Two profiles, built by `efi/build_efi.py` in `build/EFI/EFI/`:

| Profile | Folder | What for | Compile? |
| --- | --- | --- | --- |
| `install` | `OC-INSTALL` | Install macOS, recovery. The config that installed macOS on the test machine | No, downloads only |
| `full` | `OC` | The system with the drivers | Yes: ten kexts, from the forks and NMAppFree |

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
| Base | Lilu, AMFIPass, RestrictEvents, CpuTopologyRebuild, HybridPM (on with `-hpm`), NVMeFix, NMAppFree (Chrome's Widevine with the AMFI boot-args) |
| Graphics | WhateverXe (DEBUG build, in place of WhateverGreen), BrightnessKeys |
| Audio | AppleALC, SimpleHDA, NMHDA, IDispHDA (the Iris Xe over USB-C) |
| SMC | VirtualSMC, SMCBatteryManager, SMCLightSensor, SMCProcessor, SMCSuperIO, SMCNvidiaGPU |
| Input | VoodooI2C with its plugins, VoodooI2CHID, VoodooPS2Controller with its plugins |
| USB | USBToolBox, UTBMap-ANV, XHCI-unsupported |
| Network | RealtekRTL8111, AirportMtkWlan, SimpleMtkBtFw, SimpleMtkBtPatcher, BlueToolFixup: the original MediaTek MT7920. SimpleMtkBtFw gets one more USB match, `13D3:3622`, the Bluetooth of this laptop. SimpleMtkBtPatcher is compiled from the fork: it prepares USB buffers read only, without the backtraces the release logs for every USB transfer |
| Laptop | NitroEC |

Present and disabled: UTBDefault, EHD0Off-ANV, USBPorts, WhateverGreen, itlwm, and AirportItlwm, IntelBluetoothFirmware and IntelBTPatcher. **With an Intel card** in place of the MT7920, enable those three and disable AirportMtkWlan, SimpleMtkBtFw and SimpleMtkBtPatcher: that was tested with an AC 8265.

## Boot-args of the `full` profile

| Boot-arg | Whose | What for |
| --- | --- | --- |
| `-v keepsyms=1 debug=0x100` | macOS | Text boot, symbols in panics, no restart after a panic |
| `ctrsmt=full` | CpuTopologyRebuild | Core topology |
| `revpatch=sbvmm,cpuname revcpu=1` | RestrictEvents | CPU name, updates |
| `nvfb=1 nvaccel=1 nvfbheads=4 -nvkmsnosmooth` | NullMoth | Framebuffer and accelerator of the RTX |
| `amfi_get_out_of_my_way=0x1 amfi=0x80 ipc_control_port_options=0` | NullMoth, Graphics | WindowServer can load Metal drivers not signed by Apple. Without them the kernel rejects both plugins and the desktop does not arrive. They also put every app under the kernel's strictest Mach IPC rules: NMAppFree takes the user apps back out, see the [README](../README.md#chrome-and-nmappfree) |
| `gfxrst=4` | WhateverXe, NullMoth | No copy of the boot screen |
| `-allow3d -disablegfxfirmware -igfxdvmt` | WhateverXe | Intel acceleration, fixed stolen memory |
| `-wexdbg -wex-display13-trace -liludbg liludump=90` | WhateverXe, Lilu | Logs: the kext is the DEBUG build |
| `-wex-reset-recover` | WhateverXe | Recovery from GPU hangs. No real hang has triggered it yet |
| `-wex-scanout-coherent -wex-hidpi-dbuf` | WhateverXe | What scaled modes need: coherent scanout, and a larger display buffer for primary plane and cursor |
| `nvrmtgp=1` | NVRM | TGP mode of the GSP; the limit goes up only on request |
| `-wex-hdr-modes -wex-hdr-sgx` | WhateverXe | The HDR switch for a monitor on USB-C |
| `-hpm hpmepp=96` | HybridPM | CPU turbo: one core at 4.64 GHz, about 10 W more at idle |
| `-mtkhe` | AirportMtkWlan | Wi-Fi 6 on the MT7920 |
| `-nmintelfboff`, `wexdpalt=0x8` | | No effect here: the first is for NMIntelFB, which is not installed, and 0.7.0 ignores the second. They stay to match the tested profile |

## Differences from the tested EFIs

**`install` profile:** all 71 assembled files are identical to the ones that installed macOS on the test machine. The only difference in `config.plist` is the identity. `Tools/` and `Resources/` are absent, as the `Builtin` picker does not use them. It keeps the MacBookPro16,1 model of that install, with a serial generated for 16,2: on the test machine the move from 16,1 to 16,2 happened on a system already installed.

**`full` profile:** the comparison is in `tools/sanitize_config.py compare`. In `config.plist` only these change:

- the identity;
- 15 keys an editor had dropped, put back with the value OpenCore 1.0.9 uses when they are absent, so that `ocvalidate` passes: same behaviour. Among them `FixupAppleEfiImages`, `false` because that is what its absence meant in the tests. `InitialMode` is `Auto`: an empty one is illegal for `ocvalidate`;
- `-nmappfreedbg`, NMAppFree's log line for each app it exempts, left out;
- `-mtkhe`, added: the test machine's working config does not have it yet, its test entry does (see the [README](../README.md#boot-args-you-can-take-out));
- the comments.

Among the binaries, everything downloaded matches the test machine byte for byte, except:

| File | Difference |
| --- | --- |
| `AirportItlwm` | Tested: build `738d4c6`. Downloaded: `7204c69`, because the `v2.4.0-alpha` release was published again and the old build is gone. **Not tested** |
| `WhateverXe`, `AppleALC`, `NMHDA`, `SMCNvidiaGPU`, `HybridPM`, `NitroEC`, `IDispHDA`, `AirportMtkWlan`, `SimpleMtkBtPatcher`, `NMAppFree` | Compiled by you, from the latest commit of the forks and of NMAppFree: see [postinstall/README.md](../postinstall/README.md). `AirportMtkWlan` holds MediaTek's firmware: do not publish it |
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

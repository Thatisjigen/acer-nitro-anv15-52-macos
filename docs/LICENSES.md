# Licenses and redistribution

The rule of this repository: **no Apple binary and no third-party package unless it was verified that it can be redistributed.** In practice there is no binary of anyone else here: everything is downloaded from fixed URLs, with its hash, on the machine of whoever installs.

## What is in the repository

| File | License | Notes |
| --- | --- | --- |
| Scripts, documents, `efi/kexts/UTBMap-ANV.kext`, `efi/kexts/EHD0Off-ANV.kext`, `efi/kexts/USBPorts.kext`, the `*-ANV` SSDTs, `postinstall/overrides/` | MIT ([LICENSE](../LICENSE)) | Written for this project. `SSDT-PLUG-ANV`, `SSDT-EC-USBX-ANV` and `SSDT-AWAC-ANV` follow the samples of OpenCore |
| `efi/config.template.plist`, `efi/config.install.template.plist` | BSD-3-Clause ([text](../efi/licenses/OpenCore-BSD-3-Clause.txt)) | They derive from OpenCore's `Sample.plist` |
| `efi/kexts/XHCI-unsupported.kext/Contents/Info.plist` | GPL-2.0 ([text](../efi/licenses/GPL-2.0.txt)) | By RehabMan, with more IDs than in his repository; only an `Info.plist` |
| `efi/acpi/SSDT-NITRO.*` | GPL-3.0 | From ptnzzn's fork of NitroSense-macOS |
| `efi/acpi/SSDT-USB-Reset.*` | Not stated | Copied from the EFI of NullMoth's 1401 app: 110 bytes, one condition on `_STA`. To be redone separately if the author asks |
| `postinstall/drop_flat_weak_binds.py`, `layoutcheck.m`, `blendtest.m` | MIT | Written for this project |
| `postinstall/xefix/xefix.m` | Thou Shalt Not Profit 1.0 ([text](../postinstall/xefix/LICENSE-TSNPL-1.0.txt)) | A modified copy of part of `macos/src/libxedrv.m` by [JulioNectar](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe), commit `dabacb7`, with his notice and the list of changes at the top. Non-profit use, same license |

**Non-profit declaration, for `xefix.m`:** Section 18 of the Thou Shalt Not Profit License 1.0 allows distribution only with the declaration of its section 17. So: the maintainer of this repository, an individual acting on a not-for-profit basis, represents and declares that they derive no revenue whatsoever from the distribution of this work or of derivative works, or from support or services relating to them.

## What is downloaded

URLs and hashes are in [efi/sources.lock.json](../efi/sources.lock.json) and [postinstall/manifest.json](../postinstall/manifest.json).

| Component | License | How this repository treats it |
| --- | --- | --- |
| OpenCore, Lilu, VirtualSMC, WhateverGreen, RestrictEvents, BrightnessKeys | BSD-3-Clause | Downloaded from their releases |
| VoodooI2C | GPL-3.0 | Downloaded |
| itlwm, AirportItlwm | GPL-3.0 | Downloaded |
| BlueToolFixup (BrcmPatchRAM) | GPL-2.0 | Downloaded |
| NVMeFix, VoodooPS2, RealtekRTL8111, CpuTopologyRebuild, SimpleHDA, USBToolBox, IntelBluetoothFirmware, AMFIPass | See each project | Downloaded |
| `HfsPlus.efi`, `apfs_aligned.efi` | Apple binaries | Downloaded from acidanthera/OcBinaryData, never copied here |
| WhateverXe Graphics 0.4.0 | Tools BSD-2-Clause, payloads excluded | **Modified Apple drivers:** downloaded from b00t0x's release. The file patched by `posh_patch.sh` is created on your machine and must not be published |
| NullMoth 2.7.2 | PolyForm Noncommercial 1.0.0; Mesa; NVIDIA firmware with its own license | Downloaded from the release. **Noncommercial use** |
| Sound Open Firmware firmware | Intel license | Downloaded, embedded in the kext on your machine. Do not publish that kext without reading `LICENCE.Intel` |
| open-gpu-kernel-modules | MIT and GPL-2.0 | Downloaded to compile NVRM |
| SimpleMtkBtFw | GPL-3.0 | Downloaded; one USB match is added to its `Info.plist`. The patcher's `Info.plist` also comes from this release |
| MT7920 firmware, from linux-firmware | MediaTek's licence (`LICENCE.mediatek`) | Downloaded with its hash and built into AirportMtkWlan on your machine. It may be redistributed with MediaTek chips, but not under the GPL: **do not publish the compiled kext** |

## What is compiled from the forks

| Fork | License | What it means |
| --- | --- | --- |
| nvidia-macos-driver | PolyForm Noncommercial 1.0.0; translator LGPL-3.0 | **The compiled kexts and plugin are for noncommercial use only.** The branch also holds 25 commits by kitsuneislife from [nmx-intel](https://github.com/kitsuneislife/nmx-intel), 4 in the NVAccel compiled here and 21 in NMIntelFB, which is not installed here. That project states no license: the author agreed to their use, with nothing in writing |
| NvGfx (`darwin.mk`, `linecc.py`, to compile) | PolyForm Noncommercial 1.0.0 | Not redistributed |
| HybridPM | Thou Shalt Not Profit 1.0 | XE-PM code by JulioNectar: non-profit use, same license |
| NGShim (`ngshim.m` of umeow0716/NootedGreen) | Thou Shalt Not Profit 1.0 | Downloaded with its hash and compiled on your machine with `xefix.m`, not redistributed |
| WhateverXe, AppleALC | BSD-3-Clause | |
| SimpleMtkWlan | GPL-2.0 | Without its firmware, which is generated at build |
| SimpleMtkBtFw (the patcher) | GPL-3.0 | |
| LatSOF-Audio, nvenc, SMCNvidiaGPU | MIT | |
| NitroSense-macOS | GPL-3.0 | |
| NMAppFree | BSD-3-Clause | Not a fork: written for this laptop, in its own repository |

**macOS** belongs to Apple, and its license says it runs on Apple hardware. This repository does not contain macOS: the recovery is downloaded from Apple. Decide what you are allowed to do.

Licenses were checked on 3 November 2026; where it says "see each project" they were not read one by one, because nothing of those projects is redistributed here.

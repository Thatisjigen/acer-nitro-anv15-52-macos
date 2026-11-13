# Install guide

**Nobody has followed this guide from start to end.** It puts in order what worked on one machine, piece by piece, over three weeks. Keep a copy of your data off the SSD, and read [RECOVERY.md](RECOVERY.md) first.

You need a USB stick, Linux or macOS on this or another PC to prepare it, and Ethernet or a USB network adapter.

Panel, Wi-Fi card, SSD and GPU can differ within the same model. Check yours from Linux; the ones of the test machine are below.

```bash
lspci -nn | grep -E 'VGA|3D|Network|Audio|Non-Volatile'
```

| Component | Test machine |
| --- | --- |
| iGPU | Intel Iris Xe (Raptor Lake-P), `8086:A7A0` rev 04 |
| dGPU | NVIDIA RTX 5050 Laptop, `10DE:2D98` |
| Audio | Realtek ALC245 `10EC:0245` on Intel cAVS `8086:51CA`; HDMI audio `10DE:22EC` |
| Wi-Fi, Bluetooth | MediaTek MT7920 `14C3:7920`, Bluetooth on USB `13D3:3622` |
| Ethernet | Realtek Killer E2600, `10EC:2600` |
| Trackpad | ELAN0524, I2C HID `04F3:3215` |
| SSD | Kingston OM8PGP41024Q-AA, 1 TB NVMe, `2646:501B` |

## 1. BIOS and disk

- **VMD off,** or macOS does not see the SSD. If you also use Windows, prepare its boot first: with VMD off it does not start without a safe-mode step. The change applies to every system. Search for "RST to AHCI safe mode" in your SSD maker's guide.
- **Secure Boot off.**
- Above 4G decoding was already on here. Nothing else was changed.
- **A partition for macOS:** here it was created from Linux as exFAT, then erased as APFS in Recovery. Do not erase the whole disk, or you lose ESP, Windows and Linux. After this step the Windows recovery partition looked absorbed: check yours before you go on.

## 2. rEFInd

rEFInd stays the main boot manager, and OpenCore is one of its entries. This EFI has no `EFI/BOOT/BOOTx64.efi`, does not write BootOrder and does not register itself in the firmware. Linux and Windows start from their own rEFInd entries, without going through OpenCore: the ACPI tables and the SMBIOS of this EFI only touch macOS.

If you do not have rEFInd, install it [from its site](https://www.rodsbooks.com/refind/installing.html). Then add the entries of [efi/refind-opencore.conf](../efi/refind-opencore.conf) to `refind.conf`, with the name of your volume.

## 3. Identity and USB stick

You need Python 3 and `git`. Format a USB stick of at least 4 GB as FAT32, and name it `OPENCORE`: EFI and recovery fit together.

```bash
git clone https://github.com/Thatisjigen/acer-nitro-anv15-52-macos.git
```

```bash
cd acer-nitro-anv15-52-macos
```

Generate serial, MLB, UUID and ROM, once. They go in `private/identity.json`, outside Git. **Keep a copy:** without it, macOS sees another Mac.

```bash
python3 efi/build_efi.py identity
```

The EFI that installs macOS only needs downloads:

```bash
python3 efi/build_efi.py build --profile install
```

```bash
python3 efi/build_efi.py deploy --profile install --volume /Volumes/OPENCORE --go
```

On Linux the volume is where the stick is mounted, for example `/run/media/$USER/OPENCORE`. The recovery comes with `macrecovery.py`, which is in the OpenCore archive in `build/cache`:

```bash
unzip -o build/cache/*OpenCore-1.0.9-RELEASE.zip 'Utilities/macrecovery/*' -d build/oc
```

```bash
python3 build/oc/Utilities/macrecovery/macrecovery.py -b Mac-CFF7D910A743CAAF -m 00000000000000000 -os latest -o /Volumes/OPENCORE/com.apple.recovery.boot download
```

Note the version you download: `latest` changes over time.

## 4. Install macOS

1. In rEFInd choose **OpenCore install**. In the picker choose the recovery, with Space if it is hidden.
2. In Disk Utility: View › Show All Devices, and erase as APFS **only** the partition you prepared.
3. Install macOS. It needs the Internet: connect Ethernet.
4. At each restart go back to **OpenCore install**, choose `macOS Installer`, then the macOS volume.

With this same EFI the install worked here, and USB keyboard and mouse worked. The `install` profile has no acceleration and no audio.

## 5. Get to the tested build of macOS

Everything was tested on **macOS 26.7.3 (25G342)**. See which build you have:

```bash
sw_vers
```

If it is older, update from System Settings. If it is newer, the post-install stops and asks for `--any-build`: nobody has tried that combination. Graphics 0.4.1 says "Tahoe 26.7 or newer" upstream, but that holds for its authors on their hardware.

## 6. Build the drivers

You need about 3 GB free, the network and about 15 minutes. First the build tools, without Xcode:

```bash
xcode-select --install
```

Then, from the repository folder. What each step does is in [postinstall/README.md](../postinstall/README.md). `fetch` takes the latest commit of each fork's `acer/current`, and says so if it is newer than what was last tested; `fetch --tested` takes those instead.

```bash
python3 postinstall/postinstall.py doctor
```

```bash
python3 postinstall/postinstall.py fetch
```

```bash
python3 postinstall/postinstall.py build
```

## 7. The final EFI, before the drivers

**This comes before `install`.** Once the Apple Intel driver is in `/Library`, without WhateverXe in the EFI it would attach to the GPU without its fixes, so there must never be a moment when it is missing. This writes only `EFI/OC` on the stick, next to `EFI/OC-INSTALL`, which stays.

```bash
python3 efi/build_efi.py build --profile full --compiled ~/anv15-52-build/out
```

```bash
python3 efi/build_efi.py deploy --profile full --volume /Volumes/OPENCORE --go
```

## 8. The drivers

Nothing in these scripts restarts the PC. Read the plan, and connect the charger.

```bash
python3 postinstall/postinstall.py plan
```

```bash
sudo python3 postinstall/postinstall.py install --go
```

**Do not restart until it says it has finished,** even if NullMoth's installer prints "Done. Reboot now" half way. If a step stops, run the same command again to go on, or go back with the command it prints.

## 9. First boot

Shut down, do not restart. In rEFInd choose **OpenCore**, not **OpenCore install**, and in the picker the macOS volume: OpenCore does not start it by itself. The first boot can stop for up to a minute at "PCI configuration end" while the RTX starts, and it can stay slow until login: here the external monitor stayed on the Apple logo until then the first time, not the second. If macOS asks you to allow extensions, do it in System Settings › Privacy & Security, and restart.

At the desktop:

```bash
python3 postinstall/postinstall.py verify
```

`verify` says what is loaded, not whether it is stable. Then try what you need by hand, starting from the status table in the [README](../README.md). Keep the USB-C monitor connected from boot until you have saved your work: unplugging a port that never lit up has killed the PC on earlier builds.

If something goes wrong: [RECOVERY.md](RECOVERY.md).

## If you try it

Whoever follows this guide makes the first real test of these scripts. An issue with your macOS build, the output of `verify` and the point where it stopped helps. **Remove your identifiers from the logs** before you attach them.

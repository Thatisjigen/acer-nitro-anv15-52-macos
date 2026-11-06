# Recovery

The EFI and `/Library` are two separate things. **Changing the EFI does not remove the drivers installed in macOS,** and removing the drivers does not fix the EFI.

Nothing on this page has been tried after a clean install. Lines marked **tried** were used on the test machine, with earlier scripts.

## macOS starts, but something is wrong

From the repository folder:

```bash
sudo python3 postinstall/postinstall.py rollback
```

Without `--go` it says what it would do. With `--go` it puts everything back as it was before `install`, last step first: paths that were not there are removed.

Then restart with an EFI without WhateverXe, that is `install`.

**The rollback is always complete.** Half way, the kexts on disk would not match the auxiliary collection, and that combination has never booted. To turn off a single driver use the boot-args below.

**JulioNectar's fixes can be turned off live,** in every process within a second, without a reboot: `echo obx > /private/var/tmp/xedrv.off`. `o` is the compute order, `b` the serial barrier, `x` the blur fix. Remove the file to turn them on again.

The copies are in `/Library/ANV15-52/backup-<date>`. The rollback does not delete them. If it stops half way it can be run again: a `BAD line` message points to a line of the copies' journal that was left alone.

## macOS does not reach the desktop

**Turn off a driver from the boot-args.** Change `boot-args` in the `NVRAM` section of `config.plist` from another system: the EFI is on a FAT32 stick, which Linux and Windows can edit.

| Boot-arg | Effect | Whose |
| --- | --- | --- |
| `-nvoff` | The NVIDIA part does not start. **Tried.** It does not prove the GPU powers off, and **do not sleep in this mode:** the Intel GPU hangs and a watchdog panic follows | NullMoth |
| `-wexoff` | WhateverXe does not load. The Apple driver of the Iris Xe stays in the collection, so the outcome is not known | WhateverXe |
| `-nmhdaoff` | No HDMI audio. **Tried,** to get around a hang at wake | NMHDA |
| `-latsofoff` | LatSOF-Audio does not start | LatSOF-Audio |
| `nvsensoff=1` | SMCNvidiaGPU does not read the sensors | SMCNvidiaGPU |
| `-nmappfreeoff` | NMAppFree exempts no app: every app goes back under the strict Mach IPC rules, and Chrome loses protected video | NMAppFree |

Note the last visible line, or take a photo: with `-v` in the boot-args you see where it stops.

**NullMoth's guard:** after two boots in a row with no screen lit, the driver turns itself off and macOS starts on the firmware's framebuffer.

**A previous EFI:** `efi/build_efi.py deploy` saves the folder it replaces in `private/efi-backups/`. Copy it back on the stick. **Tried** many times, with earlier scripts.

**A panel saved at a scaled mode:** the kext of an older build can leave only HDMI alive. Go back to 1920×1080 in System Settings before you change the kext.

## Rollback from Recovery

If macOS does not start and the boot-args are not enough:

1. In rEFInd choose **OpenCore install**, then the recovery. Recovery loads nothing from `/Library`, so the drivers are not a problem there.
2. Open Utilities › Terminal.
3. With FileVault, unlock the volume first in Disk Utility.
4. Find the copy and run it. `rollback.sh` does not need Python, which Recovery does not have; the commands it uses are there, checked in the 26.6.2 recovery.

```bash
ls /Volumes/*Data/Library/ANV15-52/
```

Replace `NAME` with the name of your volume and `DATE` with the one of the folder:

```bash
bash "/Volumes/NAME - Data/Library/ANV15-52/backup-DATE/rollback.sh" --go
```

Then start from **OpenCore install**. This path has never been tried: it is the first thing to check, on a machine whose data you have already saved.

## Why not boot `install` with Graphics installed

The `install` profile has no WhateverXe. With the Graphics kexts in the auxiliary collection, the Apple driver attaches to the Iris Xe without the fixes. **So `install` is for the recovery and for reinstalling, not for the system with the drivers.** The exact outcome was not tried: a hang or a panic is expected.

## Reinstall from scratch

- `private/identity.json` is yours: keep it. With the same identity macOS sees the same Mac.
- Start again from step 4 of [INSTALL.md](INSTALL.md).
- The macOS partition can be erased without touching the others: in Disk Utility choose the volume, not the disk.

## After a macOS update

macOS rebuilds the auxiliary collection by itself from the kexts in `/Library/Extensions`, as seen going from 26.7.1 to 26.7.2. The fixes in NullMoth and WhateverXe depend on the kernel: an update can turn off acceleration or stop the boot. **Do not update macOS, OpenCore and the graphics stack at the same time,** or you cannot tell what broke what.

Save the EFI that works first.

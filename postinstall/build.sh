#!/bin/bash
# Compile the drivers of the Acer Nitro ANV15-52 from the sources postinstall.py fetch has placed in $WORK. No sudo; everything is
# written under $WORK, nothing is installed or loaded. Run it through postinstall.py build, which sets the variables below from
# manifest.json and hashes what comes out.
#   bash postinstall/build.sh [stage ...]    default: every stage, in order. A stage that is done is redone: delete nothing by hand
# Only the Command Line Tools are needed (no Xcode): clang, swiftc, make, git. Rust is installed under $WORK by the translator stage.
# The recipes are the ones that built the tested binaries; they differ only in where they read and write.
set -euo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
: "${WORK:?run this through postinstall.py build}"
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$WORK/src; DEPS=$WORK/deps; OBJ=$WORK/obj; OUT=$WORK/out; LOGS=$WORK/logs
NM=$SRC/nvidia-macos-driver; LILU=$DEPS/lilu-debug/Lilu.kext; LILU_SDK=$LILU/Contents/Resources; MKSDK=$DEPS/MacKernelSDK
OGKM=$DEPS/open-gpu-kernel-modules; NVGFX=$DEPS/NvGfx; PKG=$DEPS/nullmoth/pkgroot
RM=$OBJ/rm; COMPLETION=$RM/completion; JOBS=${JOBS:-$(sysctl -n hw.logicalcpu)}
CC=$(xcrun -f clang); CXX=$(xcrun -f clang++)
SDKROOT=$(xcrun --show-sdk-path); export SDKROOT; KHDR="$SDKROOT/System/Library/Frameworks/Kernel.framework/Headers"
mkdir -p "$OBJ" "$OUT" "$LOGS"
say() { echo "== $*"; }
die() { echo "STOP: $*" >&2; exit 1; }
sha() { shasum -a 256 "$1" | cut -c1-16; }
export_tree() {   # <checkout> <folder> [paths...]: a clean copy of the pinned commit; the builds never touch the checkout
  local from=$1 to=$2; shift 2; rm -rf "${to:?}"; mkdir -p "$to"; git -C "$from" archive HEAD "$@" | tar -x -C "$to"
}
stamp() { xattr -cr "$1" 2>/dev/null || true; chmod -R u+rwX,go+rX "$1"; }

# The include paths and -D flags of NVIDIA's RM, for everything that talks to it.
rm_flags() {
  local NV=$OGKM/src/nvidia KMS=$OGKM/src/nvidia-modeset C=$OGKM/src/common
  RMINC=( -I"$NV/arch/nvalloc/unix/include" -I"$NV/arch/nvalloc/common/inc" -I"$NV/arch/nvalloc/common/inc/gsp"
    -I"$C/sdk/nvidia/inc" -I"$C/sdk/nvidia/inc/hw" -I"$C/inc" -I"$C/shared/inc" -I"$NV/inc" -I"$NV/inc/os" -I"$NV/inc/kernel"
    -I"$NV/kernel/inc" -I"$NV/interface" -I"$C/nvlink/interface" -I"$C/inc/swref" -I"$C/inc/swref/published"
    -I"$NV/inc/libraries" -I"$NV/src/libraries" -I"$NV/generated" -I"$NV/src/mm/uvm/interface"
    -I"$C/uproc/os/libos-v2.0.0/include" -I"$C/uproc/os/common/include" -I"$C/inc/displayport" -I"$C/nvlink/inband/interface" )
  KMSINC=( -I"$KMS/os-interface/include" -I"$KMS/kapi/interface" -I"$KMS/kapi/include" -I"$C/unix/nvidia-push/interface"
    -I"$KMS/interface" -I"$KMS/include" -I"$C/unix/common/inc" -I"$C/modeset" -I"$C/unix/common/utils/interface" )
  RMDEFS=(); while read -r d; do RMDEFS+=("$d"); done < <(head -1 "$NV/_out/Darwin_x86_64/compile_cmds.sh" | tr ' ' '\n' | grep -E '^-D' | sed -e 's/"//g' | grep -v -E '^-D(NVRM|_LANGUAGE_C)$')
}

# RM and NVKMS of open-gpu-kernel-modules 615.78.08 as static archives, with the Darwin overlay of NvGfx: the part NVRM links. About 10 minutes.
component() {   # <dir under src> <archive> [make vars]
  local dir=$1 lib=$2; shift 2
  local d=$OGKM/src/$dir out=$OGKM/src/$dir/_out/Darwin_x86_64
  local cflags="-arch x86_64 -mmacosx-version-min=15.0 -mkernel -DNV_UNIX -DNV_BSD"
  local vars=( -f Makefile -f "$NVGFX/build/nvgfx/nvrm/darwin.mk" NV_VERBOSE=1 CC="$CC" CXX="$CXX" LD="$(xcrun -f ld)" AR="$(xcrun -f ar)"
    TARGET_OS=Darwin TARGET_ARCH=x86_64 NV_BUILD_USER=anv1552 NV_BUILD_HOST=anv1552 EXTRA_CFLAGS="$cflags" )
  mkdir -p "$out"
  say "$dir: make -j$JOBS, log $LOGS/$dir.log"
  ( cd "$d" && nice make "${vars[@]}" "$@" -j"$JOBS" NVGFX_LIB="$lib" nvgfx-archive ) > "$LOGS/$dir.log" 2>&1 \
    || { grep -E "error:|\*\*\*" "$LOGS/$dir.log" | head -20; die "$dir did not build"; }
  ( cd "$d" && make "${vars[@]}" "$@" -n -B nvgfx-objs 2> /dev/null ) | grep -E ' -c [^ ]+ -o ' > "$out/compile_cmds.sh"
  local n_obj n_cmd; n_obj=$( (cd "$d" && make "${vars[@]}" "$@" nvgfx-print-objs 2> /dev/null) | wc -l | tr -d ' ')
  n_cmd=$(wc -l < "$out/compile_cmds.sh" | tr -d ' ')
  [ "$n_obj" = "$n_cmd" ] || die "$dir: $n_cmd compile lines for $n_obj objects"
  say "$dir: $n_obj objects, $lib $(stat -f %z "$out/$lib") B"
}
stage_rm() {
  [ "$(git -C "$OGKM" rev-parse HEAD)" = "${OGKM_COMMIT:?}" ] || die "open-gpu-kernel-modules is not at $OGKM_COMMIT"
  # 615 has the kern_fsp.c half of this patch; NullMoth's release also carries the timer_ostimer.c half.
  local T=src/nvidia/src/kernel/gpu/timer/timer_ostimer.c P=$NM/kexts/NVRM/patches/610-fsp-timer-double-destroy.patch
  git -C "$OGKM" apply --include="$T" --reverse --check "$P" 2> /dev/null || git -C "$OGKM" apply --include="$T" "$P"
  component nvidia libnvkernel.a
  component nvidia-modeset libnvkms.a SHADER_OBJS=
  # NullMoth's script swaps its patched nvkms-kapi.c and nvkms-rm.c into a copy of libnvkms.a. Its list lacks the viewport patch that
  # its own release carries: the copy here applies it last.
  local X=$RM/kexts; export_tree "$NM" "$X"; X=$X/kexts/NVRM
  sed "s/'610-setmode-reason.patch'\]/'610-setmode-reason.patch','615-viewport-scaling.patch']/" "$X/build-completion-archive.py" > "$X/build-completion-archive-anv.py"
  grep -q "'615-viewport-scaling.patch'\]" "$X/build-completion-archive-anv.py" || die "the completion script changed: check the viewport patch by hand"
  rm -rf "$COMPLETION"
  python3 -I "$X/build-completion-archive-anv.py" --vendor "$OGKM/src/nvidia-modeset" --output "$COMPLETION" > "$LOGS/completion.log" 2>&1 || { tail -20 "$LOGS/completion.log"; die "completion archive"; }
  local syms; syms=$(nm "$COMPLETION/libnvkms.a" 2> /dev/null)
  grep -q " t _GetFlipPendingStatus$" <<< "$syms" || die "no GetFlipPendingStatus in the completion archive"
}

# The kext's Info.plist comes from the NullMoth package: the tree's says version 0.1.
kext_out() {   # <name> <binary>
  local name=$1 bin=$2 X=$OUT/$1.kext
  rm -rf "$X"; mkdir -p "$X/Contents/MacOS"; cp "$bin" "$X/Contents/MacOS/$name"
  cp "$PKG/Library/Extensions/$name.kext/Contents/Info.plist" "$X/Contents/Info.plist"
  stamp "$X"; say "$name $(sha "$X/Contents/MacOS/$name") $(stat -f %z "$X/Contents/MacOS/$name") B"
}

stage_nvrm() {
  [ -f "$OGKM/src/nvidia/_out/Darwin_x86_64/libnvkernel.a" ] && [ -f "$COMPLETION/libnvkms.a" ] || die "run the rm stage first"
  local S=$OBJ/nvrm/src O=$OBJ/nvrm/out G=$OBJ/nvrm/out/glue K
  export_tree "$NM" "$S" kexts/NVRM; rm -rf "$O"; mkdir -p "$G"; K=$S/kexts/NVRM; rm_flags
  local NV=$OGKM/src/nvidia KMS=$OGKM/src/nvidia-modeset
  local FLAGS=( -arch x86_64 -mmacosx-version-min=15.0 -fapple-kext -mkernel -nostdinc -I"$KHDR" -I"$K" "${RMINC[@]}" "${KMSINC[@]}"
    -DKERNEL -DKERNEL_PRIVATE -DDRIVER_PRIVATE -DAPPLE -DNeXT "${RMDEFS[@]}" -std=c++17 -fno-rtti -fno-exceptions -fno-builtin -fno-common
    -Wall -Wno-unused-parameter -Wno-inconsistent-missing-override -Wno-unused-function -O2 -ffile-prefix-map="$S"=/src -ffile-prefix-map="$HOME"=/build )
  local f pids=() rc=0
  for f in NVRM os-xnu os-xnu2 nv_xnu_stubs nv_xnu_power os-nvkms-xnu nvkms_shaders nvrm_fbinfo nvrm_gpuva nvrm_surfshare nvrm_power; do
    "$CXX" "${FLAGS[@]}" -c "$K/$f.cpp" -o "$G/$f.o" 2> "$G/$f.err" & pids+=($!)
  done
  for f in "${pids[@]}"; do wait "$f" || rc=1; done
  [ $rc = 0 ] || { grep -h "error:" "$G"/*.err | head -20; die "NVRM glue"; }
  OGKM=$OGKM python3 -I "$K/rmcc.py" "$K/nvrm_pageoff.c" "$G/nvrm_pageoff.o" 2> "$G/nvrm_pageoff.err" || { cat "$G/nvrm_pageoff.err"; die "nvrm_pageoff"; }
  OGKM=$OGKM python3 -I "$K/rmcc.py" "$K/nvrm_physctl.c" "$G/nvrm_physctl.o" 2> "$G/nvrm_physctl.err" || { cat "$G/nvrm_physctl.err"; die "nvrm_physctl"; }
  python3 -I "$NVGFX/build/nvgfx/nvrm/linecc.py" "$KMS" kapi/src/nvkms-kapi.c "$K/nvrm_kapi_fields.c" "$G/nvrm_kapi_fields.o" 2> "$G/nvrm_kapi_fields.err" || { cat "$G/nvrm_kapi_fields.err"; die "nvrm_kapi_fields"; }
  "$CXX" -arch x86_64 -mmacosx-version-min=15.0 -fapple-kext -nostdlib -Xlinker -kext \
    "$G/nv_xnu_stubs.o" "$G/nvkms_shaders.o" "$G/nvrm_fbinfo.o" "$G/nvrm_gpuva.o" "$G/nvrm_surfshare.o" "$G/NVRM.o" \
    "$G/os-nvkms-xnu.o" "$G/os-xnu.o" "$G/os-xnu2.o" "$G/nv_xnu_power.o" "$G/nvrm_kapi_fields.o" "$G/nvrm_pageoff.o" \
    "$G/nvrm_power.o" "$G/nvrm_physctl.o" "$NV/_out/Darwin_x86_64/libnvkernel.a" "$COMPLETION/libnvkms.a" \
    -lkmodc++ -lkmod -lcc_kext -o "$O/NVRM" > "$O/link.log" 2>&1 || { grep -v "built for newer macOS" "$O/link.log" | head -30; die "NVRM link"; }
  kext_out NVRM "$O/NVRM"
}

stage_nvrmfb() {
  local S=$OBJ/nvrmfb/src O=$OBJ/nvrmfb/out SR
  export_tree "$NM" "$S" kexts/NVRMFB kexts/NVRM kexts/NMHDA; rm -rf "$O"; mkdir -p "$O"; SR=$S/kexts/NVRMFB; rm_flags
  "$CXX" -arch x86_64 -fapple-kext -mkernel -nostdinc -I"$KHDR" -DKERNEL -DKERNEL_PRIVATE -DDRIVER_PRIVATE -DAPPLE -DNeXT \
    -std=c++17 -fno-rtti -fno-exceptions -fno-builtin -fno-common -Wall -Wno-unused-parameter -Wno-inconsistent-missing-override -Wno-unused-function -O2 \
    -ffile-prefix-map="$S"=/src -ffile-prefix-map="$HOME"=/build -I"$SR" -I"$S/kexts/NVRM" "${RMINC[@]}" "${KMSINC[@]}" "${RMDEFS[@]}" -I"$SR/fb" \
    -c "$SR/fb/nvrm-fb.cpp" -o "$O/nvrm-fb.o" 2> "$O/fb.err" || { grep error "$O/fb.err" | head -20; die "NVRMFB compile"; }
  "$CXX" -arch x86_64 -fapple-kext -nostdlib -Xlinker -kext -lkmodc++ -lkmod -lcc_kext "$O/nvrm-fb.o" -o "$O/NVRMFB" > "$O/link.log" 2>&1 || { head -20 "$O/link.log"; die "NVRMFB link"; }
  kext_out NVRMFB "$O/NVRMFB"
}

stage_nvaccel() {   # NullMoth's own script, without NM_TAHOE: its macOS 26 variant is not what was tested
  local S=$OBJ/nvaccel/src O=$OBJ/nvaccel/out
  export_tree "$NM" "$S" kexts/NVRM build/accel_build.sh; rm -rf "$O"
  ( cd "$S" && OGKM="$OGKM" bash build/accel_build.sh kexts/NVRM "$O" ) > "$LOGS/nvaccel.log" 2>&1 || { tail -20 "$LOGS/nvaccel.log"; die "NVAccel"; }
  kext_out NVAccel "$O/NVAccel.kext/Contents/MacOS/NVAccel"
}

stage_nvrmagdc() {   # against MacKernelSDK's headers, as the binary that ran
  local S=$OBJ/nvrmagdc/src O=$OBJ/nvrmagdc/out D
  export_tree "$NM" "$S" kexts/NVRMAGDC; rm -rf "$O"; mkdir -p "$O"; D=$S/kexts/NVRMAGDC
  ( cd "$D" && "$CXX" -arch x86_64 -fapple-kext -mkernel -nostdinc -I"$(mksdk)/Headers" -I. -DKERNEL -DKERNEL_PRIVATE -DDRIVER_PRIVATE -DAPPLE -DNeXT \
    -std=c++17 -fno-rtti -fno-exceptions -fno-builtin -fno-common -Wall -Wno-unused-parameter -Wno-inconsistent-missing-override -Wno-unused-function -O2 \
    -c nvrm-agdc.cpp -o "$O/k1.o" ) 2> "$O/cc.err" || { grep error "$O/cc.err" | head; die "NVRMAGDC compile"; }
  "$CXX" -arch x86_64 -fapple-kext -nostdlib -Xlinker -kext -lkmodc++ -lkmod -lcc_kext "$O/k1.o" -o "$O/NVRMAGDC" 2> "$O/ld.err" || { head "$O/ld.err"; die "NVRMAGDC link"; }
  kext_out NVRMAGDC "$O/NVRMAGDC"
}

epoch() { date -j -u -f '%Y-%m-%d %H:%M:%S' "$1 12:00:00" +%s; }
# Lilu plugins build against acidanthera's MacKernelSDK at one commit, exported so its checkout stays clean.
mksdk() { local to=$OBJ/MacKernelSDK; [ -d "$to/Headers" ] || { mkdir -p "$to"; git -C "$MKSDK" archive "${MKSDK_COMMIT:?}" | tar -x -C "$to"; }; echo "$to"; }

stage_nmhda() {   # injected by OpenCore, not installed in /Library
  local S=$OBJ/nmhda/src O=$OBJ/nmhda/out
  export_tree "$NM" "$S" kexts/NMHDA; rm -rf "$O"; mkdir -p "$O"
  # the date goes into the kext's version: this one gives the binary that ran
  SOURCE_DATE_EPOCH=$(epoch "${NMHDA_DATE:?}") bash "$S/kexts/NMHDA/build.sh" "$LILU" "$(mksdk)" "$O" > "$LOGS/nmhda.log" 2>&1 || { tail -20 "$LOGS/nmhda.log"; die "NMHDA"; }
  rm -rf "$OUT/NMHDA.kext"; cp -R "$O/NMHDA.kext" "$OUT/NMHDA.kext"; stamp "$OUT/NMHDA.kext"
  say "NMHDA $(sha "$OUT/NMHDA.kext/Contents/MacOS/NMHDA")"
}

stage_plugin() {   # NVMTLDriver: Objective-C against Mesa's Vulkan headers
  local S=$OBJ/plugin/src INC=$DEPS/mesa-include/include
  [ -f "$INC/vulkan/vulkan_core.h" ] || die "no Mesa headers in $INC"
  export_tree "$NM" "$S" plugin; mkdir -p "$OUT/bundle"
  ( cd "$S/plugin" && xcrun clang -arch x86_64 -mmacosx-version-min=15.0 -bundle -fobjc-arc -O1 -DNVMTL_RELEASE=1 \
      -Wno-protocol -Wno-incomplete-implementation -Werror=unguarded-availability-new -I"$INC" -o "$OUT/bundle/NVMTLDriver" NVMTLDevice.m \
      -framework Foundation -framework Metal -framework IOSurface -framework IOKit -framework CoreFoundation -framework MetalFX ) > "$LOGS/plugin.log" 2>&1 || { grep ' error:' "$LOGS/plugin.log" | head -20; die "plugin"; }
  codesign -f -s - "$OUT/bundle/NVMTLDriver" 2> /dev/null
  say "NVMTLDriver $(sha "$OUT/bundle/NVMTLDriver")"
}

stage_translator() {   # libnvmtl_translate: Rust, toolchain and crates under $WORK, no shell profile touched. About 5 minutes the first time.
  local R=$DEPS/rust
  export RUSTUP_HOME=$R/rustup CARGO_HOME=$R/cargo RUSTUP_TOOLCHAIN=${RUST_VERSION:?}
  if [ ! -x "$R/cargo/bin/cargo" ]; then
    mkdir -p "$R/dl"
    ( cd "$R/dl" && curl -sSfO https://static.rust-lang.org/rustup/dist/x86_64-apple-darwin/rustup-init \
      && echo "$(curl -sSf https://static.rust-lang.org/rustup/dist/x86_64-apple-darwin/rustup-init.sha256 | cut -d' ' -f1)  rustup-init" | shasum -a 256 -c - \
      && chmod +x rustup-init && ./rustup-init -y -q --no-modify-path --profile minimal --default-toolchain "$RUST_VERSION" ) || die "Rust toolchain"
  fi
  export PATH=$CARGO_HOME/bin:$PATH
  # Always this folder: wrapper depends on the crate above it, outside its workspace, so cargo puts that absolute path into the hash in every symbol, and another folder gives another file
  local B=/private/tmp/anv15-52-translator
  rm -rf "$B" || die "$B belongs to someone else: remove it"; mkdir -m 700 "$B" || die "cannot create $B"; export_tree "$NM" "$B/src" translator
  # File names end up in the library, for panics: these prefixes, which name no machine, give the same bytes wherever this folder is
  export RUSTFLAGS="--remap-path-prefix=$B/src=/build/translator/src --remap-path-prefix=$CARGO_HOME=/build/cargo -C link-arg=-Wl,-install_name,@rpath/libnvmtl_translate.dylib"
  ( cd "$B/src/translator" && cargo build --locked --release --target x86_64-apple-darwin --manifest-path wrapper/Cargo.toml --target-dir "$B/target" ) > "$LOGS/translator.log" 2>&1 \
    || { grep -A6 '^error' "$LOGS/translator.log" | head -30; die "translator"; }
  local D=$OUT/bundle/libnvmtl_translate.dylib; mkdir -p "$OUT/bundle"
  cp "$B/target/x86_64-apple-darwin/release/libnvmtl_translate.dylib" "$D"
  strip -S "$D"; install_name_tool -id @rpath/libnvmtl_translate.dylib "$D"; codesign -f -s - "$D"
  rm -rf "$B"
  say "libnvmtl_translate $(sha "$D")"
}

stage_nvenc() {   # libnvencvt: the decoders for H.264, HEVC, VP9 and AV1 on the RTX 5050
  local F=$SRC/nvenc K=$DEPS/open-gpu-kernel-modules-610 D=$DEPS/open-gpu-doc S=$DEPS/webkit-spi W=$OBJ/nvenc
  export_tree "$F" "$W" src vt; mkdir -p "$OUT/bundle" "$W/o"; : > "$LOGS/nvenc.log"
  # one object at a time, with fixed names: clang's own temporary names make the linker order differ at every build
  local f objs=()
  for f in "$W/vt/nvencvt.c" "$W/vt/nvencvt_dec.c" "$W"/src/*.c; do
    objs+=("$W/o/$(basename "$f" .c).o")
    xcrun clang -O2 -Wall -DNVENC_VERSION="\"${NVENC_VERSION:?}\"" -I "$W/src" -I "$S" -I "$K/src/common/sdk/nvidia/inc" -I "$K/src/nvidia/arch/nvalloc/unix/include" -I "$D/classes/video" \
      -c "$f" -o "${objs[${#objs[@]}-1]}" >> "$LOGS/nvenc.log" 2>&1 || { grep 'error:' "$LOGS/nvenc.log" | head; die "nvenc"; }
  done
  # the internal name, by default the output path, decides where the linker puts things: a fixed one gives the same file on every machine
  xcrun clang -dynamiclib -Wl,-install_name,/Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/libnvdec_h264.dylib -o "$OUT/bundle/libnvencvt.dylib" "${objs[@]}" \
    -framework IOKit -framework CoreFoundation -framework CoreMedia -framework CoreVideo -framework VideoToolbox -framework Accelerate -framework IOSurface >> "$LOGS/nvenc.log" 2>&1 \
    || { grep 'error:' "$LOGS/nvenc.log" | head; die "nvenc link"; }
  codesign -f -s - "$OUT/bundle/libnvencvt.dylib" 2> /dev/null
  say "libnvencvt $(sha "$OUT/bundle/libnvencvt.dylib")"
}

stage_ngshim() {   # umeow0716's bridge for the Intel Metal driver, with the flags of its NGShim/build.sh. layoutcheck.m runs its guards on this macOS
  local W=$OBJ/ngshim N=$OBJ/ngshim/impostor.dylib; rm -rf "$W"; mkdir -p "$W" "$OUT/bundle"
  # with the fixes of JulioNectar beside it: xefix.m without ARC, ngshim.m with ARC
  { xcrun clang -arch x86_64 -c -fno-objc-arc -O2 -mmacosx-version-min=14.0 -o "$W/xefix.o" "$HERE/xefix/xefix.m" \
    && xcrun clang -arch x86_64 -c -fobjc-arc -O2 -Wall -mmacosx-version-min=14.0 -o "$W/ngshim.o" "$DEPS/ngshim/ngshim.m" \
    && xcrun clang -arch x86_64 -dynamiclib -mmacosx-version-min=14.0 -install_name @loader_path/impostor.dylib -framework Foundation -framework Metal -o "$N" "$W/ngshim.o" "$W/xefix.o"; } \
    > "$LOGS/ngshim.log" 2>&1 || { grep 'error:' "$LOGS/ngshim.log" | head; die "NGShim"; }
  codesign -f -s - -i impostor "$N" && codesign -v "$N" || die "NGShim signature"
  ! otool -L "$N" | grep -q descriptor.dylib || die "NGShim should not need descriptor.dylib"
  [ "$(otool -D "$N" | tail -1)" = "@loader_path/impostor.dylib" ] || die "NGShim install name"
  ! nm -g "$N" | grep -v ' U ' | grep -v -E '_OBJC_(CLASS|METACLASS|IVAR)_\$_Xe' | grep -q . || die "NGShim should export only the classes of xefix.m"
  xcrun clang -arch x86_64 -fobjc-arc -framework Foundation -framework Metal -o "$W/layoutcheck" "$HERE/layoutcheck.m" >> "$LOGS/ngshim.log" 2>&1 || die "layoutcheck"
  "$W/layoutcheck" >> "$LOGS/ngshim.log" 2>&1 || { tail -8 "$LOGS/ngshim.log"; die "NGShim's guards would not all pass on this macOS"; }
  cp "$N" "$OUT/bundle/impostor.dylib"
  say "NGShim $(sha "$OUT/bundle/impostor.dylib")"
}

stage_latsof() {   # internal microphone. The firmware is embedded at link time and is downloaded, never in a repository
  local W=$OBJ/latsof FW=$DEPS/sof/sof-rpl.ri
  export_tree "$SRC/LatSOF-Audio" "$W"; cp "$FW" "$W/kext/LatSOFAudio/Firmware/sof-rpl.ri"
  SOURCE_DATE_EPOCH=1790000000 make -C "$W/kext" > "$LOGS/latsof.log" 2>&1 || { tail -30 "$LOGS/latsof.log"; die "LatSOF"; }
  rm -rf "$OUT/LatSOFAudio.kext"; cp -R "$W/kext/LatSOFAudio.kext" "$OUT/LatSOFAudio.kext"; stamp "$OUT/LatSOFAudio.kext"
  say "LatSOFAudio $(sha "$OUT/LatSOFAudio.kext/Contents/MacOS/LatSOFAudio")"
}

stage_nitrosense() {   # NitroEC for the EFI; nitrod, nitroctl and the app for the system
  local W=$OBJ/nitrosense
  export_tree "$SRC/NitroSense-macOS" "$W"
  make -C "$W" kext cli daemon app OPEN_GPU="$OGKM" > "$LOGS/nitrosense.log" 2>&1 || { tail -30 "$LOGS/nitrosense.log"; die "NitroSense"; }
  rm -rf "$OUT/NitroEC.kext" "$OUT/nitrosense"; mkdir -p "$OUT/nitrosense"
  cp -R "$W/build/NitroEC.kext" "$OUT/NitroEC.kext"; stamp "$OUT/NitroEC.kext"
  cp "$W/build/nitrod" "$W/build/nitroctl" "$OUT/nitrosense/"; cp -R "$W/build/NitroSense.app" "$OUT/nitrosense/NitroSense.app"
  say "NitroEC $(sha "$OUT/NitroEC.kext/Contents/MacOS/NitroEC"), nitrod $(sha "$OUT/nitrosense/nitrod"), app $(sha "$OUT/nitrosense/NitroSense.app/Contents/MacOS/NitroSense")"
}

stage_smcnvidiagpu() {   # has to match the NVRM above: it is given that binary, and the two go together
  local W=$OBJ/smcnvidiagpu NVRM=$OUT/NVRM.kext/Contents/MacOS/NVRM
  [ -f "$NVRM" ] || die "run the nvrm stage first"
  export_tree "$SRC/SMCNvidiaGPU" "$W"
  MODE=release NVRM=$NVRM VSMCDIR="$DEPS/VirtualSMC" LILUDIR="$LILU_SDK" MACKERNELSDK="$(mksdk)" bash "$W/kext/build.sh" "$W/out" > "$LOGS/smcnvidiagpu.log" 2>&1 \
    || { tail -30 "$LOGS/smcnvidiagpu.log"; die "SMCNvidiaGPU"; }
  rm -rf "$OUT/SMCNvidiaGPU.kext"; cp -R "$W/out/SMCNvidiaGPU.kext" "$OUT/SMCNvidiaGPU.kext"; stamp "$OUT/SMCNvidiaGPU.kext"
  say "SMCNvidiaGPU $(sha "$OUT/SMCNvidiaGPU.kext/Contents/MacOS/SMCNvidiaGPU")"
}

stage_whateverxe() {   # the DEBUG build, as the one that ran: the boot-args in the config ask for its logs
  local W=$OBJ/whateverxe/src O=$OBJ/whateverxe/out
  export_tree "$SRC/WhateverXe" "$W"; rm -rf "$O"; mkdir -p "$O"
  ( cd "$W" && SOURCE_DATE_EPOCH=$(epoch "${WHATEVERXE_DATE:?}") python3 tools/build.py --sdk "$(mksdk)" --lilu "$LILU" --output "$O" ) > "$LOGS/whateverxe.log" 2>&1 || { grep -E 'error' "$LOGS/whateverxe.log" | head -20; die "WhateverXe"; }
  ( cd "$W" && python3 tools/test.py ) > "$LOGS/whateverxe-test.log" 2>&1 || { tail -5 "$LOGS/whateverxe-test.log"; die "WhateverXe tests"; }
  rm -rf "$OUT/WhateverXe.kext"; cp -R "$O/WhateverXe.kext" "$OUT/WhateverXe.kext"; stamp "$OUT/WhateverXe.kext"
  say "WhateverXe $(sha "$OUT/WhateverXe.kext/Contents/MacOS/WhateverXe"); $(tail -1 "$LOGS/whateverxe-test.log" | cut -c1-80)"
}

stage_hybridpm() {   # its own script, reproducible: on with -hpm in boot-args
  local W=$OBJ/hybridpm
  export_tree "$SRC/HybridPM" "$W"
  LILU_ZIP="$DEPS/lilu-debug.zip" bash "$W/build.sh" > "$LOGS/hybridpm.log" 2>&1 || { tail -20 "$LOGS/hybridpm.log"; die "HybridPM"; }
  rm -rf "$OUT/HybridPM.kext"; cp -R "$W/build/out/HybridPM.kext" "$OUT/HybridPM.kext"; stamp "$OUT/HybridPM.kext"
  say "HybridPM $(sha "$OUT/HybridPM.kext/Contents/MacOS/HybridPM")"
}

stage_applealc() {   # AppleALC 1.9.8 with ALC245 layouts 66 and 67. The steps follow AppleALC.xcodeproj, Release configuration
  local B=$OBJ/applealc VER=1.9.8 SDK=$LILU_SDK K S; export_tree "$SRC/AppleALC" "$B/AppleALC"; K=$(mksdk)/Headers; S=$B/AppleALC/AppleALC
  local SOURCE_DATE_EPOCH=1790544554; export SOURCE_DATE_EPOCH   # fixes Lilu's kextVersion (__DATE__/__TIME__); local, so the stages after this one do not get it
  rm -rf "$B/bin" "$B/obj" "$B/out"; mkdir -p "$B/bin" "$B/obj" "$B/out/AppleALC.kext/Contents/MacOS"
  xcrun clang++ -std=c++14 -fobjc-arc -O2 -w "$B/AppleALC/ResourceConverter/main.mm" -framework Foundation -framework Cocoa -o "$B/bin/ResourceConverter"
  PROJECT_DIR="$B/AppleALC" TARGET_BUILD_DIR="$B/bin" bash -e "$B/AppleALC/ResourceConverter/generate.sh" > "$LOGS/applealc-generate.log" 2>&1 || { tail -20 "$LOGS/applealc-generate.log"; die "AppleALC resources"; }
  local FLAGS=(-arch x86_64 -mmacosx-version-min=10.6 -std=c++14 -mkernel -fapple-kext -nostdinc -I"$K" -I"$SDK" -I"$S" -I"$S/ALCUserClient" -I"$S/ALCUserClientProvider"
    -DKERNEL -DKERNEL_PRIVATE -DDRIVER_PRIVATE -DAPPLE -DNeXT -DMODULE_VERSION=$VER -DPRODUCT_NAME=AppleALC -DHAVE_ANALOG_AUDIO=1
    -O3 -flto -fvisibility=hidden -fno-rtti -fno-exceptions -fno-common -mmmx -msse -msse2 -msse3 -mfpmath=sse -mssse3 -ftree-vectorize -fno-non-call-exceptions -fno-builtin -fno-asynchronous-unwind-tables
    -Wno-unknown-warning-option -Wno-ossharedptr-misuse -Wno-vla -Wno-stdlibcxx-not-found -Wno-deprecated-declarations)
  local f
  for f in "$S/kern_alc.cpp" "$S/ALCUserClientProvider/ALCUserClientProvider.cpp" "$S/ALCUserClient/ALCUserClient.cpp" "$SDK/Library/plugin_start.cpp" "$S/kern_start.cpp" "$S/kern_resources.cpp"; do
    xcrun clang++ "${FLAGS[@]}" -c "$f" -o "$B/obj/$(basename "${f%.cpp}").o" 2>> "$LOGS/applealc.log" || { tail -20 "$LOGS/applealc.log"; die "AppleALC compile"; }
  done
  cat > "$B/obj/AppleALC_info.c" <<EOF
#include <mach/mach_types.h>
extern kern_return_t _start(kmod_info_t *ki, void *data);
extern kern_return_t _stop(kmod_info_t *ki, void *data);
__private_extern__ kern_return_t AppleALC_kern_start(kmod_info_t *ki, void *data);
__private_extern__ kern_return_t AppleALC_kern_stop(kmod_info_t *ki, void *data);
__attribute__((visibility("default"))) KMOD_EXPLICIT_DECL(as.vit9696.AppleALC, "$VER", _start, _stop)
__private_extern__ kmod_start_func_t *_realmain = AppleALC_kern_start;
__private_extern__ kmod_stop_func_t *_antimain = AppleALC_kern_stop;
__private_extern__ int _kext_apple_cc = __APPLE_CC__ ;
EOF
  xcrun clang -arch x86_64 -mmacosx-version-min=10.6 -mkernel -nostdinc -I"$K" -DKERNEL -DKERNEL_PRIVATE -O3 -flto -fvisibility=hidden -c "$B/obj/AppleALC_info.c" -o "$B/obj/AppleALC_info.o"
  local BIN=$B/out/AppleALC.kext/Contents/MacOS/AppleALC
  xcrun clang++ -arch x86_64 -mmacosx-version-min=10.6 -mkernel -fapple-kext -nostdlib -flto -Xlinker -kext -Xlinker -dead_strip -static -L"$(dirname "$K")/Library/universal" \
    "$B"/obj/{kern_alc,ALCUserClientProvider,ALCUserClient,plugin_start,kern_start,kern_resources,AppleALC_info}.o -lkmodc++ -lkmod -lcc_kext -o "$BIN"
  strip -S "$BIN"; strip -x -T "$BIN" 2>/dev/null || strip -x "$BIN"
  python3 -I - "$B/AppleALC" "$B/out/AppleALC.kext/Contents/Info.plist" $VER <<'PY'
import plistlib, sys
tree, out, ver = sys.argv[1:]
t = open(f'{tree}/AppleALC/AppleALC-Info.plist').read()
for k, v in {'EXECUTABLE_NAME': 'AppleALC', 'PRODUCT_BUNDLE_IDENTIFIER': 'as.vit9696.AppleALC', 'PRODUCT_NAME:rfc1034identifier': 'AppleALC',
             'PRODUCT_NAME': 'AppleALC', 'MODULE_VERSION': ver}.items():
    t = t.replace(f'$({k})', v)
assert '$(' not in t
info = plistlib.loads(t.encode())
pc = plistlib.load(open(f'{tree}/Resources/PinConfigs.kext/Contents/Info.plist', 'rb'))
info['IOKitPersonalities']['as.vit9696.AppleALC'] = pc['IOKitPersonalities']['as.vit9696.AppleALC']
info['CFBundleSupportedPlatforms'] = ['MacOSX']; info['LSMinimumSystemVersion'] = '10.6'
plistlib.dump(info, open(out, 'wb'))
PY
  rm -rf "$OUT/AppleALC.kext"; cp -R "$B/out/AppleALC.kext" "$OUT/AppleALC.kext"; stamp "$OUT/AppleALC.kext"
  say "AppleALC $(sha "$OUT/AppleALC.kext/Contents/MacOS/AppleALC")"
}

stage_idisphda() {   # the Intel display codec, for audio over USB-C: from the AppleALC fork, with its own build.sh, which first runs its table tests
  local W=$OBJ/idisphda O=$OBJ/idisphda/out
  export_tree "$SRC/AppleALC" "$W" IDispHDA; rm -rf "${O:?}"
  SOURCE_DATE_EPOCH=$(epoch "${IDISPHDA_DATE:?}") bash "$W/IDispHDA/build.sh" "$LILU" "$(mksdk)" "$O" > "$LOGS/idisphda.log" 2>&1 || { tail -20 "$LOGS/idisphda.log"; die "IDispHDA"; }
  rm -rf "${OUT:?}/IDispHDA.kext"; cp -R "$O/IDispHDA.kext" "$OUT/IDispHDA.kext"; stamp "$OUT/IDispHDA.kext"
  say "IDispHDA $(sha "$OUT/IDispHDA.kext/Contents/MacOS/IDispHDA")"
}

stage_mtkwlan() {   # the original MT7920 Wi-Fi card: AirportMtkWlan, Debug as tested, with the flags of the fork's build-macos.sh and without Xcode
  local F=$OBJ/mtkwlan/src O=$OBJ/mtkwlan/out NAME=AirportMtkWlan BID=com.flxxxxddd.AirportMtkWlan
  export_tree "$SRC/SimpleMtkWlan" "$F"; rm -rf "${F:?}/MacKernelSDK"; cp -R "$(mksdk)" "$F/MacKernelSDK"
  # the firmware comes from linux-firmware, downloaded with its hash by fetch: MediaTek's licence keeps it out of Git and out of this repository
  python3 -I "$F/tools/gen-mt7920-fw.py" --from "$DEPS/mt7920" > "$LOGS/mtkwlan.log" 2>&1 || { tail -5 "$LOGS/mtkwlan.log"; die "MT7920 firmware"; }
  local COMMIT VERSION HDR KMOD SOURCES=() INCS FLAGS OBJECTS=() f o d
  COMMIT=${MTK_GIT_COMMIT:-$(git -C "$SRC/SimpleMtkWlan" rev-parse --short=7 HEAD)}
  VERSION=$(sed -n 's/.*MODULE_VERSION = \([0-9.]*\);.*/\1/p' "$F/SimpleMtkWlan.xcodeproj/project.pbxproj" | head -1)
  HDR=$F/MacKernelSDK/Headers; KMOD=$F/MacKernelSDK/Library/x86_64/libkmod.a
  while IFS= read -r f; do SOURCES+=("$f"); done < <(cd "$F" && ls \
    include/FwBinary.cpp include/HAL/MtkHalService.cpp mtk80211/compat.cpp mtk80211/zutil.c \
    mtk80211/openbsd/crypto/*.c mtk80211/openbsd/net80211/*.c mtk80211/openbsd/net80211/*.cpp \
    mtk80211/openbsd/sys/arp.c mtk80211/openbsd/sys/_ifq.cpp mtk80211/openbsd/sys/_mbuf.cpp mtk80211/openbsd/sys/_task.cpp \
    SimpleMtkWlan/hal_mwx/MtkMwx.cpp SimpleMtkWlan/MtkLog.cpp AirportMtkWlan/*.cpp AirportMtkWlan/WCL/*.cpp)
  [ "${#SOURCES[@]}" -gt 30 ] || die "AirportMtkWlan: ${#SOURCES[@]} sources"
  INCS=(-I "$HDR"); for d in mtk80211/openbsd mtk80211 include; do INCS+=(-isystem "$F/$d"); done
  while IFS= read -r d; do INCS+=(-I "$d"); done < <(find "$F/SimpleMtkWlan" "$F/include" "$F/mtk80211" -type d)
  INCS+=(-I "$F/AirportMtkWlan")
  FLAGS=(-target x86_64-apple-macos10.12 -x c++ -std=gnu++14 -mkernel -fapple-kext -fno-rtti -fno-exceptions -fno-builtin -fno-common -nostdlib
    -fno-use-cxa-atexit -fno-asynchronous-unwind-tables -DKERNEL -DIEEE80211_STA_ONLY -D__PRIVATE_SPI__
    -DAIRPORT -DAIRPORT_WCL -D__IO80211_TARGET=__MAC_26_0 -DIO80211FAMILY_V2
    "-DSMTW_VERSION=\"$VERSION\"" "-DGIT_COMMIT=\"$COMMIT\"" "-DITLWM_VERSION=\"$VERSION\"" -include "$F/SimpleMtkWlan/PrivateSPI.pch"
    -Wno-deprecated-register -Wno-everything -Werror=return-type -O0 -DDEBUG=1)
  rm -rf "${O:?}"; mkdir -p "$O/obj" "$O/$NAME.kext/Contents/MacOS"; : > "$LOGS/mtkwlan.log"
  for f in "${SOURCES[@]}"; do
    o=$O/obj/$(echo "$f" | tr '/' '_').o; OBJECTS+=("$o")
    "$CXX" "${FLAGS[@]}" "${INCS[@]}" -c "$F/$f" -o "$o" >> "$LOGS/mtkwlan.log" 2>&1 || { tail -20 "$LOGS/mtkwlan.log"; die "AirportMtkWlan: $f"; }
  done
  cat > "$O/obj/kmod_info.c" <<KMOD
#include <mach/kmod.h>
extern kern_return_t _start(kmod_info_t *, void *);
extern kern_return_t _stop(kmod_info_t *, void *);
__attribute__((visibility("default"))) kmod_start_func_t *_realmain = 0;
__attribute__((visibility("default"))) kmod_stop_func_t *_antimain = 0;
__attribute__((visibility("default"))) kmod_info_t kmod_info = {
	0, KMOD_INFO_VERSION, -1U, "$BID", "$VERSION", -1, 0, 0, 0, 0, _start, _stop,
};
KMOD
  "$CC" -target x86_64-apple-macos10.12 -mkernel -fno-builtin -fno-common -nostdlib -DKERNEL -I "$HDR" -c "$O/obj/kmod_info.c" -o "$O/obj/kmod_info.o"
  OBJECTS+=("$O/obj/kmod_info.o")
  "$(xcrun -f ld)" -arch x86_64 -kext -static -macos_version_min 10.12 -undefined dynamic_lookup -o "$O/$NAME.kext/Contents/MacOS/$NAME" "${OBJECTS[@]}" "$KMOD" >> "$LOGS/mtkwlan.log" 2>&1 \
    || { tail -20 "$LOGS/mtkwlan.log"; die "AirportMtkWlan link"; }
  python3 -I - "$F/AirportMtkWlan/WCL/Info.plist" "$O/$NAME.kext/Contents/Info.plist" "$VERSION" "$NAME" "$BID" <<'PYPLIST'
import sys
src, dst, ver, name, bid = sys.argv[1:6]
s = open(src).read()
for k, v in {"$(DEVELOPMENT_LANGUAGE)": "en", "$(EXECUTABLE_NAME)": name, "$(PRODUCT_BUNDLE_IDENTIFIER)": bid, "$(PRODUCT_NAME)": name,
             "$(PRODUCT_BUNDLE_PACKAGE_TYPE)": "KEXT", "$(MODULE_VERSION)": ver, "$(CURRENT_PROJECT_VERSION)": ver}.items():
    s = s.replace(k, v)
assert "$(" not in s, "a build variable is left in Info.plist"
open(dst, "w").write(s)
PYPLIST
  rm -rf "${OUT:?}/AirportMtkWlan.kext"; cp -R "$O/$NAME.kext" "$OUT/AirportMtkWlan.kext"; stamp "$OUT/AirportMtkWlan.kext"
  say "AirportMtkWlan $(sha "$OUT/AirportMtkWlan.kext/Contents/MacOS/AirportMtkWlan")"
}

stage_mtkbt() {   # the MT7920's Bluetooth patcher with USB buffers prepared read only; the Xcode Debug settings, the Info.plist of the v1.1.0 DEBUG release
  local B=$OBJ/mtkbt NAME=SimpleMtkBtPatcher BID=com.laobamac.SimpleMtkBtPatcher VERSION=1.1.0 K FLAGS
  export_tree "$SRC/SimpleMtkBtFw" "$B/src" SimpleMtkBtPatcher; K=$(mksdk)
  # the date goes into Lilu's kextVersion: this one gives the binary that ran
  local SOURCE_DATE_EPOCH; SOURCE_DATE_EPOCH=$(epoch "${MTKBT_DATE:?}"); export SOURCE_DATE_EPOCH
  rm -rf "${B:?}/obj" "${B:?}/$NAME.kext"; mkdir -p "$B/obj" "$B/$NAME.kext/Contents/MacOS"
  FLAGS=(-target x86_64-apple-macos10.12 -x c++ -std=gnu++14 -mkernel -fapple-kext -fno-rtti -fno-exceptions -fno-builtin -fno-common -nostdlib
    -fno-use-cxa-atexit -fno-asynchronous-unwind-tables -O0 -DKERNEL -DDEBUG=1 -DMODULE_VERSION=$VERSION -DPRODUCT_NAME=$NAME
    -I "$K/Headers" -I "$LILU_SDK" -I "$B/src/SimpleMtkBtPatcher" -Wno-deprecated-register -Werror=return-type)
  cat > "$B/obj/kmod_info.c" <<KMOD
#include <mach/kmod.h>
extern kern_return_t _start(kmod_info_t *, void *);
extern kern_return_t _stop(kmod_info_t *, void *);
extern kern_return_t ${NAME}_kern_start(kmod_info_t *, void *);
extern kern_return_t ${NAME}_kern_stop(kmod_info_t *, void *);
__attribute__((visibility("default"))) kmod_start_func_t *_realmain = ${NAME}_kern_start;
__attribute__((visibility("default"))) kmod_stop_func_t *_antimain = ${NAME}_kern_stop;
__attribute__((visibility("default"))) kmod_info_t kmod_info = {
	0, KMOD_INFO_VERSION, -1U, "$BID", "$VERSION", -1, 0, 0, 0, 0, _start, _stop,
};
KMOD
  { "$CXX" "${FLAGS[@]}" -c "$B/src/SimpleMtkBtPatcher/SimpleMtkBtPatcher.cpp" -o "$B/obj/patcher.o" &&
    "$CXX" "${FLAGS[@]}" -c "$LILU_SDK/Library/plugin_start.cpp" -o "$B/obj/plugin_start.o" &&
    "$CC" -target x86_64-apple-macos10.12 -mkernel -fno-builtin -fno-common -nostdlib -DKERNEL -I "$K/Headers" -c "$B/obj/kmod_info.c" -o "$B/obj/kmod_info.o" &&
    "$(xcrun -f ld)" -arch x86_64 -kext -static -macos_version_min 10.12 -undefined dynamic_lookup -o "$B/$NAME.kext/Contents/MacOS/$NAME" \
      "$B/obj/patcher.o" "$B/obj/plugin_start.o" "$B/obj/kmod_info.o" "$K/Library/x86_64/libkmod.a"; } > "$LOGS/mtkbt.log" 2>&1 \
    || { tail -20 "$LOGS/mtkbt.log"; die "SimpleMtkBtPatcher"; }
  unzip -p "$DEPS/mtkbt/SimpleMtkBtFw-1.1.0-DEBUG.zip" "$NAME.kext/Contents/Info.plist" > "$B/$NAME.kext/Contents/Info.plist" || die "the Info.plist of SimpleMtkBtFw 1.1.0"
  xcrun otool -hv "$B/$NAME.kext/Contents/MacOS/$NAME" | grep -q KEXTBUNDLE || die "SimpleMtkBtPatcher is not a kext"
  rm -rf "$OUT/$NAME.kext"; cp -R "$B/$NAME.kext" "$OUT/$NAME.kext"; stamp "$OUT/$NAME.kext"
  say "SimpleMtkBtPatcher $(sha "$OUT/$NAME.kext/Contents/MacOS/$NAME")"
}

ALL="rm nvrm nvrmfb nvaccel nvrmagdc nmhda plugin translator nvenc ngshim latsof nitrosense smcnvidiagpu whateverxe hybridpm applealc idisphda mtkwlan mtkbt"
[ $# -gt 0 ] || set -- $ALL
for s in "$@"; do
  case " $ALL " in *" $s "*) ;; *) die "no stage $s; stages: $ALL" ;; esac
  say "stage $s"; "stage_$s"
done

// CPU-only probe (ours): repeats NGShim's four ABI guards and the binary-archive check on this macOS build.
// No Metal device is created. Exit 0 = every guard passes, 1 = at least one differs.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <string.h>
static int bad;
static void check(const char *cls, size_t size, uint8_t offset, const char *encoding) {
  Class c = objc_getClass(cls);
  [c class];
  Method m = c ? class_getInstanceMethod(c, sel_registerName("_descriptorPrivate")) : NULL;
  size_t isz = c ? class_getInstanceSize(c) : 0;
  const uint8_t expected[] = {0x55,0x48,0x89,0xe5,0x48,0x8d,0x47,offset,0x5d,0xc3};
  const uint8_t *impl = m ? (const uint8_t *)method_getImplementation(m) : NULL;
  int accOk = impl && !memcmp(impl, expected, sizeof(expected));
  const char *enc = m ? method_getTypeEncoding(m) : "(none)";
  int encOk = m && !strcmp(enc, encoding);
  if (!(isz == size && accOk && encOk)) bad = 1;
  printf("%s: instanceSize 0x%zx (%s), accessor lea +0x%02x (%s), encoding (%s)\n", cls, isz, isz == size ? "ok" : "DIFF",
         offset, accOk ? "ok" : "DIFF", encOk ? "ok" : "DIFF");
  if (!encOk) printf("  actual encoding: %s\n", enc);
}
int main(void) { @autoreleasepool {
  printf("macOS %s\n", [[[NSProcessInfo processInfo] operatingSystemVersionString] UTF8String]);
  check("MTLRenderPipelineDescriptorInternal", 0x338, 0x30,
    "r^{MTLRenderPipelineDescriptorPrivate=@[8Q]QQQQcQQQQQcqqq(?=QQ)Q(?=If)QQ(?=[2I]"
    "{?=b2b2b1b2b1b1b1b1b1b1b1b1b1b1b8b3b1b4b1b1b1b1b1b1b6})IIQ@@@@@@{?=QQQ}{?=QQQ}"
    "{?=QQQ}Q@@QQ@@@@@^v^v@cI@Q@@@@@@@@QQccQQcc@IQ{?=QQQ}{?=QQQ}@qQQQQQ}16@0:8");
  check("MTLComputePipelineDescriptorInternal", 0x100, 0x10,
    "r^{MTLComputePipelineDescriptorPrivate=@@cS@@@@@(?=@@)@cqqqcQQ@cb1b1b1b29@@QcQ@Q{?=QQQ}@}16@0:8");
  check("MTLRenderPipelineColorAttachmentDescriptorInternal", 0x10, 0x08,
    "r^{MTLRenderPipelineAttachmentDescriptorPrivate=(?={?=b2b3b3b5b5b5b5b5b1b4b22}{?=Q})}16@0:8");
  check("MTLRenderPassDescriptorInternal", 0x100, 0x30,
    "r^{MTLRenderPassDescriptorPrivate=@@QQQccccQQQ(?=QQ)QQ[8{?=ff}]Q@@cqc}16@0:8");
  Method a = class_getInstanceMethod(objc_getClass("_MTLDevice"), @selector(newBinaryArchiveWithDescriptor:error:));
  const char *ae = a ? method_getTypeEncoding(a) : "(none)";
  int aOk = a && !strcmp(ae, "@32@0:8@16^@24");
  if (!aOk) bad = 1;
  printf("_MTLDevice newBinaryArchiveWithDescriptor:error: encoding %s (%s)\n", ae, aOk ? "ok" : "DIFF");
  printf("%s\n", bad ? "GUARDS DIFFER: NGShim would disable the differing translation" : "all NGShim guards pass");
  return bad; } }

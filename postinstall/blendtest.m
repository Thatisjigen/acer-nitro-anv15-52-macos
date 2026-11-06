// Read-only: build a blended render pipeline on the Intel Metal device (the path that crashes in generateBlendState).
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <stdlib.h>
int main(void) { @autoreleasepool {
  id<MTLDevice> dev = nil;
  for (id<MTLDevice> d in MTLCopyAllDevices()) if ([d.name containsString:@"Intel"]) dev = d;
  if (!dev) { printf("no Intel Metal device\n"); return 2; }
  printf("device: %s\n", dev.name.UTF8String);
  NSString *src = @"#include <metal_stdlib>\nusing namespace metal;\n"
    "vertex float4 v(uint i [[vertex_id]]) { return float4(float(i&1), float(i>>1), 0, 1); }\n"
    "fragment float4 f() { return float4(1, 0.5, 0.25, 0.5); }\n";
  NSError *err = nil;
  id<MTLLibrary> lib = [dev newLibraryWithSource:src options:nil error:&err];
  if (!lib) { printf("library failed: %s\n", err.localizedDescription.UTF8String); return 3; }
  MTLRenderPipelineDescriptor *d = [MTLRenderPipelineDescriptor new];
  d.vertexFunction = [lib newFunctionWithName:@"v"]; d.fragmentFunction = [lib newFunctionWithName:@"f"];
  d.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
  d.colorAttachments[0].blendingEnabled = YES;
  d.colorAttachments[0].sourceRGBBlendFactor = MTLBlendFactorSourceAlpha;
  d.colorAttachments[0].destinationRGBBlendFactor = MTLBlendFactorOneMinusSourceAlpha;
  id<MTLRenderPipelineState> p = [dev newRenderPipelineStateWithDescriptor:d error:&err];
  printf("blended pipeline: %s\n", p ? "ok" : err.localizedDescription.UTF8String);
  if (!p) return 1;
  MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:8 height:8 mipmapped:NO];
  td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeManaged;
  id<MTLTexture> t = [dev newTextureWithDescriptor:td];
  MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
  rp.colorAttachments[0].texture = t; rp.colorAttachments[0].loadAction = MTLLoadActionClear;
  rp.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 1); rp.colorAttachments[0].storeAction = MTLStoreActionStore;
  id<MTLCommandQueue> q = [dev newCommandQueue]; id<MTLCommandBuffer> cb = [q commandBuffer];
  id<MTLRenderCommandEncoder> e = [cb renderCommandEncoderWithDescriptor:rp];
  [e setRenderPipelineState:p]; [e drawPrimitives:MTLPrimitiveTypeTriangleStrip vertexStart:0 vertexCount:4]; [e endEncoding];
  id<MTLBlitCommandEncoder> b = [cb blitCommandEncoder]; [b synchronizeResource:t]; [b endEncoding];
  [cb commit]; [cb waitUntilCompleted];
  uint8_t px[8*8*4]; [t getBytes:px bytesPerRow:32 fromRegion:MTLRegionMake2D(0,0,8,8) mipmapLevel:0];
  int x = 6, y = 1; const uint8_t *c = px + (y*8+x)*4;   // inside the quad: NDC x,y in 0..1 is the top-right quarter
  printf("pixel BGRA = %u %u %u %u (expected about 32 64 128 for 0.5*src + 0.5*black)\n", c[0], c[1], c[2], c[3]);
  int ok = abs(c[2]-128) <= 3 && abs(c[1]-64) <= 3 && abs(c[0]-32) <= 3;
  printf("blend result: %s\n", ok ? "correct" : "WRONG");
  return ok ? 0 : 4;
}}

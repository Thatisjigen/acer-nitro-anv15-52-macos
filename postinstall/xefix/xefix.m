// xefix: three fixes for Apple's Metal driver for Tiger Lake (16.0.32), copied unchanged from libxedrv v21-v24 by JulioNectar:
// compute ordered against render and blit, working barriers in serial compute encoders, no rectangles in WindowServer's backdrop blur.
//
// ATTRIBUTION NOTICE: this file is a MODIFIED copy of part of macos/src/libxedrv.m in
// https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe at commit dabacb7, by JulioNectar, licensed under the
// Thou Shalt Not Profit License 1.0 (LICENSE-TSNPL-1.0.txt beside this file); this file is under the same license.
// Changes: only those sections are taken; the logging and the method swap are his, shortened to what they need here; the install
// at load is new. The comments in Portuguese and the measurements in them are the author's, on his Dell XPS 13 Plus 9320.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#import <objc/message.h>
#import <pthread.h>
#import <syslog.h>
#import <stdarg.h>
#import <stdint.h>
#import <stdio.h>
#import <stdlib.h>
#import <string.h>
#import <unistd.h>
#import <fcntl.h>
#import <time.h>

static void xe_log(const char* fmt, ...) __attribute__((format(printf, 1, 2)));
static void xe_log(const char* fmt, ...) {
  char b[1024]; va_list a; va_start(a, fmt); vsnprintf(b, sizeof b, fmt, a); va_end(a);
  syslog(LOG_ERR, "xefix: %s", b);
}
#define LOG(...) xe_log(__VA_ARGS__)

static IMP troca(Class k, const char* sel, IMP nova) {
  Method m = k ? class_getInstanceMethod(k, sel_registerName(sel)) : NULL;
  if (!m) { LOG("sem %s", sel); return NULL; }
  return method_setImplementation(m, nova);
}

// v21 (28/10): COMPUTE FORA DE ORDEM COM RENDER/BLIT. No driver 16.0.32 o trabalho de compute vai para outro motor e
// não espera o render/blit anterior (nem o render/blit espera o compute), no mesmo command buffer E entre command buffers
// seguidos da mesma fila; updateFence/waitForFence e MTLEvent não resolvem. Medido em ~/xe/build/edpfull/mipblit/order
// (render pesado -> compute lê dados velhos 6/6; compute escreve -> render/blit no mesmo CB lê dados velhos 6/6; com
// CB separado 1-5/6). Um par encodeSignalEvent/encodeWaitForEvent de MTLSharedEvent entre os encoders serializa os
// motores (0 falhas em 216 casos, também no início do CB seguinte).
// Correção (parte A): ao criar um encoder cuja classe (compute x render/blit) difere da do encoder anterior do mesmo
// command buffer (ou, no primeiro encoder, do último encoder da fila), insere signal+wait de um MTLSharedEvent do próprio
// command buffer (de um pool por device, devolvido quando o CB termina). XE_COMPUTE_NATIVO=1 desliga a parte A.
@interface XeEventoV21 : NSObject { @public id<MTLSharedEvent> ev; uint64_t v; } @end
@implementation XeEventoV21
- (void)dealloc { [ev release]; [super dealloc]; }
@end
@interface XeCBV21 : NSObject { @public int ultima; XeEventoV21* e; } @end
@implementation XeCBV21
- (void)dealloc { [e release]; [super dealloc]; }
@end
@interface XeFilaV21 : NSObject { @public volatile int ultima; } @end
@implementation XeFilaV21
@end
static IMP g_ce, g_ce_dt, g_re, g_pre, g_be; static long g_ord_n; static int g_ord_off = -1;
static const void* kXeCB21 = &kXeCB21, *kXeFila21 = &kXeFila21, *kXePool21 = &kXePool21;
static pthread_mutex_t g_ordm = PTHREAD_MUTEX_INITIALIZER;
static XeEventoV21* xe_ev_get(id<MTLDevice> dev) {
  XeEventoV21* x = nil;
  pthread_mutex_lock(&g_ordm);
  NSMutableArray* pool = objc_getAssociatedObject(dev, kXePool21);
  if (!pool) { pool = [NSMutableArray array]; objc_setAssociatedObject(dev, kXePool21, pool, OBJC_ASSOCIATION_RETAIN); }
  if (pool.count) { x = [[pool lastObject] retain]; [pool removeLastObject]; }
  pthread_mutex_unlock(&g_ordm);
  if (!x) { x = [XeEventoV21 new]; x->ev = [dev newSharedEvent]; if (!x->ev) { [x release]; return nil; } }
  return x;   // +1
}
static void xe_ev_put(id<MTLDevice> dev, XeEventoV21* x) {
  pthread_mutex_lock(&g_ordm);
  NSMutableArray* pool = objc_getAssociatedObject(dev, kXePool21);
  if (pool && pool.count < 16) [pool addObject:x];
  pthread_mutex_unlock(&g_ordm);
}
// classe: 0 = render/blit (motor 3D), 1 = compute
static void xe_ordem(id cb, int classe) {
  if (g_ord_off) return;
  XeCBV21* st = objc_getAssociatedObject(cb, kXeCB21);
  if (!st) { st = [XeCBV21 new]; st->ultima = -1; objc_setAssociatedObject(cb, kXeCB21, st, OBJC_ASSOCIATION_RETAIN); [st release]; }
  id<MTLCommandQueue> q = [cb commandQueue];
  XeFilaV21* fq = q ? objc_getAssociatedObject(q, kXeFila21) : nil;
  if (q && !fq) { fq = [XeFilaV21 new]; fq->ultima = -1; objc_setAssociatedObject(q, kXeFila21, fq, OBJC_ASSOCIATION_RETAIN); [fq release]; }
  int ant = st->ultima >= 0 ? st->ultima : fq ? fq->ultima : -1;
  st->ultima = classe; if (fq) fq->ultima = classe;
  if (ant < 0 || ant == classe) return;
  id<MTLDevice> dev = [cb device];
  if (!st->e) {
    st->e = xe_ev_get(dev); if (!st->e) return;
    XeEventoV21* x = st->e;
    [cb addCompletedHandler:^(id<MTLCommandBuffer> c) { xe_ev_put(dev, x); }];
  }
  st->e->v++;
  [cb encodeSignalEvent:st->e->ev value:st->e->v];
  [cb encodeWaitForEvent:st->e->ev value:st->e->v];
  long n = __sync_add_and_fetch(&g_ord_n, 1);
  if (n <= 4 || (n & (n - 1)) == 0) LOG("ORDEM %s -> %s: barreira por MTLSharedEvent no command buffer (n=%ld)", ant ? "compute" : "render/blit",
      classe ? "compute" : "render/blit", n);
}
// v21 (parte B): BARREIRA DE COMPUTE INEFICAZ EM ENCODER SERIAL. No driver 16.0.32 o encoder serial (o padrão) ignora
// memoryBarrierWithScope:/WithResources: (ChalContext::ChalAddMemoryBarrier, driver+0x32d20, só age com
// isConcurrentDispatch) e ainda avisa o Metal do Tahoe, que zera o rastreamento de hazards -> o dispatch seguinte lê
// dados velhos (mipblit/cc: 2/30). Com recursos untracked (heaps do MPS/Core Image) o flush que o encoder serial põe
// depois de cada dispatch não basta (mipblit/ccheap: 3/30; MPSImageGaussianBlur errado ~1/150, CIGaussianBlur na GPU
// diferente do software ~13/90). No modo concorrente a barreira vira PIPE_CONTROL antes do dispatch e funciona (0/30).
// Correção: todo encoder de compute serial nasce concorrente e recebe uma barreira do próprio driver antes de cada
// dispatch a partir do segundo; dispatchType continua respondendo "serial". XE_BARREIRA_NATIVA=1 desliga a parte B.
@interface XeSerialV21 : NSObject { @public long n; } @end
@implementation XeSerialV21
@end
static IMP g_dt_q, g_disp_t, g_disp_tg, g_disp_ind, g_mb_scope; static int g_bar_off = -1; static long g_bar_n;
static const void* kXeSerial21 = &kXeSerial21;
static id xe_serial_emulado(id cb) {
  id e = ((id(*)(id, SEL, NSUInteger))g_ce_dt)(cb, sel_registerName("computeCommandEncoderWithDispatchType:"), MTLDispatchTypeConcurrent);
  if (e) { XeSerialV21* x = [XeSerialV21 new]; objc_setAssociatedObject(e, kXeSerial21, x, OBJC_ASSOCIATION_RETAIN); [x release]; }
  return e;
}
static void xe_antes_dispatch(id e) {
  XeSerialV21* x = objc_getAssociatedObject(e, kXeSerial21);
  if (!x || x->n++ == 0) return;
  ((void(*)(id, SEL, NSUInteger))g_mb_scope)(e, sel_registerName("memoryBarrierWithScope:"), MTLBarrierScopeBuffers | MTLBarrierScopeTextures);
  long k = __sync_add_and_fetch(&g_bar_n, 1);
  if (k <= 2 || (k & (k - 1)) == 0) LOG("BARREIRA serial emulada antes do dispatch %ld do encoder (n=%ld)", x->n, k);
}
static NSUInteger w_dt_q(id s, SEL c) { return objc_getAssociatedObject(s, kXeSerial21) ? MTLDispatchTypeSerial : ((NSUInteger(*)(id, SEL))g_dt_q)(s, c); }
static void w_disp_t(id s, SEL c, MTLSize a, MTLSize b) { xe_antes_dispatch(s); ((void(*)(id, SEL, MTLSize, MTLSize))g_disp_t)(s, c, a, b); }
static void w_disp_tg(id s, SEL c, MTLSize a, MTLSize b) { xe_antes_dispatch(s); ((void(*)(id, SEL, MTLSize, MTLSize))g_disp_tg)(s, c, a, b); }
static void w_disp_ind(id s, SEL c, id buf, NSUInteger off, MTLSize b) { xe_antes_dispatch(s); ((void(*)(id, SEL, id, NSUInteger, MTLSize))g_disp_ind)(s, c, buf, off, b); }
static id w_ce(id s, SEL c) { xe_ordem(s, 1); if (!g_bar_off) return xe_serial_emulado(s); return ((id(*)(id, SEL))g_ce)(s, c); }
static id w_ce_dt(id s, SEL c, NSUInteger t) {
  xe_ordem(s, 1);
  if (!g_bar_off && t == MTLDispatchTypeSerial) return xe_serial_emulado(s);
  return ((id(*)(id, SEL, NSUInteger))g_ce_dt)(s, c, t); }
static id w_re(id s, SEL c, id d) { xe_ordem(s, 0); return ((id(*)(id, SEL, id))g_re)(s, c, d); }
static id w_pre(id s, SEL c, id d) { xe_ordem(s, 0); return ((id(*)(id, SEL, id))g_pre)(s, c, d); }
static id w_be(id s, SEL c) { xe_ordem(s, 0); return ((id(*)(id, SEL))g_be)(s, c); }
static void install_ordem(void) {
  if (g_ord_off < 0) g_ord_off = getenv("XE_COMPUTE_NATIVO") != NULL;
  if (g_bar_off < 0) g_bar_off = getenv("XE_BARREIRA_NATIVA") != NULL;
  if (g_ord_off && g_bar_off) { LOG("compute: ordem e barreira nativas (XE_COMPUTE_NATIVO, XE_BARREIRA_NATIVA)"); g_ce = (IMP)1; return; }
  Class k = objc_getClass("MTLIGAccelCommandBuffer"), ce = objc_getClass("MTLIGAccelComputeCommandEncoder");
  if (!k || !ce) return;
  static int done; if (done) return; done = 1;
  if (!g_bar_off) {   // parte B: precisa do memoryBarrierWithScope: original e de todos os dispatches
    Method mb = class_getInstanceMethod(ce, sel_registerName("memoryBarrierWithScope:"));
    g_mb_scope = mb ? method_getImplementation(mb) : NULL;
    if (g_mb_scope) {
      g_dt_q = troca(ce, "dispatchType", (IMP)w_dt_q);
      g_disp_t = troca(ce, "dispatchThreads:threadsPerThreadgroup:", (IMP)w_disp_t);
      g_disp_tg = troca(ce, "dispatchThreadgroups:threadsPerThreadgroup:", (IMP)w_disp_tg);
      g_disp_ind = troca(ce, "dispatchThreadgroupsWithIndirectBuffer:indirectBufferOffset:threadsPerThreadgroup:", (IMP)w_disp_ind);
    }
    if (!g_mb_scope || !g_dt_q || !g_disp_t || !g_disp_tg || !g_disp_ind) { LOG("barreira serial: métodos faltando, parte B desligada"); g_bar_off = 1; }
  }
  g_ce_dt = troca(k, "computeCommandEncoderWithDispatchType:", (IMP)w_ce_dt);
  if (!g_ce_dt) g_bar_off = 1;   // sem o criador com tipo não há como nascer concorrente
  g_ce = troca(k, "computeCommandEncoder", (IMP)w_ce);
  if (!g_ord_off) {
    g_re = troca(k, "renderCommandEncoderWithDescriptor:", (IMP)w_re);
    g_pre = troca(k, "parallelRenderCommandEncoderWithDescriptor:", (IMP)w_pre);
    g_be = troca(k, "blitCommandEncoder", (IMP)w_be);
    if (!g_ce || !g_ce_dt || !g_re || !g_be) LOG("ordem compute/render: métodos faltando (ce=%d cedt=%d re=%d be=%d)", !!g_ce, !!g_ce_dt, !!g_re, !!g_be);
  }
  LOG("compute: ordem com render/blit=%s, barreira serial emulada=%s (ce=%d cedt=%d re=%d pre=%d be=%d)", g_ord_off ? "nativa" : "ligada",
      g_bar_off ? "nativa" : "ligada", !!g_ce, !!g_ce_dt, !!g_re, !!g_pre, !!g_be);
  if (!g_ce) g_ce = (IMP)1;   // sem o método: não tentar de novo
}

// v23 (29/10): RETÂNGULOS NO DESFOQUE DO WINDOWSERVER. Nas atualizações parciais do fundo desfocado (blur de janela,
// backdrop-filter de WebKit, NSVisualEffectView), o CoreAnimation monta uma cópia do fundo atrás da janela (textura
// não-IOSurface, loadAction=Load) e pinta faixas com o pipeline "PBGRAXb_Xhf" que saem (0,0,0,0) neste driver; o
// desfoque de 27 amostras espalha essas faixas e aparecem retângulos com desfoque diferente em volta do hover.
// Medido no laboratório (v22, flag X): 35/24 quadros com glitch em 10 s -> 0/2 ao pular esses desenhos (a faixa fica com
// o conteúdo anterior, que é o fundo certo). Só no WindowServer. XE_XHF_NATIVO=1 desliga.
static IMP g_xf_re, g_xf_ps, g_xf_di; static volatile int g_xf_off;
static const void* kXfEnc = &kXfEnc;
static id w_xf_re(id s, SEL c, MTLRenderPassDescriptor* d) {
  id enc = ((id(*)(id, SEL, id))g_xf_re)(s, c, d);
  MTLRenderPassColorAttachmentDescriptor* a = d.colorAttachments[0];
  if (enc && !g_xf_off && a.texture && !a.texture.iosurface && a.loadAction == MTLLoadActionLoad) objc_setAssociatedObject(enc, kXfEnc, @1, OBJC_ASSOCIATION_RETAIN);
  return enc;
}
static void w_xf_ps(id s, SEL c, id<MTLRenderPipelineState> p) {
  if (!g_xf_off && objc_getAssociatedObject(s, kXfEnc)) objc_setAssociatedObject(s, kXfEnc, [p.label isEqualToString:@"com.apple.coreanimation.PBGRAXb_Xhf"] ? @2 : @1, OBJC_ASSOCIATION_RETAIN);
  ((void(*)(id, SEL, id))g_xf_ps)(s, c, p);
}
static void w_xf_di(id s, SEL c, MTLPrimitiveType t, NSUInteger n, MTLIndexType it, id b, NSUInteger off) {
  NSNumber* m = g_xf_off ? nil : objc_getAssociatedObject(s, kXfEnc);
  if (m && m.intValue == 2) { static long k; if (++k <= 2 || !(k & (k - 1))) LOG("v23: faixa Xhf da cópia do fundo pulada (n=%ld)", k); return; }
  ((void(*)(id, SEL, MTLPrimitiveType, NSUInteger, MTLIndexType, id, NSUInteger))g_xf_di)(s, c, t, n, it, b, off);
}
static void install_xhf(void) {
  static int done; if (done || strcmp(getprogname(), "WindowServer") || getenv("XE_XHF_NATIVO")) return;
  Class cb = objc_getClass("MTLIGAccelCommandBuffer"), re = objc_getClass("MTLIGAccelRenderCommandEncoder");
  if (!cb || !re) return;
  done = 1;
  g_xf_re = troca(cb, "renderCommandEncoderWithDescriptor:", (IMP)w_xf_re);
  g_xf_ps = troca(re, "setRenderPipelineState:", (IMP)w_xf_ps);
  g_xf_di = troca(re, "drawIndexedPrimitives:indexCount:indexType:indexBuffer:indexBufferOffset:", (IMP)w_xf_di);
  LOG("v23: correção do desfoque instalada (re=%d ps=%d di=%d)", !!g_xf_re, !!g_xf_ps, !!g_xf_di);
}

// v24 (29/10): CHAVES AO VIVO para medir custo sem reiniciar. /private/var/tmp/xedrv.off (lido 1x/s em cada processo):
// 'o' = sem ordem compute/render (v21 A), 'b' = sem barreira serial emulada (v21 B, vale para encoders novos),
// 'x' = sem a correção do desfoque (v23). Arquivo ausente = tudo ligado. As variáveis de ambiente continuam valendo.
static int g_env_ord, g_env_bar;
static void install_chaves(void) {
  static int done; if (done) return; done = 1;
  g_env_ord = g_ord_off > 0; g_env_bar = g_bar_off > 0;
  dispatch_source_t t = dispatch_source_create(DISPATCH_SOURCE_TYPE_TIMER, 0, 0, dispatch_get_global_queue(QOS_CLASS_UTILITY, 0));
  dispatch_source_set_timer(t, dispatch_time(DISPATCH_TIME_NOW, NSEC_PER_SEC), NSEC_PER_SEC, NSEC_PER_SEC / 4);
  dispatch_source_set_event_handler(t, ^{
    char b[16] = {0}; int fd = open("/private/var/tmp/xedrv.off", O_RDONLY);
    if (fd >= 0) { read(fd, b, sizeof b - 1); close(fd); }
    int o = g_env_ord || strchr(b, 'o') != NULL, ba = g_env_bar || strchr(b, 'b') != NULL, x = strchr(b, 'x') != NULL;
    if (g_ce != (IMP)1 && (o != g_ord_off || ba != g_bar_off)) { LOG("v24: ordem compute %s, barreira serial %s", o ? "DESLIGADA" : "ligada", ba ? "DESLIGADA" : "ligada"); g_ord_off = o; g_bar_off = ba; }
    if (x != g_xf_off) { if (g_xf_re) LOG("v24: correção do desfoque %s", x ? "DESLIGADA" : "ligada"); g_xf_off = x; }
  });
  dispatch_resume(t);
}

// The driver's classes exist only once its image has loaded, after this library: try until they do.
static void* late(void* a) {
  for (int t = 0; t < 20000 && !(g_ce && (g_xf_re || strcmp(getprogname(), "WindowServer") || getenv("XE_XHF_NATIVO"))); t++) {
    if (!g_ce && objc_getClass("MTLIGAccelCommandBuffer")) install_ordem();
    if (!g_xf_re) install_xhf();
    if (!g_ce || !g_xf_re) usleep(500);
  }
  return NULL;
}

__attribute__((constructor)) static void xefix_load(void) {
  install_chaves();
  pthread_t th; pthread_create(&th, NULL, late, NULL); pthread_detach(th);
}

/* Offline register-stream adapter for the GPL-2.0-or-later P.E.Op.S./PCSX
 * rearmed SPU renderer. No game code is compiled into this program.
 * Input: 512 KiB SPU RAM, then native little-endian uint32 triples
 * (sample clock, register offset, value). Output: raw 44100 Hz stereo PCM16.
 */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include "spu.h"
#include "spu_config.h"
#include "out.h"
#include "externals.h"
static FILE *output;
static void finish(void){}
static int busy(void){return 0;}
static void feed(void *data,int bytes){fwrite(data,1,bytes,output);}
static struct out_driver driver={"offline",NULL,finish,busy,feed};
struct out_driver *out_current=&driver;
void SetupSound(void){}
static void irq(int n){(void)n;}
static void schedule(unsigned int n){(void)n;}
long DoFreeze(int a,struct SPUFreeze*b,unsigned short**c,void*d,unsigned int e){return 0;}
int main(int argc,char **argv){
 if(argc!=5)return 2;
 FILE *ram=fopen(argv[1],"rb"),*commands=fopen(argv[2],"rb");output=fopen(argv[3],"wb");
 if(!ram||!commands||!output)return 3;
 spu_config.iVolume=1024;spu_config.iUseInterpolation=2;spu_config.iUseReverb=1;
 SPUinit();SPUopen();SPUregisterCallback(irq);SPUregisterScheduleCb(schedule);
 if(fread(spu.spuMemC,1,512*1024,ram)!=512*1024)return 4;fclose(ram);
 uint32_t event[3];unsigned int clock=0;
 while(fread(event,sizeof(event),1,commands)==1){
  while(clock<event[0]){unsigned int next=clock+256;if(next>event[0])next=event[0];clock=next;SPUasync(clock*768,1);}
  SPUwriteRegister(0x1f801c00+event[1],event[2],clock*768);
 }
 const unsigned int end=(unsigned int)strtoul(argv[4],NULL,10);
 while(clock<end){unsigned int next=clock+256;if(next>end)next=end;clock=next;SPUasync(clock*768,1);}
 SPUshutdown();fclose(commands);fclose(output);return 0;
}

#include "fx_blocks.hpp"
#include <cassert>
#include <cstring>

// Memory-only test entry. One 32-byte configuration per eight input frames.
extern "C" void pitch_quality_run(float* l,float* r,unsigned frames,const uint8_t* controls){
 assert(frames%8==0);
 mpp::fx::Engine engine;
 std::memset(&engine,0xa5,sizeof(engine));
 engine.reset();
 for(unsigned i=0;i<frames;i+=8){
  const auto* config=controls+4*i;
  assert(mpp::fx::valid(config));
  engine.process(config,l+i,r+i,8);
 }
}
extern "C" unsigned pitch_quality_engine_bytes(){return sizeof(mpp::fx::Engine);}

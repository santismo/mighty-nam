#include "startup_memory.hpp"
namespace mpp::board {
void initialize_data(const unsigned char* load,unsigned char* data,unsigned n,unsigned char* zero,unsigned nz) {
 for(unsigned i=0;i<n;++i)data[i]=load[i];
 for(unsigned i=0;i<nz;++i)zero[i]=0;
}
}

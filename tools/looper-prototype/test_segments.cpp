// MIT (c) 2026 santismo. File/memory only; ASan/UBSan, no audio devices.
#include "ima_adpcm.hpp"
#include "layout.hpp"
#include <vector>
#include <cassert>
#include <algorithm>
#include <cstdio>
using namespace mighty_loop;
int main() {
    constexpr unsigned frames=720000,n=layout::first_bytes,m=layout::second_bytes;
    std::vector<uint8_t> first(n+64,0xa5),second(m+64,0x5a),flat(n+m,0);
    std::fill(first.begin()+32,first.end()-32,0);std::fill(second.begin()+32,second.end()-32,0);
    AdpcmStore split(first.data()+32,n,second.data()+32,m,frames);
    AdpcmStore reference(flat.data(),flat.size(),frames);
    unsigned random=17;
    for(unsigned i=0;i<frames;++i){random=random*1664525+1013904223;
        const auto sample=int16_t(random>>16);assert(split.append(sample));assert(reference.append(sample));}
    assert(!split.append(1) && !reference.append(1));
    assert(std::equal(flat.begin(),flat.begin()+n,first.begin()+32));
    assert(std::equal(flat.begin()+n,flat.end(),second.begin()+32));
    for(unsigned i=0;i<frames*3;++i)assert(split.next()==reference.next());
    for(unsigned i=0;i<32;++i){assert(first[i]==0xa5 && first[n+32+i]==0xa5);
        assert(second[i]==0x5a && second[m+32+i]==0x5a);}
    assert(!split.failed);
    assert(!AdpcmStore(first.data(),n-1,second.data(),m,frames).capacity);
    assert(!AdpcmStore(first.data(),n,second.data(),m-1,frames).capacity);
    assert(!AdpcmStore(nullptr,n,second.data(),m,frames).capacity);
    assert(!AdpcmStore(first.data(),n,nullptr,m,frames).capacity);
    assert(!AdpcmStore(first.data(),n,second.data(),m,0xffffffff).capacity);
    // A bad header exactly at the segment boundary fails closed.
    split.cursor=2048*256;second[34]=89;assert(split.next()==0 && split.failed);
    std::puts("PASS segmented 30s encode, 90s decode, exact parity, guards and invalid bounds");
}

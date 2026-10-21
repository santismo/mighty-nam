#include "cut_eq.hpp"
namespace {mpp::cut::Engine engine;uint32_t previous_route;
uint32_t read(uintptr_t at){return *(volatile uint32_t*)at;}}
extern "C" void mpp_cut_eq_init(){engine.reset();previous_route=0;}
extern "C" void mpp_cut_eq_process(const float* l,const float* r,float* ol,float* orr){
 const auto* p=(const volatile uint8_t*)(uintptr_t)read(0x20005ad0);
 if((p[4]&63)!=4){mpp_cut_eq_init();((void(*)(const float*,const float*,float*,float*))0x1307f)(l,r,ol,orr);return;}
 uint32_t route=1;for(unsigned i=90;i<99;++i)route=route*31+p[i];
 if(route!=previous_route){engine.reset();previous_route=route;}
 engine.process(!(p[4]&64),p[36],p[37],l,r,ol,orr,8);
}

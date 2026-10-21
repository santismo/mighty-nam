// Offline impulse/phase audit of the actual cut EQ. No audio or device APIs.
#include "../target/link/cut_eq.hpp"
#include <cassert>
#include <cmath>
#include <complex>
#include <cstdio>
#include <vector>
using Complex = std::complex<double>;
constexpr double pi = 3.14159265358979323846, fs = 48000;

static Complex response(const std::vector<float>& impulse, double hz) {
    Complex out = 0;
    for (unsigned i = 0; i < impulse.size(); ++i)
        out += double(impulse[i]) * std::polar(1., -2*pi*hz*i/fs);
    return out;
}
static Complex reference(double hz, unsigned low, unsigned high) {
    Complex h = 1, z = std::polar(1., -2*pi*hz/fs);
    for (unsigned index = 0; index < 2; ++index) {
        unsigned value = index ? high : low;
        if (!value) continue;
        double g = std::tan(pi*mpp::cut::frequency(value, index != 0)/fs);
        double norm = 1/(1+std::sqrt(2.)*g+g*g);
        double b0 = (index ? g*g : 1)*norm;
        double b1 = (index ? 2 : -2)*b0;
        double a1 = 2*(g*g-1)*norm, a2 = (1-std::sqrt(2.)*g+g*g)*norm;
        h *= (b0+b1*z+b0*z*z)/(1.+a1*z+a2*z*z);
    }
    return h;
}
int main() {
    std::printf("{\"status\":\"PASS_OFFLINE_CUT_EQ_PHASE_AUDIT\",\"sample_rate_hz\":48000,\"cases\":[");
    for (unsigned mode = 0; mode < 4; ++mode) {
        // Latest reported Green values: low 35 ~= 77 Hz, high 70 ~= 8.07 kHz.
        unsigned lo = mode == 1 || mode == 3 ? 35 : 0;
        unsigned hi = mode == 2 || mode == 3 ? 70 : 0;
        mpp::cut::Engine e; e.reset();
        float zero[8]{}, left[8]{}, right[8]{};
        for (unsigned i = 0; i < 64; ++i) e.process(true,lo,hi,zero,zero,left,right,8);
        std::vector<float> impulse;
        for (unsigned block = 0; block < 1024; ++block) {
            float input[8]{}; if (!block) input[0] = .25f;
            e.process(true,lo,hi,input,input,left,right,8);
            for (unsigned i = 0; i < 8; ++i) {
                assert(std::isfinite(left[i]) && left[i] == right[i]);
                impulse.push_back(left[i]*4);
            }
        }
        assert(std::abs(impulse[0]) > 1e-6); // Immediate response; no whole-block queue.
        if (!mode) {
            assert(impulse[0] == 1);
            for (unsigned i = 1; i < impulse.size(); ++i) assert(impulse[i] == 0);
        }
        std::printf("%s{\"low_cut\":%u,\"high_cut\":%u,\"first_response_sample\":0,\"frequencies\":[",mode?",":"",lo,hi);
        bool first = true;
        for (double hz : {82.4069,110.,329.6276,1000.,5000.}) {
            const double df = .5;
            Complex h = response(impulse,hz), ref = reference(hz,lo,hi);
            assert(std::abs(h-ref) < 2e-5);
            double delay = -std::arg(response(impulse,hz+df)*std::conj(response(impulse,hz-df)))/(4*pi*df)*1000;
            double expected = -std::arg(reference(hz+df,lo,hi)*std::conj(reference(hz-df,lo,hi)))/(4*pi*df)*1000;
            assert(std::abs(delay-expected) < .005);
            std::printf("%s{\"hz\":%.4f,\"gain_db\":%.6f,\"group_delay_ms\":%.6f}",first?"":",",hz,20*std::log10(std::abs(h)),delay);
            first = false;
        }
        std::printf("]}");
    }
    std::printf("],\"reference\":\"Independent bilinear Butterworth response\",\"physical_latency_measured\":false,\"host_audio_access\":false,\"device_access\":false,\"meaning\":\"Frequency-dependent filter group delay, not a uniform added delay or measured headphone latency\"}\n");
}

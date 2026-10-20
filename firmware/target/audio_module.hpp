#pragma once
// Board-independent module, NOT a boot entry point or complete firmware.
// Initialize outside the audio callback. Single processing thread only.
extern "C" bool mpp_audio_initialize();
extern "C" bool mpp_audio_process(const float* input, float* output, unsigned frames);

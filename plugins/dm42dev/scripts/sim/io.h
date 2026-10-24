// Host-side services for dm42sim; see io.cc.
#ifndef DM42SIM_IO_H
#define DM42SIM_IO_H

#include <vector>

// Writes a w x h monochrome image (one byte per pixel, nonzero = lit) as a PNG,
// each pixel enlarged to scale x scale. Returns false on any I/O failure.
bool write_png(const char *path, int w, int h, const std::vector<unsigned char> &on, int scale);

#endif

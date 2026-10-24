// Host-side services for dm42sim that must not see the core's headers: with
// ARM defined, core_helpers.h turns FILE into int and routes stdio through the
// statefile_* functions that DMCP provides on the calculator. Here they wrap
// stdio. Also a dependency-free PNG writer for screen snapshots.
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

#include "io.h"

extern "C" {
int statefile_read(void *ptr, size_t size, size_t nmemb, int *stream) {
    return (int) fread(ptr, size, nmemb, (FILE *) stream);
}
int statefile_write(const void *ptr, size_t size, size_t nmemb, int *stream) {
    return (int) fwrite(ptr, size, nmemb, (FILE *) stream);
}
int *statefile_open(const char *pathname, const char *mode) {
    return (int *) fopen(pathname, mode);
}
int statefile_close(int *stream) {
    return fclose((FILE *) stream);
}
int statefile_seek(int *stream, long offset, int whence) {
    return fseek((FILE *) stream, offset, whence);
}
int statefile_getc(int *stream) {
    return fgetc((FILE *) stream);
}
int statefile_ungetc(int c, int *stream) {
    return ungetc(c, (FILE *) stream);
}
long statefile_tell(int *stream) {
    return ftell((FILE *) stream);
}
int statefile_putc(int c, int *stream) {
    return fputc(c, (FILE *) stream);
}
}

static uint32_t crc_table[256];

static uint32_t crc32(const unsigned char *p, size_t n, uint32_t c = 0xffffffffu) {
    if (crc_table[1] == 0)
        for (uint32_t i = 0; i < 256; i++) {
            uint32_t v = i;
            for (int k = 0; k < 8; k++)
                v = v & 1 ? 0xedb88320u ^ (v >> 1) : v >> 1;
            crc_table[i] = v;
        }
    for (size_t i = 0; i < n; i++)
        c = crc_table[(c ^ p[i]) & 0xff] ^ (c >> 8);
    return c;
}

static void put32(std::string &s, uint32_t v) {
    for (int i = 3; i >= 0; i--)
        s += (char) ((v >> (8 * i)) & 0xff);
}

static void chunk(std::string &out, const char *type, const std::string &data) {
    put32(out, (uint32_t) data.size());
    std::string body = std::string(type, 4) + data;
    out += body;
    put32(out, crc32((const unsigned char *) body.data(), body.size()) ^ 0xffffffffu);
}

bool write_png(const char *path, int w, int h, const std::vector<unsigned char> &on, int scale) {
    // 8-bit greyscale, lit pixels black on white like the LCD; deflate "stored" blocks.
    int W = w * scale, H = h * scale;
    std::string raw;
    raw.reserve((size_t) (W + 1) * H);
    for (int y = 0; y < H; y++) {
        raw += '\0';
        for (int x = 0; x < W; x++)
            raw += on[(size_t) (y / scale) * w + x / scale] ? '\0' : '\xff';
    }
    std::string z = "\x78\x01";
    uint32_t a = 1, b = 0;
    for (unsigned char c : raw) {
        a = (a + c) % 65521;
        b = (b + a) % 65521;
    }
    for (size_t pos = 0; pos < raw.size() || pos == 0;) {
        size_t n = raw.size() - pos < 65535 ? raw.size() - pos : 65535;
        z += (char) (pos + n == raw.size() ? 1 : 0);
        z += (char) (n & 0xff);
        z += (char) (n >> 8);
        z += (char) (~n & 0xff);
        z += (char) ((~n >> 8) & 0xff);
        z.append(raw, pos, n);
        pos += n;
        if (n == 0)
            break;
    }
    put32(z, (b << 16) | a);
    std::string ihdr;
    put32(ihdr, (uint32_t) W);
    put32(ihdr, (uint32_t) H);
    ihdr += std::string("\x08\x00\x00\x00\x00", 5);
    std::string png = "\x89PNG\r\n\x1a\n";
    chunk(png, "IHDR", ihdr);
    chunk(png, "IDAT", z);
    chunk(png, "IEND", "");
    FILE *f = fopen(path, "wb");
    if (f == NULL)
        return false;
    bool ok = fwrite(png.data(), 1, png.size(), f) == png.size();
    return fclose(f) == 0 && ok;
}

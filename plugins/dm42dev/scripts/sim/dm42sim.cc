// dm42sim: headless SwissMicros DM42/DM42n emulator for scripted testing.
//
// The calculator is SwissMicros' Free42 core (github.com/swissmicros/free42),
// compiled as for the device (ARM defined, DM42_OLDHW not: the DM42n build), so
// its DM42 extensions are live: the virtual variables GrMod, RefLCD, ResX, ResY,
// DevID and Vbat, the 200x120 and 400x240 graphics modes, and WIDTH/HEIGHT
// following GrMod. What DM42PGM (github.com/swissmicros/DM42PGM, dm/dm42_fns.cc)
// adds on DMCP is re-implemented headless where it changes what a program sees:
// the display hooks, and the rule that keys 1-6 keep their own functions while a
// menu shows, F1-F6 being the menu keys. DMCP itself (system menus, files, LCD
// refresh timing, speed, power) is out of scope.
//
//   dm42sim run [ACTIONS|-]    run an action script; JSON lines out
//   dm42sim compile IN OUT.raw program text (or .raw) to .raw, as txt2raw does
//   dm42sim decode IN.raw      .raw to program text on stdout, as raw2txt does
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <regex>
#include <sstream>
#include <string>
#include <vector>

#include "core_aux.h"
#include "core_globals.h"
#include "core_main.h"
#include "core_variables.h"
#include "io.h"
#include "shell.h"
#include "shell_spool.h"

int vartype2string(const vartype *v, char *buf, int buflen, int max_mant_digits = 12);

static const int LCD_W = 400, LCD_H = 240, DISP_BYTES = 17 * 16;
static std::vector<unsigned char> lcd(LCD_W *LCD_H);  // DMCP LCD, as drawn in GrMod 2 and 3
static std::vector<unsigned char> old(131 * 16);      // the core's own 131x16 display
static int is_graphics = 0;  // as in DM42PGM: 0 text, 1 classic graphics, 2/3 hi-res graphics
static char tlcd[2][23];
static std::string menu_label[6], edit_line, last_message;
static bool menu_hl[6];
static std::vector<char> disp_back(DISP_BYTES);
static bool disp_back_restore = false;

static long long steps = 0, action_start = 0, step_cap = 1000000000LL;
static bool capped = false, timeout3_pending = false, squeaked = false;
static long long draws = 0;
static double vbat = 3.0;
static int devid = 0;

// ---------------------------------------------------------------- JSON output

static std::string jstr(const std::string &s) {
    std::string o = "\"";
    for (unsigned char c : s) {
        if (c == '"' || c == '\\')
            o += '\\', o += (char) c;
        else if (c == '\n')
            o += "\\n";
        else if (c < 0x20) {
            char b[8];
            snprintf(b, sizeof b, "\\u%04x", c);
            o += b;
        } else
            o += (char) c;
    }
    return o + "\"";
}

static std::string hp_text(const char *s, int len) {
    std::vector<char> buf(5 * len + 1);
    int n = hp2ascii(buf.data(), s, len);
    return std::string(buf.data(), n);
}

static std::string value_text(const vartype *v) {
    if (v == NULL)
        return "";
    // Full precision whatever the calculator's settings: ALL mode, a period as
    // radix mark, no digit separators, and E for the exponent sign.
    char fix = flags.f.fix_or_all, eng = flags.f.eng_or_all;
    char dp = flags.f.decimal_point, sep = flags.f.thousands_separators;
    flags.f.fix_or_all = flags.f.eng_or_all = 1;
    flags.f.decimal_point = 1;
    flags.f.thousands_separators = 0;
    char buf[200];
    int n = vartype2string(v, buf, sizeof buf, 34);
    flags.f.fix_or_all = fix;
    flags.f.eng_or_all = eng;
    flags.f.decimal_point = dp;
    flags.f.thousands_separators = sep;
    std::string t = hp_text(buf, n);
    for (size_t i; (i = t.find("\xe1\xb4\x87")) != std::string::npos;)
        t.replace(i, 3, "E");
    return t;
}

// UTF-8 text split into characters, each passed whole to the core.
static std::vector<std::string> utf8_chars(const std::string &s) {
    std::vector<std::string> out;
    for (size_t i = 0; i < s.size();) {
        size_t n = 1;
        unsigned char c = s[i];
        if (c >= 0xf0)
            n = 4;
        else if (c >= 0xe0)
            n = 3;
        else if (c >= 0xc0)
            n = 2;
        out.push_back(s.substr(i, n));
        i += n;
    }
    return out;
}

// ------------------------------------------------------------ display hooks

static void lcd_clear() {
    std::fill(lcd.begin(), lcd.end(), 0);
}

static void old_from_core() {
    const char *bits = core_display_buffer();
    for (int r = 0; r < 16; r++)
        for (int c = 0; c < 131; c++)
            old[(size_t) r * 131 + c] = (bits[r * 17 + (c >> 3)] >> (c & 7)) & 1;
}

static void lcd_op(int x, int y, int mode, bool on) {
    if (x < 0 || x >= LCD_W || y < 0 || y >= LCD_H)
        return;
    unsigned char &p = lcd[(size_t) y * LCD_W + x];
    switch (mode) {
        case 0: p |= on; break;    // OR
        case 1: p = on; break;     // copy
        case 2: p &= !on; break;   // AND NOT
        case 3: p ^= on; break;    // XOR
    }
}

static void clear_tlcd_row(int row) {
    memset(tlcd[row], ' ', 22);
    tlcd[row][22] = 0;
    edit_line.clear();
    if (is_graphics > 1)
        lcd_clear();
}

void thell_draw_pixel(int x, int y) {
    draws++;
    int gm = graphics_mode();
    if (!gm) {
        is_graphics = 1;
        return;
    }
    if (!is_graphics)
        lcd_clear();
    is_graphics = gm;
    int s = gm == 2 ? 2 : gm == 3 ? 1 : 0;
    for (int dy = 0; dy < s; dy++)
        for (int dx = 0; dx < s; dx++)
            lcd_op(x * s + dx, y * s + dy, 0, true);
}

void thell_draw_pattern(int x, int y, const char *pattern, int width, int mode) {
    draws++;
    int gm = graphics_mode();
    if (!gm) {
        is_graphics = 1;
        return;
    }
    if (!is_graphics)
        lcd_clear();
    int maxx = gr_MAXX();
    if (x < 0) {
        width += x;
        pattern -= x;
        x = 0;
    }
    if (x + width > maxx)
        width = maxx - x;
    is_graphics = gm;
    int s = gm == 2 ? 2 : gm == 3 ? 1 : 0;
    for (int c = 0; c < width; c++)
        for (int k = 0; k < 8; k++) {
            bool on = (pattern[c] >> k) & 1;
            for (int dy = 0; dy < s; dy++)
                for (int dx = 0; dx < s; dx++)
                    lcd_op((x + c) * s + dx, (y + k) * s + dy, mode, on);
        }
}

void thell_clear_display() {
    clear_tlcd_row(0);
    clear_tlcd_row(1);
}

void thell_clear_row(int row) {
    clear_tlcd_row(row);
}

void thell_draw_char(int x, int y, char c) {
    is_graphics = 0;
    if (x >= 0 && x < 22 && y >= 0 && y < 2)
        tlcd[y][x] = c;
}

// On the DM42 the menu has its own bar: the core saves its display before drawing
// a menu into it (n = -1) and has the front end restore it afterwards (n = -2).
void thell_draw_menu_key(int n, int highlight, const char *s, int length) {
    if (n == -1) {
        memcpy(disp_back.data(), core_display_buffer(), DISP_BYTES);
        disp_back_restore = true;
        return;
    }
    if (n == -2) {
        if (disp_back_restore) {
            disp_back_restore = false;
            memcpy(core_display_buffer(), disp_back.data(), DISP_BYTES);
            old_from_core();
        }
        return;
    }
    if (n < 0 || n > 5)
        return;
    std::string t;
    for (int i = 0; i < length; i++)
        if (!(s[i] & 0x80))  // bytes with bit 7 set mark Free42's command-name shortcuts
            t += s[i];
    menu_label[n] = hp_text(t.data(), (int) t.size());
    menu_hl[n] = highlight != 0;
}

void thell_start_show() {}

void thell_edit_number(const char *prompt, int prompt_len, const char *line, int line_length) {
    edit_line = hp_text(prompt, prompt_len) + hp_text(line, line_length);
}

// ---------------------------------------------------------- shell callbacks

const char *shell_platform() { return "dm42sim"; }

void shell_blitter(const char *bits, int bpl, int x, int y, int w, int h) {
    for (int r = y; r < y + h && r < 16; r++)
        for (int c = x; c < x + w && c < 131; c++)
            old[(size_t) r * 131 + c] = (bits[r * bpl + (c >> 3)] >> (c & 7)) & 1;
}

void shell_beeper(int tone) {
    if (tone == 10)
        squeaked = true;  // squeak(): the calculator refused a key or command
}
void shell_annunciators(int updn, int shf, int prt, int run, int g, int rad) {}

bool shell_wants_cpu() {
    if (++steps - action_start >= step_cap) {
        capped = true;
        return true;
    }
    return false;
}

void shell_delay(int duration) {}
void shell_request_timeout3(int delay) { timeout3_pending = true; }
uint8 shell_get_mem() { return 1 << 30; }
bool shell_low_battery() { return false; }
void shell_powerdown() {}
int8 shell_random_seed() { return 42; }
uint4 shell_milliseconds() { return (uint4) steps; }
const char *shell_number_format() { return ".,"; }
int shell_date_format() { return 0; }
bool shell_clk24() { return true; }
void shell_print(const char *text, int length, const char *bits, int bytesperline, int x, int y, int width,
                 int height) {}
void shell_get_time_date(uint4 *time, uint4 *date, int *weekday) {
    *time = 0;
    *date = 20260101;
    *weekday = 4;
}
void shell_message(const char *message) { last_message = message; }
void shell_log(const char *message) {}

void shell_malloc_fail(size_t size, const char *file, int line) {
    printf("{\"event\":\"fatal\",\"error\":\"out of memory\",\"size\":%zu,\"at\":%s}\n", size,
           jstr(std::string(file) + ":" + std::to_string(line)).c_str());
    exit(3);
}
double shell_vbat() { return vbat; }
int shell_dev_id() { return devid; }
void shell_force_lcd_refresh(int what) {}

// ------------------------------------------------------------ running keys

static bool menu_active() {
    return core_menu() || core_alpha_menu() || core_hex_menu();
}

static void settle(bool keep_running) {
    bool enq;
    int rep;
    for (;;) {
        while (keep_running && !capped)
            keep_running = core_keydown(0, &enq, &rep);
        if (capped || !timeout3_pending)
            return;
        timeout3_pending = false;
        keep_running = core_timeout3(true);
    }
}

// A physical key 1-37. As on the DM42, keys 1-6 keep their own functions while a
// menu shows (DM42PGM's no_menu_key); the menu items are F1-F6 (menu_key).
static void press(int key) {
    bool enq;
    int rep;
    bool k = core_keydown_ex(key, &enq, &rep, menu_active() && key >= 1 && key <= 6);
    if (!enq)
        k = core_keyup();
    settle(k);
}

static void menu_key(int n) {
    bool enq;
    int rep;
    bool k = core_keydown_ex(n, &enq, &rep, 0);
    if (!enq)
        k = core_keyup();
    settle(k);
}

// A built-in command by name, or (is_text) one character typed in ALPHA entry.
// Returns false when the calculator squeaked, i.e. refused it.
static bool command(const std::string &name, bool is_text) {
    bool enq;
    int rep;
    char audio = flags.f.audio_enable;
    flags.f.audio_enable = 1;
    squeaked = false;
    bool k = core_keydown_command(name.c_str(), is_text, &enq, &rep);
    if (!enq)
        k = core_keyup();
    settle(k);
    flags.f.audio_enable = audio;
    return !squeaked;
}

static int key_code(const std::string &k) {
    static const char *names[] = {
        "SIGMA+", "1/X", "SQRT", "LOG", "LN", "XEQ", "STO", "RCL", "RDN", "SIN", "COS", "TAN",
        "ENTER", "X<>Y", "CHS", "E", "BSP", "UP", "7", "8", "9", "/", "DOWN", "4", "5", "6", "*",
        "SHIFT", "1", "2", "3", "-", "EXIT", "0", ".", "R/S", "+"};
    for (int i = 0; i < 37; i++)
        if (k == names[i])
            return i + 1;
    if (k.size() == 2 && k[0] == 'F' && k[1] >= '1' && k[1] <= '6')
        return 100 + (k[1] - '0');  // F1..F6
    if (k.size() > 1 && k[0] == '#') {
        int n = atoi(k.c_str() + 1);
        if (n >= 1 && n <= 37)
            return n;
    }
    return 0;
}

static bool parse_int(const std::string &s, long long &v) {
    static const std::regex integer(R"([+-]?\d+)");
    if (!std::regex_match(s, integer))
        return false;
    v = atoll(s.c_str());
    return true;
}

static bool parse_real(const std::string &s) {
    static const std::regex number(R"([+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?)");
    return std::regex_match(s, number);
}

// Steps in program i, counting its END; 1 means an empty program.
static int program_steps(int i) {
    int saved = current_prgm;
    char mode = flags.f.prgm_mode;
    current_prgm = i;
    flags.f.prgm_mode = 1;  // core_copy() lists the program only in program mode
    char *txt = core_copy();
    std::istringstream lines(txt);
    free(txt);
    flags.f.prgm_mode = mode;
    current_prgm = saved;
    int n = 0;
    std::string l;
    while (std::getline(lines, l))
        if (l.size() > 2 && isdigit((unsigned char) l[0]) && l.find('{') == std::string::npos)
            n++;
    return n;
}

static bool has_label(const std::string &name) {
    for (int i = 0; i < labels_count; i++)
        if (labels[i].length > 0 && hp_text(labels[i].name, labels[i].length) == name)
            return true;
    return false;
}

// ------------------------------------------------------------ state output

static bool hires() {
    return is_graphics > 1;
}

static int lit() {
    int n = 0;
    if (hires())
        for (unsigned char p : lcd)
            n += p;
    else
        for (unsigned char p : old)
            n += p;
    return n;
}

static std::string rows_json() {
    return "[" + jstr(hp_text(tlcd[0], 22)) + "," + jstr(hp_text(tlcd[1], 22)) + "]";
}

static void emit_result(const std::string &action, const std::string &arg) {
    printf("{\"action\":%s,\"arg\":%s,\"steps\":%lld,\"running\":%s,\"getkey\":%s,\"capped\":%s,"
           "\"screen\":%s,\"rows\":%s}\n",
           jstr(action).c_str(), jstr(arg).c_str(), steps - action_start, mode_running ? "true" : "false",
           mode_getkey ? "true" : "false", capped ? "true" : "false", hires() ? "\"lcd\"" : "\"classic\"",
           rows_json().c_str());
}

static void emit_state() {
    std::string s = "{\"event\":\"state\"";
    const char *reg[] = {"x", "y", "z", "t"};
    for (int i = 0; i < 4 && i <= sp; i++)
        s += std::string(",\"") + reg[i] + "\":" + jstr(value_text(stack[sp - i]));
    s += ",\"lastx\":" + jstr(value_text(lastx));
    s += ",\"alpha\":" + jstr(hp_text(reg_alpha, reg_alpha_length));
    s += ",\"angle\":" + std::string(flags.f.rad ? "\"RAD\"" : flags.f.grad ? "\"GRAD\"" : "\"DEG\"");
    s += ",\"grmod\":" + std::to_string(graphics_mode());
    s += ",\"width\":" + std::to_string(gr_MAXX()) + ",\"height\":" + std::to_string(gr_MAXY());
    s += ",\"running\":" + std::string(mode_running ? "true" : "false");
    s += ",\"getkey\":" + std::string(mode_getkey ? "true" : "false");
    s += ",\"screen\":" + std::string(hires() ? "\"lcd\"" : "\"classic\"") + ",\"lit\":" + std::to_string(lit());
    s += ",\"draws\":" + std::to_string(draws) + ",\"total_steps\":" + std::to_string(steps);
    s += ",\"rows\":" + rows_json() + ",\"menu\":[";
    bool shown = menu_active();
    for (int i = 0; shown && i < 6; i++)
        s += (i ? "," : "") + jstr(menu_label[i] + (menu_hl[i] ? "*" : ""));
    s += "],\"cmdline\":" + jstr(edit_line) + ",\"flags\":\"";
    for (int i = 0; i < 100; i++)
        s += flags.farray[i] ? '1' : '0';
    s += "\",\"vars\":{";
    bool first = true;
    for (int i = 0; i < vars_count; i++) {
        std::string name = hp_text(vars[i].name, vars[i].length);
        if (vars[i].level != -1)
            name += "@" + std::to_string(vars[i].level);  // local variable and its level
        s += (first ? "" : ",") + jstr(name) + ":" + jstr(value_text(vars[i].value));
        first = false;
    }
    s += "}}";
    puts(s.c_str());
}

static bool snapshot(const std::string &path, int scale, int which) {
    bool use_lcd = which == 1 || (which == 0 && hires());
    return use_lcd ? write_png(path.c_str(), LCD_W, LCD_H, lcd, scale)
                   : write_png(path.c_str(), 131, 16, old, scale);
}

// ------------------------------------------------------------ actions

static int fail(const std::string &msg) {
    printf("{\"event\":\"error\",\"error\":%s}\n", jstr(msg).c_str());
    return 2;
}

static bool readable(const std::string &path) {
    std::ifstream in(path, std::ios::binary);
    return (bool) in;
}

static bool is_raw(const std::string &path) {
    if (path.size() < 4)
        return false;
    std::string ext = path.substr(path.size() - 4);
    for (char &c : ext)
        c = (char) tolower((unsigned char) c);
    return ext == ".raw";
}

// Adds the programs in a text or .raw file after the existing ones. Text goes into
// a new program, as GTO .. would make, so a load moves the program pointer.
static std::string load_program(const std::string &path) {
    if (!readable(path))
        return "cannot read " + path;
    last_message.clear();
    if (is_raw(path)) {
        core_import_programs(0, path.c_str());
        return last_message;
    }
    if (mode_command_entry)
        return "a command is being entered; finish it before load";
    std::ifstream in(path, std::ios::binary);
    std::stringstream ss;
    ss << in.rdbuf();
    goto_dot_dot(false);
    flags.f.prgm_mode = 1;
    core_paste(ss.str().c_str());
    flags.f.prgm_mode = 0;
    return last_message;
}

static int run_actions(std::istream &in) {
    core_init(0, 0, NULL, 0);
    thell_clear_display();
    std::string line;
    int lineno = 0;
    while (std::getline(in, line)) {
        lineno++;
        size_t b = line.find_first_not_of(" \t\r");
        if (b == std::string::npos || line[b] == '#')
            continue;
        line = line.substr(b);
        while (!line.empty() && (line.back() == '\r' || line.back() == ' ' || line.back() == '\t'))
            line.pop_back();
        size_t sp_ = line.find_first_of(" \t");
        std::string verb = line.substr(0, sp_), arg = sp_ == std::string::npos ? "" : line.substr(sp_ + 1);
        arg.erase(0, arg.find_first_not_of(" \t"));
        std::istringstream argv(arg);
        std::string where = " (line " + std::to_string(lineno) + ")";
        action_start = steps;
        capped = false;
        if (verb == "load") {
            std::string err = load_program(arg);
            if (!err.empty())
                return fail(err + where);
        } else if (verb == "xeq") {
            if (!has_label(arg))
                return fail("no global label " + arg + where);
            if (arg.size() == 1 && ((arg[0] >= 'A' && arg[0] <= 'J') || (arg[0] >= 'a' && arg[0] <= 'e')))
                return fail("XEQ \"" + arg + "\" names local label " + arg + "; on the calculator a one-letter global "
                            "label A-J or a-e is run from the XEQ menu (key XEQ, then F-keys)" + where);
            command("XEQ", false);
            press(KEY_SHIFT);
            press(KEY_ENTER);
            for (const std::string &c : utf8_chars(arg))
                command(c, true);
            press(KEY_ENTER);
        } else if (verb == "key") {
            std::string k;
            while (argv >> k) {
                int code = key_code(k);
                if (code == 0)
                    return fail("unknown key " + k + where);
                if (code > 100) {
                    if (!menu_active())
                        return fail(k + " with no menu is a DM42 front-end shortcut (help, menu, volume, "
                                        "fonts), not emulated" + where);
                    menu_key(code - 100);
                } else
                    press(code);
                if (quitting)
                    break;
            }
        } else if (verb == "cmd") {
            if (!command(arg, false))
                return fail("the calculator refused command " + arg + where);
        } else if (verb == "text") {
            if (!core_alpha_menu())
                return fail("text needs ALPHA entry (SHIFT ENTER, or a prompt in ALPHA mode)" + where);
            for (const std::string &c : utf8_chars(arg)) {
                if (c == "\xc3\xb7")
                    return fail("÷ is character 0, which the core's text input cannot type" + where);
                if (!command(c, true))
                    return fail("the calculator refused " + c + where);
            }
        } else if (verb == "run") {
            press(KEY_RUN);
        } else if (verb == "continue") {
            if (!mode_running)
                return fail("continue needs a running program (one stopped by maxsteps)" + where);
            settle(true);
        } else if (verb == "var") {
            std::string name, value, extra;
            argv >> name >> value >> extra;
            phloat p;
            bool ascii = !name.empty() && name.size() <= 7;
            for (char c : name)
                ascii = ascii && c > ' ' && c < 127;
            if (!ascii || !extra.empty() || !parse_real(value)
                || string2phloat(value.c_str(), (int) value.size(), &p) != 0)
                return fail("var takes a name of 1-7 ASCII characters and a decimal number" + where);
            store_var(name.c_str(), (int) name.size(), new_real(p));
        } else if (verb == "flag") {
            int n = -1, v = -1;
            argv >> n >> v;
            if (n < 0 || n > 99 || (v != 0 && v != 1))
                return fail("flag takes a number 0-99 and 0 or 1" + where);
            flags.farray[n] = (char) v;
        } else if (verb == "mode") {
            if (arg != "RAD" && arg != "GRAD" && arg != "DEG")
                return fail("mode is DEG, RAD or GRAD" + where);
            flags.f.rad = arg == "RAD";
            flags.f.grad = arg == "GRAD";
        } else if (verb == "grmod") {
            long long gm;
            if (!parse_int(arg, gm))
                return fail("grmod takes an integer" + where);
            store_var("GrMod", 5, new_real(phloat((int) gm)));  // exactly as STO "GrMod"
        } else if (verb == "devid") {
            long long v;
            if (!parse_int(arg, v))
                return fail("devid takes an integer" + where);
            devid = (int) v;
        } else if (verb == "vbat") {
            if (!parse_real(arg))
                return fail("vbat takes a decimal number" + where);
            vbat = atof(arg.c_str());
        } else if (verb == "maxsteps") {
            long long v;
            if (!parse_int(arg, v) || v < 1)
                return fail("maxsteps takes a positive integer" + where);
            step_cap = v;
        } else if (verb == "state") {
            emit_state();
            continue;
        } else if (verb == "snap" || verb == "snaplcd" || verb == "snapclassic") {
            std::string path = arg;
            int scale = 1;
            size_t cut = arg.find_last_of(" \t");
            long long sc;
            if (cut != std::string::npos && parse_int(arg.substr(cut + 1), sc)) {
                path = arg.substr(0, arg.find_last_not_of(" \t", cut) + 1);
                scale = (int) sc;
            }
            if (path.empty() || scale < 1 || !snapshot(path, scale, verb == "snaplcd" ? 1 : verb == "snap" ? 0 : 2))
                return fail("cannot write snapshot " + path + where);
        } else {
            return fail("unknown action " + verb + where);
        }
        if (quitting)
            return fail("the calculator was switched off (OFF, or SHIFT EXIT); power-off is not emulated" + where);
        emit_result(verb, arg);
    }
    return 0;
}

int main(int argc, char *argv[]) {
    std::string mode = argc > 1 ? argv[1] : "";
    if (mode == "run" && argc <= 3) {
        if (argc == 3 && strcmp(argv[2], "-") != 0) {
            std::ifstream in(argv[2]);
            if (!in)
                return fail(std::string("cannot read ") + argv[2]);
            return run_actions(in);
        }
        return run_actions(std::cin);
    }
    if (mode == "compile" && argc == 4) {
        core_init(0, 0, NULL, 0);
        std::string err = load_program(argv[2]);
        if (!err.empty())
            return fail(err);
        bool any = false;
        for (int i = 0; i < prgms_count; i++)
            any = any || program_steps(i) > 1;
        if (!any)
            return fail(std::string("no program steps in ") + argv[2]);
        std::vector<int> idx(prgms_count);
        for (int i = 0; i < prgms_count; i++)
            idx[i] = i;
        remove(argv[3]);
        last_message.clear();
        core_export_programs(prgms_count, idx.data(), argv[3]);
        if (!last_message.empty() || !readable(argv[3]))
            return fail("cannot write " + std::string(argv[3]) + (last_message.empty() ? "" : ": " + last_message));
        return 0;
    }
    if (mode == "decode" && argc == 3) {
        core_init(0, 0, NULL, 0);
        if (!readable(argv[2]))
            return fail(std::string("cannot read ") + argv[2]);
        last_message.clear();
        core_import_programs(0, argv[2]);
        if (!last_message.empty())
            return fail("cannot import " + std::string(argv[2]) + ": " + last_message);
        // The import replaces the fresh calculator's empty program; list the non-empty ones.
        flags.f.prgm_mode = 1;
        std::string out;
        for (int i = 0; i < prgms_count; i++) {
            if (program_steps(i) <= 1)
                continue;
            current_prgm = i;
            char *txt = core_copy();
            out += std::string(txt) + "\n";
            free(txt);
        }
        if (out.empty())
            return fail("no program in " + std::string(argv[2]));
        fputs(out.c_str(), stdout);
        return 0;
    }
    fprintf(stderr,
            "usage: %s run [ACTIONS|-]       action script, JSON lines out\n"
            "       %s compile IN OUT.raw    program text (or .raw) to .raw\n"
            "       %s decode IN.raw         .raw to program text\n",
            argv[0], argv[0], argv[0]);
    return 1;
}

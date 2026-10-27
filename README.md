# Pico 2 W Handheld for Game Boy and Game Boy Color games

Firmware and the SD card tool for the 3D-printed Raspberry Pi Pico 2 W handheld on MakerWorld ("Pico 2 W Handheld
for Game Boy and Game Boy Color"). The printable parts and photos are on MakerWorld; the build guide is on both
(`docs/BUILD_GUIDE.pdf` here). This page exists because MakerWorld doesn't take firmware files.

No games are included. Use game files you own.

## What's here

| File | What it is |
|---|---|
| `firmware/pico_games_handheld.uf2` | The ready firmware for the Pico 2 W (RP2350), wired as in the build guide |
| `tools/make_menu_card.py`, `tools/font8x8_basic.h` | Makes the menu's files on the games card (covers or name tiles, genres) |
| `docs/BUILD_GUIDE.pdf` | Parts, wiring for every pin, assembly, firmware and card set-up |
| `docs/pico_wiring.png` | The Pico's wiring drawing |
| `LICENSES.txt` | The licence of every part the firmware is built from |
| `SHA256SUMS` | Checksums of the files above (`sha256sum -c SHA256SUMS`) |

## Putting the firmware on

Hold the Pico's BOOTSEL button while plugging its USB into a computer. A drive called `RP2350` appears: copy
`pico_games_handheld.uf2` onto it. The Pico restarts into the menu.

Later, with the shell closed: with the handheld on USB-C, setting its serial port to 1200 baud restarts it into the
`RP2350` drive (on Linux: `stty -F /dev/ttyACM0 1200`). Then copy the .uf2 as above.

## The games card

Format a microSD card FAT32 (up to 32 GB) or exFAT, copy your .gb / .gbc files into its top folder or one folder down,
then make the menu files (Python 3 with Pillow and numpy):

```
python3 tools/make_menu_card.py <the card's folder>
```

The build guide has the details, including cover pictures.

## Credits and licences

The firmware is built on Peanut-GB (Mahyar Koshkouei), Pico-GB (YouMakeTech), minigb_apu, an I2S driver by Vincent
Mistler, FatFs (ChaN), the Raspberry Pi Pico SDK and TinyUSB, font8x8 and Hedley. Every licence's full text is in
`LICENSES.txt`.

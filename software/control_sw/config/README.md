## Clock configuration files

Clock configuration is made by setting the `lmkfile` and `lmxfile`
keys of a configuration YAML file.

In order to use a clock file, it should be present on the RFSoC
board's filesystem in directory `/lib/firmware/`.

This can be achieved using `scp` (or your favourite file copying protocol),
or `SoukMkidReadout.rfdc.core.upload_clock_file(<local file path>)`.
If using `scp`, the typical username:password on an RFSoC board is:
`casper:casper`.

You can check what clock files are currently available with:
`SoukMkidReadout.rfdc.core.show_clk_files()`.

### LMX Configuration

245.76 MHz reference: `rfsoc4x2_LMX_REF_245M76_OUT_491M52.txt`

### LMK Configuration

On-board 100 MHz reference: `rfsoc4x2_PL_122M88_REF_245M76.txt`
External 10 MHz reference: `rfsoc4x2_PL_122M88_REF_245M76_10M_EXTREF.txt`

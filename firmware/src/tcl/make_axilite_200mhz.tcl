# Hackery to get 200 MHz AXI clock
set AXI_CLK_MHZ 200
# Set MPSoC PL clock output to 200 MHz
set_property CONFIG.PSU__CRL_APB__PL0_REF_CTRL__FREQMHZ $AXI_CLK_MHZ [get_bd_cells mpsoc]
# Readback actual clock rate after PLL rounding
set axi_clk_hz [get_property CONFIG.FREQ_HZ [get_bd_pins mpsoc/pl_clk0]]
set axi_clk_mhz [expr {$axi_clk_hz / 1000000.0} ]
# Set RFDC AXI-Lite interface clock
set_property CONFIG.Axiclk_Freq $axi_clk_mhz [get_bd_cells usp_rf_data_converter_0]
# Set block diagram input/output clock port rate
set_property CONFIG.FREQ_HZ $axi_clk_hz [get_bd_ports pl_sys_clk]
set_property CONFIG.FREQ_HZ $axi_clk_hz [get_bd_ports s_axi_aclk]
# Update clock rate of output MAXI interface by associating with clock port
set_property CONFIG.ASSOCIATED_BUSIF {M_AXI} [get_bd_ports /pl_sys_clk]

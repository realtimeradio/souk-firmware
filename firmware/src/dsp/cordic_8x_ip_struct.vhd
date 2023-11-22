library IEEE;
use IEEE.std_logic_1164.all;
library xil_defaultlib;
use xil_defaultlib.conv_pkg.all;
entity cordic_8x_ip_struct is
  port (
    phase_inc : in std_logic_vector( 64-1 downto 0 );
    load  : in std_logic_vector( 1-1 downto 0 );
    amplitude  : in std_logic_vector( 16-1 downto 0 );
    clk_1 : in std_logic;
    ce_1  : in std_logic;
    dout  : out std_logic_vector( 288-1 downto 0 )
  );
end cordic_8x_ip_struct;

architecture structural of cordic_8x_ip_struct is
  component cordic_8x
    port (
      phase_inc  : in std_logic_vector( 64-1 downto 0 );
      load  : in std_logic_vector( 1-1 downto 0 );
      amplitude  : in std_logic_vector( 16-1 downto 0 );
      clk   : in std_logic;
      dout  : out std_logic_vector( 288-1 downto 0 )
    );
  end component;

begin
  cordic_8x_ip_inst : cordic_8x
  port map (
    phase_inc => phase_inc, 
    load      => load, 
    amplitude => amplitude,
    clk       => clk_1, 
    dout      => dout
  );
end structural; 

library IEEE;
use IEEE.std_logic_1164.all;
library xil_defaultlib;
use xil_defaultlib.conv_pkg.all;
entity cordic_1x_ip_struct is
  port (
    phase_step : in std_logic_vector( 32-1 downto 0 );
    phase_offset : in std_logic_vector( 32-1 downto 0 );
    scale : in std_logic_vector( 32-1 downto 0 );
    sync  : in std_logic_vector( 1-1 downto 0 );
    rst  : in std_logic_vector( 1-1 downto 0 );
    clk_1 : in std_logic;
    ce_1  : in std_logic;
    lo_out : out std_logic_vector( 36-1 downto 0 );
    sync_out : out std_logic_vector( 1-1 downto 0 )
  );
end cordic_1x_ip_struct;

architecture structural of cordic_1x_ip_struct is
  component cordic_1x
    port (
      phase_step : in std_logic_vector( 32-1 downto 0 );
      phase_offset : in std_logic_vector( 32-1 downto 0 );
      scale : in std_logic_vector( 32-1 downto 0 );
      sync  : in std_logic_vector( 1-1 downto 0 );
      rst  : in std_logic_vector( 1-1 downto 0 );
      clk : in std_logic;
      lo_out : out std_logic_vector( 36-1 downto 0 );
      sync_out : out std_logic_vector( 1-1 downto 0 )
    );
  end component;

begin
  cordic_1x_ip_inst : cordic_1x
  port map (
    phase_step => phase_step, 
    phase_offset => phase_offset, 
    scale    => scale, 
    rst      => rst, 
    sync     => sync, 
    clk      => clk_1, 
    lo_out   => lo_out,
    sync_out => sync_out
  );
end structural; 

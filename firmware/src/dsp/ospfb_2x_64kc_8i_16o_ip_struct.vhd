library IEEE;
use IEEE.std_logic_1164.all;
library xil_defaultlib;
use xil_defaultlib.conv_pkg.all;
entity ospfb_2x_64kc_8i_16o_ip_struct is
  port (
    din   : in std_logic_vector( 256-1 downto 0 );
    shift : in std_logic_vector( 32-1 downto 0 );
    sync  : in std_logic_vector( 1-1 downto 0 );
    clk_1 : in std_logic;
    ce_1  : in std_logic;
    dout  : out std_logic_vector( 576-1 downto 0 );
    overflow : out std_logic_vector( 1-1 downto 0 );
    sync_out : out std_logic_vector( 1-1 downto 0 )
  );
end ospfb_2x_64kc_8i_16o_ip_struct;

architecture structural of ospfb_2x_64kc_8i_16o_ip_struct is
  component ospfb_2x_64kc_8i_16o
    port (
      din   : in std_logic_vector( 256-1 downto 0 );
      shift : in std_logic_vector( 32-1 downto 0 );
      sync  : in std_logic_vector( 1-1 downto 0 );
      clk   : in std_logic;
      dout  : out std_logic_vector( 576-1 downto 0 );
      overflow : out std_logic_vector( 1-1 downto 0 );
      sync_out : out std_logic_vector( 1-1 downto 0 )
    );
  end component;
begin
  ospfb_2x_64kc_8i_16o_ip_inst : ospfb_2x_64kc_8i_16o
  port map (
    din => din,
    shift    => shift, 
    sync     => sync, 
    clk      => clk_1, 
    dout     => dout,
    overflow => overflow, 
    sync_out => sync_out 
  );
end structural; 

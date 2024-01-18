
function os_polyphase_synth_config(this_block)

  this_block.setTopLevelLanguage('VHDL');

  this_block.setEntityName('os_polyphase_synth_ip_struct');

  % System Generator has to assume that your entity  has a combinational feed through; 
  %   if it  doesn't, then comment out the following line:
  %this_block.tagAsCombinational;

  
  this_block.addSimulinkInport('sync');
  this_block.addSimulinkInport('shift');
  this_block.addSimulinkInport('din0');
  this_block.addSimulinkInport('din1');

  this_block.addSimulinkOutport('sync_out');
  this_block.addSimulinkOutport('dout0');
  this_block.addSimulinkOutport('dout1');
  this_block.addSimulinkOutport('overflow');

  overflow_port = this_block.port('overflow');
  overflow_port.setType('Bool');
  dout0_port = this_block.port('dout0');
  dout0_port.setType('UFix_288_0');
  dout1_port = this_block.port('dout1');
  dout1_port.setType('UFix_288_0');
  sync_out_port = this_block.port('sync_out');
  sync_out_port.setType('Bool');

  % -----------------------------
  if (this_block.inputTypesKnown)
    % do input type checking, dynamic output type and generic setup in this code block.

    if (this_block.port('din0').width ~= 288);
      this_block.setError('Input data type for port "din0" must have width=288.');
    end
    if (this_block.port('din1').width ~= 288);
      this_block.setError('Input data type for port "din1" must have width=288.');
    end
    if (this_block.port('shift').width ~= 32);
      this_block.setError('Input data type for port "shift" must have width=32.');
    end
    if (this_block.port('sync').width ~= 1);
      this_block.setError('Input data type for port "sync" must have width=1.');
    end
    %this_block.port('sync').useHDLVector(false);
  end  % if(inputTypesKnown)
  % -----------------------------

  % -----------------------------
   if (this_block.inputRatesKnown)
     setup_as_single_rate(this_block,'clk_1','ce_1')
   end  % if(inputRatesKnown)
  % -----------------------------

    % (!) Set the inout port rate to be the same as the first input 
    %     rate. Change the following code if this is untrue.
    uniqueInputRates = unique(this_block.getInputRates);


  % Add addtional source files as needed.
  %  |-------------
  %  | Add files in the order in which they should be compiled.
  %  | If two files "a.vhd" and "b.vhd" contain the entities
  %  | entity_a and entity_b, and entity_a contains a
  %  | component of type entity_b, the correct sequence of
  %  | addFile() calls would be:
  %  |    this_block.addFile('b.vhd');
  %  |    this_block.addFile('a.vhd');
  %  |-------------

  %    this_block.addFile('');
  %    this_block.addFile('');
  this_block.addFile('dsp/os_polyphase_synth_ip_struct.vhd');

return;


% ------------------------------------------------------------

function setup_as_single_rate(block,clkname,cename) 
  inputRates = block.inputRates; 
  uniqueInputRates = unique(inputRates); 
  if (length(uniqueInputRates)==1 & uniqueInputRates(1)==Inf) 
    block.addError('The inputs to this block cannot all be constant.'); 
    return; 
  end 
  if (uniqueInputRates(end) == Inf) 
     hasConstantInput = true; 
     uniqueInputRates = uniqueInputRates(1:end-1); 
  end 
  if (length(uniqueInputRates) ~= 1) 
    block.addError('The inputs to this block must run at a single rate.'); 
    return; 
  end 
  theInputRate = uniqueInputRates(1); 
  for i = 1:block.numSimulinkOutports 
     block.outport(i).setRate(theInputRate); 
  end 
  block.addClkCEPair(clkname,cename,theInputRate); 
  return; 

% ------------------------------------------------------------


function build_ip_cores()
    %   Build the DSP IP cores used by the top-level design

    cores = { ...
	'src/dsp/ospfb_2x_8192c_8i_16o.slx', ...
	'src/dsp/cordic_1x4.slx', ...
	'src/dsp/zoom_fft_1024c_d512.slx', ...
	'src/dsp/os_polyphase_synth.slx', ...
	'src/dsp/cordic_8x.slx', ...
    };

    for corecell = cores
        core = corecell{1};
	if ~isfile(core)
	    error(['Core ' core 'does not exist!']);
	end
        [core_filepath, core_name, core_ext] = fileparts(which(core));
        dcp_name = [core_filepath '/' core_name '/' core_name '.dcp'];
        if isfile(dcp_name)
            disp(['Design checkpoint for model ' core ' already exists - not recompiling']);
        else
            disp(['Building design checkpoint for model ' core]);
            open_system(core);
            xsg_result = xlGenerateButton([core_name '/ System Generator']);
            
            close_system(core, 0);
	end
    end

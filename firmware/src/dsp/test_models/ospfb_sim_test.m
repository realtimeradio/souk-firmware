NTAP=8;
NPARALLEL=1;
NFFT=2^6;
TARGET_BIN=10;
SYNC_START=10;
NSPAN  = 2;
NTRIAL = 30;
sim_time = NTAP*NFFT / NPARALLEL + (NFFT/NPARALLEL);


sim_sync = timeseries(zeros(sim_time,1));
sim_din1r = timeseries(zeros(sim_time,1));
sim_din1i = timeseries(zeros(sim_time,1));


dout = zeros(NTRIAL, 2*NFFT);
dout_sum = zeros(NTRIAL, NFFT);

ftrial = linspace(TARGET_BIN-NSPAN, TARGET_BIN+NSPAN, NTRIAL);

for ii = [1:NTRIAL]
    ii
    ts = 1/NPARALLEL; % sample time
    t = [0:(NPARALLEL*sim_time-1)];
    bin_width = 1./(2*ts*NFFT);
    f = bin_width * ftrial(ii);

    d = exp(2*pi*1j*f*t*ts) * 2^14;
    dr = real(d);
    di = imag(d);

    sim_din1r.Data(SYNC_START+1:SYNC_START+1+(NFFT*NTAP/NPARALLEL)-1) = dr(1:NPARALLEL:NFFT*NTAP+0);
    sim_din1i.Data(SYNC_START+1:SYNC_START+1+(NFFT*NTAP/NPARALLEL)-1) = di(1:NPARALLEL:NFFT*NTAP+0);
    sim_sync.Data(SYNC_START) = 1;


    set_param(bdroot, 'StopTime', num2str(sim_time));
    clear('out');
    out = sim(bdroot);

    out_sync_pos = find(out.sim_sync_out.Data == 1)

    sw_fft_data_in = zeros(2*NFFT, 1);

    sw_fft_data_in(1:NPARALLEL:NFFT + 0)        = out.sim_dout_r1.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1) + 1j*out.sim_dout_i1.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1);
    sw_fft_data_in(1+NFFT:NPARALLEL:2*NFFT + 0) = out.sim_dout_r2.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1) + 1j*out.sim_dout_i2.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1);
    
    
    
    dout(ii,:) = sw_fft_data_in;
    dout_sum(ii,:) = out.sim_dout_sumr.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1) + 1j*out.sim_dout_sumi.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1);
    %F = fft(sw_fft_data_in);
    %semilogy(fftshift(abs(F).^2));
end

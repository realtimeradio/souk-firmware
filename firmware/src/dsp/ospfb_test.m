NTAP=8;
NPARALLEL=8;
NFFT=2^11;
TARGET_BIN=10;
SYNC_START=10;
NSPAN  = 2;
NTRIAL = 25;
sim_time = NTAP*NFFT / NPARALLEL + (NFFT/NPARALLEL);


sim_sync = timeseries(zeros(sim_time,1));
sim_din1r = timeseries(zeros(sim_time,1));
sim_din2r = timeseries(zeros(sim_time,1));
sim_din3r = timeseries(zeros(sim_time,1));
sim_din4r = timeseries(zeros(sim_time,1));
sim_din5r = timeseries(zeros(sim_time,1));
sim_din6r = timeseries(zeros(sim_time,1));
sim_din7r = timeseries(zeros(sim_time,1));
sim_din8r = timeseries(zeros(sim_time,1));

sim_din1i = timeseries(zeros(sim_time,1));
sim_din2i = timeseries(zeros(sim_time,1));
sim_din3i = timeseries(zeros(sim_time,1));
sim_din4i = timeseries(zeros(sim_time,1));
sim_din5i = timeseries(zeros(sim_time,1));
sim_din6i = timeseries(zeros(sim_time,1));
sim_din7i = timeseries(zeros(sim_time,1));
sim_din8i = timeseries(zeros(sim_time,1));

dout = zeros(NTRIAL, 2*NFFT);
dout_noos = zeros(NTRIAL, NFFT);

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
    sim_din2r.Data(SYNC_START+1:SYNC_START+1+(NFFT*NTAP/NPARALLEL)-1) = dr(2:NPARALLEL:NFFT*NTAP+1);
    sim_din3r.Data(SYNC_START+1:SYNC_START+1+(NFFT*NTAP/NPARALLEL)-1) = dr(3:NPARALLEL:NFFT*NTAP+2);
    sim_din4r.Data(SYNC_START+1:SYNC_START+1+(NFFT*NTAP/NPARALLEL)-1) = dr(4:NPARALLEL:NFFT*NTAP+3);
    sim_din5r.Data(SYNC_START+1:SYNC_START+1+(NFFT*NTAP/NPARALLEL)-1) = dr(5:NPARALLEL:NFFT*NTAP+4);
    sim_din6r.Data(SYNC_START+1:SYNC_START+1+(NFFT*NTAP/NPARALLEL)-1) = dr(6:NPARALLEL:NFFT*NTAP+5);
    sim_din7r.Data(SYNC_START+1:SYNC_START+1+(NFFT*NTAP/NPARALLEL)-1) = dr(7:NPARALLEL:NFFT*NTAP+6);
    sim_din8r.Data(SYNC_START+1:SYNC_START+1+(NFFT*NTAP/NPARALLEL)-1) = dr(8:NPARALLEL:NFFT*NTAP+7);

    sim_din1i.Data(SYNC_START+1:SYNC_START+1+(NFFT*NTAP/NPARALLEL)-1) = di(1:NPARALLEL:NFFT*NTAP+0);
    sim_din2i.Data(SYNC_START+1:SYNC_START+1+(NFFT*NTAP/NPARALLEL)-1) = di(2:NPARALLEL:NFFT*NTAP+1);
    sim_din3i.Data(SYNC_START+1:SYNC_START+1+(NFFT*NTAP/NPARALLEL)-1) = di(3:NPARALLEL:NFFT*NTAP+2);
    sim_din4i.Data(SYNC_START+1:SYNC_START+1+(NFFT*NTAP/NPARALLEL)-1) = di(4:NPARALLEL:NFFT*NTAP+3);
    sim_din5i.Data(SYNC_START+1:SYNC_START+1+(NFFT*NTAP/NPARALLEL)-1) = di(5:NPARALLEL:NFFT*NTAP+4);
    sim_din6i.Data(SYNC_START+1:SYNC_START+1+(NFFT*NTAP/NPARALLEL)-1) = di(6:NPARALLEL:NFFT*NTAP+5);
    sim_din7i.Data(SYNC_START+1:SYNC_START+1+(NFFT*NTAP/NPARALLEL)-1) = di(7:NPARALLEL:NFFT*NTAP+6);
    sim_din8i.Data(SYNC_START+1:SYNC_START+1+(NFFT*NTAP/NPARALLEL)-1) = di(8:NPARALLEL:NFFT*NTAP+7);

    sim_sync.Data(SYNC_START) = 1;


    set_param(bdroot, 'StopTime', num2str(sim_time));
    clear('out');
    out = sim(bdroot);

    out_sync_pos = find(out.sim_sync_out.Data == 1)

    sw_fft_data_in = zeros(2*NFFT, 1);
    sw_fft_data_in_noos = zeros(NFFT, 1);

    sw_fft_data_in(1:NPARALLEL:NFFT + 0) = out.sim_dout_r1.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1) + 1j*out.sim_dout_i1.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1);
    sw_fft_data_in(2:NPARALLEL:NFFT + 1) = out.sim_dout_r2.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1) + 1j*out.sim_dout_i2.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1);
    sw_fft_data_in(3:NPARALLEL:NFFT + 2) = out.sim_dout_r3.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1) + 1j*out.sim_dout_i3.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1);
    sw_fft_data_in(4:NPARALLEL:NFFT + 3) = out.sim_dout_r4.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1) + 1j*out.sim_dout_i4.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1);
    sw_fft_data_in(5:NPARALLEL:NFFT + 4) = out.sim_dout_r5.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1) + 1j*out.sim_dout_i5.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1);
    sw_fft_data_in(6:NPARALLEL:NFFT + 5) = out.sim_dout_r6.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1) + 1j*out.sim_dout_i6.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1);
    sw_fft_data_in(7:NPARALLEL:NFFT + 6) = out.sim_dout_r7.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1) + 1j*out.sim_dout_i7.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1);
    sw_fft_data_in(8:NPARALLEL:NFFT + 7) = out.sim_dout_r8.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1) + 1j*out.sim_dout_i8.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1);

    sw_fft_data_in(1+NFFT:NPARALLEL:2*NFFT + 0) = out.sim_dout_r9.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1) + 1j*out.sim_dout_i9.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1);
    sw_fft_data_in(2+NFFT:NPARALLEL:2*NFFT + 1) = out.sim_dout_r10.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1) + 1j*out.sim_dout_i10.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1);
    sw_fft_data_in(3+NFFT:NPARALLEL:2*NFFT + 2) = out.sim_dout_r11.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1) + 1j*out.sim_dout_i11.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1);
    sw_fft_data_in(4+NFFT:NPARALLEL:2*NFFT + 3) = out.sim_dout_r12.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1) + 1j*out.sim_dout_i12.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1);
    sw_fft_data_in(5+NFFT:NPARALLEL:2*NFFT + 4) = out.sim_dout_r13.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1) + 1j*out.sim_dout_i13.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1);
    sw_fft_data_in(6+NFFT:NPARALLEL:2*NFFT + 5) = out.sim_dout_r14.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1) + 1j*out.sim_dout_i14.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1);
    sw_fft_data_in(7+NFFT:NPARALLEL:2*NFFT + 6) = out.sim_dout_r15.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1) + 1j*out.sim_dout_i15.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1);
    sw_fft_data_in(8+NFFT:NPARALLEL:2*NFFT + 7) = out.sim_dout_r16.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1) + 1j*out.sim_dout_i16.Data(out_sync_pos+1:out_sync_pos+1+(NFFT/NPARALLEL)-1);

    dout(ii,:) = sw_fft_data_in;
    %F = fft(sw_fft_data_in);
    %semilogy(fftshift(abs(F).^2));
end

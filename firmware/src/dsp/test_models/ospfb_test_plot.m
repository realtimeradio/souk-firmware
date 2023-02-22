% dout2 = zeros(30,2048)
% for i=[1:30]
%     for j=[1:8]
%         dout2(i,j:8:NFFT) = dout(i,j:8:NFFT) + dout(i,NFFT+j:8:2*NFFT);
%     end
% end
% 
% fft_out2 = abs(fft(dout, 2048, 2)).^2
% 
% semilogy(fft_out2(:,6));

% dout2 = zeros(NTRIAL,NFFT);
% for ii=[1:NTRIAL]
%     dout2(ii,:) = dout(ii,1:NFFT) + dout(ii,NFFT+1:2*NFFT);
% end
% 
% fft_out2 = abs(fft(dout2, NFFT, 2)).^2;
% 
% semilogy(fft_out2(:,6));

dout2 = zeros(NTRIAL,2*NFFT);
for ii=[1:NTRIAL]
    dout2(ii,:) = dout(ii,:);%dout(ii,1:NFFT) + dout(ii,NFFT+1:2*NFFT);
end

fft_out2 = abs(fft(dout2, 2*NFFT, 2)).^2;

%plot(fft_out2(1,:))
figure;
semilogy(fft_out2(:,9));
hold on;
semilogy(fft_out2(:,10));
semilogy(fft_out2(:,11));
semilogy(fft_out2(:,12));
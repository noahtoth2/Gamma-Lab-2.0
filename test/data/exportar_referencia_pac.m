d = 'C:\Users\noah\Downloads\Gamma-Lab-2.0\test\data\';

writematrix(v_Data,        [d 'pac_entrada_matlab.csv']);

writematrix(srate,         [d 'pac_srate_matlab.csv']);

writematrix(v_Data_phase,  [d 'pac_fase_matlab.csv']);

writematrix(m_phase_av,    [d 'pac_mapa_matlab.csv'], 'Delimiter', ';');

writematrix(fr(:),         [d 'pac_frecuencias_matlab.csv']);

writematrix(hist_pre_1(:), [d 'pac_histograma_matlab.csv']);

writematrix([real(v_pha_av_pre1) imag(v_pha_av_pre1)], ...
            [d 'pac_vector_matlab.csv']);

disp('--- Referencia de PAC exportada a test/data/ ---');


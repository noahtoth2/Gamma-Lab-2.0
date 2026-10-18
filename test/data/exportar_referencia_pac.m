%% ===================================================================
%  Exportar la referencia de PAC desde BOARD_FTD_PACC hacia Gamma Lab 2.0
%  ===================================================================
%
%  QUE HACE
%  Guarda siete archivos en test/data/ con lo que MATLAB calcula por dentro.
%  Con ellos, test/plugins_test/test_pac_vs_matlab.py deja de saltarse y
%  compara el porte contra el original.
%
%  COMO SE USA
%   1. Abrir BOARD_FTD_PACC.mlapp y cargar  test/data/17308005.abf
%   2. Generar los trials como se haga normalmente
%   3. Poner Single Trial = 1 y los valores por defecto:
%          Sample Fq 2000 | Fq P1 3 | Fq P2 8 | Fq A1 25 | Fq A2 500
%   4. Abrir f_Phase_PAC.m y pegar el bloque de abajo JUSTO DESPUES de la
%      linea 74, la que dice:
%          m_phase_av_aux_pre = m_phase_av_aux;
%   5. Guardar y pulsar el boton PAC
%   6. Comprobar que aparecieron los siete .csv en test/data/
%   7. Quitar el bloque de f_Phase_PAC.m (o dejarlo comentado)
%
%  EL MAS IMPORTANTE ES EL PRIMERO
%  pac_entrada_matlab.csv es la senal YA RECORTADA Y SUBMUESTREADA con la que
%  MATLAB trabajo. Sin el, comparar las dos aplicaciones no demuestra nada: el
%  recorte de trials usa parametros propios en cada una, y entre un trial y
%  otro del mismo archivo la fase del vector se mueve de 185 a 326 grados. Con
%  el, cualquier diferencia que quede solo puede venir del algoritmo.
%
%  QUE NO SE EXPORTA, Y POR QUE
%  La matriz completa de la transformada de Morse (m_tf_Data) pesaria unos
%  200 MB en CSV, porque es de 1.900 x 6.101. El mapa (m_phase_av) es de
%  1.900 x 100, unos 3 MB, y ya permite comparar el resultado. Si hiciera
%  falta aislar la transformada, se pide despues.
%
%% ===================================================================
%  PEGAR DESDE AQUI
%% ===================================================================

d = 'C:\Users\noah\Downloads\Gamma-Lab-2.0\test\data\';

% 1. La senal de entrada, ya submuestreada  <- EL MAS IMPORTANTE
writematrix(v_Data,        [d 'pac_entrada_matlab.csv']);

% 2. La frecuencia de muestreo despues del submuestreo
writematrix(srate,         [d 'pac_srate_matlab.csv']);

% 3. La fase instantanea: angle(hilbert(v_Data_Filt))
writematrix(v_Data_phase,  [d 'pac_fase_matlab.csv']);

% 4. El mapa fase/frecuencia SIN normalizar (antes del z-score).
%    Sin normalizar a proposito: asi un fallo en la normalizacion no se
%    confunde con uno en el agrupado por fase.
writematrix(m_phase_av,    [d 'pac_mapa_matlab.csv'], 'Delimiter', ';');

% 5. El eje de frecuencias de la transformada
writematrix(fr(:),         [d 'pac_frecuencias_matlab.csv']);

% 6. El histograma: sum(m_phase_av, 1)
writematrix(hist_pre_1(:), [d 'pac_histograma_matlab.csv']);

% 7. El vector medio, en parte real e imaginaria (lo que dibuja la brujula)
writematrix([real(v_pha_av_pre1) imag(v_pha_av_pre1)], ...
            [d 'pac_vector_matlab.csv']);

disp('--- Referencia de PAC exportada a test/data/ ---');

%% ===================================================================
%  HASTA AQUI
%% ===================================================================

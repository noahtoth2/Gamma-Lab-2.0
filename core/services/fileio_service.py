from pathlib import Path
from ..model.signal_dataset import SignalDataset
import numpy as np
import pyabf
import pyedflib
from scipy.io import loadmat
import h5py

class FileIOService:
    """File readers. Each loader returns a SignalDataset."""
    def load_abf(self, file_path: str) -> SignalDataset:
        print(f"\n=== Loading ABF file: {file_path} ===")
        abf = pyabf.ABF(file_path)

        channel_count = abf.channelCount
        print(f"Detected channel count: {channel_count}")

        # pyabf ya tiene el archivo entero en memoria: `abf.data` es la matriz
        # (canales, muestras) y `abf.sweepX` el eje de tiempo. Copiar ambos
        # duplicaba los datos —medido: el working set crecia al doble del tamano
        # de los arreglos (problema nº 12)—. Como el objeto `abf` muere al salir
        # de aqui, basta con quedarse con sus arreglos en lugar de copiarlos:
        # NumPy los mantiene vivos y nadie mas los referencia.
        print("Reading channels:")
        if abf.sweepCount == 1:
            # Con una sola sweep, abf.data[ch] es exactamente la sweep 0 del canal.
            signals = abf.data
            for ch in range(channel_count):
                print(f"  Channel {ch}: {signals.shape[1]} points")
        else:
            # Con varias sweeps hay que armar la matriz con la sweep 0 de cada
            # canal, que no coincide con abf.data. Se escribe en un arreglo ya
            # reservado para no apilar copias al final.
            abf.setSweep(sweepNumber=0, channel=0)
            primer_canal = abf.sweepY
            n_muestras = len(primer_canal)
            signals = np.empty((channel_count, n_muestras), dtype=primer_canal.dtype)
            signals[0, :] = primer_canal
            print(f"  Channel 0: {n_muestras} points")
            for ch in range(1, channel_count):
                abf.setSweep(sweepNumber=0, channel=ch)
                y = abf.sweepY
                if len(y) != n_muestras:
                    raise ValueError(
                        f"El canal {ch} tiene {len(y)} muestras y el canal 0 tiene {n_muestras}; "
                        f"no se puede armar una matriz con canales de distinto largo.")
                signals[ch, :] = y
                print(f"  Channel {ch}: {len(y)} points")

        # Se toma al final y sin copiar: ningun setSweep posterior lo altera.
        abf.setSweep(sweepNumber=0, channel=0)
        time_data = abf.sweepX
        print(f"Obtained time data, length: {len(time_data)}")
        print(f"Time range: {time_data[0]:.4f} - {time_data[-1]:.4f} s")

        channel_names = [str(n) for n in abf.adcNames]
        units = list(abf.adcUnits)
        print(f"Channel names: {channel_names}")
        print(f"Units: {units}")

        sampling_rate = float(abf.dataRate)
        print(f"Sampling rate: {sampling_rate} Hz")
        print("ABF processed successfully")

        ds = SignalDataset(
            name=Path(file_path).name,
            format="abf",
            source_path=file_path,
            sampling_rate=sampling_rate,
            time=time_data,
            signals=signals,
            channel_names=channel_names,
            units=units,
            metadata={
                "sweepCount": abf.sweepCount,
                "channelCount": channel_count,
                "protocolPath": getattr(abf, 'protocolPath', None),
            },
            sampling_rate_source="header",
            original_sampling_rate=sampling_rate,
        )
        return ds
    
    
    def load_edf(self, file_path: str) -> SignalDataset:

        print(f"\n=== Loading EDF file: {file_path} ===")
        edf = pyedflib.EdfReader(file_path)

        try:
            C = edf.signals_in_file
            print(f"Detected channel count: {C}")

            # Primero solo la cabecera: nombres, unidades, frecuencias y largos.
            # Asi se puede decidir la forma de la matriz y reservarla antes de
            # leer datos. Antes se leian los C canales a una lista y se apilaban
            # con np.stack, lo que dejaba la lista y la copia apilada vivas a la
            # vez: el doble de memoria (problema nº 12). En el camino de
            # remuestreo era peor, porque `signals_raw` seguia vivo mientras se
            # construia `resampled`: hasta el triple.
            channel_names = []
            units = []
            fs_list = []
            n_list = []
            durations = []

            n_samples_cabecera = edf.getNSamples()
            print("Reading channel headers:")
            for i in range(C):
                fs_i = float(edf.samplefrequency(i))
                name_i = edf.getLabel(i).strip() or f"ch{i}"
                unit_i = edf.getPhysicalDimension(i).strip() or "uV"
                n_i = int(n_samples_cabecera[i])

                channel_names.append(str(name_i))
                units.append(str(unit_i))
                fs_list.append(fs_i)
                n_list.append(n_i)
                durations.append(n_i / fs_i)
                print(f"  Channel {i}: {n_i} points, fs={fs_i}Hz, name={name_i}, unit={unit_i}")

            same_fs = all(abs(f - fs_list[0]) < 1e-9 for f in fs_list)
            same_len = len(set(n_list)) == 1

            if same_fs and same_len:
                sampling_rate = fs_list[0]
                N = n_list[0]
                time = np.arange(N, dtype=np.float64) / sampling_rate
                signals = np.empty((C, N), dtype=np.float64)
                for i in range(C):
                    sig = edf.readSignal(i)
                    if len(sig) != N:
                        raise ValueError(
                            f"El canal {i} declara {N} muestras en la cabecera pero entrega "
                            f"{len(sig)}; el archivo EDF es inconsistente.")
                    signals[i, :] = sig
                print("EDF with uniform fs and length.")
            else:
                print("Warning: Channels with different fs/lengths. Resampling…")
                sampling_rate = float(min(fs_list))
                T_common = float(min(durations))
                N = int(np.floor(T_common * sampling_rate))
                time = np.arange(N, dtype=np.float64) / sampling_rate

                # Se interpola canal por canal directo en la fila que le toca,
                # de modo que solo un canal crudo esta vivo a la vez.
                signals = np.empty((C, N), dtype=np.float64)
                for i in range(C):
                    sig = edf.readSignal(i)
                    t_i = np.arange(sig.shape[0], dtype=np.float64) / fs_list[i]
                    signals[i, :] = np.interp(time, t_i, sig)

            print(f"Time data created: {len(time)} points")
            print(f"Time range: {time[0]:.4f} - {time[-1]:.4f} s")
            print(f"Sampling rate (common): {sampling_rate} Hz")

            ds = SignalDataset(
                name=Path(file_path).name,
                format="edf",
                source_path=file_path,
                sampling_rate=sampling_rate,
                time=time,
                signals=signals,
                channel_names=channel_names,
                units=units,
                metadata={
                    "channelCount": C,
                    "fs_list": fs_list,
                    "uniform": same_fs and same_len,
                },
                sampling_rate_source="header",
                original_sampling_rate=sampling_rate,
            )
            print("EDF processed successfully")
            return ds

        finally:
            edf.close()


    def load_mat(self, file_path: str) -> SignalDataset:
        """
        Load a MATLAB (.mat) file and convert it into a SignalDataset.
        Supports both classic format (scipy) and v7.3 (HDF5).
        """
        print(f"\n=== Loading MAT file: {file_path} ===")

        try:
            # Try classic format first
            mat_data = loadmat(file_path)
            valid_keys = [k for k in mat_data.keys() if not k.startswith("__")]
            print("File loaded with scipy.io.loadmat")
            print(f"Found variables: {valid_keys}")

            data_key = None
            for key in valid_keys:
                arr = mat_data[key]
                if (
                    isinstance(arr, np.ndarray)
                    and arr.ndim in (1, 2)
                    and arr.size > 1
                    and np.issubdtype(arr.dtype, np.number)
                ):
                    data_key = key
                    break
            if data_key is None:
                raise ValueError("No numeric data matrix found in the .mat file")

            raw = np.asarray(mat_data[data_key], dtype=np.float64)
            if raw.ndim == 1:
                signals = raw.reshape(1, -1)
            else:
                # MATLAB files from this lab store samples x channels (far more
                # samples than channels); the model expects channels x samples.
                signals = raw.T if raw.shape[0] >= raw.shape[1] else raw

            C, N = signals.shape
            channel_names = [f"ch{i + 1}" for i in range(C)]
            sampling_rate = 1.0  # .mat files don't carry it (R80); corrected via CU-018
            time_data = np.arange(N, dtype=np.float64) / sampling_rate

            ds = SignalDataset(
                name=Path(file_path).name,
                format="mat",
                source_path=file_path,
                sampling_rate=sampling_rate,
                time=time_data,
                signals=signals,
                channel_names=channel_names,
                units=["a.u."] * C,
                metadata={"variable": data_key, "variables": valid_keys},
                sampling_rate_source="default",
                original_sampling_rate=None,
            )
            print(f"MAT file processed successfully (classic format, variable='{data_key}').")
            return ds
        except NotImplementedError:
            with h5py.File(file_path, "r") as f:
                print(".mat file in HDF5 (v7.3) format. Loading with h5py...")
                keys = list(f.keys())
                print(f"Found variables (HDF5): {keys}")

                # Filter valid numeric channels
                channels = []
                channel_names = []

                for key in keys:
                    data = f[key]
                    if not isinstance(data, h5py.Dataset):
                        continue

                    arr = np.array(data)

                    # Check if the dataset is numeric
                    if np.issubdtype(arr.dtype, np.number):
                        channels.append(arr.flatten())
                        channel_names.append(key)
                        print(f"  Channel {key}: {len(arr.flatten())} samples")
                    else:
                        print(f"  ⚠️ Variable {key} ignored (non-numeric, dtype {arr.dtype})")

                if not channels:
                    raise ValueError("No numeric channels found in the .mat file")

                # Normalize length (pad with NaN to equalize)
                max_len = max(len(ch) for ch in channels)
                padded = [np.pad(ch, (0, max_len - len(ch)), constant_values=np.nan) for ch in channels]
                signals = np.stack(padded, axis=0)

                # Generate a dummy time axis if not present
                time_data = np.arange(max_len, dtype=float)
                sampling_rate = 1.0  # unknown

                ds = SignalDataset(
                    name=Path(file_path).name,
                    format="mat",
                    source_path=file_path,
                    sampling_rate=sampling_rate,
                    time=time_data,
                    signals=signals,
                    channel_names=channel_names,
                    units=["a.u."] * len(channel_names),
                    metadata={"variables": keys},
                    sampling_rate_source="default",
                    original_sampling_rate=None,
                )

                print("MAT file processed successfully.")
                return ds

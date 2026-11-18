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

        print("Reading channels:")
        if abf.sweepCount == 1:
            signals = abf.data
            for ch in range(channel_count):
                print(f"  Channel {ch}: {signals.shape[1]} points")
        else:
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
                signals = raw.T if raw.shape[0] >= raw.shape[1] else raw

            C, N = signals.shape
            channel_names = [f"ch{i + 1}" for i in range(C)]
            sampling_rate = 1.0
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

                channels = []
                channel_names = []

                for key in keys:
                    data = f[key]
                    if not isinstance(data, h5py.Dataset):
                        continue

                    clase = data.attrs.get("MATLAB_class", b"")
                    clase = clase.decode(errors="replace") if isinstance(clase, bytes) else str(clase)
                    arr = np.array(data)

                    if clase == "char" or not np.issubdtype(arr.dtype, np.number):
                        print(f"  Variable {key} ignorada (no numérica: {clase or arr.dtype})")
                        continue
                    if arr.size <= 1 or arr.ndim > 2:
                        print(f"  Variable {key} ignorada (forma {arr.shape}: no es un vector ni una matriz)")
                        continue

                    raw = np.asarray(arr, dtype=np.float64).T
                    if raw.ndim == 1:
                        filas = raw.reshape(1, -1)
                    else:
                        filas = raw.T if raw.shape[0] >= raw.shape[1] else raw

                    if filas.shape[0] == 1:
                        channels.append(filas[0])
                        channel_names.append(key)
                    else:
                        for i, fila in enumerate(filas, start=1):
                            channels.append(fila)
                            channel_names.append(f"{key}_ch{i}")
                    print(f"  Variable {key}: {filas.shape[0]} canal(es) de {filas.shape[1]} muestras")

                if not channels:
                    raise ValueError("No se encontró ningún vector ni matriz numérica en el archivo .mat (v7.3).")

                max_len = max(len(ch) for ch in channels)
                padded = [np.pad(ch, (0, max_len - len(ch)), constant_values=np.nan) for ch in channels]
                signals = np.stack(padded, axis=0)

                time_data = np.arange(max_len, dtype=float)
                sampling_rate = 1.0

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

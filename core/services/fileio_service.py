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

        time_data = abf.sweepX.copy()
        print(f"Obtained time data, length: {len(time_data)}")
        print(f"Time range: {time_data[0]:.4f} - {time_data[-1]:.4f} s")

        signal_rows = []
        print("Reading channels:")
        for ch in range(channel_count):
            abf.setSweep(sweepNumber=0, channel=ch)
            y = abf.sweepY.copy()
            signal_rows.append(y)
            print(f"  Channel {ch}: {len(y)} points")

        signals = np.stack(signal_rows, axis=0)

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
        )
        return ds
    
    
    def load_edf(self, file_path: str) -> SignalDataset:

        print(f"\n=== Loading EDF file: {file_path} ===")
        edf = pyedflib.EdfReader(file_path)

        try:
            C = edf.signals_in_file
            print(f"Detected channel count: {C}")

            signals_raw = []
            channel_names = []
            units = []
            fs_list = []
            durations = []

            print("Reading channels:")
            for i in range(C):
                sig = edf.readSignal(i)
                fs_i = float(edf.samplefrequency(i))
                name_i = edf.getLabel(i).strip() or f"ch{i}"
                unit_i = edf.getPhysicalDimension(i).strip() or "uV"

                signals_raw.append(np.asarray(sig, dtype=np.float64))
                channel_names.append(str(name_i))
                units.append(str(unit_i))
                fs_list.append(fs_i)
                durations.append(len(sig) / fs_i)
                print(f"  Channel {i}: {len(sig)} points, fs={fs_i}Hz, name={name_i}, unit={unit_i}")

            same_fs = all(abs(f - fs_list[0]) < 1e-9 for f in fs_list)
            same_len = len({len(s) for s in signals_raw}) == 1

            if same_fs and same_len:
                sampling_rate = fs_list[0]
                N = len(signals_raw[0])
                time = np.arange(N, dtype=np.float64) / sampling_rate
                signals = np.stack(signals_raw, axis=0) 
                print("EDF with uniform fs and length.")
            else:
                print("Warning: Channels with different fs/lengths. Resampling…")
                sampling_rate = float(min(fs_list))
                T_common = float(min(durations))
                N = int(np.floor(T_common * sampling_rate))
                time = np.arange(N, dtype=np.float64) / sampling_rate

                resampled = []
                for sig, fs_i in zip(signals_raw, fs_list):
                    t_i = np.arange(sig.shape[0], dtype=np.float64) / fs_i
                    y_i = np.interp(time, t_i, sig)
                    resampled.append(y_i.astype(np.float64))
                signals = np.stack(resampled, axis=0)

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
                )

                print("MAT file processed successfully.")
                return ds

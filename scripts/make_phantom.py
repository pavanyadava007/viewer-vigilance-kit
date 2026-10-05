"""Generate small synthetic DICOM test series (deterministic, no patient data).

tests/data/phantom_axial/    8 axial CT-like slices, 64x64, uint16 + intercept -1024,
                             anisotropic PixelSpacing (0.8 row, 0.5 col), multi-valued
                             window tags, file names in an order unrelated to position.
tests/data/phantom_sagittal/ 5 sagittal slices (all z equal), positions along x.
tests/data/mono1.dcm         one MONOCHROME1 image with a known gradient.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, generate_uid

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests/data"


def _uid(*parts: str) -> str:
    return generate_uid(entropy_srcs=["viewer-vigilance-kit", *parts])


def make_ds(pixels: np.ndarray, key: str, **tags) -> FileDataset:
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = CTImageStorage
    meta.MediaStorageSOPInstanceUID = _uid(key)
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset(key, {}, file_meta=meta, preamble=b"\0" * 128)
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID = _uid("study")
    ds.PatientName = "PHANTOM^SYNTHETIC"
    ds.PatientID = "PHANTOM0001"
    ds.Modality = "CT"
    ds.Rows, ds.Columns = pixels.shape
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = tags.pop("PhotometricInterpretation", "MONOCHROME2")
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    for k, v in tags.items():
        setattr(ds, k, v)
    ds.PixelData = pixels.astype(np.uint16).tobytes()
    return ds


def axial() -> None:
    d = OUT / "phantom_axial"
    d.mkdir(parents=True, exist_ok=True)
    n, size = 8, 64
    # file names deliberately not in spatial order
    names = ["k3", "a7", "q1", "c5", "z0", "m6", "b2", "x4"]
    yy, xx = np.mgrid[0:size, 0:size]
    for i in range(n):
        hu = np.full((size, size), -1000.0)  # air
        body = (yy - 32) ** 2 / 26**2 + (xx - 32) ** 2 / 28**2 <= 1
        hu[body] = 40.0  # soft tissue
        hu[(yy - 32) ** 2 + (xx - 32) ** 2 <= 36] = 700.0  # "bone" core
        hu[20:26, 44:50] = 300.0  # marker on patient left (high column index)
        hu[40 : 40 + i + 1, 10:14] = 1000.0  # bar whose length encodes the slice index
        raw = np.round(hu + 1024).astype(np.uint16)
        ds = make_ds(
            raw,
            f"axial{i}",
            SeriesInstanceUID=_uid("axial"),
            InstanceNumber=i + 1,
            ImagePositionPatient=[-25.6, -16.0, -10.0 + 2.5 * i],
            ImageOrientationPatient=[1, 0, 0, 0, 1, 0],
            PixelSpacing=[0.8, 0.5],
            SliceThickness=2.5,
            RescaleIntercept=-1024,
            RescaleSlope=1,
            WindowCenter=[40, -600],
            WindowWidth=[400, 1500],
        )
        ds.save_as(d / f"{names[i]}.dcm", enforce_file_format=True)


def sagittal() -> None:
    d = OUT / "phantom_sagittal"
    d.mkdir(parents=True, exist_ok=True)
    names = ["s_d", "s_b", "s_e", "s_a", "s_c"]
    for i in range(5):
        raw = np.full((48, 48), 100 + 200 * i, dtype=np.uint16)
        ds = make_ds(
            raw,
            f"sag{i}",
            SeriesInstanceUID=_uid("sagittal"),
            InstanceNumber=i + 1,
            # row direction = +y (posterior), column direction = -z (towards feet)
            ImageOrientationPatient=[0, 1, 0, 0, 0, -1],
            ImagePositionPatient=[-4.0 + 2.0 * i, -100.0, 50.0],
            PixelSpacing=[1.0, 1.0],
        )
        ds.save_as(d / f"{names[i]}.dcm", enforce_file_format=True)


def mono1() -> None:
    raw = np.tile(np.arange(0, 256, 4, dtype=np.uint16), (16, 1))  # 16 x 64 ramp 0..252
    ds = make_ds(
        raw,
        "mono1",
        PhotometricInterpretation="MONOCHROME1",
        SeriesInstanceUID=_uid("mono1"),
        InstanceNumber=1,
        PixelSpacing=[0.2, 0.2],
        WindowCenter=128,
        WindowWidth=256,
    )
    ds.save_as(OUT / "mono1.dcm", enforce_file_format=True)


if __name__ == "__main__":
    axial()
    sagittal()
    mono1()
    print("wrote", sorted(p.relative_to(ROOT).as_posix() for p in OUT.rglob("*.dcm")))

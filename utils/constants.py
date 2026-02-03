import numpy as np

# 門口多邊形區域（左上、右上、右下、左下）
ENTRY_ROI = np.array([
    (  1, 300),
    ( 25, 290),
    (100, 330),
    (250, 340),
    (510, 650),
    (1000, 720),
    ( 1, 720),
], np.int32)

ENTRY_ROI_PTS = ENTRY_ROI.reshape((-1, 1, 2))

# 店內多邊形區域（左上、右上、右下、左下）
INSIDE_ROI = np.array([
    (1,    301),
    (1, 1),
    (1280, 1),
    (1280, 720),
    (1001, 720),
    (511, 649),
    (251, 339),
    (101, 329),
    ( 26, 289),
], np.int32)

INSIDE_ROI_PTS = INSIDE_ROI.reshape((-1, 1, 2))

# 連續幾幀沒看到才算離店
MAX_DISAPPEAR = 5

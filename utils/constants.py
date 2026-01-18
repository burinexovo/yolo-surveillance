import numpy as np

# 門口多邊形區域（左上、右上、右下、左下）
ENTRY_ROI = np.array([
    (0,   0),
    (1920, 0),
    (1920, 300),
    (0,   300)
], np.int32)

ENTRY_ROI_PTS = ENTRY_ROI.reshape((-1, 1, 2))

# 店內多邊形區域（左上、右上、右下、左下）
INSIDE_ROI = np.array([
    (0,    300),
    (1920, 300),
    (1920, 1080),
    (0,    1080)
], np.int32)

INSIDE_ROI_PTS = INSIDE_ROI.reshape((-1, 1, 2))

# 連續幾幀沒看到才算離店
MAX_DISAPPEAR = 5

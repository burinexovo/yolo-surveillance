import os
import torch
import numpy as np
import cv2
import torchreid
from torchvision import transforms
from PIL import Image

# 設置路徑
DATA_ROOT = 'datasets'
OUTPUT_FILE = os.path.join(DATA_ROOT, 'gallery_features.npy')
USE_GPU = True


# 初始化 ReID 模型和預處理
def initialize_reid_model(use_gpu=USE_GPU):
    # device = 'cuda' if use_gpu and torch.cuda.is_available() else ('mps' if torch.backends.mps.is_available() else 'cpu')
    if use_gpu and torch.cuda.is_available():
        device = "cuda"
    elif torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"
    
    print(f"Using device for feature extraction: {device}")

    # 使用 OSNet 作為特徵提取器
    model = torchreid.models.build_model(
        name='osnet_x1_0',
        num_classes=1000,
        pretrained=True
    )
    model.to(device)
    model.eval()

    transform = transforms.Compose([
        transforms.Resize((256, 128)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[
                             0.229, 0.224, 0.225]),
    ])

    return model, transform, device


def extract_feature(img_path, model, transform, device):
    """讀取單張圖片並提取特徵"""
    img = cv2.imread(img_path)
    if img is None:
        print(f"Warning: 圖片讀取失敗: {img_path}")
        return None

    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

    input_tensor = transform(img_pil).unsqueeze(0).to(device)

    with torch.no_grad():
        feature = model(input_tensor)
        # 正規化特徵，這是 ReID 比對的標準步驟
        feature = feature.div(feature.norm(p=2, dim=1, keepdim=True))

    return feature.squeeze(0).cpu().numpy()  # 轉為 numpy array 方便儲存


def generate_gallery_features():
    model, transform, device = initialize_reid_model()

    gallery = {}

    # 遍歷 photos 資料夾下的每個子資料夾（代表一個人）
    person_dirs = [d for d in os.listdir(DATA_ROOT)
                   if os.path.isdir(os.path.join(DATA_ROOT, d))]
    print(person_dirs)

    if not person_dirs:
        print(f"Error: 在 {DATA_ROOT} 中沒有找到任何人物資料夾。請確認資料結構。")
        return

    print(f"Found {len(person_dirs)} identities to process.")

    # for person_name in person_dirs:
    #     person_path = os.path.join(DATA_ROOT, person_name)
    #     features_list = []
    #     image_count = 0

    #     # 遍歷該人物資料夾下的所有圖片
    #     for filename in os.listdir(person_path):
    #         if filename.endswith(('.jpg', '.png', '.jpeg')):
    #             img_path = os.path.join(person_path, filename)
    #             feature = extract_feature(img_path, model, transform, device)

    #             if feature is not None:
    #                 features_list.append(feature)
    #                 image_count += 1

    #     if features_list:
    #         # 儲存 (N, D) 結構的 numpy array，N是圖片數量，D是特徵維度
    #         gallery[person_name] = np.array(features_list)
    #         print(f"-> {person_name}: 提取了 {image_count} 張圖片的特徵。")
    #     else:
    #         print(f"-> {person_name}: 沒有提取到有效的特徵。")

    # # 儲存特徵字典
    # if gallery:
    #     np.save(OUTPUT_FILE, gallery)
    #     print(f"\n✅ 特徵提取完成！數據已成功儲存至 {OUTPUT_FILE}")
    # else:
    #     print("\n⚠️ 特徵庫為空，未儲存檔案。")


if __name__ == '__main__':
    generate_gallery_features()

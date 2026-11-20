# Brain MRI model training (Google Colab recommended)

## 1. Dataset

Use a brain MRI dataset with clear usage terms and labels. The training script expects:

```text
brain-tumor-dataset/
  Training/
    glioma/
    meningioma/
    notumor/
    pituitary/
  Testing/
    glioma/
    meningioma/
    notumor/
    pituitary/
```

The class folder names are read automatically. Do not mix classes or rename labels without checking the dataset documentation. Do not upload identifiable patient data to a public notebook.

## 2. Google Colab

1. Open Google Colab and choose Runtime -> Change runtime type -> T4 GPU (if available).
2. Upload this project's `train.py` or clone/copy the project into the notebook.
3. Install dependencies:

```python
!pip install tensorflow==2.16.2 scikit-learn
```

4. Put the dataset in Colab storage or mount Google Drive. Then run (adjust the path):

```python
!python train.py --data-dir /content/brain-tumor-dataset --epochs 12
```

5. Download the entire generated `model` folder, including `brain_mri_model.keras` and `metadata.json`.

## 3. Connect the model locally

Copy both generated files into:

```text
MedVisionAI/ml/mri/brain_tumor/model/
```

In the same Python environment used to run FastAPI, install inference dependencies:

```powershell
python -m pip install -r ..\ml\mri\brain_tumor\requirements.txt
```

Run the backend from its `backend` directory. The API automatically looks for the model at the path above. Alternatively set `MEDVISION_MRI_MODEL` to the absolute `.keras` model path before starting FastAPI.

Check readiness at:

```text
http://127.0.0.1:8000/api/model-status?modality=Brain%20MRI&task=Brain%20tumour%20screening
```

## Important limitations

- This script uses the dataset's existing `Training` and `Testing` folders and makes a validation split from `Training`. If patient IDs are available, split by patient, not by image. Many public teaching datasets do not include patient identifiers; results from those datasets are not evidence of clinical generalization.
- The test metrics are only descriptive of the supplied held-out dataset. They are not clinical validation and must not be presented as diagnostic accuracy for real-world patients.
- The four output classes are dataset labels. A model trained on 2D images cannot automatically interpret every MRI sequence or diagnose stroke.
- Brain tumour screening is the only MRI task wired in this starter integration. Stroke, X-ray, CT and ultrasound remain unconnected until separately trained, evaluated and integrated.
- Confidence is the model's softmax score, not calibrated clinical certainty.
- Grad-CAM is an explanation visualization, not proof that a highlighted area is a tumour.

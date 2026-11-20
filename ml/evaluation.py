def evaluate_predictions(y_true, y_pred):
    \"\"\"Calculate basic metrics after installing scikit-learn in the ML environment.\"\"\"
    try:
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
    except ImportError as exc:
        raise RuntimeError("Install scikit-learn in your ML environment first.") from exc
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist()
    }

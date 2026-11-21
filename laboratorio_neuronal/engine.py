"""Motor experimental SIAI: modelos de referencia, regresión ridge y validación temporal.

El núcleo usa solo la biblioteca estándar. PyTorch es opcional y se carga únicamente
cuando se solicita un modelo neuronal o una PINN. Las filas deben estar ordenadas
cronológicamente antes de ejecutar el experimento.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Callable, Sequence


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Resuelve Ax=b mediante eliminación gaussiana con pivoteo parcial."""
    a = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
    n = len(vector)
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-12:
            raise ValueError("Matriz singular: reduzca variables o aumente regularización.")
        a[col], a[pivot] = a[pivot], a[col]
        scale = a[col][col]
        a[col] = [v / scale for v in a[col]]
        for row in range(n):
            if row == col:
                continue
            factor = a[row][col]
            if factor:
                a[row] = [x - factor * y for x, y in zip(a[row], a[col])]
    return [a[i][-1] for i in range(n)]


def _standardize(train: Sequence[Sequence[float]], other: Sequence[Sequence[float]]):
    means = [sum(row[j] for row in train) / len(train) for j in range(len(train[0]))]
    scales = []
    for j, mean in enumerate(means):
        variance = sum((row[j] - mean) ** 2 for row in train) / len(train)
        scales.append(math.sqrt(variance) or 1.0)
    transform = lambda rows: [[(row[j] - means[j]) / scales[j] for j in range(len(means))] for row in rows]
    return transform(train), transform(other), means, scales


def _ridge_fit(x: Sequence[Sequence[float]], y: Sequence[float], alpha: float):
    width = len(x[0])
    # Intercept explícito; no se regulariza.
    design = [[1.0, *row] for row in x]
    gram = [[sum(r[i] * r[j] for r in design) for j in range(width + 1)] for i in range(width + 1)]
    rhs = [sum(r[i] * target for r, target in zip(design, y)) for i in range(width + 1)]
    for i in range(1, width + 1):
        gram[i][i] += alpha
    return _solve(gram, rhs)


def _predict(coefficients, x):
    return [coefficients[0] + sum(c * v for c, v in zip(coefficients[1:], row)) for row in x]


def metrics(actual: Sequence[float], predicted: Sequence[float]) -> dict:
    errors = [p - y for y, p in zip(actual, predicted)]
    mae = sum(abs(e) for e in errors) / len(errors)
    rmse = math.sqrt(sum(e * e for e in errors) / len(errors))
    mean = sum(actual) / len(actual)
    total = sum((y - mean) ** 2 for y in actual)
    r2 = 1.0 - sum(e * e for e in errors) / total if total else None
    return {"mae": mae, "rmse": rmse, "r2": r2, "n": len(actual)}


def run_experiment(rows: Sequence[dict], target: str, features: Sequence[str],
                   test_fraction: float = 0.2, alpha: float = 1.0) -> dict:
    """Compara persistencia y ridge con partición temporal, sin mezclar pasado y futuro."""
    if len(rows) < 8:
        raise ValueError("Se requieren al menos 8 observaciones ordenadas cronológicamente.")
    if not features:
        raise ValueError("Debe indicarse al menos una variable explicativa.")
    if not 0.1 <= test_fraction <= 0.5:
        raise ValueError("test_fraction debe estar entre 0.1 y 0.5.")
    required = [target, *features]
    clean = []
    for index, row in enumerate(rows):
        try:
            values = [float(row[key]) for key in required]
            if not all(math.isfinite(v) for v in values):
                continue
            clean.append((index, values))
        except (KeyError, TypeError, ValueError):
            continue
    if len(clean) < 8:
        raise ValueError("Hay menos de 8 filas numéricas completas para las variables seleccionadas.")
    split = max(5, min(len(clean) - 2, int(len(clean) * (1 - test_fraction))))
    train, test = clean[:split], clean[split:]
    x_train = [[v for v in values[1:]] for _, values in train]
    y_train = [values[0] for _, values in train]
    x_test = [[v for v in values[1:]] for _, values in test]
    y_test = [values[0] for _, values in test]
    x_train_s, x_test_s, means, scales = _standardize(x_train, x_test)
    coefficients = _ridge_fit(x_train_s, y_train, alpha)
    ridge_predictions = _predict(coefficients, x_test_s)
    # Referencia ingenua: último valor observado antes del período de prueba.
    naive_predictions = [y_train[-1]] * len(y_test)
    return {
        "status": "completed",
        "method": "chronological_holdout",
        "target": target,
        "features": list(features),
        "observations": len(clean),
        "train_observations": len(train),
        "test_observations": len(test),
        "excluded_rows": len(rows) - len(clean),
        "models": {
            "persistence": {"metrics": metrics(y_test, naive_predictions)},
            "ridge": {"metrics": metrics(y_test, ridge_predictions),
                      "coefficients_standardized": coefficients},
        },
        "preprocessing": {"feature_means": means, "feature_scales": scales,
                          "ridge_alpha": alpha},
        "predictions": [{"actual": y, "persistence": n, "ridge": p}
                        for y, n, p in zip(y_test, naive_predictions, ridge_predictions)],
        "limitations": [
            "Experimento inicial: no sustituye una validación sectorial ni causal.",
            "Las filas deben estar ordenadas por fecha antes de cargar el CSV.",
            "La regresión ridge es una referencia interpretable, no una red neuronal.",
            "No se imputan faltantes: se excluyen filas incompletas y se informa su cantidad."
        ]
    }


def rolling_origin_backtest(rows: Sequence[dict], target: str, features: Sequence[str],
                            min_train: int = 6, horizon: int = 1, alpha: float = 1.0) -> dict:
    """Backtesting expansivo: cada pronóstico usa exclusivamente observaciones anteriores."""
    if horizon < 1 or min_train < 5 or len(rows) <= min_train + horizon:
        raise ValueError("Datos insuficientes o parámetros de backtesting inválidos.")
    folds = []
    for end in range(min_train, len(rows) - horizon + 1):
        train_rows = rows[:end]
        test_rows = rows[end:end + horizon]
        try:
            result = run_experiment(train_rows + test_rows, target, features,
                                    test_fraction=horizon / len(test_rows + train_rows), alpha=alpha)
            # run_experiment fija un holdout cronológico; se conserva el resultado de cada origen.
            folds.append({"origin": end, "metrics": result["models"]["ridge"]["metrics"]})
        except ValueError:
            continue
    if not folds:
        raise ValueError("No se pudieron construir ventanas válidas.")
    return {"method": "expanding_window", "folds": folds,
            "mean_rmse": sum(f["metrics"]["rmse"] for f in folds) / len(folds)}


def train_torch_mlp(rows: Sequence[dict], target: str, features: Sequence[str],
                    epochs: int = 300, learning_rate: float = 0.01, seed: int = 17) -> dict:
    """Entrena una MLP pequeña; requiere instalar el extra opcional PyTorch."""
    try:
        import torch
        from torch import nn
    except ImportError as exc:
        raise RuntimeError("PyTorch no está instalado. Instale requirements-neuronal.txt.") from exc
    torch.manual_seed(seed)
    clean = []
    for row in rows:
        try:
            vals = [float(row[k]) for k in [*features, target]]
            if all(math.isfinite(v) for v in vals):
                clean.append(vals)
        except (KeyError, TypeError, ValueError):
            continue
    if len(clean) < 12:
        raise ValueError("La MLP requiere al menos 12 filas numéricas completas.")
    split = max(8, min(len(clean) - 2, int(len(clean) * 0.8)))
    x = torch.tensor([r[:-1] for r in clean], dtype=torch.float32)
    y = torch.tensor([[r[-1]] for r in clean], dtype=torch.float32)
    mean, std = x[:split].mean(0), x[:split].std(0).clamp_min(1e-8)
    ym, ys = y[:split].mean(), y[:split].std().clamp_min(1e-8)
    x = (x - mean) / std
    y = (y - ym) / ys
    model = nn.Sequential(nn.Linear(len(features), 32), nn.Tanh(),
                          nn.Linear(32, 16), nn.Tanh(), nn.Linear(16, 1))
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    loss_fn = nn.MSELoss()
    for _ in range(epochs):
        model.train()
        optimizer.zero_grad()
        loss = loss_fn(model(x[:split]), y[:split])
        loss.backward()
        optimizer.step()
    model.eval()
    with torch.no_grad():
        predictions = (model(x[split:]) * ys + ym).flatten().tolist()
    actual = [r[-1] for r in clean[split:]]
    return {"model": "torch_mlp", "epochs": epochs, "train_observations": split,
            "test_observations": len(actual), "metrics": metrics(actual, predictions),
            "warning": "Resultado experimental; comparar con persistencia y ridge antes de utilizar."}


def pinn_residual_loss(model, coordinates, residual_fn: Callable):
    """Calcula pérdida física mediante una función residual definida por el dominio.

    residual_fn(model, coordinates) debe devolver residuos de ecuaciones físicas.
    No se impone una ecuación universal: cada aplicación debe aportar la suya.
    """
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch no está instalado. Instale requirements-neuronal.txt.") from exc
    coordinates = coordinates.detach().clone().requires_grad_(True)
    residual = residual_fn(model, coordinates)
    if not torch.is_tensor(residual):
        raise TypeError("residual_fn debe devolver un tensor de PyTorch.")
    return torch.mean(residual ** 2)


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Experimento neuronal y validación temporal SIAI")
    parser.add_argument("csv", type=Path, help="CSV ordenado cronológicamente")
    parser.add_argument("--target", required=True, help="Columna objetivo")
    parser.add_argument("--features", required=True, help="Columnas explicativas separadas por coma")
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--torch-mlp", action="store_true", help="Entrena además una MLP PyTorch opcional")
    args = parser.parse_args(argv)
    rows = read_csv(args.csv)
    features = [v.strip() for v in args.features.split(",") if v.strip()]
    output = run_experiment(rows, args.target, features, alpha=args.alpha)
    if args.torch_mlp:
        output["torch_mlp"] = train_torch_mlp(rows, args.target, features)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

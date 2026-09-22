"""Train a PyTorch model from random weights: python train.py --epochs 40."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import random
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler
from veitch.model import GroupModel, dataset, metrics, MODEL_PATH


def split_ids(seed):
    # Distinct functions across all three splits. Constants belong to the training set.
    ids = list(range(1, 65535))
    random.Random(seed).shuffle(ids)
    ids = [0, 65535] + ids
    return ids[:50000], ids[50000:58192], ids[58192:]


def train(epochs=40, seed=42, output=MODEL_PATH):
    if epochs < 1:
        raise ValueError("Количество эпох должно быть положительным.")
    torch.set_num_threads(1)
    train_ids, val_ids, test_ids = split_ids(seed)
    x, y = dataset(train_ids)
    xv, yv = dataset(val_ids)
    model = GroupModel(seed)
    optimizer = torch.optim.Adam(model.parameters(), lr=.002)
    # Sample uniformly by truth-table density so large groups appear often enough.
    density = x.sum(dim=1).long()
    counts = torch.bincount(density, minlength=17)
    sampling = counts[density].double().reciprocal()
    sampling /= sampling.sum()
    frequency = (y * sampling[:, None]).sum(dim=0)
    positive_weights = ((1 - frequency) / frequency.clamp_min(1e-5)).clamp(1, 20).float()
    criterion = nn.BCEWithLogitsLoss(pos_weight=positive_weights)
    sampler = WeightedRandomSampler(sampling, len(x), replacement=True,
                                    generator=torch.Generator().manual_seed(seed))
    loader = DataLoader(TensorDataset(x, y), batch_size=256, sampler=sampler,
                        generator=torch.Generator().manual_seed(seed))
    best_score, best_weights, best_epoch, history = -1, None, 0, []
    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.
        for xb, yb in loader:
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(xb), yb)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(xb)
        validation = metrics(model, xv, yv)
        score = 2 * validation["precision"] * validation["recall"] / max(
            validation["precision"] + validation["recall"], 1e-9)
        if score > best_score:
            best_score = score
            best_weights = deepcopy(model.state_dict())
            best_epoch = epoch
        row = {"epoch": epoch, "loss": total_loss / len(x), "validation": validation}
        history.append(row)
        print(f"Epoch {epoch:02}: loss={row['loss']:.5f}, val precision={validation['precision']:.4f}, "
              f"recall={validation['recall']:.4f}", flush=True)
    model.load_state_dict(best_weights)
    model.eval()
    model.save(output)
    xt, yt = dataset(test_ids)
    report = {"framework": "PyTorch", "torch_version": str(torch.__version__),
              "seed": seed, "epochs": epochs, "best_epoch": best_epoch,
              "split": "python.random.Random(seed).shuffle; constants in training",
              "architecture": "16 → 96 ReLU → 81 logits; sigmoid for inference",
              "objective": "valid Boolean cubes; density-balanced BCEWithLogitsLoss; torch.optim.Adam",
              "train_functions": len(x), "validation_functions": len(xv), "test_functions": len(xt),
              "test": metrics(model, xt, yt), "history": history,
              "note": "Model ranks groups; the exact solver guarantees minimum DNF independently."}
    Path(output).with_suffix(".json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["test"], indent=2), flush=True)
    return model, report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Обучение собственной сети PyTorch с нуля.")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=MODEL_PATH)
    args = parser.parse_args()
    train(args.epochs, args.seed, args.output)

"""PyTorch group scorer, initialized and trained from scratch."""
from pathlib import Path
import torch
from torch import nn
from .logic import cubes

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "groups.pt"


class GroupModel(nn.Module):
    def __init__(self, seed=42):
        super().__init__()
        # Reproducible initialization without changing the caller's CPU RNG state.
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed)
            self.network = nn.Sequential(nn.Linear(16, 96), nn.ReLU(), nn.Linear(96, 81))

    def forward(self, x):
        """Return logits; BCEWithLogitsLoss applies the sigmoid during training."""
        return self.network(x)

    @torch.inference_mode()
    def predict(self, function):
        n = len(function.variables)
        x = torch.tensor([[int((i >> (4 - n)) in function.ones) for i in range(16)]],
                         dtype=torch.float32, device=next(self.parameters()).device)
        probabilities = self(x).sigmoid()[0].tolist()
        all_scores = {p: score for (p, _), score in zip(cubes(4), probabilities)}
        return {p: all_scores[p + (-1,) * (4 - n)] for p, _ in cubes(n)}

    def save(self, path=MODEL_PATH):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"version": 2, "state_dict": {
            key: value.detach().cpu() for key, value in self.state_dict().items()}}, path)

    @classmethod
    def load(cls, path=MODEL_PATH):
        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
        if not isinstance(checkpoint, dict) or checkpoint.get("version") != 2:
            raise ValueError("Неподдерживаемая версия модели.")
        model = cls()
        state = checkpoint.get("state_dict")
        expected = model.state_dict()
        if not isinstance(state, dict) or state.keys() != expected.keys():
            raise ValueError("Повреждены параметры модели.")
        for key, tensor in state.items():
            if (not isinstance(tensor, torch.Tensor) or tensor.shape != expected[key].shape
                    or tensor.dtype != expected[key].dtype or not torch.isfinite(tensor).all()):
                raise ValueError("Повреждены параметры модели.")
        model.load_state_dict(state, strict=True)
        return model.eval()


def dataset(ids):
    """Function ID's bit i is its value on assignment i; labels mark valid cubes."""
    ids = torch.as_tensor(ids, dtype=torch.int64)
    x = ((ids[:, None] >> torch.arange(16)) & 1).float()
    masks = torch.tensor([mask for _, mask in cubes(4)], dtype=torch.int64)
    y = ((ids[:, None] & masks) == masks).float()
    return x, y


@torch.inference_mode()
def metrics(model, x, y):
    was_training = model.training
    model.eval()
    try:
        prediction = model(x) >= 0
        positive = y.bool()
        tp = int((prediction & positive).sum())
        return {"precision": tp / max(int(prediction.sum()), 1),
                "recall": tp / max(int(positive.sum()), 1),
                "all_groups_exact": (prediction == positive).all(dim=1).float().mean().item()}
    finally:
        model.train(was_training)

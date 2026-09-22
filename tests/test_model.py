import tempfile
from pathlib import Path
import unittest
import torch
from torch import nn
from train import split_ids, train
from veitch.model import GroupModel, dataset, metrics, MODEL_PATH
from veitch.logic import parse
from veitch.service import solve

torch.set_num_threads(1)


class ModelTests(unittest.TestCase):
    def test_splits_are_disjoint_and_exhaustive(self):
        a, b, c = map(set, split_ids(42))
        self.assertFalse(a & b or a & c or b & c)
        self.assertEqual(a | b | c, set(range(65536)))

    def test_labels(self):
        x, y = dataset([0, 65535])
        self.assertFalse(x[0].any())
        self.assertTrue(x[1].all())
        self.assertFalse(y[0].any())
        self.assertTrue(y[1].all())

    def test_training_updates_all_layers_and_reduces_loss(self):
        model = GroupModel()
        x, y = dataset([0, 3, 65535, 731])
        criterion = nn.BCEWithLogitsLoss(pos_weight=torch.full((81,), 2.))
        optimizer = torch.optim.Adam(model.parameters(), lr=.01)
        before = criterion(model(x), y).item()
        initial = {key: value.clone() for key, value in model.state_dict().items()}
        for _ in range(40):
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(x), y)
            loss.backward()
            self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all()
                                for p in model.parameters()))
            optimizer.step()
        self.assertLess(criterion(model(x), y).item(), before * .5)
        for key, value in model.state_dict().items():
            self.assertFalse(torch.equal(value, initial[key]), key)

    def test_save_load(self):
        model = GroupModel()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.pt"
            model.save(path)
            loaded = GroupModel.load(path)
        self.assertFalse(loaded.training)
        self.assertEqual(model.predict(parse("A+B")), loaded.predict(parse("A+B")))

    def test_corrupt_checkpoint_rejected(self):
        model = GroupModel()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.pt"
            torch.save({"version": 1, "state_dict": model.state_dict()}, path)
            with self.assertRaises(ValueError):
                GroupModel.load(path)
            state = model.state_dict()
            state["network.0.weight"][0, 0] = float("nan")
            torch.save({"version": 2, "state_dict": state}, path)
            with self.assertRaises(ValueError):
                GroupModel.load(path)

    def test_seed_reproducible_and_inference_has_no_gradients(self):
        a, b, c = GroupModel(42), GroupModel(42), GroupModel(43)
        for key, value in a.state_dict().items():
            torch.testing.assert_close(value, b.state_dict()[key], rtol=0, atol=0)
        self.assertFalse(torch.equal(a.network[0].weight, c.network[0].weight))
        a.predict(parse("A+B"))
        self.assertTrue(all(p.grad is None for p in a.parameters()))

    def test_training_pipeline_saves_reloadable_checkpoint_and_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trained.pt"
            model, report = train(epochs=1, output=path)
            loaded = GroupModel.load(path)
            self.assertEqual(report["framework"], "PyTorch")
            self.assertEqual(report["test_functions"], 7344)
            self.assertTrue(path.with_suffix(".json").exists())
            self.assertEqual(model.predict(parse("A^B")), loaded.predict(parse("A^B")))

    def test_trained_checkpoint_on_unseen_functions(self):
        self.assertTrue(MODEL_PATH.exists(), "Сначала выполните python train.py")
        model = GroupModel.load()
        _, _, test_ids = split_ids(42)
        result = metrics(model, *dataset(test_ids))
        self.assertGreater(result["precision"], .99)
        self.assertGreater(result["recall"], .99)
        self.assertEqual(solve("A*B+A*!B", model)["formula"], "A")
        for source in ["0", "1", "A^B", "A+B*C", "F(A,B,C,D)=!B*!D"]:
            a, b = solve(source, model), solve(source)
            self.assertEqual((a["terms"], a["literals"]), (b["terms"], b["literals"]))

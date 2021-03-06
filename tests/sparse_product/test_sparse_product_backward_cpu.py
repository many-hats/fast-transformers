#
# Copyright (c) 2020 Idiap Research Institute, http://www.idiap.ch/
# Written by Angelos Katharopoulos <angelos.katharopoulos@idiap.ch>,
# Apoorv Vyas <avyas@idiap.ch>
#

import os
import time
from os import getenv
import unittest

import torch

from fast_transformers.sparse_product import sparse_dot_product


class TestSparseProductBackward(unittest.TestCase):
    @property
    def device(self):
        return "cpu"

    def _zero_grad(self, Q, K):
        for x in [Q, K]:
            if x.grad is not None:
                x.grad[...] = 0

    def test_simple_grad(self):
        N = 2
        H = 4
        L = 100
        S = 100
        E = 32
        k = 10
        Q = torch.randn(N, H, L, E).to(self.device).requires_grad_(True)
        K = torch.randn(N, H, S, E).to(self.device).requires_grad_(True)
        topk = torch.round(
                torch.cumsum(torch.rand(N, H, L, k)*10, dim=-1)
            ).long().to(self.device)

        self._zero_grad(Q, K)
        QK_full = torch.einsum("nhle,nhse->nhls", Q, K)
        QK_selected = QK_full[
            torch.arange(N).view(N, 1, 1, 1).to(self.device),
            torch.arange(H).view(1, H, 1, 1).to(self.device),
            torch.arange(L).view(1, 1, L, 1).to(self.device),
            topk
        ]
        QK_selected.sum().backward()
        grad = [torch.clone(Q.grad), torch.clone(K.grad)]

        self._zero_grad(Q, K)
        QK_selected_hat = sparse_dot_product(Q, K, topk)
        QK_selected_hat.sum().backward()
        grad_hat = [torch.clone(Q.grad), torch.clone(K.grad)]

        self.assertLess(
            torch.abs(QK_selected - QK_selected_hat).max(),
            1e-4
        )
        for g1, g2 in zip(grad, grad_hat):
            self.assertLess(
                torch.abs(g1 - g2).max(),
                1e-4
            )

    @unittest.skipUnless(os.getenv("BENCHMARK_TESTS", ""), "no benchmarks")
    def test_benchmark_forward(self):
        N = 12
        H = 8
        L = 1024
        S = 1024
        E = 32
        k = 32
        Q = torch.randn(N, H, L, E).to(self.device).requires_grad_(True)
        K = torch.randn(N, H, S, E).to(self.device).requires_grad_(True)
        topk = torch.round(
                torch.cumsum(torch.rand(N, H, L, k)*(S//k), dim=-1)
            ).long().to(self.device)
        n_runs = 10
        s = time.time()
        for i in range(n_runs):
            QK = torch.einsum("nhle,nhse->nhls", Q, K)
            QK.sum()
        e = time.time()
        t_full = (e - s) / n_runs

        s = time.time()
        for i in range(n_runs):
            QK = sparse_dot_product(Q, K, topk)
            QK.sum()
        e = time.time()
        t_sparse = (e - s) / n_runs
        print("Benchmark Forward: T_Full: {}, T_Sparse: {}".format(t_full, t_sparse))

    @unittest.skipUnless(os.getenv("BENCHMARK_TESTS", ""), "no benchmarks")
    def test_benchmark_forward_backward(self):
        N = 12
        H = 8
        L = 1024
        S = 1024
        E = 32
        k = 32
        Q = torch.randn(N, H, L, E).to(self.device).requires_grad_(True)
        K = torch.randn(N, H, S, E).to(self.device).requires_grad_(True)
        topk = torch.round(
                torch.cumsum(torch.rand(N, H, L, k)*(S//k), dim=-1)
            ).long().to(self.device)
        n_runs = 10
        self._zero_grad(Q, K)
        s = time.time()
        for i in range(n_runs):
            QK = torch.einsum("nhle,nhse->nhls", Q, K)
            QK.sum().backward()
        e = time.time()
        t_full = (e - s) / n_runs

        self._zero_grad(Q, K)
        s = time.time()
        for i in range(n_runs):
            QK = sparse_dot_product(Q, K, topk)
            QK.sum().backward()
        e = time.time()
        t_sparse = (e - s) / n_runs
        print("Benchmark Forward-Backward: T_Full: {}, T_Sparse: {}".format(t_full, t_sparse))


if __name__ == "__main__":
    unittest.main()

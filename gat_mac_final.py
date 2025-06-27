import torch
from torch_geometric.nn import GATConv
from torch_geometric.data import Data

# Принудительно используем CPU (пока PyG не поддерживает MPS полностью)
device = torch.device('cpu')
print(f"Используемое устройство: {device}")

# Тестовые данные
edge_index = torch.tensor([[0, 1, 1, 2], [1, 0, 2, 1]], dtype=torch.long, device=device)
x = torch.randn(3, 8, device=device)  # 3 узла, 8 признаков

# Упрощенная модель GAT
class StableGAT(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = GATConv(8, 16, heads=2)
        self.conv2 = GATConv(16*2, 32)
        
    def forward(self, x, edge_index):
        x = self.conv1(x, edge_index).relu()
        return self.conv2(x, edge_index)

model = StableGAT().to(device)
out = model(x, edge_index)
print(f"Вывод модели: {out.shape}")
print("✅ GAT стабильно работает на CPU")

# Проверка обучения
optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
for epoch in range(3):
    optimizer.zero_grad()
    out = model(x, edge_index)
    loss = out.mean()
    loss.backward()
    optimizer.step()
    print(f"Эпоха {epoch+1}, Loss: {loss.item():.4f}")
# coding: UTF-8
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn import metrics
import time
import matplotlib.pyplot as plt
from utils import get_time_dif
from pytorch_pretrained.optimization import BertAdam


# 权重初始化
def init_network(model, method='xavier', exclude='embedding', seed=123):
    for name, w in model.named_parameters():
        if exclude not in name:
            if len(w.size()) < 2:
                continue
            if 'weight' in name:
                if method == 'xavier':
                    nn.init.xavier_normal_(w)
                elif method == 'kaiming':
                    nn.init.kaiming_normal_(w)
                else:
                    nn.init.normal_(w)
            elif 'bias' in name:
                nn.init.constant_(w, 0)


def train(config, model, train_iter, dev_iter, test_iter):
    start_time = time.time()
    model.train()

    # ======== 记录指标 ========
    train_losses, train_accs = [], []
    dev_losses, dev_accs = [], []

    param_optimizer = list(model.named_parameters())
    no_decay = ['bias', 'LayerNorm.bias', 'LayerNorm.weight']
    optimizer_grouped_parameters = [
        {'params': [p for n, p in param_optimizer if not any(nd in n for nd in no_decay)], 'weight_decay': 0.01},
        {'params': [p for n, p in param_optimizer if any(nd in n for nd in no_decay)], 'weight_decay': 0.0}
    ]

    optimizer = BertAdam(
        optimizer_grouped_parameters,
        lr=config.learning_rate,
        warmup=0.05,
        t_total=len(train_iter) * config.num_epochs
    )

    total_batch = 0
    dev_best_loss = float('inf')
    last_improve = 0
    flag = False

    for epoch in range(config.num_epochs):
        print(f'Epoch [{epoch + 1}/{config.num_epochs}]')

        for i, (trains, labels) in enumerate(train_iter):
            outputs = model(trains)
            model.zero_grad()

            loss = F.cross_entropy(outputs, labels)
            loss.backward()
            optimizer.step()

            if total_batch % 100 == 0:
                true = labels.data.cpu()
                predic = torch.max(outputs.data, 1)[1].cpu()
                train_acc = metrics.accuracy_score(true, predic)

                dev_acc, dev_loss = evaluate(config, model, dev_iter)

                # ======== 记录 ========
                train_losses.append(loss.item())
                train_accs.append(train_acc)
                dev_losses.append(dev_loss)
                dev_accs.append(dev_acc)

                if dev_loss < dev_best_loss:
                    dev_best_loss = dev_loss
                    torch.save(model.state_dict(), config.save_path)
                    improve = '*'
                    last_improve = total_batch
                else:
                    improve = ''

                time_dif = get_time_dif(start_time)
                msg = ('Iter: {0:>6}, Train Loss: {1:>5.2f}, Train Acc: {2:>6.2%}, '
                       'Val Loss: {3:>5.2f}, Val Acc: {4:>6.2%}, Time: {5} {6}')
                print(msg.format(total_batch, loss.item(), train_acc, dev_loss, dev_acc, time_dif, improve))

                model.train()

            total_batch += 1

            if total_batch - last_improve > config.require_improvement:
                print("No optimization for a long time, auto-stopping...")
                flag = True
                break

        if flag:
            break

    # ======== 画训练曲线 ========
    plot_metrics(train_losses, dev_losses, train_accs, dev_accs)

    test(config, model, test_iter)


def test(config, model, test_iter):
    model.load_state_dict(torch.load(config.save_path))
    model.eval()

    start_time = time.time()

    test_acc, test_loss, test_report, test_confusion = evaluate(
        config, model, test_iter, test=True
    )

    print(f'Test Loss: {test_loss:>5.2f}, Test Acc: {test_acc:>6.2%}')
    print("Precision, Recall and F1-Score...")
    print(test_report)

    print("Confusion Matrix...")
    plot_confusion_matrix(test_confusion, config.class_list)

    time_dif = get_time_dif(start_time)
    print("Time usage:", time_dif)


def evaluate(config, model, data_iter, test=False):
    model.eval()

    loss_total = 0
    predict_all = np.array([], dtype=int)
    labels_all = np.array([], dtype=int)

    with torch.no_grad():
        for texts, labels in data_iter:
            outputs = model(texts)
            loss = F.cross_entropy(outputs, labels)
            loss_total += loss.item()

            labels = labels.data.cpu().numpy()
            predic = torch.max(outputs.data, 1)[1].cpu().numpy()

            labels_all = np.append(labels_all, labels)
            predict_all = np.append(predict_all, predic)

    acc = metrics.accuracy_score(labels_all, predict_all)

    if test:
        report = metrics.classification_report(
            labels_all, predict_all,
            target_names=config.class_list,
            digits=4
        )
        confusion = metrics.confusion_matrix(labels_all, predict_all)
        return acc, loss_total / len(data_iter), report, confusion

    return acc, loss_total / len(data_iter)


# ================== 可视化 ==================

def plot_metrics(train_losses, dev_losses, train_accs, dev_accs):
    plt.figure(figsize=(10, 4))

    # Loss
    plt.subplot(1, 2, 1)
    plt.plot(train_losses, label='Train Loss')
    plt.plot(dev_losses, label='Dev Loss')
    plt.legend()
    plt.title('Loss Curve')

    # Acc
    plt.subplot(1, 2, 2)
    plt.plot(train_accs, label='Train Acc')
    plt.plot(dev_accs, label='Dev Acc')
    plt.legend()
    plt.title('Accuracy Curve')

    plt.savefig('training_curve.png')
    plt.show()


def plot_confusion_matrix(cm, class_names):
    import matplotlib.pyplot as plt
    import numpy as np
    import os

    plt.clf()
    plt.close('all')

    # 🔥 转换为百分比（按行归一化）
    cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]

    plt.figure(figsize=(8, 6))
    plt.imshow(cm, interpolation='nearest', cmap='Blues')
    plt.title("Confusion Matrix (%)")
    plt.colorbar()

    tick_marks = np.arange(len(class_names))
    plt.xticks(tick_marks, class_names, rotation=45)
    plt.yticks(tick_marks, class_names)

    # 🔥 显示百分比
    for i in range(len(cm)):
        for j in range(len(cm)):
            plt.text(j, i, f"{cm[i][j]*100:.1f}%",
                     ha='center', va='center',
                     color='white' if cm[i][j] > 0.5 else 'black')

    plt.ylabel('True Label')
    plt.xlabel('Predicted Label')

    plt.tight_layout()

    save_path = os.path.join(os.getcwd(), "confusion_matrix.png")
    plt.savefig(save_path, dpi=300)

    print(f">>> 百分比混淆矩阵已保存到: {save_path}")

    plt.close()

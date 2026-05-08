# coding: UTF-8
import time
import torch
import numpy as np
from importlib import import_module
import argparse
from utils import build_dataset, build_iterator, get_time_dif
from train_eval import test

parser = argparse.ArgumentParser(description='Chinese Text Classification')
parser.add_argument('--model', type=str, required=True, help='choose a model: bert / bert_cnn')
args = parser.parse_args()

if __name__ == '__main__':
    dataset = 'THUCNews'

    model_name = args.model
    x = import_module('models.' + model_name)
    config = x.Config(dataset)

    # 固定随机种子（其实测试用不到，但保留无妨）
    np.random.seed(1)
    torch.manual_seed(1)
    torch.cuda.manual_seed_all(1)
    torch.backends.cudnn.deterministic = True

    print("Loading data...")
    start_time = time.time()

    # ⚠️ 只需要 test 数据
    _, _, test_data = build_dataset(config)
    test_iter = build_iterator(test_data, config)

    print("Time usage:", get_time_dif(start_time))

    # 加载模型
    model = x.Model(config).to(config.device)

    # 只测试
    test(config, model, test_iter)
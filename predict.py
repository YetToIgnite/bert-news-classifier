import torch
from importlib import import_module
import torch.nn.functional as F
import pymysql
from datetime import datetime
from db import get_db

# ======================
# 模型加载
# ======================
dataset = 'THUCNews'
model_name = 'bert'

x = import_module('models.' + model_name)
config = x.Config(dataset)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

model = x.Model(config).to(device)
model.load_state_dict(torch.load(config.save_path, map_location=device))
model.eval()

class_list = config.class_list
tokenizer = config.tokenizer

label_map = {
    'finance': '财经',
    'realty': '房产',
    'stocks': '股票',
    'education': '教育',
    'science': '科技',
    'society': '社会',
    'politics': '政治',
    'sports': '体育',
    'game': '游戏',
    'entertainment': '娱乐'
}


# ======================
# 保存记录
# ======================
def save_record(content, prediction, confidence, username):
    db = get_db()
    cursor = db.cursor()

    sql = """
    INSERT INTO record (username, content, prediction, confidence, create_time)
    VALUES (%s, %s, %s, %s, %s)
    """

    cursor.execute(sql, (username, content, prediction, confidence, datetime.now()))
    db.commit()

    cursor.close()
    db.close()

# ======================
# 核心预测（原始Top3）
# ======================
def predict(text, username=None):
    token = tokenizer.tokenize(text)
    token = ['[CLS]'] + token
    seq_len = len(token)

    token_ids = tokenizer.convert_tokens_to_ids(token)

    if len(token_ids) < config.pad_size:
        mask = [1] * len(token_ids) + [0] * (config.pad_size - len(token_ids))
        token_ids += ([0] * (config.pad_size - len(token_ids)))
    else:
        mask = [1] * config.pad_size
        token_ids = token_ids[:config.pad_size]
        seq_len = config.pad_size

    input_ids = torch.LongTensor([token_ids]).to(device)
    seq_len = torch.LongTensor([seq_len]).to(device)
    mask = torch.LongTensor([mask]).to(device)

    with torch.no_grad():
        outputs = model((input_ids, seq_len, mask))

    probs = F.softmax(outputs, dim=1)
    topk = torch.topk(probs, 3)

    indices = topk.indices[0].cpu().numpy()
    values = topk.values[0].cpu().numpy()

    results = []
    for i in range(3):
        label = label_map[class_list[indices[i]]]
        prob = round(values[i] * 100, 2)
        results.append([label, prob])

    # 写数据库（只存Top1）
    if username:
        try:
            save_record(
                text,
                results[0][0],
                results[0][1],
                username
            )
        except Exception as e:
            print("数据库写入失败:", e)

    return results


# ======================
# ✔ 关键修复：对外接口（方案一核心）
# ======================
def predict_label_with_conf(text, username=None):
    results = predict(text, username=username)

    return {
        "label": results[0][0],
        "confidence": results[0][1],
        "top3": results
    }


# ======================
# 只返回label（带置信度拒绝机制的优化版）
# ======================
def predict_label(text):
    res = predict_label_with_conf(text)
    label = res["label"]
    confidence = res["confidence"]

    # 🌟 优化核心：如果模型对分类的把握低于 60%，就不要强行归类到专业领域
    # 将其分配到 "泛阅读"（你可以提前在数据库 category_dict 中增加一个 '泛阅读' 或 '社会' 的类别）
    if confidence < 60.0:
        return "社会"  # 兜底类别，避免荒谬的跨领域误判

    return label


# ======================
# 测试入口
# ======================
if __name__ == "__main__":
    text = "樊振东在乒乓球世界杯中夺得冠军，实现三连冠。"

    res = predict_label_with_conf(text)

    print("预测结果：")
    print(res)
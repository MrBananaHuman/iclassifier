## iclassifier

reference pytorch code for intent(sentence) classification.
- embedding
  - Glove, BERT, ALBERT, ROBERTa
- encoding
  - CNN
  - DenseNet
    - [Dynamic Self-Attention: Computing Attention over Words Dynamically for Sentence Embedding](https://arxiv.org/pdf/1808.07383.pdf)
    - implementation from [ntagger](https://github.com/dsindex/ntagger)
  - DSA(Dynamic Self Attention)
    - [Dynamic Self-Attention: Computing Attention over Words Dynamically for Sentence Embedding](https://arxiv.org/pdf/1808.07383.pdf)
  - CLS
    - classified by '[CLS]' only for BERT-like architectures. 
- decoding
  - Softmax

## requirements

- python >= 3.6

- pip install -r requirements.txt

- pretrained embedding
  - glove
    - [download Glove6B](http://nlp.stanford.edu/data/glove.6B.zip)
  - unzip to 'embeddings' dir
  ```
  $ mkdir embeddings
  $ ls embeddings
  glove.6B.zip
  $ unzip glove.6B.zip 
  ```
  - BERT(huggingface's [transformers](https://github.com/huggingface/transformers.git))
  ```
  $ pip install tensorflow-gpu==2.0.0
  $ pip install git+https://github.com/huggingface/transformers.git
  ```

- data
  - Snips
    - `data/snips`
    - from [joint-intent-classification-and-slot-filling-based-on-BERT](https://github.com/lytum/joint-intent-classification-and-slot-filling-based-on-BERT)
    - paper : [BERT for Joint Intent Classification and Slot Filling](https://arxiv.org/pdf/1902.10909.pdf)
      - intent classification accuracy : **98.6%** (test set)
    - [previous SOTA on SNIPS data](https://paperswithcode.com/sota/intent-detection-on-snips)
      - intent classification accuracy : 97.7% (test set)
  - SST-2
    - `data/sst2`
    - from [GLUE benchmark data](https://github.com/nyu-mll/GLUE-baselines/blob/master/download_glue_data.py)
      - `test.txt` from [pytorch-sentiment-classification](https://github.com/clairett/pytorch-sentiment-classification)
    - [SOTA on SST2 data](https://paperswithcode.com/sota/sentiment-analysis-on-sst-2-binary)
      - sentence classification accuracy : **97.4%** (valid set)
      - [GLUE leaderboard](https://gluebenchmark.com/leaderboard/)
  - TCCC
    - [Toxic Comment Classification Challenge](https://www.kaggle.com/c/jigsaw-toxic-comment-classification-challenge/overview)

## Snips data

### experiments summary

|                     | Accuracy (%)|
| ------------------- | ----------- |
| Glove, CNN          | 97.86       |
| Glove, Densenet-CNN | 97.57       |
| Glove, Densenet-DSA | 97.43       |
| BERT-large, CNN     | **98.00**   |
| BERT-large, CLS     | 97.86       |

### emb_class=glove, enc_class=cnn

- train
```
* token_emb_dim in configs/config-glove-cnn.json == 300 (ex, glove.6B.300d.txt )
$ python preprocess.py
$ python train.py --decay_rate=0.9 --embedding_trainable

* tensorboardX
$ rm -rf runs
$ tensorboard --logdir runs/ --port port-number --bind_all
```

- evaluation
```
$ python evaluate.py
INFO:__main__:[Accuracy] : 0.9786,   685/  700
INFO:__main__:[Elapsed Time] : 1351ms, 1.793991416309013ms on average
```

### emb_class=glove, enc_class=densenet-cnn

- train
```
* token_emb_dim in configs/config-densenet-cnn.json == 300 (ex, glove.6B.300d.txt )
$ python preprocess.py --config=configs/config-densenet-cnn.json
$ python train.py --config=configs/config-densenet-cnn.json --decay_rate=0.9 --embedding_trainable
```

- evaluation
```
$ python evaluate.py --config=configs/config-densenet-cnn.json

INFO:__main__:[Accuracy] : 0.9757,   683/  700
INFO:__main__:[Elapsed Time] : 2633ms, 3.609442060085837ms on average
```

### emb_class=glove, enc_class=densenet-dsa

- train
```
* token_emb_dim in configs/config-densenet-dsa.json == 300 (ex, glove.6B.300d.txt )
$ python preprocess.py --config=configs/config-densenet-dsa.json
$ python train.py --config=configs/config-densenet-dsa.json --decay_rate=0.9
```

- evaluation
```
$ python evaluate.py --config=configs/config-densenet-dsa.json

INFO:__main__:[Accuracy] : 0.9743,   682/  700
INFO:__main__:[Elapsed Time] : 5367ms, 7.500715307582261ms on average
```

### emb_class=bert, enc_class=cnn | cls

- train
```
* n_ctx size should be less than 512

* enc_class=cnn
$ python preprocess.py --config=configs/config-bert-cnn.json --bert_model_name_or_path=./embeddings/bert-base-uncased --bert_do_lower_case
$ python train.py --config=configs/config-bert-cnn.json --bert_model_name_or_path=./embeddings/bert-base-uncased --bert_do_lower_case --bert_output_dir=bert-checkpoint --lr=5e-5 --epoch=3 --batch_size=64

* enc_class=cls
$ python preprocess.py --config=configs/config-bert-cls.json --bert_model_name_or_path=./embeddings/bert-base-uncased --bert_do_lower_case
$ python train.py --config=configs/config-bert-cls.json --bert_model_name_or_path=./embeddings/bert-base-uncased --bert_do_lower_case --bert_output_dir=bert-checkpoint --lr=5e-5 --epoch=3 --batch_size=64

* --bert_use_feature_based for feature-based
```

- evaluation
```
* enc_class=cnn
$ python evaluate.py --config=configs/config-bert-cnn.json --bert_output_dir=bert-checkpoint --bert_do_lower_case

INFO:__main__:[Accuracy] : 0.9743,   682/  700
INFO:__main__:[Elapsed Time] : 9353ms, 13.361428571428572ms on average
  
  ** --bert_model_name_or_path=bert-large-uncased --lr=2e-5 , without --bert_do_lower_case
  INFO:__main__:[Accuracy] : 0.9800,   686/  700
  INFO:__main__:[Elapsed Time] : 16994ms, 24.277142857142856ms on average

* enc_class=cls
$ python evaluate.py --config=configs/config-bert-cls.json --bert_output_dir=bert-checkpoint --bert_do_lower_case

INFO:__main__:[Accuracy] : 0.9743,   682/  700
INFO:__main__:[Elapsed Time] : 8940ms, 12.771428571428572ms on average
  
  ** --bert_model_name_or_path=bert-large-uncased --lr=2e-5 , without --bert_do_lower_case
  INFO:__main__:[Accuracy] : 0.9786,   685/  700
  INFO:__main__:[Elapsed Time] : 16480ms, 23.542857142857144ms on average
```

## SST-2 data

### experiments summary

- iclassifier

|                     | Accuracy (%)| Etc           | Elapsed time / example (ms)  |
| ------------------- | ----------- | ------------- | ---------------------------- |
| Glove, CNN          | 83.42       |               | 1.6873  |
| Glove, DenseNet-CNN | 86.38       |               | 3.6203  |
| Glove, DenseNet-DSA | 85.34       |               | 6.2450  |
| BERT-tiny, CNN      | 79.08       |               | 4.8604  |
| BERT-tiny, CLS      | 80.83       |               | 3.8461  |
| BERT-mini, CNN      | 83.36       |               | 7.0983  |
| BERT-mini, CLS      | 83.69       |               | 5.5521  |
| BERT-small, CNN     | 87.53       |               | 7.2010  |
| BERT-small, CLS     | 87.86       |               | 6.0450  |
| BERT-medium, CNN    | 88.58       |               | 11.9082 |
| BERT-medium, CLS    | 89.24       |               | 9.5857  |
| BERT-base, CNN      | 91.43       |               | 13.9335 |
| BERT-base, CLS      | 89.29       |               | 12.8572 |
| BERT-large, CNN     | 93.08       |               | 28.6490 |
| BERT-large, CLS     | 93.85       |               | 27.9967 |
| ALBERT-base, CNN    | 86.66       | feature-based | 16.9665 |           
| ALBERT-xxlarge, CNN | 91.32       | feature-based | 56.0900 |
| ROBERTa-base, CNN   | 92.31       |               | 15.8802 |
| ROBERTa-base, CLS   | -           |               | -       |
| ROBERTa-large, CNN  | 94.62       |               | 27.6xxx |
| ROBERTa-large, CLS  | **95.66**   |               | 23.7395 |

- [sst2 learderboard](https://paperswithcode.com/sota/sentiment-analysis-on-sst-2-binary)

|                   | Accuracy (%)|
| ----------------- | ----------- |
| T5-3B             | 97.4        |
| ALBERT            | 97.1        |
| RoBERTa           | 96.7        |
| MT-DNN            | 95.6        |
| DistilBERT        | 92.7        |

### emb_class=glove, enc_class=cnn

- train
```
* token_emb_dim in configs/config-glove-cnn.json == 300 (ex, glove.6B.300d.txt )
$ python preprocess.py --data_dir=data/sst2
$ python train.py --data_dir=data/sst2 --decay_rate=0.9 
```

- evaluation
```
$ python evaluate.py --data_dir=data/sst2

INFO:__main__:[Accuracy] : 0.8342,  1519/ 1821
INFO:__main__:[Elapsed Time] : 3161ms, 1.6873626373626374ms on average
```

### emb_class=glove, enc_class=densenet-cnn

- train
```
* token_emb_dim in configs/config-densenet-cnn.json == 300 (ex, glove.6B.300d.txt )
$ python preprocess.py --config=configs/config-densenet-cnn.json --data_dir=data/sst2
$ python train.py --config=configs/config-densenet-cnn.json --data_dir=data/sst2 --decay_rate=0.9
```

- evaluation
```
$ python evaluate.py --config=configs/config-densenet-cnn.json --data_dir=data/sst2

INFO:__main__:[Accuracy] : 0.8638,  1573/ 1821
INFO:__main__:[Elapsed Time] : 6678ms, 3.6203296703296703ms on average
```

### emb_class=glove, enc_class=densenet-dsa

- train
```
* token_emb_dim in configs/config-densenet-dsa.json == 300 (ex, glove.6B.300d.txt )
$ python preprocess.py --config=configs/config-densenet-dsa.json --data_dir=data/sst2
$ python train.py --config=configs/config-densenet-dsa.json --data_dir=data/sst2 --decay_rate=0.9
```

- evaluation
```
$ python evaluate.py --config=configs/config-densenet-dsa.json --data_dir=data/sst2

INFO:__main__:[Accuracy] : 0.8534,  1554/ 1821
INFO:__main__:[Elapsed Time] : 11459ms, 6.245054945054945ms on average
```

### emb_class=bert, enc_class=cnn | cls

- train
```
* n_ctx size should be less than 512

* enc_class=cnn
$ python preprocess.py --config=configs/config-bert-cnn.json --data_dir=data/sst2 --bert_model_name_or_path=./embeddings/bert-base-uncased --bert_do_lower_case
$ python train.py --config=configs/config-bert-cnn.json --data_dir=data/sst2 --bert_model_name_or_path=./embeddings/bert-base-uncased --bert_do_lower_case --bert_output_dir=bert-checkpoint --lr=5e-5 --epoch=3 --batch_size=64

* enc_class=cls
$ python preprocess.py --config=configs/config-bert-cls.json --data_dir=data/sst2 --bert_model_name_or_path=./embeddings/bert-base-uncased --bert_do_lower_case
$ python train.py --config=configs/config-bert-cls.json --data_dir=data/sst2 --bert_model_name_or_path=./embeddings/bert-base-uncased --bert_do_lower_case --bert_output_dir=bert-checkpoint --lr=5e-5 --epoch=3 --batch_size=64
```

- evaluation
```
* enc_class=cnn
$ python evaluate.py --config=configs/config-bert-cnn.json --data_dir=data/sst2 --bert_output_dir=bert-checkpoint --bert_do_lower_case 

INFO:__main__:[Accuracy] : 0.9143,  1665/ 1821
INFO:__main__:[Elapsed Time] : 25373ms, 13.933552992861065ms on average

  ** --bert_model_name_or_path=bert-large-uncased --lr=1e-5 , without --bert_do_lower_case
  INFO:__main__:[Accuracy] : 0.9308,  1695/ 1821
  INFO:__main__:[Elapsed Time] : 52170ms, 28.649093904448105ms on average

  ** --bert_model_name_or_path=embeddings/pytorch.uncased_L-8_H-512_A-8 --lr=1e-5
  INFO:__main__:[Accuracy] : 0.8858,  1613/ 1821
  INFO:__main__:[Elapsed Time] : 21791ms, 11.908241758241758ms on average

  ** --bert_model_name_or_path=embeddings/pytorch.uncased_L-4_H-512_A-8 --lr=1e-5
  INFO:__main__:[Accuracy] : 0.8753,  1594/ 1821
  INFO:__main__:[Elapsed Time] : 13206ms, 7.201098901098901ms on average

  ** --bert_model_name_or_path=embeddings/pytorch.uncased_L-4_H-256_A-4 --lr=1e-5
  INFO:__main__:[Accuracy] : 0.8336,  1518/ 1821
  INFO:__main__:[Elapsed Time] : 13021ms, 7.098351648351648ms on average

  ** --bert_model_name_or_path=embeddings/pytorch.uncased_L-2_H-128_A-2 --lr=1e-5
  INFO:__main__:[Accuracy] : 0.7908,  1440/ 1821
  INFO:__main__:[Elapsed Time] : 8951ms, 4.86043956043956ms on average

* enc_class=cls
$ python evaluate.py --config=configs/config-bert-cls.json --data_dir=data/sst2 --bert_output_dir=bert-checkpoint --bert_do_lower_case

INFO:__main__:[Accuracy] : 0.8929,  1626/ 1821
INFO:__main__:[Elapsed Time] : 23413ms, 12.85722130697419ms on average

  ** --bert_model_name_or_path=bert-large-uncased --lr=2e-5 , without --bert_do_lower_case
  INFO:__main__:[Accuracy] : 0.9385,  1709/ 1821
  INFO:__main__:[Elapsed Time] : 50982ms, 27.99670510708402ms on average

  ** --bert_model_name_or_path=embeddings/pytorch.uncased_L-8_H-512_A-8 --lr=1e-5
  INFO:__main__:[Accuracy] : 0.8924,  1625/ 1821
  INFO:__main__:[Elapsed Time] : 17558ms, 9.585714285714285ms on average

  ** --bert_model_name_or_path=embeddings/pytorch.uncased_L-4_H-512_A-8 --lr=1e-5
  INFO:__main__:[Accuracy] : 0.8786,  1600/ 1821
  INFO:__main__:[Elapsed Time] : 11104ms, 6.045054945054945ms on average

  ** --bert_model_name_or_path=embeddings/pytorch.uncased_L-4_H-256_A-4 --lr=1e-5
  INFO:__main__:[Accuracy] : 0.8369,  1524/ 1821
  INFO:__main__:[Elapsed Time] : 10196ms, 5.552197802197802ms on average

  ** --bert_model_name_or_path=embeddings/pytorch.uncased_L-2_H-128_A-2 --lr=1e-5
  INFO:__main__:[Accuracy] : 0.8083,  1472/ 1821
  INFO:__main__:[Elapsed Time] : 7124ms, 3.8461538461538463ms on average

```

### emb_class=albert, enc_class=cnn | cls

- train
```
* n_ctx size should be less than 512

* enc_class=cnn
$ python preprocess.py --config=configs/config-albert-cnn.json --data_dir=data/sst2 --bert_model_name_or_path=./embeddings/albert-base-v2
$ python train.py --config=configs/config-albert-cnn.json --data_dir=data/sst2 --bert_model_name_or_path=./embeddings/albert-base-v2 --bert_output_dir=bert-checkpoint --lr=5e-5 --epoch=15 --batch_size=64 --bert_use_feature_based

** albert-xxlarge-v2
$ python preprocess.py --config=configs/config-albert-cnn.json --data_dir=data/sst2 --bert_model_name_or_path=./embeddings/albert-xxlarge-v2
$ python train.py --config=configs/config-albert-cnn.json --data_dir=data/sst2 --bert_model_name_or_path=./embeddings/albert-xxlarge-v2 --bert_output_dir=bert-checkpoint --lr=5e-5 --epoch=15 --batch_size=32 --bert_use_feature_based

```

- evaluation
```
* enc_class=cnn
$ python evaluate.py --config=configs/config-albert-cnn.json --data_dir=data/sst2 --bert_output_dir=bert-checkpoint 
  
** fine-tuning ALBERT doesn't work well. i guess ALBERT needs more data.
** feature-based
  INFO:__main__:[Accuracy] : 0.8666,  1578/ 1821
  INFO:__main__:[Elapsed Time] : 30896ms, 16.966501922020868ms on average

** albert-xxlarge-v2
  INFO:__main__:[Accuracy] : 0.9132,  1663/ 1821
  INFO:__main__:[Elapsed Time] : 102140ms, 56.090060406370127ms on average
```

### emb_class=roberta, enc_class=cnn | cls

- train
```
* n_ctx size should be less than 512

* enc_class=cnn
$ python preprocess.py --config=configs/config-roberta-cnn.json --data_dir=data/sst2 --bert_model_name_or_path=./embeddings/roberta-large
$ python train.py --config=configs/config-roberta-cnn.json --data_dir=data/sst2 --bert_model_name_or_path=./embeddings/roberta-large --bert_output_dir=bert-checkpoint --lr=1e-5 --epoch=10 --decay_rate=0.9 --batch_size=32

* enc_class=cls
$ python preprocess.py --config=configs/config-roberta-cls.json --data_dir=data/sst2 --bert_model_name_or_path=./embeddings/roberta-large 
$ python train.py --config=configs/config-roberta-cls.json --data_dir=data/sst2 --bert_model_name_or_path=./embeddings/roberta-large --bert_output_dir=bert-checkpoint --lr=1e-5 --epoch=10 --decay_rate=0.9 --batch_size=32
```

- evaluation
```
* enc_class=cnn
$ python evaluate.py --config=configs/config-roberta-cnn.json --data_dir=data/sst2 --bert_output_dir=bert-checkpoint

1)
INFO:__main__:[Accuracy] : 0.9462,  1723/ 1821

2)
INFO:__main__:[Accuracy] : 0.9374,  1707/ 1821
INFO:__main__:[Elapsed Time] : 50526ms, 27.662087912087912ms on average

3)
INFO:__main__:[Accuracy] : 0.9390,  1710/ 1821
INFO:__main__:[Elapsed Time] : 49663ms, 27.196153846153845ms on average

  ** --batch_size=64

  ** --bert_model_name_or_path=./embeddings/roberta-large-mnli
  INFO:__main__:[Accuracy] : 0.9336,  1700/ 1821
  INFO:__main__:[Elapsed Time] : 57243ms, 31.35879120879121ms on average

  ** --bert_model_name_or_path=./embeddings/roberta-base
  INFO:__main__:[Accuracy] : 0.9231,  1681/ 1821
  INFO:__main__:[Elapsed Time] : 29048ms, 15.88021978021978ms on average

* enc_class=cls
$ python evaluate.py --config=configs/config-roberta-cls.json --data_dir=data/sst2 --bert_output_dir=bert-checkpoint
INFO:__main__:[Accuracy] : 0.9325,  1698/ 1821
INFO:__main__:[Elapsed Time] : 46867ms, 25.665384615384614ms on average

  ** --batch_size=64
  INFO:__main__:[Accuracy] : 0.9566,  1742/ 1821
  INFO:__main__:[Elapsed Time] : 43363ms, 23.73956043956044ms on average

  ** --bert_model_name_or_path=./embeddings/roberta-base --batch_size=64

```

## experiments for Korean

- [KOR_EXPERIMENTS.md](/KOR_EXPERIMENTS.md)

## references

- [Intent Detection](https://paperswithcode.com/task/intent-detection)
- [Intent Classification](https://paperswithcode.com/task/intent-classification)
- [Identifying Hate Speech with BERT and CNN](https://towardsdatascience.com/identifying-hate-speech-with-bert-and-cnn-b7aa2cddd60d)
- [RoBERTa](https://github.com/pytorch/fairseq/tree/master/examples/roberta)
  - [RoBERTa GLUE task setting](https://github.com/pytorch/fairseq/blob/master/examples/roberta/README.glue.md)
- [BERT Miniatures](https://huggingface.co/google/bert_uncased_L-12_H-128_A-2)
  - search range of hyperparameters
    - batch sizes: 8, 16, 32, 64, 128
    - learning rates: 1e-4, 3e-4, 3e-5, 5e-5

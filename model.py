from __future__ import absolute_import, division, print_function

import os
import pdb

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable
import numpy as np
from numpy import pi
import random

class BaseModel(nn.Module):
    def __init__(self, config=None):
        super(BaseModel, self).__init__()
        if config and hasattr(config['opt'], 'seed'):
            self.set_seed(config['opt'])

    def set_seed(self, opt):
        random.seed(opt.seed)
        np.random.seed(opt.seed)
        torch.manual_seed(opt.seed)
        torch.cuda.manual_seed(opt.seed)

    def load_embedding(self, input_path):
        weights_matrix = np.load(input_path)
        weights_matrix = torch.as_tensor(weights_matrix)
        return weights_matrix

    def create_embedding_layer(self, vocab_dim, emb_dim, weights_matrix=None, non_trainable=True, padding_idx=0):
        emb_layer = nn.Embedding(vocab_dim, emb_dim, padding_idx=padding_idx)
        if torch.is_tensor(weights_matrix):
            emb_layer.load_state_dict({'weight': weights_matrix})
        if non_trainable:
            emb_layer.weight.requires_grad = False
        return emb_layer

    def load_label(self, input_path):
        labels = {}
        with open(input_path, 'r', encoding='utf-8') as f:
            for idx, line in enumerate(f):
                toks = line.strip().split()
                label = toks[0]
                label_id = int(toks[1])
                labels[label_id] = label
        return labels

# ------------------------------------------------------------------------------ #
# source code from https://github.com/tbung/naive-bayes-layer
# ------------------------------------------------------------------------------ #
class GaussianNaiveBayes(nn.Module):
    def __init__(self, features, classes, fix_variance=False):
        super(self.__class__, self).__init__()

        self.features = features
        self.classes = classes

        # We need mean and variance per feature and class
        self.register_buffer(
            "means",
            Variable(torch.Tensor(self.classes, self.features))
        )
        if not fix_variance:
            self.register_parameter(
                "variances",
                nn.Parameter(torch.Tensor(self.classes, self.features))
            )
        else:
            self.register_buffer(
                "variances",
                Variable(torch.Tensor(self.classes, self.features))
            )

        # We need the class priors
        self.register_parameter(
            "class_priors",
            nn.Parameter(torch.Tensor(self.classes))
        )

        self.reset_parameters()

    def reset_parameters(self):
        self.means.data = torch.eye(self.classes, self.features)
        self.variances.data.fill_(1)
        # self.variances.data = torch.eye(self.classes, self.features)
        self.class_priors.data.uniform_()

    def forward(self, x):
        x = x[:,np.newaxis,:]
        return (torch.sum(- 0.5 * torch.log(2 * pi * torch.abs(self.variances))
                - (x - self.means)**2 / torch.abs(self.variances) / 2, dim=-1)
                + torch.log(self.class_priors))

class TextCNN(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_sizes):
        super(TextCNN, self).__init__()
        convs = []
        for ks in kernel_sizes:
            convs.append(nn.Conv1d(in_channels=in_channels, out_channels=out_channels, kernel_size=ks))
            '''
            # depthwise convolution, 'out_channels' should be 'K * in_channels'
            # see https://pytorch.org/docs/stable/nn.html#torch.nn.Conv1d , https://towardsdatascience.com/a-basic-introduction-to-separable-convolutions-b99ec3102728
            convs.append(nn.Conv1d(in_channels=in_channels, out_channels=out_channels, kernel_size=ks, groups=in_channels))
            '''
        self.convs = nn.ModuleList(convs)
        self.last_dim = len(kernel_sizes) * out_channels

    def forward(self, x):
        # x : [batch_size, seq_size, emb_dim]
        # num_filters == out_channels
        x = x.permute(0, 2, 1)
        # x : [batch_size, emb_dim, seq_size]
        conved = [F.relu(conv(x)) for conv in self.convs]
        # conved : [ [batch_size, num_filters, *], [batch_size, num_filters, *], [batch_size, num_filters, *] ]
        # for ONNX conversion, do not use F.max_pool1d(),
        pooled = [torch.max(cv, dim=2)[0] for cv in conved]
        # pooled : [ [batch_size, num_filters], [batch_size, num_filters], [batch_size, num_filters] ]
        cat = torch.cat(pooled, dim = 1)
        # cat : [batch_size, len(kernel_sizes) * num_filters]
        return cat

class DenseNet(nn.Module):
    def __init__(self, densenet_kernels, emb_dim, first_num_filters, num_filters, last_num_filters, activation=F.relu):
        super(DenseNet, self).__init__()
        self.activation = activation
        self.densenet_kernels = densenet_kernels
        self.densenet_width = len(densenet_kernels[0])
        self.densenet_block = []
        for i, kss in enumerate(self.densenet_kernels): # densenet depth
            if i == 0:
                in_channels = emb_dim
                out_channels = first_num_filters
            else:
                in_channels = first_num_filters + num_filters * (i-1)
                out_channels = num_filters
            convs = []
            for j, ks in enumerate(kss):                # densenet width
                padding = (ks - 1)//2
                conv = nn.Conv1d(in_channels=in_channels, out_channels=out_channels, kernel_size=ks, padding=padding)
                convs.append(conv)
            convs = nn.ModuleList(convs)
            self.densenet_block.append(convs)
        self.densenet_block = nn.ModuleList(self.densenet_block)
        ks = 1
        in_channels = emb_dim + num_filters * self.densenet_width
        out_channels = last_num_filters
        padding = (ks - 1)//2
        self.conv_last = nn.Conv1d(in_channels=in_channels, out_channels=out_channels, kernel_size=ks, padding=padding)
        self.last_dim = last_num_filters

    def forward(self, x, mask):
        # x     : [batch_size, seq_size, emb_dim]
        # mask  : [batch_size, seq_size]
        x = x.permute(0, 2, 1)
        # x     : [batch_size, emb_dim, seq_size]
        masks = mask.unsqueeze(2).to(torch.float)
        # masks : [batch_size, seq_size, 1]
        masks = masks.permute(0, 2, 1)
        # masks : [batch_size, 1, seq_size]

        merge_list = []
        for j in range(self.densenet_width):
            conv_results = []
            for i, kss in enumerate(self.densenet_kernels):
                if i == 0: conv_in = x
                else: conv_in  = torch.cat(conv_results, dim=-2)
                conv_out = self.densenet_block[i][j](conv_in)
                # conv_out first : [batch_size, first_num_filters, seq_size]
                # conv_out other : [batch_size, num_filters, seq_size]
                conv_out *= masks # masking, auto broadcasting along with second dimension
                conv_out = self.activation(conv_out)
                conv_results.append(conv_out)
            merge_list.append(conv_results[-1]) # last one only

        conv_last = self.conv_last(torch.cat([x] + merge_list, dim=-2))
        conv_last *= masks
        conv_last = F.relu(conv_last)
        # conv_last : [batch_size, last_num_filters, seq_size]
        conv_last = conv_last.permute(0, 2, 1)
        # conv_last : [batch_size, seq_size, last_num_filters]
        return conv_last

class DSA(nn.Module):
    def __init__(self, config, dsa_num_attentions, dsa_input_dim, dsa_dim, dsa_r=3):
        super(DSA, self).__init__()
        self.config = config
        self.device = config['opt'].device
        dsa = []
        for i in range(dsa_num_attentions):
            dsa.append(nn.Linear(dsa_input_dim, dsa_dim))
        self.dsa = nn.ModuleList(dsa)
        self.dsa_r = dsa_r # r iterations
        self.last_dim = dsa_num_attentions * dsa_dim

    def __self_attention(self, x, mask, r=3):
        # x    : [batch_size, seq_size, dsa_dim]
        # mask : [batch_size, seq_size]
        # r    : r iterations
        # initialize
        mask = mask.to(torch.float)
        inv_mask = mask.eq(0.0)
        # inv_mask : [batch_size, seq_size], ex) [False, ..., False, True, ..., True]
        softmax_mask = mask.masked_fill(inv_mask, -1e20)
        # softmax_mask : [batch_size, seq_size], ex) [1., 1., 1.,  ..., -1e20, -1e20, -1e20] 
        q = torch.zeros(mask.shape[0], mask.shape[-1], requires_grad=False).to(torch.float).to(self.device)
        # q : [batch_size, seq_size]
        z_list = []
        # iterative computing attention
        for idx in range(r):
            # softmax masking
            q *= softmax_mask
            # attention weights
            a = torch.softmax(q.detach().clone(), dim=-1) # preventing from unreachable variable at gradient computation. 
            # a : [batch_size, seq_size]
            a *= mask
            a = a.unsqueeze(2)
            # a : [batch_size, seq_size, 1]
            # element-wise multiplication(broadcasting) and summation along 1 dim
            s = (a * x).sum(1)
            # s : [batch_size, dsa_dim]
            z = torch.tanh(s)
            # z : [batch_size, dsa_dim]
            z_list.append(z)
            # update q
            m = z.unsqueeze(2)
            # m : [batch_size, dsa_dim, 1]
            q += torch.matmul(x, m).squeeze(2)
            # q : [batch_size, seq_size]
        return z_list[-1]

    def forward(self, x, mask):
        # x     : [batch_size, seq_size, dsa_input_dim]
        # mak   : [batch_size, seq_size]
        z_list = []
        for p in self.dsa: # dsa_num_attentions
            # projection to dsa_dim
            p_out = F.leaky_relu(p(x))
            # p_out : [batch_size, seq_size, dsa_dim]
            z_j = self.__self_attention(p_out, mask, r=self.dsa_r)
            # z_j : [batch_size, dsa_dim]
            z_list.append(z_j)
        z = torch.cat(z_list, dim=-1)
        # z : [batch_size, dsa_num_attentions * dsa_dim]
        return z

class TextGloveGNB(BaseModel):
    def __init__(self, config, embedding_path, label_path):
        super().__init__(config=config)

        self.config = config
        self.device = config['opt'].device
        seq_size = config['n_ctx']
        token_emb_dim = config['token_emb_dim']

        # glove embedding layer
        weights_matrix = super().load_embedding(embedding_path)
        vocab_dim, emb_dim = weights_matrix.size()
        padding_idx = config['pad_token_id']
        self.embed = super().create_embedding_layer(vocab_dim, emb_dim, weights_matrix=weights_matrix, non_trainable=True, padding_idx=padding_idx)
        emb_dim = token_emb_dim 

        self.labels = super().load_label(label_path)
        label_size = len(self.labels)

        # gaussian naive bayes layer
        features = emb_dim
        classes = label_size
        self.gnb = GaussianNaiveBayes(features, classes, fix_variance=False)

        self.dropout = nn.Dropout(config['dropout'])

    def forward(self, x):
        # 1. glove embedding
        # x : [batch_size, seq_size]
        embedded = self.dropout(self.embed(x))
        # embedded : [batch_size, seq_size, emb_dim]

        # 2. gaussian naive bayes
        embedded_x, _ = embedded.max(1) # extract max feature value along with dim=1
        # embedded_x : [batch_size, emb_dim]
        gnb_out = self.gnb(embedded_x)
        # gnb_out : [batch_size, label_size]

        # for MSELoss
        if self.config['opt'].augmented: return gnb_out
        output = torch.softmax(gnb_out, dim=-1)
        return output


class TextGloveCNN(BaseModel):
    def __init__(self, config, embedding_path, label_path, emb_non_trainable=True):
        super().__init__(config=config)

        self.config = config
        self.device = config['opt'].device
        seq_size = config['n_ctx']
        token_emb_dim = config['token_emb_dim']

        # glove embedding layer
        weights_matrix = super().load_embedding(embedding_path)
        vocab_dim, emb_dim = weights_matrix.size()
        padding_idx = config['pad_token_id']
        self.embed = super().create_embedding_layer(vocab_dim, emb_dim, weights_matrix=weights_matrix, non_trainable=emb_non_trainable, padding_idx=padding_idx)
        emb_dim = token_emb_dim 

        # convolution layer
        num_filters = config['num_filters']
        kernel_sizes = config['kernel_sizes']
        self.textcnn = TextCNN(emb_dim, num_filters, kernel_sizes)
        self.layernorm_textcnn = nn.LayerNorm(self.textcnn.last_dim)

        self.dropout = nn.Dropout(config['dropout'])

        # fully connected layer
        fc_hidden_size = config['fc_hidden_size']
        self.labels = super().load_label(label_path)
        label_size = len(self.labels)
        self.fc_hidden = nn.Linear(len(kernel_sizes) * num_filters, fc_hidden_size)
        self.layernorm_fc_hidden = nn.LayerNorm(fc_hidden_size)
        self.fc = nn.Linear(fc_hidden_size, label_size)

    def forward(self, x):
        # 1. glove embedding
        # x : [batch_size, seq_size]
        embedded = self.dropout(self.embed(x))
        # embedded : [batch_size, seq_size, emb_dim]

        # 2. convolution
        textcnn_out = self.textcnn(embedded)
        # textcnn_out : [batch_size, len(kernel_sizes) * num_filters]
        textcnn_out = self.layernorm_textcnn(textcnn_out)
        textcnn_out = self.dropout(textcnn_out)

        # 3. fully connected
        fc_hidden = self.fc_hidden(textcnn_out)
        # fc_hidden : [batch_size, fc_hidden_size]
        fc_hidden = self.layernorm_fc_hidden(fc_hidden)
        fc_hidden = self.dropout(fc_hidden)
        fc_out = self.fc(fc_hidden)
        # fc_out : [batch_size, label_size]
        # for MSELoss
        if self.config['opt'].augmented: return fc_out
        output = torch.softmax(fc_out, dim=-1)
        return output

class TextGloveDensenetCNN(BaseModel):
    def __init__(self, config, embedding_path, label_path, emb_non_trainable=True):
        super().__init__(config=config)

        self.config = config
        self.device = config['opt'].device
        seq_size = config['n_ctx']
        token_emb_dim = config['token_emb_dim']

        # glove embedding layer
        weights_matrix = super().load_embedding(embedding_path)
        vocab_dim, emb_dim = weights_matrix.size()
        padding_idx = config['pad_token_id']
        self.embed = super().create_embedding_layer(vocab_dim, emb_dim, weights_matrix=weights_matrix, non_trainable=emb_non_trainable, padding_idx=padding_idx)
        
        # Densenet layer
        densenet_kernels = config['densenet_kernels']
        emb_dim = token_emb_dim
        densenet_first_num_filters = config['densenet_first_num_filters']
        densenet_num_filters = config['densenet_num_filters']
        densenet_last_num_filters = config['densenet_last_num_filters']
        self.densenet = DenseNet(densenet_kernels, emb_dim, densenet_first_num_filters, densenet_num_filters, densenet_last_num_filters, activation=F.relu)
        self.layernorm_densenet = nn.LayerNorm(self.densenet.last_dim)

        # convolution layer
        num_filters = config['num_filters']
        kernel_sizes = config['kernel_sizes']
        self.textcnn = TextCNN(densenet_last_num_filters, num_filters, kernel_sizes)
        self.layernorm_textcnn = nn.LayerNorm(self.textcnn.last_dim)

        self.dropout = nn.Dropout(config['dropout'])

        # fully connected layer
        self.labels = super().load_label(label_path)
        label_size = len(self.labels)
        self.fc = nn.Linear(len(kernel_sizes) * num_filters, label_size)

    def forward(self, x):
        # x : [batch_size, seq_size]

        mask = torch.sign(torch.abs(x)).to(torch.uint8).to(self.device)
        # mask : [batch_size, seq_size]

        # 1. glove embedding
        embed_out = self.dropout(self.embed(x))
        # [batch_size, seq_size, token_emb_dim]

        # 2. DenseNet
        densenet_out = self.densenet(embed_out, mask)
        # densenet_out : [batch_size, seq_size, densenet_last_num_filters]
        densenet_out = self.layernorm_densenet(densenet_out)
        densenet_out = self.dropout(densenet_out)

        # 3. convolution
        textcnn_out = self.textcnn(densenet_out)
        # [batch_size, len(kernel_sizes) * num_filters]
        textcnn_out = self.layernorm_textcnn(textcnn_out)
        textcnn_out = self.dropout(textcnn_out)

        # 4. fully connected
        fc_out = self.fc(textcnn_out)
        # [batch_size, label_size]
        # for MSELoss
        if self.config['opt'].augmented: return fc_out
        output = torch.softmax(fc_out, dim=-1)
        return output

class TextGloveDensenetDSA(BaseModel):
    def __init__(self, config, embedding_path, label_path, emb_non_trainable=True):
        super().__init__(config=config)

        self.config = config
        self.device = config['opt'].device
        seq_size = config['n_ctx']
        token_emb_dim = config['token_emb_dim']

        # glove embedding layer
        weights_matrix = super().load_embedding(embedding_path)
        vocab_dim, emb_dim = weights_matrix.size()
        padding_idx = config['pad_token_id']
        self.embed = super().create_embedding_layer(vocab_dim, emb_dim, weights_matrix=weights_matrix, non_trainable=emb_non_trainable, padding_idx=padding_idx)
        
        # Densenet layer
        densenet_kernels = config['densenet_kernels']
        emb_dim = token_emb_dim
        densenet_first_num_filters = config['densenet_first_num_filters']
        densenet_num_filters = config['densenet_num_filters']
        densenet_last_num_filters = config['densenet_last_num_filters']
        self.densenet = DenseNet(densenet_kernels, emb_dim, densenet_first_num_filters, densenet_num_filters, densenet_last_num_filters, activation=F.leaky_relu)
        self.layernorm_densenet = nn.LayerNorm(self.densenet.last_dim)

        # DSA(Dynamic Self Attention) layer
        dsa_num_attentions = config['dsa_num_attentions']
        dsa_input_dim = densenet_last_num_filters
        dsa_dim = config['dsa_dim']
        dsa_r = config['dsa_r']
        self.dsa = DSA(config, dsa_num_attentions, dsa_input_dim, dsa_dim, dsa_r=dsa_r)
        self.layernorm_dsa = nn.LayerNorm(self.dsa.last_dim)

        self.dropout = nn.Dropout(config['dropout'])

        # fully connected layer
        self.labels = super().load_label(label_path)
        label_size = len(self.labels)
        fc_hidden_size = config['fc_hidden_size']
        if fc_hidden_size > 0:
            self.fc_hidden = nn.Linear(dsa_num_attentions * dsa_dim, fc_hidden_size)
            self.layernorm_fc_hidden = nn.LayerNorm(fc_hidden_size)
            self.fc = nn.Linear(fc_hidden_size, label_size)
        else:
            self.fc_hidden = None
            self.fc = nn.Linear(dsa_num_attentions * dsa_dim, label_size)

    def forward(self, x):
        # x : [batch_size, seq_size]

        mask = torch.sign(torch.abs(x)).to(torch.uint8).to(self.device)
        # mask : [batch_size, seq_size]

        # 1. glove embedding
        embed_out = self.dropout(self.embed(x))
        # [batch_size, seq_size, token_emb_dim]

        # 2. DenseNet
        densenet_out = self.densenet(embed_out, mask)
        # densenet_out : [batch_size, seq_size, densenet_last_num_filters]
        densenet_out = self.layernorm_densenet(densenet_out)
        densenet_out = self.dropout(densenet_out)

        # 3. DSA(Dynamic Self Attention)
        dsa_out = self.dsa(densenet_out, mask) 
        # dsa_out : [batch_size, dsa_num_attentions * dsa_dim]
        dsa_out = self.layernorm_dsa(dsa_out)
        dsa_out = self.dropout(dsa_out)

        # 4. fully connected
        if self.fc_hidden:
            fc_hidden_out = self.fc_hidden(dsa_out)
            # fc_hidden_out : [batch_size, fc_hidden_size]
            fc_hidden_out = self.layernorm_fc_hidden(fc_hidden_out)
            fc_hidden_out = self.dropout(fc_hidden_out)
            fc_out = self.fc(fc_hidden_out)
            # fc_out : [batch_size, label_size]
        else:
            fc_out = self.fc(dsa_out)
            # fc_out : [batch_size, label_size]
        # for MSELoss
        if self.config['opt'].augmented: return fc_out
        output = torch.softmax(fc_out, dim=-1)
        return output

class TextBertCNN(BaseModel):
    def __init__(self, config, bert_config, bert_model, bert_tokenizer, label_path, feature_based=False):
        super().__init__(config=config)

        self.config = config
        self.device = config['opt'].device
        seq_size = config['n_ctx']

        # bert embedding layer
        self.bert_config = bert_config
        self.bert_model = bert_model
        self.bert_tokenizer = bert_tokenizer
        self.bert_hidden_size = bert_config.hidden_size
        self.bert_feature_based = feature_based
        emb_dim = self.bert_hidden_size

        # convolution layer
        num_filters = config['num_filters']
        kernel_sizes = config['kernel_sizes']
        self.textcnn = TextCNN(emb_dim, num_filters, kernel_sizes)
        self.layernorm_textcnn = nn.LayerNorm(self.textcnn.last_dim)

        self.dropout = nn.Dropout(config['dropout'])

        # fully connected layer
        fc_hidden_size = config['fc_hidden_size']
        self.labels = super().load_label(label_path)
        label_size = len(self.labels)
        self.fc_hidden = nn.Linear(len(kernel_sizes) * num_filters, fc_hidden_size)
        self.layernorm_fc_hidden = nn.LayerNorm(fc_hidden_size)
        self.fc = nn.Linear(fc_hidden_size, label_size)

    def _compute_bert_embedding(self, x):
        if self.bert_feature_based:
            # feature-based
            with torch.no_grad():
                if self.config['emb_class'] in ['bart', 'distilbert']:
                    bert_outputs = self.bert_model(input_ids=x[0],
                                                   attention_mask=x[1])
                    embedded = bert_outputs[0]
                else:
                    bert_outputs = self.bert_model(input_ids=x[0],
                                                   attention_mask=x[1],
                                                   token_type_ids=None if self.config['emb_class'] in ['roberta'] else x[2]) # RoBERTa don't use segment_ids
                    embedded = bert_outputs[0]
        else:
            # fine-tuning
            # x[0], x[1], x[2] : [batch_size, seq_size]
            if self.config['emb_class'] in ['bart', 'distilbert']:
                bert_outputs = self.bert_model(input_ids=x[0],
                                               attention_mask=x[1])
                # bart model's output
                # [0] last decoder layer's output : [batch_size, seq_size, bert_hidden_size]
                # [1] last encoder layer's output : [seq_size, batch_size, bert_hidden_size]
                embedded = bert_outputs[0]
            else:
                bert_outputs = self.bert_model(input_ids=x[0],
                                               attention_mask=x[1],
                                               token_type_ids=None if self.config['emb_class'] in ['roberta'] else x[2]) # RoBERTa don't use segment_ids
                embedded = bert_outputs[0]
                # embedded : [batch_size, seq_size, bert_hidden_size]
        return embedded

    def forward(self, x):
        # x[0], x[1], x[2] : [batch_size, seq_size]

        # 1. bert embedding
        embedded = self._compute_bert_embedding(x)
        # embedded : [batch_size, seq_size, bert_hidden_size]
        embedded = self.dropout(embedded)

        # 2. convolution
        textcnn_out = self.textcnn(embedded)
        textcnn_out = self.layernorm_textcnn(textcnn_out)
        textcnn_out = self.dropout(textcnn_out)

        # 3. fully connected
        fc_hidden_out = self.fc_hidden(textcnn_out)
        # fc_hidden_out : [batch_size, fc_hidden_size]
        fc_hidden_out = self.layernorm_fc_hidden(fc_hidden_out)
        fc_hidden_out = self.dropout(fc_hidden_out)
        fc_out = self.fc(fc_hidden_out)
        # fc_out : [batch_size, label_size]
        # for MSELoss
        if self.config['opt'].augmented: return fc_out
        output = torch.softmax(fc_out, dim=-1)
        # output : [batch_size, label_size]
        return output

class TextBertCLS(BaseModel):
    def __init__(self, config, bert_config, bert_model, bert_tokenizer, label_path, feature_based=False):
        super().__init__(config=config)

        self.config = config
        self.device = config['opt'].device
        seq_size = config['n_ctx']

        # bert embedding layer
        self.bert_config = bert_config
        self.bert_model = bert_model
        self.bert_tokenizer = bert_tokenizer
        self.bert_hidden_size = bert_config.hidden_size
        self.bert_feature_based = feature_based

        self.dropout = nn.Dropout(config['dropout'])

        # fully connected layer
        self.labels = super().load_label(label_path)
        label_size = len(self.labels)
        self.fc = nn.Linear(self.bert_hidden_size, label_size)

    def _compute_bert_embedding(self, x):
        if self.bert_feature_based:
            # feature-based
            with torch.no_grad():
                if self.config['emb_class'] in ['bart', 'distilbert']:
                    bert_outputs = self.bert_model(input_ids=x[0],
                                                   attention_mask=x[1])
                    pooled = bert_outputs[0][:, -1, :]
                elif self.config['emb_class'] in ['electra']:
                    bert_outputs = self.bert_model(input_ids=x[0],
                                                   attention_mask=x[1],
                                                   token_type_ids=x[2])
                    # no pooling layer in electra, use the first hidden state([CLS]) of the final layer.
                    pooled = bert_outputs[0][:, 0, :]
                    # pooled : [batch_size, bert_hidden_size]
                else:
                    bert_outputs = self.bert_model(input_ids=x[0],
                                                   attention_mask=x[1],
                                                   token_type_ids=None if self.config['emb_class'] in ['roberta'] else x[2]) # RoBERTa don't use segment_ids
                    pooled = bert_outputs[1]
        else:
            # fine-tuning
            # x[0], x[1], x[2] : [batch_size, seq_size]
            if self.config['emb_class'] in ['bart', 'distilbert']:
                bert_outputs = self.bert_model(input_ids=x[0],
                                               attention_mask=x[1])
                # bart model's output
                # [0] last decoder layer's output : [batch_size, seq_size, bert_hidden_size]
                # [1] last encoder layer's output : [seq_size, batch_size, bert_hidden_size]
                # final hidden state of the final decoder token acts like '[CLS]'
                pooled = bert_outputs[0][:, -1, :]
                # pooled : [batch_size, bert_hidden_size]
            elif self.config['emb_class'] in ['electra']:
                bert_outputs = self.bert_model(input_ids=x[0],
                                               attention_mask=x[1],
                                               token_type_ids=x[2])
                # no pooling layer in electra, use the first hidden state([CLS]) of the final layer.
                pooled = bert_outputs[0][:, 0, :]
                # pooled : [batch_size, bert_hidden_size]
            else:
                bert_outputs = self.bert_model(input_ids=x[0],
                                               attention_mask=x[1],
                                               token_type_ids=None if self.config['emb_class'] in ['roberta'] else x[2]) # RoBERTa don't use segment_ids
                pooled = bert_outputs[1] # first token embedding([CLS]), see BertPooler
                # pooled : [batch_size, bert_hidden_size]
        embedded = pooled
        return embedded

    def forward(self, x):
        # x[0], x[1], x[2] : [batch_size, seq_size]
        # 1. bert embedding
        embedded = self._compute_bert_embedding(x)
        # embedded : [batch_size, bert_hidden_size]
        embedded = self.dropout(embedded)

        # 2. fully connected
        fc_out = self.fc(embedded)
        # for MSELoss
        if self.config['opt'].augmented: return fc_out
        output = torch.softmax(fc_out, dim=-1)
        # output : [batch_size, label_size]
        return output


import torch
from torch.autograd import Variable
import torch.optim as optim
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import heapq


class CorpusList():
    def __init__(self):
        f = open("./corpus.txt")
        corpusin = f.read(4096)
        corpusin = list(corpusin.strip().strip(".").strip(",").strip("!").strip("?").lower())
        f.close()
        self.corpus_list = corpusin
        self.corpus_set = set(self.corpus_list)


class HuffmanNode:
    def __init__(self, wordid, freq):
        self.wordid = wordid
        self.freq = freq
        self.parent = None
        self.check_lchild = None
        self.rchild = None
        self.lchild = None
        self.code = []
        self.path = []

class SkipGramModel(nn.Module):
    def __init__(self, embed_size, embed_dims, corpus, window=5, batch_size=150, lr=0.025):
        super(SkipGramModel, self).__init__()
        self.embed_size = embed_size
        self.embed_dims = embed_dims
        self.corpus = corpus
        self.freq = len(corpus.corpus_set)
        self.u_embeds = nn.Embedding(2 * embed_size - 1, embed_dims, sparse=True)
        self.v_embeds = nn.Embedding(2 * embed_size - 1, embed_dims, sparse=True)
        self.window = window
        self.batch_size = batch_size
        self.start_lr = lr
        self.lr = lr
        self.init_emb()
        self.optimizer = optim.SGD(self.parameters(), lr=0.025)
        self.huffman = []
        um_node = []
        self.freq_list = []
        for index, value in enumerate(corpus.corpus_set):
            self.freq_list.append(value)
        for wordid, c in enumerate(list(self.corpus.corpus_set)):
            node = HuffmanNode(wordid, c)
            heapq.heappush(um_node, (c, wordid, node))
            self.huffman.append(node)
        next_id = len(self.huffman)
        while len(um_node) > 1:
            _, _, node1 = heapq.heappop(um_node)
            _, _, node2 = heapq.heappop(um_node)
            nnode = HuffmanNode(next_id, node1.freq + node2.freq)
            node1.parent = nnode.wordid
            node2.parent = nnode.wordid
            nnode.lchild = node1.wordid
            node1.check_lchild = True
            nnode.rchild = node2.wordid
            node2.check_lchild = False
            self.huffman.append(nnode)
            heapq.heappush(um_node, (nnode.freq, nnode.wordid, nnode))
            next_id = len(self.huffman)

            self.make_huffman(um_node[0][2].lchild)
            self.make_huffman(um_node[0][2].rchild)
        self.init_samples()
        self.init_emb()

    def make_huffman(self, wordid):
        if len(self.huffman) < 1:
            return
        if self.huffman[wordid].check_lchild:
            code = [0]
        else:
            code = [1]
        self.huffman[wordid].code = self.huffman[self.huffman[wordid].parent].code + code
        self.huffman[wordid].path = self.huffman[self.huffman[wordid].parent].path + [self.huffman[wordid].parent]

        if self.huffman[wordid].lchild is not None:
            self.make_huffman(self.huffman[wordid].lchild)
        if self.huffman[wordid].rchild is not None:
            self.make_huffman(self.huffman[wordid].rchild)

    def init_samples(self):
        self.table = []
        table_size = 1e8
        freq = len(self.corpus.corpus_set)
        words = int(freq)
        ratio = freq / words
        count = np.round(ratio * table_size)
        for wordid, counter in range(int(count)):
            self.sample_table += [wordid] * counter
        self.table = np.array(self.table)

    def init_emb(self):
        initrange = 0.5 / self.embed_dims
        self.u_embeds.weight.data.uniform_(-initrange, initrange)
        self.v_embeds.weight.data.uniform_(-0, 0)

    def train_model(self):
        pair_count = self.data.evaluate_pair_count(self.window)
        batch_count = self.iteration * pair_count / self.batch_size
        iterations = batch_count
        self.save_embedding(self.data.id2word, self.window)
        pairs = self.data.get_batch_pairs(self.batch_size, self.window)
        pairs, neg_pairs = self.data.get_batch_pairs(pairs, 5)
        for x in iterations:
            pairs = self.data.get_batch_pairs(self.batch_size, self.window)
            u = [int(pair[0]) for pair in pairs]
            v = [int(pair[1]) for pair in pairs]
            neg_u = [int(pair[0]) for pair in neg_pairs]
            neg_v = [int(pair[1]) for pair in neg_pairs]

            self.optimizer.zero_grad()
            loss = self. forward(u, v, neg_u, neg_v)
            loss.backward()
            self.optimizer.step()
            iterations.set_description("loss = %0.4f, lr = %0.8f" % (loss.data[0], self.optimizer.param_groups[0]['lr']))
            if x * self.batch_size % 100000 == 0:
                self.lr = self.start_lr
                for group in self.optimizer.param_groups:
                    group['lr'] = self.lr
        self.save_embedding(self.data.id2word, self.outfilename)

    def forward(self, pos_u, pos_v, neg_u, neg_v):
        losses = []
        embed_u = self.u_embeddings(Variable(torch.LongTensor(pos_u)))
        embed_v = self.v_embeddings(Variable(torch.LongTensor(pos_v)))
        score = torch.mul(embed_u, embed_v)
        score = torch.sum(score, dim=1)
        score = F.logsigmoid(score)
        losses.append(sum(score))
        neg_embed_u = self.u_embeddings(Variable(torch.LongTensor(neg_u)))
        neg_embed_v = self.v_embeddings(Variable(torch.LongTensor(neg_v)))
        neg_score = torch.mul(neg_embed_u, neg_embed_v)
        neg_score = torch.sum(neg_score, dim=1)
        neg_score = F.logsigmoid(-1 * neg_score)
        losses.append(sum(neg_score))
        return -1 * sum(losses)

    def save_embedding(self, id2word, file_name):
        embeds = self.u_embeds.weight.data.numpy()
        fout = open(file_name, 'w', encoding="UTF-8")
        fout.write('%d %d\n' % (len(id2word), self.embed_dims))
        for wordid, w in id2word.items():
            e = embeds[wordid]
            e = ' '.join(map(lambda x: str(x), e))
            fout.write('%s %s\n' % (w, e))

class Word2Vec():
    def __init__(self):
        self.corpus = CorpusList()
        self.skipmodel = SkipGramModel(128, 100, self.corpus, window=5)

if __name__ == '__main__':
    inputfilename = "./corpus.txt"
    outputfilename = "./embeds.txt"
    infile = open(inputfilename, "r")
    corpus_in = infile.read(10240)
    infile.close()
    word2vec = Word2Vec()
    word2vec.skipmodel.train_model()
    word2vec.skipmodel.save_embedding("./embeds.txt")
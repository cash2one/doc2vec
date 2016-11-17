'''---------Notes for complete---------------------
- try different classifier
- try other approaches: rnn, bag-of-words, baiesian

'''
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import warnings

from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.base import BaseEstimator
from sklearn.manifold import TSNE
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from collections import namedtuple, defaultdict
import random, numpy as np
import os, glob, sys
import gensim
import re
import pickle

from sklearn.neural_network import MLPClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.gaussian_process import GaussianProcessClassifier
from sklearn.gaussian_process.kernels import RBF
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, AdaBoostClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.discriminant_analysis import QuadraticDiscriminantAnalysis
from sklearn.preprocessing import StandardScaler

#from config import config

import pdb

Document = namedtuple('Document', 'url topic_id doc_no words tags topic')

class Log(object):
    @staticmethod
    def info(sender, message):
        print('---INFO: ', sender, message, sep='\t')

    def warn(sender, message):
        print('---WARN: ', sender, message, sep='\t')

class Doc2Vec(object):
    def __init__(self, dm=1, size=100, window=8, min_count=5, passes=1, batch_size=0, shuffle=False, dm_mean=0, dm_concat=0):
        self.dm = dm
        self.size = size
        self.window = window
        self.min_count = min_count

        self.passes = passes
        self.shuffle = shuffle
        self.batch_size = batch_size
        
        self.model = gensim.models.Doc2Vec(dm=dm, size=self.size, window=self.window, min_count=min_count, workers=4, dm_mean=dm_mean, dm_concat=dm_concat)

        self.doc_infos = {}
        self.from_file = False

    def load(self):
        model_file = self.auto_name()
        if os.path.isfile(model_file):
            self.from_file = True
            warnings.warn('Load trained model from: ' + model_file)
            print('Load trained model from: ' + model_file)
            self.doc_infos = self.load_docinfo()#TODO the code is not reall logic
            return gensim.models.doc2vec.Doc2Vec.load(model_file)

    def plot_with_color(self, low_dim_embs, labels, classes, filename='tsne.png'):
        assert low_dim_embs.shape[0] >= len(labels), "More labels than embeddings"
        Log.info(self, 'Start drawing...')
        plt.figure(figsize=(18, 18))  #in inches
        unique_classes = list(set(classes))
        colors = cm.rainbow(np.linspace(0, 1, len(unique_classes)))
        for i, label in enumerate(labels):
            x, y = low_dim_embs[i,:]
            plt.scatter(x, y, color=colors[unique_classes.index(classes[i])])
            plt.annotate(label,
                     xy=(x, y),
                     xytext=(5, 2),
                     textcoords='offset points',
                     ha='right',
                     va='bottom')
        plt.savefig(filename + '.png')
        #Log.info(self, '######showing...')
        #plt.show()

    def visualize(self, docvecs, docs, filename, plot_only=None):
        Log.info(self, 'Start reduce docvec dimention')
        tsne = TSNE(perplexity=30, n_components=2, init='pca', n_iter=5000)
        if plot_only is not None:
            ids  = random.sample(range(0, len(docvecs)), plot_only)
            docvecs = docvecs[ids]
            docs = [docs[i] for i in ids]
        try:
            low_dim_embs = tsne.fit_transform(docvecs)
        except:
            print('!!!Cant reduce the docvecs dementions:', sys.exc_info())
            return

        #labels = [str(doc.topic) + '.' + str(doc.doc_no) for doc in docs]
        #labels = [str(doc.topic) + '.' + str(doc.tags[0]) for doc in docs]
        labels = [str(doc.topic_id) for doc in docs]
        classes = [doc.topic_id for doc in docs]

        #plot_with_labels(low_dim_embs, labels) 
        self.plot_with_color(low_dim_embs, labels, classes, filename)

    def train(self, X, *args, **kwargs):
        '''Train doc2vec model.

        Args:
            X: Document iterator.
        '''
        Log.info(self, '======Training doc2vec model====')
        model = self.load()

        if model is not None:
            self.model = model
            return self

        Log.info(self, '--build vocabs')
        self.model.build_vocab(X)

        #mutiple passes, mini-batch training
        for rep in range(0, self.passes):
            Log.info(self, '==========pass num{}'.format(rep))
            corpus = []
            for doc in X:
                if rep==0 and doc.tags[0] not in self.doc_infos:#training doc information
                    self.doc_infos[doc.tags[0]]= (doc.doc_no, doc.tags, doc.topic_id, doc.topic, doc.url)

                corpus.append(doc)
                if self.batch_size > 0 and len(corpus)>=self.batch_size:
                    if self.shuffle:
                        random.shuffle(corpus)
                    self.model.train(corpus)
                    Log.info(self, '---train a mini-batch')
            if len(corpus) !=0:
                Log.info(self, '---train the last')
                #self.model.train(corpus)

        self.model.save(self.auto_name())
        self.save_docinfo()

        self.visualize(self.model.docvecs, corpus, self.auto_name(),500) 
        return self

    def load_docinfo(self):
        fname = self.auto_name() + '.info'
        with open(fname, 'rb') as f:
            return pickle.load(f)

    def save_docinfo(self):
        fname = self.auto_name() + '.info'
        with open(fname, 'wb') as f:
            pickle.dump(self.doc_infos, f)#protocl 0 default-text-based; binary mode for1,2,-1, HIGHGEST PROTOCOL is normal???

    def auto_name(self):
        return os.path.join(model_dir, token_type + '.' + re.sub('[\W_]+', '.', str(self.model)).lower() + 'model')

    def infer_docvec(self, words):
        return self.model.infer_vector(words)

    def most_similar(self, docvec, topn = 10):
        return self.model.docvecs.most_similar(positive=[docvec], topn=topn) 

class Classifier(object):
    def __init__(self, doc2vec):
        self.doc2vec = doc2vec

    def predict(self, doc_words):
        '''Predict category for each document in X.
        Args:
            doc_words: a list of words in a document
        '''
        raise NotImplementedError()

    def fit(self, X):
        '''Score a corpus.
        Args:
            X: Document object iterator.
        '''
        Log.warn(self, 'use Classifer.fit (default)')
       

    def score(self, X):
        '''Score a corpus.
        Args:
            X: Document object iterator.
        '''
        Log.info(self, '======Score category classification with KNN====')
        correct = 0 
        total = 0
        for doc in X:
            cat_id = self.predict(doc.words)
            total += 1
            if cat_id == doc.topic_id:
                correct +=1
            
        return correct/float(total)


class KNN(object):
    def __init__(self, doc2vec, k=10):
        self.K = k
        self.doc2vec = doc2vec

    def classify_by_count(self, sim_docs):
        count = defaultdict(int)
        ret_cat = -1
        max_count = -1
        for doc in sim_docs:
            cat_id = self.doc2vec.doc_infos[doc[0]][2]
            count[cat_id] +=1
            if count[cat_id]>max_count:
                ret_cat = cat_id
                max_count = count[cat_id]
        return ret_cat

    def predict(self, doc_words):
        '''Predict category for each document in X.
        Args:
            doc_words: a list of words in a document
        '''
        docvec = self.doc2vec.infer_docvec(doc_words)
        sim_docs = self.doc2vec.most_similar(docvec, topn=self.K)
        return self.classify_by_count(sim_docs)

    def score(self, X):
        '''Score a corpus.
        Args:
            X: Document object iterator.
        '''
        Log.info(self, '======Score category classification with KNN====')
        correct = 0 
        total = 0
        for doc in X:
            cat_id = self.predict(doc.words)
            total += 1
            if cat_id == doc.topic_id:
                correct +=1
            
        return correct/float(total)

class SVNClassifier(Classifier):

    def __init__(self, doc2vec):
        super(SVNClassifier, self).__init__(doc2vec)

    def fit(self, train_docs):
        pdb.set_trace()
    
    def predict1(self, doc_words):
        pass


class MultipClassifiers(Classifier):

    def __init__(self, doc2vec):
        super(MultipClassifiers, self).__init__(doc2vec)
        self.classifiers = [
            #KNeighborsClassifier(3),
            #SVC(kernel="linear", C=0.025),
            SVC(gamma=2, C=1),
            #GaussianProcessClassifier(1.0 * RBF(1.0), warm_start=True),
            #DecisionTreeClassifier(max_depth=5),
            #RandomForestClassifier(max_depth=5, n_estimators=10, max_features=1),
            #MLPClassifier(alpha=1),
            #AdaBoostClassifier(),
            #GaussianNB(),
            #QuadraticDiscriminantAnalysis()
            ]

    def get_data(self, train_docs):
        Log.info(self, 'Get vectorized data for corpus...')
        X = []
        y = []
        infos = []
        for doc in train_docs:
            X.append(self.doc2vec.infer_docvec(doc.words))
            y.append(doc.topic_id)
            infos.append((doc.doc_no, doc.tags, doc.topic_id, doc.topic, doc.url))
            #if len(y)>2000:
                #break
        return np.array(X), y, infos

    def fit(self, train_docs):
        X, y, infos = self.get_data(train_docs)
        #Log.info(self, 'Train size ' + str(len(y)))
        X = StandardScaler().fit_transform(X)
        for cls in self.classifiers:
            Log.info(self, 'fit ' + cls.__class__.__name__)
            cls.fit(X, y)
            Log.info(self, 'score ')
            score = cls.score(X, y)
            Log.info(self, '!!!RESULT!!in train!{}:{}'.format(cls.__class__.__name__, score))
    
    def predict(self, doc_words):
        x = self.doc2vec.infer_docvec(doc_words)
        x = x.reshape(1, -1)
        x = StandardScaler().fit_transform(x)
        pres = []
        for cls in self.classifiers:
            pres.append((cls.__class__.__name__, cls.predict(x)[0]))
        return pres

    def score(self, test_docs):
        X, y, infos = self.get_data(test_docs)
        #Log.info(self, 'Test size ' + str(len(y)))
        X = StandardScaler().fit_transform(X)
        Log.info(self, '======Score category classification====')
        correct = defaultdict(int) 
        total = len(y)
        for cls in self.classifiers:
            Log.info(self, 'score ' + cls.__class__.__name__)
            pres = cls.predict(X)
            correct[cls.__class__.__name__] = sum(pres==y)/float(total)
        return correct 
        
    def score2(self, train_docs):
        Log.info(self, '======Score category classification====')
        correct = defaultdict(int) 
        total = 0
        for doc in train_docs:
            pres = self.predict(doc.words)
            for name, cat_id in pres:
                correct[name] +=1 if cat_id==doc.topic_id else 0
            total += 1

        total = float(total)
        for key in correct.keys():
            correct[key] /= total
            
        return correct

#return multiple generator
def multigen(gen_func):
    class _multigen(object):
        def __init__(self, *args, **kwargs):
            self.__args = args
            self.__kwargs = kwargs
        def __iter__(self):
            return gen_func(*self.__args, **self.__kwargs)
    return _multigen

@multigen
def read_corpus(data_dir, from_percent, to_percent):
    #corpus = []
    topic_id = -1
    doc_id = -1
    doc_count = -1
    for filename in glob.iglob(data_dir + '*.tsv'):
        topic_id += 1
        doc_count = -1
        with open(filename) as f:
            Log.info('read_corpus', '{}\t{}'.format(topic_id, os.path.basename(filename)))
            #TODO seek to the right part for reading
            docs = f.readlines()
            doc_len = float(len(docs))
            for doc in docs:
                doc_count +=1
                percent = (doc_count+1)/float(doc_len)
                if percent>=to_percent:
                    break
                if percent<from_percent:
                    continue

                doc_id += 1
                parts = doc.split('\t')
                words = ' '.join(part.strip() for part in parts[1:])
                #words = gensim.utils.to_unicode(words).split()
                #pdb.set_trace()
                #corpus.append(Document(parts[0], topic_id, doc_count, words, [doc_id]))
                yield Document(parts[0], topic_id, doc_count, words, [doc_id], os.path.basename(filename))
    #return corpus

#============global configuration
data_dir = '../crawl_news/data/zing/'
train_percent = 0.6
valid_percent = 0.2
test_percent = 0.2
token_type = 'char'#word, vn_token
model_dir = './models/'

params = {
    'dm': (1, ),
    'size': (100, 250, 500),
    'window': (3, 5, 8, 10, 15),
    'mean': (0, 1),
    'concat': (0, 1),
    'min_count': (5, 10, 30, 100), 
}

def pipeline_main():
    pipeline = make_pipeline()
    train_docs = read_corpus(data_dir, 0, train_percent)
    #pdb.set_trace()
    #pipeline.set_params(doc2vec__computed=True)#need need to be in the init method
    pipeline.fit(train_docs)#only pass to the fit method

    Log.info('main', '============call predict')
    #TODO read validation test
    pipeline.predict(train_docs)
    print('DONE')
    pdb.set_trace()

def run1():
    train_docs = read_corpus(data_dir, 0, train_percent)
    
    for dm in params['dm']:
        for size in params['size']:
            for window in params['window']:
                for mean in params['mean']:
                    for concat in params['concat']:
                        for min_count in params['min_count']:
                            doc2vec = Doc2Vec(dm=dm, size=size, window=window, dm_mean=mean, dm_concat=concat, min_count = min_count)
                            doc2vec.train(train_docs)
                            if doc2vec.from_file:
                                sys.stderr.write('!!!Ignore:' + doc2vec.auto_name() + '\n')
                                continue
                            knn = KNN(doc2vec)
                            acc = knn.score(train_docs)
                            print('!!RESULT!!====dm={},size={},window={},mean={},concat={},min_count={},acc={}'.format(dm, size, window, mean, concat,min_count, acc))
                            sys.stderr.write('!!RESULT!!====dm={},size={},window={},mean={},concat={},min_count={},acc={}\n'.format(dm, size, window, mean, concat,min_count, acc))
    print('DONE')

def run2():
    train_docs = read_corpus(data_dir, 0, train_percent)
    doc2vec = Doc2Vec()
    doc2vec.train(train_docs)
    
    cls = MultipClassifiers(doc2vec)
    cls.fit(train_docs)

    test_docs = read_corpus(data_dir, train_percent, 1.0)
    accs = cls.score(test_docs)
    print(accs)
    print('Done')
    pdb.set_trace()

def main():
    #run1()
    run2()

if __name__=='__main__':
    main()

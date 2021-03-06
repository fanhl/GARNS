# coding: utf-8
import _pickle as cPickle
import numpy as np
import pickle as pkl
import networkx as nx
import scipy.sparse as sp
import sys


def prepare_graph_data(adj):
    # adapted from preprocess_adj_bias
    num_nodes = adj.shape[0]
    adj = adj + sp.eye(num_nodes)  # self-loop
    #data =  adj.tocoo().data
    adj[adj > 0.0] = 1.0
    if not sp.isspmatrix_coo(adj):
        adj = adj.tocoo()
    adj = adj.astype(np.float32)
    indices = np.vstack((adj.col, adj.row)).transpose()
    #indices = np.vstack((adj.row, adj.col)).transpose()
    return (indices, adj.data, adj.shape), adj.row, adj.col
    #return (indices, adj.data, adj.shape), adj.row, adj.col, data#adj.data


def parse_index_file(filename):
    """Parse index file."""
    index = []
    for line in open(filename):
        index.append(int(line.strip()))
    return index

def sample_mask(idx, l):
    """Create mask."""
    mask = np.zeros(l)
    mask[idx] = 1
    return np.array(mask, dtype=np.bool)

def load_data(dataset_str): # {'pubmed', 'citeseer', 'cora'}
    """Load data."""
    names = ['x', 'y', 'tx', 'ty', 'allx', 'ally', 'graph']
    objects = []
    for i in range(len(names)):
        with open("./data/ind.{}.{}".format(dataset_str, names[i]), 'rb') as f:
            if sys.version_info > (3, 0):
                objects.append(pkl.load(f, encoding='latin1'))
            else:
                objects.append(pkl.load(f))

    x, y, tx, ty, allx, ally, graph = tuple(objects)
    test_idx_reorder = parse_index_file("./data/ind.{}.test.index".format(dataset_str))
    test_idx_range = np.sort(test_idx_reorder)

    if dataset_str == 'citeseer':
        # Fix citeseer dataset (there are some isolated nodes in the graph)
        # Find isolated nodes, add them as zero-vecs into the right position
        test_idx_range_full = range(min(test_idx_reorder), max(test_idx_reorder)+1)
        tx_extended = sp.lil_matrix((len(test_idx_range_full), x.shape[1]))
        tx_extended[test_idx_range-min(test_idx_range), :] = tx
        tx = tx_extended
        ty_extended = np.zeros((len(test_idx_range_full), y.shape[1]))
        ty_extended[test_idx_range-min(test_idx_range), :] = ty
        ty = ty_extended

    features = sp.vstack((allx, tx)).tolil()
    #因为features是allx,tx连接的，所以要重新为features中物tx部份排序
    features[test_idx_reorder, :] = features[test_idx_range, :]

    nx_graph = nx.from_dict_of_lists(graph)
    adj = nx.adjacency_matrix(nx_graph)
    edges = nx_graph.edges()

    labels = np.vstack((ally, ty))
    labels[test_idx_reorder, :] = labels[test_idx_range, :]

    idx_test = test_idx_range.tolist()
    idx_train = range(len(y))
    idx_val = range(len(y), len(y)+500)

    train_mask = sample_mask(idx_train, labels.shape[0])
    val_mask = sample_mask(idx_val, labels.shape[0])
    test_mask = sample_mask(idx_test, labels.shape[0])

    y_train = np.zeros(labels.shape)
    y_val = np.zeros(labels.shape)
    y_test = np.zeros(labels.shape)
    y_train[train_mask, :] = labels[train_mask, :]
    y_val[val_mask, :] = labels[val_mask, :]
    y_test[test_mask, :] = labels[test_mask, :]
    #
    # print(adj.shape)
    # print(features.shape)
    features_target = construct_traget_neighbors(nx_graph,features.todense())

    return sp.coo_matrix(adj), features.todense(), labels, idx_train, idx_val, idx_test,features_target

def construct_traget_neighbors(nx_G, X):
    # construct target neighbor feature matrix
    X_target = np.zeros(X.shape)
    nodes = nx_G.nodes()
    # autoencoder for reconstructing Weighted Average Neighbor
    for node in nodes:
        neighbors = list(nx_G.neighbors(node))
        if len(neighbors) == 0:
            X_target[node] = X[node]
        else:
            temp = np.array(X[node])
            for n in neighbors:
                temp = np.vstack((temp, X[n]))
            temp = np.mean(temp, axis=0)
            X_target[node] = temp
    return X_target    


def load_nell_data(DATASET='nell'):
    NAMES = ['x', 'y', 'tx', 'ty', 'allx', 'ally', 'graph']
    OBJECTS = []

    for i in range(len(NAMES)):
        OBJECTS.append(cPickle.load(open('./data/ind.{}.{}'.format(DATASET, NAMES[i]), 'rb',),encoding='latin1'))
        
    x, y, tx, ty, allx, ally, graph = tuple(OBJECTS)
    test_idx_reorder = parse_index_file("./data/ind.{}.test.index".format(DATASET))
    exclu_rang = []
    for i in range(8922, 65755):
        if i not in test_idx_reorder:
            exclu_rang.append(i)

    # get the features:X
    allx_v_tx = sp.vstack((allx, tx)).tolil()
    _x = sp.lil_matrix(np.zeros((9891, 55864)))

    up_features = sp.hstack((allx_v_tx, _x))

    _x = sp.lil_matrix(np.zeros((55864, 5414)))
    _y = sp.identity(55864, format='lil')
    down_features = sp.hstack((_x, _y))
    features = sp.vstack((up_features, down_features)).tolil()
    features[test_idx_reorder + exclu_rang, :] = features[range(8922, 65755), :]
    print("Feature matrix:" + str(features.shape))

    # get the labels: y
    up_labels = np.vstack((ally, ty))
    down_labels = np.zeros((55864, 210))
    labels = np.vstack((up_labels, down_labels))
    labels[test_idx_reorder + exclu_rang, :] = labels[range(8922, 65755), :]
    print("Label matrix:" + str(labels.shape))

    # print np.sort(graph.get(17493))

    # get the adjcent matrix: A
    # adj = nx.to_numpy_matrix(nx.from_dict_of_lists(graph))
    G = nx.from_dict_of_lists(graph)
    adj = nx.adjacency_matrix(G)
    print("Adjcent matrix:" + str(adj.shape))

    # test, validation, train
    idx_test = test_idx_reorder
    idx_train = range(len(y))
    idx_val = range(len(y), len(y) + 500)

    train_mask = sample_mask(idx_train, labels.shape[0])
    val_mask = sample_mask(idx_val, labels.shape[0])
    test_mask = sample_mask(idx_test, labels.shape[0])

    y_train = np.zeros(labels.shape)
    y_val = np.zeros(labels.shape)
    y_test = np.zeros(labels.shape)
    y_train[train_mask, :] = labels[train_mask, :]
    y_val[val_mask, :] = labels[val_mask, :]
    y_test[test_mask, :] = labels[test_mask, :]

    # # record the intermedia result for saving time

    #return adj, features, y_train, y_val, y_test, train_mask, val_mask, test_mask
    return adj, features.todense(), labels, idx_train, idx_val, idx_test
